"""
Configuration management using Pydantic settings.
Loads environment variables from .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database settings
    db_server: str = Field(default="localhost", description="SQL Server hostname")
    db_name: str = Field(default="test", description="Database name")
    db_user: Optional[str] = Field(default=None, description="Database user")
    db_password: Optional[str] = Field(default=None, description="Database password")
    db_driver: str = Field(default="SQL Server", description="Database driver")
    db_trust_connection: bool = Field(default=True, description="Use Windows authentication")
    
    # Analysis database
    analysis_db_name: str = Field(default="CrackDB", description="Analysis database name")
    
    # VirusTotal API
    vt_api_key: str = Field(default="", description="VirusTotal API key")
    
    # Redis settings
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    
    # Selenium settings
    chromedriver_path: str = Field(default="drivers/chromedriver-win64/chromedriver.exe", description="Path to chromedriver executable")
    selenium_headless: bool = Field(default=True, description="Run browser in headless mode")
    selenium_timeout: int = Field(default=10, description="Default timeout for Selenium waits")
    
    # Download settings
    download_folder: str = Field(default="downloads", description="Base folder for downloads")
    max_file_size_mb: float = Field(default=20.0, description="Maximum file size in MB")
    
    # Flask API settings
    flask_host: str = Field(default="127.0.0.1", description="Flask host")
    flask_port: int = Field(default=5000, description="Flask port")
    flask_debug: bool = Field(default=False, description="Flask debug mode")
    
    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default="logs/app.log", description="Log file path")
    
    # Crawler settings
    crawler_page_delay: int = Field(default=2, description="Delay between pages in seconds")
    crawler_retry_attempts: int = Field(default=3, description="Number of retry attempts")
    
    # VirusTotal settings
    vt_analysis_check_interval: int = Field(default=10, description="Seconds between VT analysis checks")
    vt_max_wait_time: int = Field(default=600, description="Max wait time for VT analysis")
    
    @validator('download_folder', 'log_file')
    def create_directories(cls, v):
        """Ensure directories exist for paths."""
        if v:
            path = Path(v)
            if '.' in path.name:  # It's a file path
                path.parent.mkdir(parents=True, exist_ok=True)
            else:  # It's a directory path
                path.mkdir(parents=True, exist_ok=True)
        return v
    
    @property
    def db_connection_string(self) -> str:
        """Generate database connection string."""
        if self.db_trust_connection:
            return f"""
                DRIVER={{{self.db_driver}}};
                SERVER={self.db_server};
                DATABASE={self.db_name};
                Trust_Connection=yes;
            """
        else:
            return f"""
                DRIVER={{{self.db_driver}}};
                SERVER={self.db_server};
                DATABASE={self.db_name};
                UID={self.db_user};
                PWD={self.db_password};
            """
    
    @property
    def analysis_db_connection_string(self) -> str:
        """Generate analysis database connection string."""
        if self.db_trust_connection:
            return f"""
                DRIVER={{{self.db_driver}}};
                SERVER={self.db_server};
                DATABASE={self.analysis_db_name};
                Trust_Connection=yes;
            """
        else:
            return f"""
                DRIVER={{{self.db_driver}}};
                SERVER={self.db_server};
                DATABASE={self.analysis_db_name};
                UID={self.db_user};
                PWD={self.db_password};
            """
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backwards compatibility with old config.py
settings = get_settings()
SERVER_NAME = settings.db_server
DB_USER = settings.db_user
DB_PASSWORD = settings.db_password
VT_API_KEY = settings.vt_api_key