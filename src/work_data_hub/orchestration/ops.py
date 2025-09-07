"""
Dagster ops for WorkDataHub ETL orchestration.

This module provides thin wrappers around existing WorkDataHub components as Dagster ops,
enabling structured orchestration with configuration validation, structured logging,
and proper error handling.
"""

import logging
from typing import Any, Dict, List

from dagster import Config, OpExecutionContext, op
from pydantic import field_validator, model_validator

from ..config.settings import get_settings
from ..domain.trustee_performance.service import process
from ..io.connectors.file_connector import DataSourceConnector
from ..io.loader.warehouse_loader import load
from ..io.readers.excel_reader import read_excel_rows

logger = logging.getLogger(__name__)


class DiscoverFilesConfig(Config):
    """Configuration for file discovery operation."""

    domain: str = "trustee_performance"

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain exists in configuration."""
        valid_domains = ["trustee_performance"]  # Could load from settings
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

        # Simple logging 
        context.log.info(
            f"File discovery completed for domain '{config.domain}' - found {len(discovered)} files"
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
            f"Excel reading completed - {len(rows)} rows from {file_path}"
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
            f"Domain processing completed - {len(result_dicts)} records from {file_path}"
        )

        return result_dicts

    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise


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
        # Connection is None for plan_only mode (testing)
        conn = None if config.plan_only else None  # TODO: get DB connection when needed

        result = load(
            table=config.table,
            rows=processed_rows,
            mode=config.mode,
            pk=config.pk,
            conn=conn,
        )

        # Simple logging
        mode_text = "PLAN-ONLY" if config.plan_only else "EXECUTED"
        context.log.info(
            f"Load operation completed ({mode_text}) - {result.get('inserted', 0)} rows to {config.table}"
        )

        return result

    except Exception as e:
        context.log.error(f"Load operation failed: {e}")
        raise
