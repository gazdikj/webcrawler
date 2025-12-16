"""
Refactored base crawler with proper error handling and logging.
"""
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from pathlib import Path
from typing import Optional

from downloader import Downloader
from dbManager import DBManager
from config import get_settings
from logging_config import get_logger
from exceptions import CrawlerInitializationError

logger = get_logger(__name__)
settings = get_settings()


class BaseCrawler(ABC):
    """Base class for all web crawlers."""
    
    def __init__(self, url: str, what_to_crawl: str = "", 
                 browser: str = "chrome", device: str = "desktop"):
        """
        Initialize crawler.
        
        Args:
            url: Target URL
            what_to_crawl: Search keyword
            browser: Browser type
            device: Device type (desktop/mobile)
            
        Raises:
            CrawlerInitializationError: If initialization fails
        """
        try:
            self.url = url
            self.keyword = what_to_crawl
            self.browser = browser
            self.device = device
            
            # Setup download folder
            self.download_folder = self._get_download_folder(what_to_crawl)
            logger.info(f"Download folder: {self.download_folder}")
            
            # Initialize components
            self.downloader = Downloader(str(self.download_folder))
            self.db = DBManager(url, what_to_crawl, browser, device)
            self.driver = self._init_browser(browser, device)
            
            logger.info(f"Crawler initialized: {self.__class__.__name__}")
            
        except Exception as e:
            logger.error(f"Failed to initialize crawler: {e}", exc_info=True)
            raise CrawlerInitializationError(f"Crawler initialization failed: {e}")
    
    def _get_download_folder(self, keyword: str) -> Path:
        """
        Create and return download folder path.
        
        Args:
            keyword: Search keyword for folder naming
            
        Returns:
            Path to download folder
        """
        base_folder = Path(settings.download_folder)
        crawler_folder = base_folder / self.__class__.__name__ / keyword
        crawler_folder.mkdir(parents=True, exist_ok=True)
        return crawler_folder
    
    def _init_browser(self, browser: str, device: str) -> webdriver.Chrome:
        """
        Initialize Selenium WebDriver.
        
        Args:
            browser: Browser type
            device: Device type
            
        Returns:
            WebDriver instance
            
        Raises:
            CrawlerInitializationError: If browser initialization fails
        """
        try:
            options = Options()
            
            # Download preferences
            prefs = {
                "download.default_directory": str(self.download_folder.absolute()),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False,
                "safebrowsing.disable_download_protection": True,
                "safebrowsing.for_trusted_sources_enabled": False
            }
            options.add_experimental_option("prefs", prefs)
            
            # User agent configuration
            user_agents = {
                "chrome_desktop": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
                "firefox_desktop": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:107.0) Gecko/20100101 Firefox/107.0",
                "chrome_mobile": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36",
                "firefox_mobile": "Mozilla/5.0 (Android 10; Mobile; rv:107.0) Gecko/107.0 Firefox/107.0"
            }
            
            profile = f"{browser}_{device}"
            user_agent = user_agents.get(profile, user_agents['chrome_desktop'])
            options.add_argument(f"user-agent={user_agent}")
            
            # Headless mode from config
            options.headless = settings.selenium_headless
            
            # Additional options for stability
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Initialize driver
            service = Service(settings.chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            
            logger.info(f"Browser initialized: {browser} ({device}), headless={settings.selenium_headless}")
            return driver
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}", exc_info=True)
            raise CrawlerInitializationError(f"Browser initialization failed: {e}")
    
    @abstractmethod
    def crawl(self, task):
        """
        Main crawling method to be implemented by subclasses.
        
        Args:
            task: Celery task for progress updates
        """
        pass
    
    def close(self, task=None):
        """Close browser and cleanup resources."""
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
                logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}", exc_info=True)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        if exc_type:
            logger.error(f"Exception in crawler context: {exc_val}", exc_info=True)
        return False