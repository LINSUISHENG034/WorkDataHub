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
from ..domain.annuity_performance.service import process as process_annuity
from ..domain.reference_backfill.service import derive_plan_candidates, derive_portfolio_candidates
from ..domain.sample_trustee_performance.service import process
from ..io.connectors.file_connector import DataSourceConnector
from ..io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    fill_null_only,
    insert_missing,
    load,
)
from ..io.readers.excel_reader import read_excel_rows

logger = logging.getLogger(__name__)

# psycopg2 lazy import holder to satisfy both patching styles in tests:
# 1) patch("src.work_data_hub.orchestration.ops.psycopg2") expects a module attribute here
# 2) patch builtins.__import__ expects a dynamic import path at runtime
_PSYCOPG2_NOT_LOADED = object()
psycopg2 = _PSYCOPG2_NOT_LOADED  # type: ignore


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
    # Optional: Validate data_sources.yml for fail-fast behavior
    try:
        from ..config.schema import DataSourcesValidationError, validate_data_sources_config

        validate_data_sources_config()
    except DataSourcesValidationError as e:
        logger.error(f"data_sources.yml validation failed: {e}")
        raise
    except Exception as e:
        logger.debug(f"Optional data_sources validation skipped: {e}")

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
def process_sample_trustee_performance_op(
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
        # mode="json" ensures date/datetime/Decimal become JSON friendly types
        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in processed_models
        ]

        context.log.info(
            f"Domain processing completed - source: {file_path}, "
            f"input_rows: {len(excel_rows)}, output_records: {len(result_dicts)}, "
            f"domain: sample_trustee_performance"
        )

        return result_dicts

    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise


@op
def process_annuity_performance_op(
    context: OpExecutionContext, excel_rows: List[Dict[str, Any]], file_paths: List[str]
) -> List[Dict[str, Any]]:
    """
    Process annuity performance data and return validated records as dicts.

    Handles Chinese "规模明细" Excel data with column projection to prevent
    SQL column mismatch errors.

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
        # Process using annuity performance domain service with column projection
        processed_models = process_annuity(excel_rows, data_source=file_path)

        # Convert Pydantic models to JSON-serializable dicts
        # mode="json" ensures date/datetime/Decimal become JSON friendly types
        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in processed_models
        ]

        context.log.info(
            f"Domain processing completed - source: {file_path}, "
            f"input_rows: {len(excel_rows)}, output_records: {len(result_dicts)}, "
            f"domain: annuity_performance"
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
def read_and_process_sample_trustee_files_op(
    context: OpExecutionContext, config: ReadProcessConfig, file_paths: List[str]
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

            # JSON-serializable accumulation (use mode="json" for friendly types)
            processed_dicts = [
                model.model_dump(mode="json", by_alias=True, exclude_none=True) for model in models
            ]
            all_processed.extend(processed_dicts)

            # Structured logging like existing ops
            context.log.info(
                f"Processed {file_path}: {len(rows)} rows -> {len(processed_dicts)} records"
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

    table: str = "sample_trustee_performance"
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


class BackfillRefsConfig(Config):
    """Configuration for reference backfill operation."""

    targets: List[str] = []  # Empty list means no backfill
    mode: str = "insert_missing"  # or "fill_null_only"
    plan_only: bool = True
    chunk_size: int = 1000

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, v: List[str]) -> List[str]:
        """Validate backfill targets are supported."""
        if not v:  # Allow empty list to disable backfill
            return v
        valid = ["plans", "portfolios", "all"]
        for target in v:
            if target not in valid:
                raise ValueError(f"Invalid target: {target}. Valid: {valid}")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate backfill mode is supported."""
        valid_modes = ["insert_missing", "fill_null_only"]
        if v not in valid_modes:
            raise ValueError(f"Mode '{v}' not supported. Valid: {valid_modes}")
        return v


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
    conn = None
    try:
        if not config.plan_only:
            # Lazy import psycopg2 into module-global for test compatibility
            global psycopg2  # type: ignore
            if psycopg2 is None:  # type: ignore
                # Explicitly treated as unavailable (tests may patch to None)
                raise DataWarehouseLoaderError("psycopg2 not available for database operations")
            if psycopg2 is _PSYCOPG2_NOT_LOADED:  # type: ignore
                try:
                    import psycopg2 as _psycopg2  # type: ignore
                except ImportError:
                    raise DataWarehouseLoaderError("psycopg2 not available for database operations")
                psycopg2 = _psycopg2  # type: ignore

            settings = get_settings()

            # Primary DSN retrieval with fallback for test compatibility
            dsn = None
            # Primary: consolidated accessor
            if hasattr(settings, "get_database_connection_string"):
                try:
                    dsn = settings.get_database_connection_string()
                except Exception:
                    dsn = None
            # Fallback: compatibility wrapper
            if not isinstance(dsn, str) and hasattr(settings, "database"):
                try:
                    dsn = settings.database.get_connection_string()  # type: ignore[attr-defined]
                except Exception:
                    pass
            if not isinstance(dsn, str) or not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            context.log.info(f"Connecting to database for execution (table: {config.table})")

            # CRITICAL: Only catch psycopg2.connect failures
            try:
                conn = psycopg2.connect(dsn)  # type: ignore  # Bare connection, no context manager
            except Exception as e:
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. Check WDH_DATABASE__* environment variables."
                ) from e

            # Call loader - it handles transactions with 'with conn:'
            result = load(
                table=config.table,
                rows=processed_rows,
                mode=config.mode,
                pk=config.pk,
                conn=conn,
            )
        else:
            # Plan-only: no connection created
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
    finally:
        # CRITICAL: Clean up bare connection in finally
        if conn is not None:
            conn.close()


@op
def derive_plan_refs_op(
    context: OpExecutionContext,
    processed_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Derive plan reference candidates from processed fact data.

    Args:
        context: Dagster execution context
        processed_rows: Processed annuity performance fact data

    Returns:
        List of plan candidate dictionaries ready for backfill
    """
    try:
        candidates = derive_plan_candidates(processed_rows)

        context.log.info(
            "Plan candidate derivation completed",
            extra={
                "input_rows": len(processed_rows),
                "unique_plans": len(candidates),
                "domain": "annuity_performance",
            },
        )

        return candidates

    except Exception as e:
        context.log.error(f"Plan candidate derivation failed: {e}")
        raise


@op
def derive_portfolio_refs_op(
    context: OpExecutionContext,
    processed_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Derive portfolio reference candidates from processed fact data.

    Args:
        context: Dagster execution context
        processed_rows: Processed annuity performance fact data

    Returns:
        List of portfolio candidate dictionaries ready for backfill
    """
    try:
        candidates = derive_portfolio_candidates(processed_rows)

        context.log.info(
            "Portfolio candidate derivation completed",
            extra={
                "input_rows": len(processed_rows),
                "unique_portfolios": len(candidates),
                "domain": "annuity_performance",
            },
        )

        return candidates

    except Exception as e:
        context.log.error(f"Portfolio candidate derivation failed: {e}")
        raise


@op
def backfill_refs_op(
    context: OpExecutionContext,
    config: BackfillRefsConfig,
    plan_candidates: List[Dict[str, Any]],
    portfolio_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute reference backfill operations for plans and/or portfolios.

    Args:
        context: Dagster execution context
        config: Backfill configuration
        plan_candidates: Plan candidate dictionaries
        portfolio_candidates: Portfolio candidate dictionaries

    Returns:
        Dictionary with backfill execution metadata
    """
    conn = None
    try:
        # Mirror load_op connection handling pattern
        if not config.plan_only:
            global psycopg2  # type: ignore
            if psycopg2 is None:  # type: ignore
                raise DataWarehouseLoaderError("psycopg2 not available for database operations")
            if psycopg2 is _PSYCOPG2_NOT_LOADED:  # type: ignore
                try:
                    import psycopg2 as _psycopg2  # type: ignore
                except ImportError:
                    raise DataWarehouseLoaderError("psycopg2 not available for database operations")
                psycopg2 = _psycopg2  # type: ignore

            settings = get_settings()

            # Primary DSN retrieval with fallback for test compatibility
            dsn = None
            if hasattr(settings, "get_database_connection_string"):
                try:
                    dsn = settings.get_database_connection_string()
                except Exception:
                    dsn = None
            if not isinstance(dsn, str) and hasattr(settings, "database"):
                try:
                    dsn = settings.database.get_connection_string()  # type: ignore[attr-defined]
                except Exception:
                    pass
            if not isinstance(dsn, str) or not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            context.log.info("Connecting to database for reference backfill execution")

            try:
                conn = psycopg2.connect(dsn)  # type: ignore
            except Exception as e:
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. Check WDH_DATABASE__* environment variables."
                ) from e

        result: Dict[str, Any] = {"operations": [], "plan_only": config.plan_only}

        # Early return if no backfill targets specified
        if not config.targets:
            context.log.info("Reference backfill skipped - no targets specified")
            return result

        # Execute backfill for plans
        if ("plans" in config.targets or "all" in config.targets) and plan_candidates:
            if config.mode == "insert_missing":
                plan_result = insert_missing(
                    table="年金计划",
                    key_cols=["年金计划号"],
                    rows=plan_candidates,
                    conn=conn,
                    chunk_size=config.chunk_size,
                )
            elif config.mode == "fill_null_only":
                plan_result = fill_null_only(
                    table="年金计划",
                    key_cols=["年金计划号"],
                    rows=plan_candidates,
                    updatable_cols=["计划全称", "计划类型", "客户名称", "company_id"],
                    conn=conn,
                )
            else:
                raise DataWarehouseLoaderError(f"Unsupported backfill mode: {config.mode}")

            result["operations"].append({"table": "年金计划", **plan_result})

        # Execute backfill for portfolios
        if ("portfolios" in config.targets or "all" in config.targets) and portfolio_candidates:
            if config.mode == "insert_missing":
                portfolio_result = insert_missing(
                    table="组合计划",
                    key_cols=["组合代码"],
                    rows=portfolio_candidates,
                    conn=conn,
                    chunk_size=config.chunk_size,
                )
            elif config.mode == "fill_null_only":
                portfolio_result = fill_null_only(
                    table="组合计划",
                    key_cols=["组合代码"],
                    rows=portfolio_candidates,
                    updatable_cols=["组合名称", "组合类型", "运作开始日"],
                    conn=conn,
                )
            else:
                raise DataWarehouseLoaderError(f"Unsupported backfill mode: {config.mode}")

            result["operations"].append({"table": "组合计划", **portfolio_result})

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            f"Reference backfill completed ({mode_text})",
            extra={
                "targets": config.targets,
                "mode": config.mode,
                "operations": len(result["operations"]),
                "plan_candidates": len(plan_candidates),
                "portfolio_candidates": len(portfolio_candidates),
            },
        )

        return result

    except Exception as e:
        context.log.error(f"Reference backfill failed: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()
