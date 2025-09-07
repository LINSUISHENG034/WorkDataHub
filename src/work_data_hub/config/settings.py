"""
Configuration management for WorkDataHub.

This module provides environment-based configuration using Pydantic BaseSettings,
allowing for flexible deployment across development, testing, and production
environments while maintaining secure credential management.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseModel):
    """Database connection configuration."""

    model_config = ConfigDict(
        env_prefix="WDH_DATABASE__",
        case_sensitive=False,
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    user: str = Field(default="user", description="Database user")
    password: str = Field(default="password", description="Database password")
    db: str = Field(default="database", description="Database name")

    # Optional URI override
    uri: Optional[str] = Field(None, description="Complete database URI")

    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        if self.uri:
            return self.uri
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    This class defines all configurable parameters for WorkDataHub, with
    sensible defaults for development and support for environment-based
    overrides in production.

    Environment variables are automatically loaded with the WDH_ prefix.
    For example, WDH_DATA_BASE_DIR will override the data_base_dir setting.
    """

    # Core application settings
    app_name: str = Field(default="WorkDataHub", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Data processing configuration
    data_base_dir: str = Field(
        default="./data", description="Base directory for data file discovery"
    )

    data_sources_config: str = Field(
        default="./src/work_data_hub/config/data_sources.yml",
        description="Path to data sources configuration file",
    )

    # Performance settings
    max_file_size_mb: int = Field(
        default=100, description="Maximum Excel file size to process (MB)"
    )

    max_workers: int = Field(
        default=4, description="Maximum number of concurrent processing workers"
    )

    # Development settings
    dev_sample_size: Optional[int] = Field(
        default=None, description="Limit processing to N rows for development (None = no limit)"
    )

    # Database configuration
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Database connection settings"
    )

    model_config = ConfigDict(
        env_prefix="WDH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses LRU cache to ensure settings are loaded once and reused across
    the application lifecycle, improving performance and consistency.

    Returns:
        Settings instance with loaded configuration
    """
    return Settings()


def validate_data_directory(settings: Settings) -> bool:
    """
    Validate that the configured data directory exists and is accessible.

    Args:
        settings: Settings instance to validate

    Returns:
        True if data directory is valid, False otherwise
    """
    try:
        data_path = Path(settings.data_base_dir)
        return data_path.exists() and data_path.is_dir()
    except (OSError, FileNotFoundError):
        return False


def validate_config_file(settings: Settings) -> bool:
    """
    Validate that the data sources configuration file exists and is readable.

    Args:
        settings: Settings instance to validate

    Returns:
        True if config file is valid, False otherwise
    """
    try:
        config_path = Path(settings.data_sources_config)
        return config_path.exists() and config_path.is_file()
    except (OSError, FileNotFoundError):
        return False
