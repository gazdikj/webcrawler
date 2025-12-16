"""
Main entry point for running crawlers.
"""
from crawlerManager import CrawlerManager
from datoidCrawler import DatoidCrawler
from config import get_settings
from logging_config import setup_logging, get_logger

# Initialize settings and logging
settings = get_settings()
setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file
)
logger = get_logger(__name__)


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Starting crawler application")
    logger.info("="*60)
    
    try:
        manager = CrawlerManager()
        
        # Add crawlers for different websites
        manager.add_crawler(
            DatoidCrawler,
            "https://datoid.cz",
            browser="chrome",
            device="desktop"
        )
        
        logger.info("All crawlers completed")
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        manager.stop_all()
    
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        manager.stop_all()
    
    finally:
        logger.info("="*60)
        logger.info("Crawler application finished")
        logger.info("="*60)