"""
Refactored crawler manager with proper error handling and logging.
"""
from typing import List, Type
from baseCrawler import BaseCrawler
from logging_config import get_logger

logger = get_logger(__name__)


class CrawlerManager:
    """Manages multiple crawler instances."""
    
    def __init__(self):
        """Initialize crawler manager."""
        self.crawlers: List[BaseCrawler] = []
        logger.info("CrawlerManager initialized")
    
    def add_crawler(self, crawler_class: Type[BaseCrawler], url: str, 
                   browser: str = "chrome", device: str = "desktop") -> None:
        """
        Add and start a crawler.
        
        Args:
            crawler_class: Crawler class to instantiate
            url: Target URL
            browser: Browser type
            device: Device type
        """
        try:
            logger.info(f"Adding crawler: {crawler_class.__name__} for {url}")
            
            # Create crawler instance
            crawler = crawler_class(url, "katy perry roar", browser, device)
            self.crawlers.append(crawler)
            
            # Start crawling
            logger.info(f"Starting crawler: {crawler_class.__name__}")
            crawler.crawl("")
            
            logger.info(f"Crawler completed: {crawler_class.__name__}")
            
        except Exception as e:
            logger.error(f"Error adding/running crawler {crawler_class.__name__}: {e}", 
                        exc_info=True)
    
    def stop_all(self) -> None:
        """Stop all active crawlers."""
        logger.info(f"Stopping {len(self.crawlers)} crawlers")
        
        for crawler in self.crawlers:
            try:
                logger.debug(f"Stopping crawler: {crawler.__class__.__name__}")
                crawler.close()
            except Exception as e:
                logger.error(f"Error stopping crawler: {e}", exc_info=True)
        
        self.crawlers.clear()
        logger.info("All crawlers stopped")