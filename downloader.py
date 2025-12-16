"""
Refactored downloader with proper error handling and logging.
Removed unsafe proxy handling.
"""
import os
import requests
import mimetypes
import zipfile
from pathlib import Path
from typing import Tuple, Optional

from config import get_settings
from logging_config import get_logger
from exceptions import (
    DownloadException,
    DownloadTimeoutError,
    DownloadIOError,
    DownloadFileTooLargeError
)

logger = get_logger(__name__)
settings = get_settings()


class Downloader:
    """Handles file downloads with proper error handling."""
    
    def __init__(self, folder: str):
        """
        Initialize downloader.
        
        Args:
            folder: Download folder path
        """
        self.download_folder = Path(folder)
        self.download_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloader initialized with folder: {self.download_folder}")
    
    def _get_file_name(self, response: requests.Response, url: str) -> str:
        """
        Extract filename from HTTP response or URL.
        
        Args:
            response: HTTP response object
            url: Request URL
            
        Returns:
            Filename
        """
        # Try Content-Disposition header first
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition and "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[-1].strip("\"'")
            logger.debug(f"Filename from Content-Disposition: {filename}")
            return filename
        
        # Extract from URL
        filename = url.split("/")[-1]
        
        # If no extension, try to detect from Content-Type
        if "." not in filename:
            extension = self._get_file_extension(response)
            filename = filename + (extension if extension else "")
        
        logger.debug(f"Filename from URL: {filename}")
        return filename
    
    def _get_file_extension(self, response: requests.Response) -> str:
        """
        Detect file extension from Content-Type header.
        
        Args:
            response: HTTP response object
            
        Returns:
            File extension (including dot) or empty string
        """
        content_type = response.headers.get("Content-Type")
        if content_type:
            extension = mimetypes.guess_extension(content_type) or ""
            logger.debug(f"Extension from Content-Type: {extension}")
            return extension
        return ""
    
    def _get_unique_file_path(self, filename: str) -> Path:
        """
        Generate unique file path by adding counter if file exists.
        
        Args:
            filename: Base filename
            
        Returns:
            Unique file path
        """
        base_name, _ = os.path.splitext(filename)
        extension = ".zip"
        unique_filename = base_name + extension
        counter = 1
        
        file_path = self.download_folder / unique_filename
        
        while file_path.exists():
            unique_filename = f"{base_name}({counter}){extension}"
            file_path = self.download_folder / unique_filename
            counter += 1
        
        logger.debug(f"Generated unique file path: {file_path}")
        return file_path
    
    def validate_file_size(self, file_size: str) -> bool:
        """
        Validate if file size is within allowed limits.
        
        Args:
            file_size: File size string (e.g., "15 MB", "2 GB")
            
        Returns:
            True if file size is acceptable
            
        Raises:
            DownloadFileTooLargeError: If file is too large
        """
        if 'GB' in file_size:
            logger.warning(f"File size {file_size} exceeds limit (GB not allowed)")
            raise DownloadFileTooLargeError(file_size, settings.max_file_size_mb)
        
        if 'MB' in file_size:
            # Extract numeric value
            size_str = "".join(c for c in file_size if c.isdigit() or c == ".")
            try:
                size = float(size_str)
                
                if size > settings.max_file_size_mb:
                    logger.warning(f"File size {size} MB exceeds limit of {settings.max_file_size_mb} MB")
                    raise DownloadFileTooLargeError(file_size, settings.max_file_size_mb)
                
                logger.debug(f"File size {size} MB is acceptable")
                return True
            except ValueError:
                logger.warning(f"Could not parse file size: {file_size}")
                return True  # Allow download if size can't be parsed
        
        logger.debug(f"File size {file_size} is acceptable")
        return True
    
    def download_file(self, url: str) -> Tuple[str, Optional[Path], bool]:
        """
        Download file from URL and save as ZIP.
        
        Args:
            url: Download URL
            
        Returns:
            Tuple of (status_message, file_path, has_error)
        """
        logger.info(f"Starting download from: {url}")
        
        try:
            # Send GET request with timeout
            response = requests.get(
                url,
                stream=True,
                timeout=settings.selenium_timeout
            )
            response.raise_for_status()
            
            # Get filename
            file_name = self._get_file_name(response, url)
            
            # Get unique file path
            file_path = self._get_unique_file_path(file_name)
            
            # Download and save as ZIP
            try:
                with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    with zipf.open(file_name, "w") as zip_file:
                        downloaded_size = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                zip_file.write(chunk)
                                downloaded_size += len(chunk)
                
                logger.info(f"File successfully downloaded: {file_path} ({downloaded_size} bytes)")
                return "File successfully downloaded", file_path, False
                
            except (OSError, IOError, zipfile.BadZipFile) as file_error:
                # Clean up incomplete file
                if file_path.exists():
                    file_path.unlink()
                    logger.warning(f"Deleted incomplete file: {file_path}")
                
                error_msg = f"File write error: {file_error}"
                logger.error(error_msg, exc_info=True)
                raise DownloadIOError(error_msg)
                
        except requests.exceptions.Timeout as e:
            error_msg = f"Download timeout: {e}"
            logger.error(error_msg)
            return error_msg, None, True
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Download request failed: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg, None, True
            
        except DownloadIOError as e:
            return str(e), None, True
            
        except Exception as e:
            error_msg = f"Unexpected download error: {e}"
            logger.error(error_msg, exc_info=True)
            return error_msg, None, True