"""
Custom exception classes for the application.
Provides specific exceptions for different error scenarios.
"""


class CrawlerException(Exception):
    """Base exception for all crawler-related errors."""
    pass


class CrawlerInitializationError(CrawlerException):
    """Raised when crawler fails to initialize."""
    pass


class CrawlerTimeoutError(CrawlerException):
    """Raised when crawler operation times out."""
    pass


class CrawlerPageNotFoundError(CrawlerException):
    """Raised when requested page is not found."""
    pass


class DatabaseException(Exception):
    """Base exception for all database-related errors."""
    pass


class DatabaseConnectionError(DatabaseException):
    """Raised when database connection fails."""
    pass


class DatabaseInsertError(DatabaseException):
    """Raised when database insert operation fails."""
    pass


class DatabaseQueryError(DatabaseException):
    """Raised when database query fails."""
    pass


class DownloadException(Exception):
    """Base exception for all download-related errors."""
    pass


class DownloadTimeoutError(DownloadException):
    """Raised when download operation times out."""
    pass


class DownloadFileTooLargeError(DownloadException):
    """Raised when file exceeds maximum allowed size."""
    def __init__(self, file_size: str, max_size: float):
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(f"File size {file_size} exceeds maximum allowed size of {max_size} MB")


class DownloadIOError(DownloadException):
    """Raised when file write operation fails."""
    pass


class VirusTotalException(Exception):
    """Base exception for VirusTotal API errors."""
    pass


class VirusTotalAPIError(VirusTotalException):
    """Raised when VirusTotal API request fails."""
    pass


class VirusTotalRateLimitError(VirusTotalException):
    """Raised when VirusTotal API rate limit is exceeded."""
    pass


class VirusTotalTimeoutError(VirusTotalException):
    """Raised when VirusTotal analysis times out."""
    pass


class ConfigurationException(Exception):
    """Base exception for configuration errors."""
    pass


class MissingConfigurationError(ConfigurationException):
    """Raised when required configuration is missing."""
    pass


class InvalidConfigurationError(ConfigurationException):
    """Raised when configuration value is invalid."""
    pass


class ValidationException(Exception):
    """Base exception for validation errors."""
    pass


class InvalidInputError(ValidationException):
    """Raised when input validation fails."""
    pass


class FileValidationError(ValidationException):
    """Raised when file validation fails."""
    pass