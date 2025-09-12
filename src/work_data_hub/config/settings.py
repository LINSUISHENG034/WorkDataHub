"""
Configuration management for WorkDataHub.

This module provides environment-based configuration using Pydantic BaseSettings,
allowing for flexible deployment across development, testing, and production
environments while maintaining secure credential management.
"""

from functools import lru_cache
import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings:
    """
    Database settings compatibility layer for unified DSN retrieval.

    This class provides a lightweight compatibility wrapper around individual
    database configuration parameters, supporting both component-based and
    URI-based connection string generation.
    """

    def __init__(
        self,
        host: str,
        port: int = 5432,
        user: str = "",
        password: str = "",
        db: str = "",
        uri: Optional[str] = None,
    ):
        """
        Initialize database settings.

        Args:
            host: Database host
            port: Database port
            user: Database user
            password: Database password
            db: Database name
            uri: Complete database URI (overrides other parameters if provided)
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db = db
        self.uri = uri

    def get_connection_string(self) -> str:
        """
        Get PostgreSQL connection string.

        Returns:
            Database connection string (DSN)
        """
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

    # Database configuration - nested settings with WDH_DATABASE__ prefix
    database_host: str = Field(default="localhost", description="Database host")
    database_port: int = Field(default=5432, description="Database port")
    database_user: str = Field(default="user", description="Database user")
    database_password: str = Field(default="password", description="Database password")
    database_db: str = Field(default="database", description="Database name")
    database_uri: Optional[str] = Field(default=None, description="Complete database URI")

    def get_database_connection_string(self) -> str:
        """Get PostgreSQL connection string.

        Unifies environment variable usage by preferring a single canonical URI
        while maintaining backward compatibility with prior naming.
        Priority order:
        1) WDH_DATABASE__URI (canonical)
        2) WDH_DATABASE_URI (alternate)
        3) self.database_uri (settings field)
        4) Construct from individual components
        """
        # Canonical and alternate environment variable overrides
        env_uri = os.getenv("WDH_DATABASE__URI") or os.getenv("WDH_DATABASE_URI")
        if env_uri:
            return env_uri
        return self.database.get_connection_string()

    @property
    def database(self) -> DatabaseSettings:
        """
        Get database settings compatibility wrapper.

        Returns:
            DatabaseSettings instance assembled from individual configuration fields
        """
        return DatabaseSettings(
            host=self.database_host,
            port=self.database_port,
            user=self.database_user,
            password=self.database_password,
            db=self.database_db,
            uri=self.database_uri,
        )

    model_config = SettingsConfigDict(
        env_prefix="WDH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Nested settings using double underscore
        env_nested_delimiter="__",
        # Accept additional env inputs (e.g., WDH_DATABASE__URI)
        extra="ignore",
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
