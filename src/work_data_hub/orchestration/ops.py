"""
Dagster ops for WorkDataHub ETL orchestration.

This module provides thin wrappers around existing WorkDataHub components as Dagster ops,
enabling structured orchestration with configuration validation, structured logging,
and proper error handling.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dagster import Config, OpExecutionContext, op
from pydantic import field_validator, model_validator

from ..config.settings import get_settings
from ..domain.trustee_performance.service import process
from ..io.connectors.file_connector import DataSourceConnector
from ..io.loader.warehouse_loader import DataWarehouseLoaderError, load
from ..io.readers.excel_reader import read_excel_rows

logger = logging.getLogger(__name__)


def _load_valid_domains() -> List[str]:
    """
    Load valid domain names from data_sources.yml configuration.

    Returns:
        List of valid domain names sorted alphabetically

    Notes:
        - Returns fallback ["trustee_performance"] if config cannot be loaded
        - Logs warnings for missing config or empty domains
        - Handles exceptions gracefully to prevent complete failure
    """
    try:
        settings = get_settings()
        config_path = Path(settings.data_sources_config)

        if not config_path.exists():
            logger.warning(f"Data sources config not found: {config_path}")
            return ["trustee_performance"]  # Fallback to current default

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        domains = data.get("domains") or {}
        valid_domains = sorted(domains.keys())

        if not valid_domains:
            logger.warning("No domains found in configuration, using default")
            return ["trustee_performance"]

        logger.debug(f"Loaded {len(valid_domains)} valid domains: {valid_domains}")
        return valid_domains

    except Exception as e:
        logger.error(f"Failed to load domains from configuration: {e}")
        # Fallback to prevent complete failure
        return ["trustee_performance"]


class DiscoverFilesConfig(Config):
    """Configuration for file discovery operation."""

    domain: str = "trustee_performance"

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain exists in data_sources.yml configuration."""
        valid_domains = _load_valid_domains()
        if v not in valid_domains:
            raise ValueError(f"Domain '{v}' not supported. Valid: {valid_domains}")
        return v


@op
def discover_files_op(context: OpExecutionContext, config: DiscoverFilesConfig) -> List[str]:
    """
    Discover files for specified domain, return file paths as strings.

    Args:
        context: Dagster execution context
        config: Configuration with domain parameter

    Returns:
        List of file paths (JSON-serializable strings)
    """
    settings = get_settings()
    connector = DataSourceConnector(settings.data_sources_config)

    try:
        discovered = connector.discover(config.domain)

        # Enhanced logging with metadata
        settings = get_settings()
        context.log.info(
            f"File discovery completed - domain: {config.domain}, "
            f"found: {len(discovered)} files, "
            f"config: {settings.data_sources_config}"
        )

        # CRITICAL: Return JSON-serializable paths, not DiscoveredFile objects
        return [file.path for file in discovered]

    except Exception as e:
        context.log.error(f"File discovery failed for domain '{config.domain}': {e}")
        raise


class ReadExcelConfig(Config):
    """Configuration for Excel reading operation."""

    sheet: int = 0

    @field_validator("sheet")
    @classmethod
    def validate_sheet(cls, v: int) -> int:
        """Validate sheet index is non-negative."""
        if v < 0:
            raise ValueError("Sheet index must be non-negative")
        return v


@op
def read_excel_op(
    context: OpExecutionContext, config: ReadExcelConfig, file_paths: List[str]
) -> List[Dict[str, Any]]:
    """
    Read Excel file from first discovered path and return rows as list of dictionaries.

    Args:
        context: Dagster execution context
        config: Configuration with sheet parameter
        file_paths: List of discovered file paths (uses first one for MVP)

    Returns:
        List of row dictionaries (JSON-serializable)
    """
    if not file_paths:
        context.log.warning("No file paths provided to read_excel_op")
        return []

    # For MVP: process first file only
    file_path = file_paths[0]

    try:
        rows = read_excel_rows(file_path, sheet=config.sheet)

        context.log.info(
            f"Excel reading completed - file: {file_path}, "
            f"sheet: {config.sheet}, rows: {len(rows)}, "
            f"columns: {list(rows[0].keys()) if rows else []}"
        )

        return rows

    except Exception as e:
        context.log.error(f"Excel reading failed for '{file_path}': {e}")
        raise


@op
def process_trustee_performance_op(
    context: OpExecutionContext, excel_rows: List[Dict[str, Any]], file_paths: List[str]
) -> List[Dict[str, Any]]:
    """
    Process trustee performance data and return validated records as dicts.

    Args:
        context: Dagster execution context
        excel_rows: Raw Excel row data
        file_paths: List of file paths (uses first one for data_source metadata)

    Returns:
        List of processed record dictionaries (JSON-serializable)
    """
    # Use first file path for data_source metadata
    file_path = file_paths[0] if file_paths else "unknown"

    try:
        # Process using existing domain service
        processed_models = process(excel_rows, data_source=file_path)

        # Convert Pydantic models to JSON-serializable dicts
        result_dicts = [model.model_dump() for model in processed_models]

        context.log.info(
            f"Domain processing completed - source: {file_path}, "
            f"input_rows: {len(excel_rows)}, output_records: {len(result_dicts)}, "
            f"domain: trustee_performance"
        )

        return result_dicts

    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise


class ReadProcessConfig(Config):
    """Configuration for reading and processing multiple trustee files."""

    sheet: int = 0
    max_files: int = 1

    @field_validator("sheet")
    @classmethod
    def validate_sheet(cls, v: int) -> int:
        """Validate sheet index is non-negative."""
        if v < 0:
            raise ValueError("Sheet index must be non-negative")
        return v

    @field_validator("max_files")
    @classmethod
    def validate_max_files(cls, v: int) -> int:
        """Validate max_files is positive and reasonable."""
        if v < 1:
            raise ValueError("max_files must be at least 1")
        if v > 20:  # Reasonable upper bound
            raise ValueError("max_files cannot exceed 20")
        return v


@op
def read_and_process_trustee_files_op(
    context: OpExecutionContext,
    config: ReadProcessConfig,
    file_paths: List[str]
) -> List[Dict]:
    """
    Process multiple trustee files and return accumulated results.

    Args:
        context: Dagster execution context
        config: Configuration with sheet and max_files parameters
        file_paths: List of discovered file paths

    Returns:
        List of processed record dictionaries (JSON-serializable)
    """
    # Limit files like existing MVP approach
    paths_to_process = (file_paths or [])[: min(len(file_paths), config.max_files)]
    all_processed: List[Dict] = []

    for file_path in paths_to_process:
        try:
            # Follow existing read_excel_op approach
            rows = read_excel_rows(file_path, sheet=config.sheet)

            # Follow existing process_trustee_performance_op approach
            models = process(rows, data_source=file_path)

            # JSON-serializable accumulation
            processed_dicts = [model.model_dump() for model in models]
            all_processed.extend(processed_dicts)

            # Structured logging like existing ops
            context.log.info(
                f"Processed {file_path}: {len(rows)} rows -> "
                f"{len(processed_dicts)} records"
            )

        except Exception as e:
            context.log.error(f"Failed to process file {file_path}: {e}")
            raise

    context.log.info(
        f"Multi-file processing completed: {len(paths_to_process)} files, "
        f"{len(all_processed)} total records"
    )
    return all_processed


class LoadConfig(Config):
    """Configuration for data loading operation."""

    table: str = "trustee_performance"
    mode: str = "delete_insert"
    pk: List[str] = ["report_date", "plan_code", "company_code"]
    plan_only: bool = True

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate load mode is supported."""
        valid_modes = ["delete_insert", "append"]
        if v not in valid_modes:
            raise ValueError(f"Mode '{v}' not supported. Valid: {valid_modes}")
        return v

    @model_validator(mode="after")
    def validate_delete_insert_requirements(self) -> "LoadConfig":
        """Ensure delete_insert mode has primary key defined."""
        if self.mode == "delete_insert" and not self.pk:
            raise ValueError("delete_insert mode requires primary key columns")
        return self


@op
def load_op(
    context: OpExecutionContext,
    config: LoadConfig,
    processed_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Load processed data to database or return execution plan.

    Args:
        context: Dagster execution context
        config: Load configuration
        processed_rows: Processed data rows to load

    Returns:
        Dictionary with execution metadata or SQL plans
    """
    try:
        conn = None
        if not config.plan_only:
            try:
                import psycopg2
                settings = get_settings()
                dsn = settings.get_database_connection_string()

                context.log.info(f"Connecting to database for execution (table: {config.table})")

                # Use context manager for automatic connection cleanup
                with psycopg2.connect(dsn) as conn:
                    result = load(
                        table=config.table,
                        rows=processed_rows,
                        mode=config.mode,
                        pk=config.pk,
                        conn=conn,
                    )

            except ImportError as e:
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for database execution. "
                    "Install with: uv sync"
                ) from e
            except Exception as e:
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. "
                    "Check WDH_DATABASE__* environment variables."
                ) from e
        else:
            # Plan-only path unchanged
            result = load(
                table=config.table,
                rows=processed_rows,
                mode=config.mode,
                pk=config.pk,
                conn=None,
            )

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            f"Load operation completed ({mode_text}) - "
            f"table: {config.table}, mode: {config.mode}, "
            f"deleted: {result.get('deleted', 0)}, inserted: {result.get('inserted', 0)}, "
            f"batches: {result.get('batches', 0)}"
        )

        return result

    except Exception as e:
        context.log.error(f"Load operation failed: {e}")
        raise
