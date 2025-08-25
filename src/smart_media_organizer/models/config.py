"""Configuration management using Pydantic Settings.

This module provides type-safe configuration management for the
Smart Media Organizer application using Pydantic Settings.
"""

from __future__ import annotations

from enum import Enum
import logging
from pathlib import Path

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Log format enumeration."""

    CONSOLE = "console"
    JSON = "json"


class MediaType(str, Enum):
    """Media type enumeration."""

    AUTO = "auto"
    MOVIE = "movie"
    TV = "tv"


class PosterQuality(str, Enum):
    """Poster image quality enumeration."""

    ORIGINAL = "original"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Settings(BaseSettings):
    """Application settings with type validation and environment variable support.

    This class provides a type-safe way to manage configuration settings,
    supporting environment variables, .env files, and default values.
    """

    # API Configuration
    hf_token: str = Field(
        ...,
        env="HF_TOKEN",
        description="Hugging Face API token for AI model access",
    )
    tmdb_api_key: str = Field(
        ...,
        env="TMDB_API_KEY",
        description="TMDB API key for movie/TV metadata",
    )

    # Logging Configuration
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        env="LOG_LEVEL",
        description="Application log level",
    )
    log_format: LogFormat = Field(
        default=LogFormat.CONSOLE,
        env="LOG_FORMAT",
        description="Log output format",
    )
    log_file: Path | None = Field(
        default=None,
        env="LOG_FILE",
        description="Optional log file path",
    )
    structured_logging: bool = Field(
        default=False,
        env="STRUCTURED_LOGGING",
        description="Enable structured logging for production",
    )

    # Performance Configuration
    max_concurrent: int = Field(
        default=10,
        ge=1,
        le=50,
        env="MAX_CONCURRENT",
        description="Maximum concurrent API requests",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        env="TIMEOUT_SECONDS",
        description="Request timeout in seconds",
    )
    batch_size: int = Field(
        default=20,
        ge=1,
        le=100,
        env="BATCH_SIZE",
        description="Batch size for processing files",
    )
    rate_limit_rpm: int = Field(
        default=300,
        ge=1,
        le=1000,
        env="RATE_LIMIT_RPM",
        description="Rate limiting (requests per minute)",
    )

    # Application Behavior
    default_media_type: MediaType = Field(
        default=MediaType.AUTO,
        env="DEFAULT_MEDIA_TYPE",
        description="Default media type detection",
    )
    default_dry_run: bool = Field(
        default=False,
        env="DEFAULT_DRY_RUN",
        description="Enable dry run mode by default",
    )
    default_verbose: bool = Field(
        default=False,
        env="DEFAULT_VERBOSE",
        description="Enable verbose logging by default",
    )

    # File Processing Configuration
    video_extensions: list[str] = Field(
        default=[".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
        env="VIDEO_EXTENSIONS",
        description="Supported video file extensions",
    )
    min_file_size_mb: int = Field(
        default=10,
        ge=0,
        env="MIN_FILE_SIZE_MB",
        description="Minimum file size in MB to process",
    )
    max_file_size_gb: int = Field(
        default=0,
        ge=0,
        env="MAX_FILE_SIZE_GB",
        description="Maximum file size in GB to process (0 = no limit)",
    )
    skip_patterns: list[str] = Field(
        default=[".sample", ".trailer", ".extras"],
        env="SKIP_PATTERNS",
        description="Skip files with these patterns",
    )

    # Output Configuration
    create_info_files: bool = Field(
        default=True,
        env="CREATE_INFO_FILES",
        description="Create info files (movie-info.json, show-info.json)",
    )
    download_posters: bool = Field(
        default=True,
        env="DOWNLOAD_POSTERS",
        description="Download movie/show posters",
    )
    max_posters: int = Field(
        default=3,
        ge=0,
        le=10,
        env="MAX_POSTERS",
        description="Maximum number of posters to download",
    )
    poster_quality: PosterQuality = Field(
        default=PosterQuality.HIGH,
        env="POSTER_QUALITY",
        description="Poster image quality",
    )

    # Safety Configuration
    create_backup: bool = Field(
        default=False,
        env="CREATE_BACKUP",
        description="Enable backup before moving files",
    )
    backup_dir: str = Field(
        default=".backup",
        env="BACKUP_DIR",
        description="Backup directory (relative to source directory)",
    )
    verify_integrity: bool = Field(
        default=True,
        env="VERIFY_INTEGRITY",
        description="Verify file integrity after move",
    )

    # Development Configuration
    debug: bool = Field(
        default=False,
        env="DEBUG",
        description="Enable debug mode",
    )
    mock_apis: bool = Field(
        default=False,
        env="MOCK_APIS",
        description="Mock API calls for testing",
    )
    test_data_dir: Path | None = Field(
        default=None,
        env="TEST_DATA_DIR",
        description="Test data directory for development",
    )

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        use_enum_values = True

    @validator("video_extensions", pre=True)
    def parse_video_extensions(cls, v) -> list[str]:
        """Parse video extensions from string or list."""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @validator("skip_patterns", pre=True)
    def parse_skip_patterns(cls, v) -> list[str]:
        """Parse skip patterns from string or list."""
        if isinstance(v, str):
            return [pattern.strip() for pattern in v.split(",")]
        return v

    @validator("log_file", pre=True)
    def parse_log_file(cls, v) -> Path | None:
        """Parse log file path."""
        if v is None or v == "":
            return None
        return Path(v)

    @validator("test_data_dir", pre=True)
    def parse_test_data_dir(cls, v) -> Path | None:
        """Parse test data directory path."""
        if v is None or v == "":
            return None
        return Path(v)

    def get_logging_level(self) -> int:
        """Get Python logging level from enum."""
        return getattr(logging, self.log_level.value)

    def is_video_file(self, file_path: Path) -> bool:
        """Check if file is a supported video file."""
        return file_path.suffix.lower() in [
            ext.lower() for ext in self.video_extensions
        ]

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped based on patterns."""
        filename = file_path.name.lower()
        return any(pattern.lower() in filename for pattern in self.skip_patterns)

    def get_file_size_limits(self) -> tuple[int, int | None]:
        """Get file size limits in bytes."""
        min_size = self.min_file_size_mb * 1024 * 1024
        max_size = None
        if self.max_file_size_gb > 0:
            max_size = self.max_file_size_gb * 1024 * 1024 * 1024
        return min_size, max_size


# Global settings instance (lazy initialization)
def get_settings() -> Settings:
    """Get application settings with lazy initialization."""
    return Settings()


# For backward compatibility
settings = None
