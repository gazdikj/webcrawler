"""
Refactored VirusTotal database manager with proper error handling.
"""
import pyodbc
from typing import Optional

from config import get_settings
from logging_config import get_logger
from exceptions import DatabaseInsertError, DatabaseConnectionError

logger = get_logger(__name__)
settings = get_settings()


def _get_connection():
    """
    Get database connection.
    
    Returns:
        Database connection
        
    Raises:
        DatabaseConnectionError: If connection fails
    """
    try:
        conn = pyodbc.connect(settings.analysis_db_connection_string)
        return conn
    except pyodbc.Error as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        raise DatabaseConnectionError(f"Failed to connect to database: {e}")


def insert_sample(filename: str, test_id: str) -> Optional[int]:
    """
    Insert sample record into database.
    
    Args:
        filename: File name
        test_id: VirusTotal test ID
        
    Returns:
        Sample ID or None if failed
    """
    logger.debug(f"Inserting sample: {filename}, test_id: {test_id}")
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO sample (name, testid, crack_id, analysis_id)
                OUTPUT INSERTED.id 
                VALUES (?, ?, NULL, NULL)
            """, (filename, test_id))
            
            sample_id = cursor.fetchone()[0]
            conn.commit()
            
            logger.info(f"Sample inserted with ID: {sample_id}")
            return sample_id
    
    except pyodbc.IntegrityError as e:
        logger.error(f"Integrity error inserting sample: {e}", exc_info=True)
        raise DatabaseInsertError(f"Failed to insert sample: {e}")
    
    except pyodbc.Error as e:
        logger.error(f"Database error inserting sample: {e}", exc_info=True)
        raise DatabaseInsertError(f"Failed to insert sample: {e}")
    
    except Exception as e:
        logger.error(f"Unexpected error inserting sample: {e}", exc_info=True)
        return None


def update_sample(test_id: str, analysis_id: int) -> bool:
    """
    Update sample with analysis ID.
    
    Args:
        test_id: VirusTotal test ID
        analysis_id: Analysis ID
        
    Returns:
        True if updated successfully, False otherwise
    """
    logger.debug(f"Updating sample: test_id: {test_id}, analysis_id: {analysis_id}")
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sample
                SET analysed = 1, analysis_id = ?
                WHERE testid = ?
            """, (analysis_id, test_id))
            
            conn.commit()
            rows_affected = cursor.rowcount
            
            if rows_affected > 0:
                logger.info(f"Sample updated: test_id: {test_id}")
                return True
            else:
                logger.warning(f"No sample found with test_id: {test_id}")
                return False
    
    except pyodbc.Error as e:
        logger.error(f"Database error updating sample: {e}", exc_info=True)
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error updating sample: {e}", exc_info=True)
        return False


def insert_analysis(status: str, undetected: int, malicious: int, 
                   harmless: int, sha256: str) -> Optional[int]:
    """
    Insert analysis record into database.
    
    Args:
        status: Analysis status
        undetected: Number of undetected results
        malicious: Number of malicious detections
        harmless: Number of harmless results
        sha256: File SHA-256 hash
        
    Returns:
        Analysis ID or None if failed
    """
    logger.debug(f"Inserting analysis: {sha256}, malicious: {malicious}")
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO analysis (status, undetected, malicious, harmless, sha256)
                OUTPUT INSERTED.id 
                VALUES (?, ?, ?, ?, ?)
            """, (status, undetected, malicious, harmless, sha256))
            
            analysis_id = cursor.fetchone()[0]
            conn.commit()
            
            logger.info(f"Analysis inserted with ID: {analysis_id}")
            return analysis_id
    
    except pyodbc.IntegrityError as e:
        logger.error(f"Integrity error inserting analysis: {e}", exc_info=True)
        raise DatabaseInsertError(f"Failed to insert analysis: {e}")
    
    except pyodbc.Error as e:
        logger.error(f"Database error inserting analysis: {e}", exc_info=True)
        raise DatabaseInsertError(f"Failed to insert analysis: {e}")
    
    except Exception as e:
        logger.error(f"Unexpected error inserting analysis: {e}", exc_info=True)
        return None


def insert_antivirus(engine_name: str, engine_category: str, 
                    engine_result: Optional[str], analysis_id: int) -> Optional[int]:
    """
    Insert antivirus result into database.
    
    Args:
        engine_name: Antivirus engine name
        engine_category: Detection category
        engine_result: Detection result
        analysis_id: Analysis ID
        
    Returns:
        Antivirus result ID or None if failed
    """
    logger.debug(f"Inserting antivirus result: {engine_name}, analysis_id: {analysis_id}")
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO antivirus (engine, category, result, analysis_id)
                OUTPUT INSERTED.id 
                VALUES (?, ?, ?, ?)
            """, (engine_name, engine_category, engine_result, analysis_id))
            
            av_id = cursor.fetchone()[0]
            conn.commit()
            
            logger.debug(f"Antivirus result inserted with ID: {av_id}")
            return av_id
    
    except pyodbc.IntegrityError as e:
        logger.error(f"Integrity error inserting antivirus: {e}", exc_info=True)
        return None
    
    except pyodbc.Error as e:
        logger.error(f"Database error inserting antivirus: {e}", exc_info=True)
        return None
    
    except Exception as e:
        logger.error(f"Unexpected error inserting antivirus: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # Test functionality
    logger.info("Testing dbVTManager...")
    
    try:
        # Test insert sample
        sample_id = insert_sample("test_file.exe", "test_id_123")
        logger.info(f"Test sample ID: {sample_id}")
        
        # Test insert analysis
        analysis_id = insert_analysis("completed", 50, 5, 45, "abc123def456")
        logger.info(f"Test analysis ID: {analysis_id}")
        
        if sample_id and analysis_id:
            # Test update sample
            success = update_sample("test_id_123", analysis_id)
            logger.info(f"Sample update: {success}")
            
            # Test insert antivirus
            av_id = insert_antivirus("TestAV", "malicious", "Trojan.Test", analysis_id)
            logger.info(f"Test antivirus ID: {av_id}")
    
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)