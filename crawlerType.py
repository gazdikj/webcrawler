"""
Refactored crawler type mapper with proper error handling and logging.
"""
from typing import Optional, Type
from baseCrawler import BaseCrawler
from datoidCrawler import DatoidCrawler
from logging_config import get_logger

logger = get_logger(__name__)

# Crawler mapping - add new crawlers here
CRAWLER_MAP = {
    "https://datoid.cz": DatoidCrawler,
    "datoid.cz": DatoidCrawler,
}


def get_crawler(url: str) -> Optional[Type[BaseCrawler]]:
    """
    Get appropriate crawler class for URL.
    
    Args:
        url: Target URL
        
    Returns:
        Crawler class or None if not found
    """
    logger.debug(f"Finding crawler for URL: {url}")
    
    # Normalize URL
    url_lower = url.lower().strip()
    
    # Try exact match first
    for domain, crawler_class in CRAWLER_MAP.items():
        if domain in url_lower:
            logger.info(f"Found crawler: {crawler_class.__name__} for {url}")
            return crawler_class
    
    logger.warning(f"No crawler found for URL: {url}")
    return None


def register_crawler(domain: str, crawler_class: Type[BaseCrawler]) -> None:
    """
    Register a new crawler for a domain.
    
    Args:
        domain: Domain or URL pattern
        crawler_class: Crawler class to use
    """
    logger.info(f"Registering crawler: {crawler_class.__name__} for {domain}")
    CRAWLER_MAP[domain] = crawler_class


def list_crawlers() -> dict:
    """
    Get all registered crawlers.
    
    Returns:
        Dictionary of domain -> crawler class mappings
    """
    return CRAWLER_MAP.copy()


if __name__ == "__main__":
    # Test functionality
    test_urls = [
        "https://datoid.cz",
        "https://datoid.cz/search",
        "https://cantfindcrawler.com"
    ]
    
    for url in test_urls:
        crawler = get_crawler(url)
        if crawler:
            logger.info(f"✓ {url} -> {crawler.__name__}")
        else:
            logger.info(f"✗ {url} -> No crawler found")