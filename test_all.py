from config import get_settings
from logging_config import get_logger
from exceptions import CrawlerException
from dbManager import DBManager
from downloader import Downloader
from hashManager import calculate_sha256
from baseCrawler import BaseCrawler
from datoidCrawler import DatoidCrawler
from crawlerManager import CrawlerManager
from crawlerType import get_crawler

print("✅ Všechny importy fungují!")

settings = get_settings()
logger = get_logger(__name__)

logger.info("Test dokončen úspěšně!")
print(f"✅ Config načten: DB Server = {settings.db_server}")
print(f"✅ Log soubor: {settings.log_file}")