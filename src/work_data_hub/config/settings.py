"""
Configuration management for WorkDataHub.

This module provides environment-based configuration using Pydantic BaseSettings,
allowing for flexible deployment across development, testing, and production
environments while maintaining secure credential management.

Story 3.0: Integrated Epic 3 data source configuration validation at startup.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import structlog
import yaml
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourceConfigV2,
    DataSourcesValidationError,
)

logger = structlog.get_logger(__name__)

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
        default="./config/data_sources.yml",
        description="Path to data sources configuration file",
    )

    # Epic 3 Story 3.0: New data source configuration
    data_sources_config_v2: str = Field(
        default="./config/data_sources.yml",
        description="Path to Epic 3 data sources configuration file",
    )

    # Loaded and validated Epic 3 data source configuration
    data_sources: Optional[DataSourceConfigV2] = Field(
        default=None,
        description="Validated Epic 3 data source configuration (loaded at startup)",
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
    eqc_token: str = Field(
        default="",
        description="EQC API token; loaded from WDH_EQC_TOKEN environment variable",
    )
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

    # Story 6.7: Async enrichment schedule configuration
    async_enrichment_enabled: bool = Field(
        default=True,
        description="Enable/disable async enrichment schedule (AC9)",
    )
    enrichment_sensor_enabled: bool = Field(
        default=False,
        description="Enable/disable enrichment queue sensor (AC5)",
    )
    enrichment_queue_threshold: int = Field(
        default=1000,
        description="Queue depth threshold for sensor triggering (AC5)",
    )
    enrichment_queue_warning_threshold: int = Field(
        default=10000,
        description="Queue depth threshold for warning logs (AC4)",
    )
    enrichment_batch_size: int = Field(
        default=100,
        description="Batch size for async enrichment processing",
    )

    enrichment_export_unknowns: bool = Field(
        default=True,
        description="Export unknown company names to CSV for manual review",
    )

    # Story 6.8: Observability configuration
    observability_log_dir: str = Field(
        default="logs/",
        description="Directory for observability CSV exports (AC8)",
    )
    enrich_enabled: bool = Field(
        default=True,
        description="Enable/disable enrichment (AC6). When False, all companies get temp IDs",
    )

    # Pipeline Framework Configuration - shared transformation pipeline settings
    annuity_pipeline_enabled: bool = Field(
        default=True,
        description="Use shared pipeline framework for annuity performance processing",
    )

    # Story 6.2.4: Reference Sync Configuration
    reference_sync_enabled: bool = Field(
        default=True,
        description="Enable/disable reference sync schedule",
    )

    # Story 6.2-P5: EQC Data Freshness Configuration
    eqc_data_freshness_threshold_days: int = Field(
        default=90,
        description="Data older than this is considered stale (days)",
    )
    eqc_data_refresh_batch_size: int = Field(
        default=100,
        description="Batch size for refresh operations",
    )
    eqc_data_refresh_rate_limit: float = Field(
        default=1.0,
        description="Requests per second during refresh",
    )

    # Legacy MySQL Configuration - for reference data sync (retained for backward compatibility)
    legacy_mysql_host: str = Field(
        default="localhost",
        description="Legacy MySQL database host",
    )
    legacy_mysql_port: int = Field(
        default=3306,
        description="Legacy MySQL database port",
    )
    legacy_mysql_user: str = Field(
        default="readonly_user",
        description="Legacy MySQL database user",
    )
    legacy_mysql_password: str = Field(
        default="",
        description="Legacy MySQL database password",
    )
    legacy_mysql_database: str = Field(
        default="annuity_hub",
        description="Legacy MySQL database name",
    )

    # Legacy PostgreSQL Configuration - for reference data sync (Story 6.2-P1)
    # The legacy data has been migrated from MySQL to PostgreSQL
    # Connection uses WDH_LEGACY_PG_* environment variables
    legacy_pg_host: str = Field(
        default="localhost",
        description="Legacy PostgreSQL database host",
    )
    legacy_pg_port: int = Field(
        default=5432,
        description="Legacy PostgreSQL database port",
    )
    legacy_pg_user: str = Field(
        default="postgres",
        description="Legacy PostgreSQL database user",
    )
    legacy_pg_password: str = Field(
        default="",
        description="Legacy PostgreSQL database password",
    )
    legacy_pg_database: str = Field(
        default="legacy",
        description="Legacy PostgreSQL database name",
    )

    # Database configuration - nested settings with WDH_DATABASE__ prefix
    database_host: str = Field(default="localhost", description="Database host")
    database_port: int = Field(default=5432, description="Database port")
    database_user: str = Field(default="user", description="Database user")
    database_password: str = Field(default="password", description="Database password")
    database_db: str = Field(default="database", description="Database name")
    database_schema: str = Field(
        default="wdh_dev", description="Database schema for all domains"
    )
    database_uri: Optional[str] = Field(
        default=None,
        description="Complete database URI",
        validation_alias=AliasChoices("DATABASE__URI", "DATABASE_URI"),
    )

    def get_database_connection_string(self) -> str:
        """Get PostgreSQL connection string from .env file only.

        Configuration is read exclusively from .env file to ensure single source
        of truth.
        Priority order:
        1) WDH_DATABASE__URI (canonical, from .env)
        2) WDH_DATABASE_URI (alternate, from .env)
        3) Construct from individual WDH_DATABASE_* components (from .env)

        Automatically corrects 'postgres://' scheme to 'postgresql://' for
        SQLAlchemy compatibility.
        """
        env_uri = os.getenv("WDH_DATABASE__URI") or os.getenv("WDH_DATABASE_URI")

        final_uri = None
        if env_uri:
            final_uri = env_uri
        elif self.database_uri:
            final_uri = self.database_uri
        else:
            final_uri = self.database.get_connection_string()

        # Fix for SQLAlchemy compatibility (postgres:// is deprecated/unsupported in newer versions)
        if final_uri and final_uri.startswith("postgres://"):
            final_uri = final_uri.replace("postgres://", "postgresql://", 1)

        return final_uri

    @model_validator(mode="before")
    @classmethod
    def _inject_database_uri(cls, values: dict[str, object]) -> dict[str, object]:
        """
        Ensure database_uri honors both environment and .env (double-underscore) keys.

        Priority:
        1) WDH_DATABASE__URI environment variable
        2) WDH_DATABASE_URI environment variable
        3) .env file entries for either name (if not already set)
        """
        env_uri = os.getenv("WDH_DATABASE__URI") or os.getenv("WDH_DATABASE_URI")

        if (
            not env_uri
            and isinstance(SETTINGS_ENV_FILE, Path)
            and SETTINGS_ENV_FILE.exists()
        ):
            for line in SETTINGS_ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("WDH_DATABASE__URI="):
                    env_uri = line.split("=", 1)[1].strip()
                    break
                if line.startswith("WDH_DATABASE_URI="):
                    env_uri = line.split("=", 1)[1].strip()
                    break

        if env_uri and "database_uri" not in values:
            values["database_uri"] = env_uri

        return values

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
            ValueError: If ENVIRONMENT is 'prod' and database URL is not PostgreSQL
        """
        # Get database URL from .env file configuration
        db_url = self.get_database_connection_string()

        if self.ENVIRONMENT == "prod" and not db_url.startswith("postgresql://"):
            db_url_preview = db_url[:20]
            raise ValueError(
                "Production environment requires PostgreSQL database. "
                f"Database URL must start with 'postgresql://', "
                f"got: {db_url_preview}..."
            )

        return self

    @model_validator(mode="after")
    def load_and_validate_data_sources(self) -> "Settings":
        """
        Load and validate Epic 3 data sources configuration at startup.

        Story 3.0: Fail-fast validation - config errors prevent startup.

        Returns:
            The validated Settings instance with loaded data_sources

        Raises:
            DataSourcesValidationError: If configuration file is missing or invalid
        """
        config_path = Path(self.data_sources_config_v2)

        # Check if config file exists
        if not config_path.exists():
            error_msg = (
                f"Epic 3 data sources configuration file not found: {config_path}. "
                "Create config/data_sources.yml with domain configurations."
            )
            logger.error(
                "configuration.file_not_found",
                config_path=str(config_path),
                error=error_msg,
            )
            raise DataSourcesValidationError(error_msg)

        # Load YAML file
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            error_msg = f"Invalid YAML in configuration file: {e}"
            logger.error(
                "configuration.yaml_parse_error",
                config_path=str(config_path),
                error=str(e),
            )
            raise DataSourcesValidationError(error_msg)
        except Exception as e:
            error_msg = f"Failed to load configuration file: {e}"
            logger.error(
                "configuration.load_error",
                config_path=str(config_path),
                error=str(e),
            )
            raise DataSourcesValidationError(error_msg)

        # Validate using Pydantic schema
        try:
            self.data_sources = DataSourceConfigV2(**raw_config)
            logger.info(
                "configuration.validated",
                schema_version=self.data_sources.schema_version,
                domain_count=len(self.data_sources.domains),
                domains=list(self.data_sources.domains.keys()),
                config_path=str(config_path),
            )
        except Exception as e:
            error_msg = f"Configuration validation failed: {e}"
            logger.error(
                "configuration.validation_failed",
                config_path=str(config_path),
                error=str(e),
            )
            raise DataSourcesValidationError(error_msg)

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
