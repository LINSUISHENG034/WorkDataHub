"""
Configuration management for WorkDataHub.

This module provides environment-based configuration using Pydantic BaseSettings,
allowing for flexible deployment across development, testing, and production
environments while maintaining secure credential management.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine project root for resolving .env by default
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
ENV_FILE_OVERRIDE = os.getenv("WDH_ENV_FILE")
if ENV_FILE_OVERRIDE:
    env_file_candidate = Path(ENV_FILE_OVERRIDE).expanduser()
    if not env_file_candidate.is_absolute():
        env_file_candidate = PROJECT_ROOT / env_file_candidate
    SETTINGS_ENV_FILE = env_file_candidate
else:
    SETTINGS_ENV_FILE = DEFAULT_ENV_FILE


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

    Story 1.4 Configuration Management fields (no prefix):
    - DATABASE_URL (required): Database connection string
    - ENVIRONMENT: Deployment environment (dev, staging, prod)
    - LOG_LEVEL: Logging level (uppercase)
    - DAGSTER_HOME: Dagster home directory
    - MAX_WORKERS: Maximum worker threads (uppercase)
    - DB_POOL_SIZE: Database connection pool size
    - DB_BATCH_SIZE: Batch size for database operations
    """

    # Story 1.4 required fields (no prefix, uppercase names)
    DATABASE_URL: str = Field(
        default="sqlite:///workdatahub_dev.db",
        validation_alias="DATABASE_URL",
        description="Database connection string (required for Story 1.4)",
    )
    ENVIRONMENT: Literal["dev", "staging", "prod"] = Field(
        default="dev",
        validation_alias="ENVIRONMENT",
        description="Deployment environment",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
        description="Logging level (uppercase)",
    )
    DAGSTER_HOME: str = Field(
        default="~/.dagster",
        validation_alias="DAGSTER_HOME",
        description="Dagster home directory",
    )
    MAX_WORKERS: int = Field(
        default=4,
        validation_alias="MAX_WORKERS",
        description="Maximum worker threads (uppercase field name)",
    )
    DB_POOL_SIZE: int = Field(
        default=10,
        validation_alias="DB_POOL_SIZE",
        description="Database connection pool size",
    )
    DB_BATCH_SIZE: int = Field(
        default=1000,
        validation_alias="DB_BATCH_SIZE",
        description="Batch size for database operations",
    )

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
        default=None,
        description="Limit processing to N rows for development (None = no limit)",
    )

    # EQC Configuration - Enterprise Query Center API settings
    eqc_enabled: bool = Field(default=True, description="Enable EQC API integration")

    eqc_timeout: int = Field(
        default=30, description="EQC API request timeout in seconds"
    )

    eqc_rate_limit: int = Field(
        default=10, description="EQC API rate limit (requests per minute)"
    )

    eqc_retry_max: int = Field(
        default=3, description="Maximum retry attempts for EQC API requests"
    )

    eqc_base_url: str = Field(
        default="https://eqc.pingan.com", description="EQC API base URL"
    )

    # Company Enrichment Configuration - service and queue settings
    company_enrichment_enabled: bool = Field(
        default=True, description="Enable company enrichment service functionality"
    )

    company_sync_lookup_limit: int = Field(
        default=5, description="Default budget for synchronous EQC lookups per request"
    )

    lookup_queue_batch_size: int = Field(
        default=50, description="Batch size for processing lookup queue requests"
    )

    lookup_retry_max: int = Field(
        default=3, description="Maximum retry attempts for failed lookup requests"
    )

    lookup_retry_delay: int = Field(
        default=300, description="Delay in seconds between lookup retry attempts"
    )

    enrichment_export_unknowns: bool = Field(
        default=True,
        description="Export unknown company names to CSV for manual review",
    )

    # Pipeline Framework Configuration - shared transformation pipeline settings
    annuity_pipeline_enabled: bool = Field(
        default=True,
        description="Use shared pipeline framework for annuity performance processing",
    )

    # Database configuration - nested settings with WDH_DATABASE__ prefix
    database_host: str = Field(default="localhost", description="Database host")
    database_port: int = Field(default=5432, description="Database port")
    database_user: str = Field(default="user", description="Database user")
    database_password: str = Field(default="password", description="Database password")
    database_db: str = Field(default="database", description="Database name")
    database_uri: Optional[str] = Field(
        default=None, description="Complete database URI"
    )

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

    @model_validator(mode="after")
    def validate_production_database_url(self) -> "Settings":
        """Validate that production environment uses PostgreSQL.

        In production environments, only PostgreSQL connections are allowed
        to prevent accidental use of SQLite or other databases that may not
        be suitable for production workloads.

        Returns:
            The validated Settings instance

        Raises:
            ValueError: If ENVIRONMENT is 'prod' and DATABASE_URL is not PostgreSQL
        """
        if self.ENVIRONMENT == "prod" and not self.DATABASE_URL.startswith(
            "postgresql://"
        ):
            db_url_preview = self.DATABASE_URL[:20]
            raise ValueError(
                "Production environment requires PostgreSQL database. "
                f"DATABASE_URL must start with 'postgresql://', "
                f"got: {db_url_preview}..."
            )

        return self

    model_config = SettingsConfigDict(
        env_prefix="WDH_",
        env_file=str(SETTINGS_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
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
    return Settings()  # type: ignore[call-arg]


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
