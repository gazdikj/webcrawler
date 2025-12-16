"""
Refactored Celery worker with proper error handling and logging.
"""
from celery import Celery
from time import sleep

from crawlerType import get_crawler
from testFile import testFile, analyseFile
from config import get_settings
from logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Initialize Celery with Redis broker
celery_app = Celery(
    "tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    celery_broker_connection_retry_on_startup=True
)

logger.info("Celery app initialized")


@celery_app.task(bind=True)
def long_running_task(self, url: str, what_to_crawl: str, browser: str, device: str):
    """
    Long-running crawling task.
    
    Args:
        url: Target URL
        what_to_crawl: Search keyword
        browser: Browser type
        device: Device type
        
    Returns:
        Completion message
    """
    logger.info(f"Starting crawl task: {url}, keyword: {what_to_crawl}")
    
    try:
        # Get appropriate crawler class
        crawler_class = get_crawler(url)
        if not crawler_class:
            error_msg = f"No crawler found for URL: {url}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Create crawler instance
        crawler = crawler_class(url, what_to_crawl, browser, device)
        
        # Start crawling
        logger.info(f"Starting crawl with {crawler_class.__name__}")
        crawler.crawl(self)
        
        logger.info(f"Crawl completed: {url}")
        return f"Crawling of {url} completed successfully"
    
    except Exception as e:
        logger.error(f"Crawl task failed: {e}", exc_info=True)
        raise


@celery_app.task(bind=True)
def analyse_sample(self, file_name: str, byte_data: bytes):
    """
    Analyze file sample with VirusTotal.
    
    Args:
        file_name: Name of the file
        byte_data: File content as bytes
        
    Returns:
        Analysis results
    """
    logger.info(f"Starting analysis task for file: {file_name}")
    
    try:
        # Update initial state
        self.update_state(
            state="FILE_UPLOADED",
            meta={
                "file_name": file_name,
                "file_size": len(byte_data),
                "current": 0,
                "status": "File uploaded for testing"
            }
        )
        
        # Upload to VirusTotal
        logger.info(f"Uploading file to VirusTotal: {file_name}")
        test_id = testFile(file_name, byte_data)
        
        # Update state
        self.update_state(
            state="ANALYSING",
            meta={
                "file_name": file_name,
                "file_size": len(byte_data),
                "current": 0,
                "status": "File uploaded to VT, waiting for analysis"
            }
        )
        
        # Wait for analysis to complete
        data = None
        attempts = 0
        max_attempts = settings.vt_max_wait_time // settings.vt_analysis_check_interval
        
        logger.info(f"Waiting for VirusTotal analysis (max {max_attempts} attempts)")
        
        while not data and attempts < max_attempts:
            data = analyseFile(test_id)
            
            if not data:
                attempts += 1
                logger.debug(f"Analysis not ready, waiting... (attempt {attempts}/{max_attempts})")
                
                self.update_state(
                    state="ANALYSING",
                    meta={
                        "file_name": file_name,
                        "file_size": len(byte_data),
                        "current": 0,
                        "status": f"Waiting for analysis (attempt {attempts}/{max_attempts})"
                    }
                )
                
                sleep(settings.vt_analysis_check_interval)
        
        if not data:
            error_msg = f"VirusTotal analysis timeout after {max_attempts} attempts"
            logger.error(error_msg)
            raise TimeoutError(error_msg)
        
        # Update final state
        self.update_state(
            state="COMPLETED",
            meta={
                "file_name": file_name,
                "file_size": len(byte_data),
                "current": 0,
                "status": "Analysis completed"
            }
        )
        
        logger.info(f"Analysis completed successfully: {file_name}")
        
        return {
            "status": "Analysis completed",
            "data": data
        }
    
    except Exception as e:
        logger.error(f"Analysis task failed: {e}", exc_info=True)
        raise