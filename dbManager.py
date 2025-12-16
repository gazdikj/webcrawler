"""
Refactored database manager with connection pooling and proper error handling.
"""
import pyodbc
from typing import Optional
from contextlib import contextmanager
from threading import Lock

from config import get_settings
from logging_config import get_logger
from exceptions import (
    DatabaseConnectionError,
    DatabaseInsertError,
    DatabaseQueryError
)

logger = get_logger(__name__)
settings = get_settings()


class ConnectionPool:
    """Simple connection pool for database connections."""
    
    def __init__(self, connection_string: str, pool_size: int = 5):
        self.connection_string = connection_string
        self.pool_size = pool_size
        self._pool = []
        self._lock = Lock()
        
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool."""
        conn = None
        try:
            with self._lock:
                if self._pool:
                    conn = self._pool.pop()
                    logger.debug(f"Reusing connection from pool. Pool size: {len(self._pool)}")
                else:
                    conn = pyodbc.connect(self.connection_string)
                    logger.debug("Created new database connection")
            
            yield conn
            
        except pyodbc.Error as e:
            logger.error(f"Database connection error: {e}", exc_info=True)
            raise DatabaseConnectionError(f"Failed to connect to database: {e}")
        finally:
            if conn:
                with self._lock:
                    if len(self._pool) < self.pool_size:
                        self._pool.append(conn)
                        logger.debug(f"Returned connection to pool. Pool size: {len(self._pool)}")
                    else:
                        conn.close()
                        logger.debug("Closed excess connection")


class DBManager:
    """Database manager with connection pooling and proper error handling."""
    
    def __init__(self, url: str, keyword: str, driver: str, device: str):
        self.connection_pool = ConnectionPool(settings.db_connection_string)
        
        try:
            self.webdriver_id = self._insert_webdriver(driver)
            self.device_id = self._insert_device(device)
            self.crawler_id = self._insert_crawler(url)
            self.job_id = self._insert_crawl_job(keyword, self.crawler_id, 
                                                  self.webdriver_id, self.device_id)
            logger.info(f"DBManager initialized with job_id: {self.job_id}")
        except Exception as e:
            logger.error(f"Failed to initialize DBManager: {e}", exc_info=True)
            raise
    
    def _get_or_create(self, table: str, column: str, value: str) -> int:
        """
        Get existing record ID or create new one.
        
        Args:
            table: Table name
            column: Column name to search
            value: Value to search for
            
        Returns:
            Record ID
            
        Raises:
            DatabaseQueryError: If query fails
            DatabaseInsertError: If insert fails
        """
        try:
            with self.connection_pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Try to get existing record
                query = f"SELECT {table}ID FROM {table} WHERE {column} = ?"
                cursor.execute(query, (value,))
                row = cursor.fetchone()
                
                if row:
                    logger.debug(f"Found existing {table} with ID: {row[0]}")
                    return row[0]
                
                # Insert new record
                insert_query = f"INSERT INTO {table} ({column}) VALUES (?)"
                cursor.execute(insert_query, (value,))
                conn.commit()
                
                # Get the new ID
                cursor.execute(query, (value,))
                new_row = cursor.fetchone()
                
                if new_row:
                    logger.info(f"Created new {table} with ID: {new_row[0]}")
                    return new_row[0]
                else:
                    raise DatabaseInsertError(f"Failed to retrieve new {table} ID")
                    
        except pyodbc.Error as e:
            logger.error(f"Database error in _get_or_create: {e}", exc_info=True)
            raise DatabaseQueryError(f"Failed to get or create {table}: {e}")
    
    def _insert_webdriver(self, name: str) -> int:
        """Insert or get WebDriver record."""
        return self._get_or_create("WebDriver", "Name", name)
    
    def _insert_device(self, name: str) -> int:
        """Insert or get Device record."""
        return self._get_or_create("Device", "Name", name)
    
    def _insert_crawler(self, url: str) -> int:
        """Insert or get Crawler record."""
        return self._get_or_create("Crawler", "WebURL", url)
    
    def _insert_crawl_job(self, keyword: str, crawler_id: int, 
                         web_driver_id: int, device_id: int) -> int:
        """
        Insert new crawl job.
        
        Args:
            keyword: Search keyword
            crawler_id: Crawler ID
            web_driver_id: WebDriver ID
            device_id: Device ID
            
        Returns:
            New job ID
            
        Raises:
            DatabaseInsertError: If insert fails
        """
        try:
            with self.connection_pool.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO CrawlJob (Keyword, StartTime, CrawlerID, WebDriverID, DeviceID) 
                    OUTPUT INSERTED.JobID  
                    VALUES (?, GETDATE(), ?, ?, ?)
                """, (keyword, crawler_id, web_driver_id, device_id))
                
                new_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Created new CrawlJob with ID: {new_id}")
                return new_id
                
        except pyodbc.IntegrityError as e:
            logger.error(f"Integrity error creating CrawlJob: {e}", exc_info=True)
            raise DatabaseInsertError(f"Failed to create CrawlJob: {e}")
        except pyodbc.Error as e:
            logger.error(f"Database error creating CrawlJob: {e}", exc_info=True)
            raise DatabaseInsertError(f"Failed to create CrawlJob: {e}")
    
    def insert_hash(self, hash_value: str) -> int:
        """
        Insert or get hash record.
        
        Args:
            hash_value: SHA256 hash value
            
        Returns:
            Hash ID
        """
        try:
            return self._get_or_create("Hash", "Hash", hash_value)
        except Exception as e:
            logger.error(f"Failed to insert hash: {e}", exc_info=True)
            raise
    
    def insert_crack(self, title: str, size: str, extension: str, 
                    zipfile: Optional[str], hash_id: Optional[int]) -> Optional[int]:
        """
        Insert crack (downloaded file) record.
        
        Args:
            title: File title
            size: File size
            extension: File extension
            zipfile: ZIP file name
            hash_id: Hash ID (optional)
            
        Returns:
            Crack ID or None if failed
        """
        try:
            with self.connection_pool.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO Crack (Title, Size, Extension, ZIPFileTitle, CreatedAt, JobID, HashID) 
                    OUTPUT INSERTED.CrackID  
                    VALUES (?, ?, ?, ?, GETDATE(), ?, ?)
                """, (title, size, extension, zipfile, self.job_id, hash_id))
                
                new_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Created new Crack with ID: {new_id}")
                return new_id
                
        except pyodbc.IntegrityError as e:
            logger.error(f"Integrity error creating Crack: {e}", exc_info=True)
            raise DatabaseInsertError(f"Failed to create Crack: {e}")
        except pyodbc.Error as e:
            logger.error(f"Database error creating Crack: {e}", exc_info=True)
            raise DatabaseInsertError(f"Failed to create Crack: {e}")
    
    def insert_error(self, error_message: str, crack_id: int) -> Optional[int]:
        """
        Insert error record.
        
        Args:
            error_message: Error message
            crack_id: Associated crack ID
            
        Returns:
            Error ID or None if failed
        """
        try:
            with self.connection_pool.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO Error (ErrorMessage, OccurredAt, CrackID)
                    OUTPUT INSERTED.ErrorID 
                    VALUES (?, GETDATE(), ?)
                """, (error_message, crack_id))
                
                new_id = cursor.fetchone()[0]
                conn.commit()
                
                logger.info(f"Created new Error with ID: {new_id}")
                return new_id
                
        except pyodbc.IntegrityError as e:
            logger.error(f"Integrity error creating Error: {e}", exc_info=True)
            return None
        except pyodbc.Error as e:
            logger.error(f"Database error creating Error: {e}", exc_info=True)
            return None


# For backwards compatibility
if __name__ == "__main__":
    import time
    db = DBManager("https://test.com", "test_keyword", "chrome", "desktop")
    
    t = time.time()
    hash_id = db.insert_hash("1234567890abcdef")
    crack_id = db.insert_crack("ABC.mp3", "10 MB", ".MP3", "ABC.zip", hash_id)
    
    logger.info(f"Time taken: {time.time() - t:.2f}s")