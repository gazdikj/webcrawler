"""
Refactored Datoid crawler with proper error handling and logging.
"""
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from hashManager import calculate_sha256, save_hashes
from baseCrawler import BaseCrawler
from config import get_settings
from logging_config import get_logger
from exceptions import (
    CrawlerTimeoutError,
    DownloadFileTooLargeError
)

logger = get_logger(__name__)
settings = get_settings()


class DatoidCrawler(BaseCrawler):
    """Crawler for datoid.cz website."""
    
    def format_url(self, url: str, text: str, index: int) -> str:
        """
        Format search URL with keyword and page number.
        
        Args:
            url: Base URL
            text: Search keyword
            index: Page number
            
        Returns:
            Formatted URL
        """
        formatted_text = text.replace(" ", "-")
        return f"{url}/s/{formatted_text}/{index}"
    
    def find_next_button(self) -> bool:
        """
        Check if next page button exists.
        
        Returns:
            True if next button found, False otherwise
        """
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.next.ajax"))
            )
            logger.info("Next page button found")
            return True
        except TimeoutException:
            logger.info("Next page button not found - last page reached")
            return False
    
    def close_window(self) -> None:
        """Close current detail window and return to main window."""
        try:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            logger.debug("Detail window closed")
        except Exception as e:
            logger.error(f"Error closing window: {e}", exc_info=True)
    
    def update_task_state(self, task, status: str, file_name: str, 
                         file_size: str, current_index: int, 
                         total_index: int, page: int) -> None:
        """
        Update Celery task state with progress information.
        
        Args:
            task: Celery task instance
            status: Current status message
            file_name: Current file name
            file_size: Current file size
            current_index: Current item index
            total_index: Total items on page
            page: Current page number
        """
        try:
            count = current_index + 25 * (page - 1)
            task.update_state(
                state="CRAWLING",
                meta={
                    "file_name": file_name,
                    "file_size": file_size,
                    "current": count,
                    "status": status
                }
            )
            logger.debug(f"Task state updated: {status}")
        except Exception as e:
            logger.error(f"Failed to update task state: {e}", exc_info=True)
    
    def get_parsed_file_info(self, file_info: str) -> tuple:
        """
        Parse file information from text.
        
        Args:
            file_info: Raw file info text
            
        Returns:
            Tuple of (title, extension, size)
        """
        try:
            cleared_data = [item.strip() for item in file_info.split("\n") if item.strip()]
            extension = cleared_data[0]
            size = cleared_data[-2]
            title = cleared_data[-1]
            logger.debug(f"Parsed file: {title}, {extension}, {size}")
            return title, extension, size
        except Exception as e:
            logger.error(f"Error parsing file info: {e}", exc_info=True)
            return "Unknown", "Unknown", "Unknown"
    
    def crawl_page(self, task, page: int) -> None:
        """
        Crawl a single page of results.
        
        Args:
            task: Celery task instance
            page: Page number
        """
        try:
            # Wait for items to load
            WebDriverWait(self.driver, settings.selenium_timeout).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span.filename"))
            )
            
            items = self.driver.find_elements(By.CSS_SELECTOR, "a:has(span.filename)")
            logger.info(f"Found {len(items)} files on page {page}")
            
            for index, item in enumerate(items):
                file_title = file_extension = file_size = None
                download_exception = size_exception = timeout_exception = None
                download_path = None
                hash_value = None
                
                try:
                    # Get file info
                    file_info = item.get_attribute("text")
                    file_title, file_extension, file_size = self.get_parsed_file_info(file_info)
                    
                    self.update_task_state(
                        task, "Getting file information", 
                        file_title, file_size, 
                        index + 1, len(items), page
                    )
                    
                    # Validate file size
                    try:
                        self.downloader.validate_file_size(file_size)
                    except DownloadFileTooLargeError as e:
                        size_exception = str(e)
                        logger.warning(f"Skipping file due to size: {file_title}")
                        self.update_task_state(
                            task, "File size exceeds limit",
                            file_title, file_size,
                            index + 1, len(items), page
                        )
                        continue
                    
                    # Open detail page
                    file_link = item.get_attribute("href")
                    logger.info(f"Opening file detail: {file_link}")
                    
                    self.driver.execute_script("window.open(arguments[0]);", file_link)
                    self.driver.switch_to.window(self.driver.window_handles[1])
                    
                    # Click download button
                    logger.debug("Clicking download button")
                    WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-download.detail-download"))
                    ).click()
                    
                    self.update_task_state(
                        task, "Waiting 30s for download preparation",
                        file_title, file_size,
                        index + 1, len(items), page
                    )
                    
                    # Wait and click final download
                    logger.debug("Waiting for final download link")
                    WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.download"))
                    ).click()
                    
                    download_link_element = WebDriverWait(self.driver, 40).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.link-to-file"))
                    )
                    
                    download_link = download_link_element.get_attribute("href")
                    logger.info(f"Download link obtained: {download_link}")
                    
                    self.close_window()
                    
                    # Download file
                    self.update_task_state(
                        task, "Downloading file",
                        file_title, file_size,
                        index + 1, len(items), page
                    )
                    
                    download_info, download_path, download_exception = self.downloader.download_file(download_link)
                    
                    self.update_task_state(
                        task, download_info,
                        file_title, file_size,
                        index + 1, len(items), page
                    )
                    
                    # Calculate hash if download successful
                    if download_path:
                        hash_value = calculate_sha256(str(download_path))
                        download_file_title = os.path.basename(download_path)
                        save_hashes(download_file_title, hash_value)
                        
                        self.update_task_state(
                            task, "Hash created for downloaded file",
                            file_title, file_size,
                            index + 1, len(items), page
                        )
                        logger.info(f"File downloaded successfully: {download_path}")
                    
                except TimeoutException as e:
                    timeout_exception = f"Timeout downloading file: {file_title}"
                    logger.error(timeout_exception, exc_info=True)
                    self.close_window()
                
                except Exception as e:
                    logger.error(f"Error processing file {file_title}: {e}", exc_info=True)
                    try:
                        self.close_window()
                    except:
                        pass
                
                finally:
                    # Save to database
                    try:
                        if download_path and hash_value:
                            db_hash_id = self.db.insert_hash(hash_value)
                            download_file_title = os.path.basename(download_path)
                            db_crack_id = self.db.insert_crack(
                                file_title, file_size, file_extension,
                                download_file_title, db_hash_id
                            )
                        else:
                            db_crack_id = self.db.insert_crack(
                                file_title, file_size, file_extension,
                                None, None
                            )
                        
                        # Insert errors if any
                        if download_exception:
                            self.db.insert_error(download_info, db_crack_id)
                        if timeout_exception:
                            self.db.insert_error(timeout_exception, db_crack_id)
                        if size_exception:
                            self.db.insert_error(size_exception, db_crack_id)
                    
                    except Exception as e:
                        logger.error(f"Error saving to database: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error crawling page {page}: {e}", exc_info=True)
            raise
    
    def crawl(self, task):
        """
        Main crawl method - iterates through all pages.
        
        Args:
            task: Celery task instance
        """
        page = 0
        try:
            while True:
                page += 1
                formatted_url = self.format_url(self.url, self.keyword, page)
                logger.info(f"Crawling page {page}: {formatted_url}")
                
                try:
                    self.driver.get(formatted_url)
                    self.crawl_page(task=task, page=page)
                    
                    if not self.find_next_button():
                        logger.info("No more pages to crawl")
                        break
                
                except Exception as e:
                    logger.error(f"Error loading page {page}: {e}", exc_info=True)
                    break
        
        finally:
            self.close()