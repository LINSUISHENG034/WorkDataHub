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
from ..domain.annuity_performance.service import process_with_enrichment
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

    # Accept sheet index (int) or sheet name (str)
    sheet: Any = 0

    @field_validator("sheet")
    @classmethod
    def validate_sheet(cls, v: Any) -> Any:
        """Validate sheet index/name."""
        # Allow string sheet names as-is
        if isinstance(v, str) and v.strip():
            return v.strip()
        # Allow non-negative integers
        try:
            iv = int(v)
        except Exception:
            raise ValueError("Sheet must be a non-negative integer or a non-empty string name")
        if iv < 0:
            raise ValueError("Sheet index must be non-negative")
        return iv


class ProcessingConfig(Config):
    """Configuration for processing operations with optional enrichment."""

    enrichment_enabled: bool = False
    enrichment_sync_budget: int = 0
    export_unknown_names: bool = True
    plan_only: bool = True

    @field_validator("enrichment_sync_budget")
    @classmethod
    def validate_sync_budget(cls, v: int) -> int:
        """Validate sync budget is non-negative."""
        if v < 0:
            raise ValueError("Sync budget must be non-negative")
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
    context: OpExecutionContext,
    config: ProcessingConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str]
) -> List[Dict[str, Any]]:
    """
    Process annuity performance data with optional enrichment and return validated records as dicts.

    Handles Chinese "规模明细" Excel data with column projection to prevent
    SQL column mismatch errors. When enrichment is enabled, performs company ID
    resolution using internal mappings, EQC lookups, and async queue processing.

    Args:
        context: Dagster execution context
        config: Processing configuration including enrichment and plan_only settings
        excel_rows: Raw Excel row data
        file_paths: List of file paths (uses first one for data_source metadata)

    Returns:
        List of processed record dictionaries (JSON-serializable)
    """
    # Use first file path for data_source metadata
    file_path = file_paths[0] if file_paths else "unknown"

    # Conditional enrichment service setup
    enrichment_service = None
    conn = None

    try:
        # GUARD: Only setup enrichment in execute mode
        if not config.plan_only and config.enrichment_enabled:
            # Import enrichment components (lazy import to avoid circular dependencies)
            from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
            from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
            from work_data_hub.io.connectors.eqc_client import EQCClient
            from work_data_hub.io.loader.company_enrichment_loader import CompanyEnrichmentLoader

            # Lazy import psycopg2 for database connection (following load_op pattern)
            global psycopg2  # type: ignore
            if psycopg2 is _PSYCOPG2_NOT_LOADED:  # type: ignore
                try:
                    import psycopg2 as _psycopg2  # type: ignore
                    psycopg2 = _psycopg2  # type: ignore
                except ImportError:
                    raise DataWarehouseLoaderError("psycopg2 not available for enrichment database operations")

            # Create database connection only in execute mode
            settings = get_settings()
            dsn = settings.get_database_connection_string()
            conn = psycopg2.connect(dsn)  # type: ignore

            # Setup enrichment service components with connection
            loader = CompanyEnrichmentLoader(conn)
            queue = LookupQueue(conn)
            eqc_client = EQCClient()  # Uses settings for auth

            enrichment_service = CompanyEnrichmentService(
                loader=loader,
                queue=queue,
                eqc_client=eqc_client,
                sync_lookup_budget=config.enrichment_sync_budget
            )

            context.log.info(
                "Enrichment service setup completed",
                extra={
                    "sync_budget": config.enrichment_sync_budget,
                    "export_unknowns": config.export_unknown_names
                }
            )

        # Call service with enrichment metadata support
        result = process_with_enrichment(
            excel_rows,
            data_source=file_path,
            enrichment_service=enrichment_service,
            sync_lookup_budget=config.enrichment_sync_budget,
            export_unknown_names=config.export_unknown_names,
        )

        # Serialize only the records for downstream compatibility
        result_dicts = [
            record.model_dump(mode="json", by_alias=True, exclude_none=True)
            for record in result.records
        ]

        # Log enrichment statistics if enrichment was used
        if enrichment_service and result.enrichment_stats.total_records > 0:
            context.log.info(
                "Enrichment completed",
                extra={
                    "total": result.enrichment_stats.total_records,
                    "internal_hits": result.enrichment_stats.success_internal,
                    "external_hits": result.enrichment_stats.success_external,
                    "pending": result.enrichment_stats.pending_lookup,
                    "temp_assigned": result.enrichment_stats.temp_assigned,
                    "failed": result.enrichment_stats.failed,
                    "budget_used": result.enrichment_stats.sync_budget_used,
                    "csv_exported": bool(result.unknown_names_csv),
                }
            )

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            f"Domain processing completed ({mode_text}) - source: {file_path}, "
            f"input_rows: {len(excel_rows)}, output_records: {len(result_dicts)}, "
            f"domain: annuity_performance, enrichment_enabled: {config.enrichment_enabled}"
        )

        return result_dicts

    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise
    finally:
        # CRITICAL: Always cleanup connection
        if conn is not None:
            conn.close()


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
    skip: bool = False  # NEW: skip flag for early return

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
    # NEW: Check skip flag and early return
    if config.skip:
        context.log.info("Fact loading skipped due to --skip-facts flag")
        return {
            "table": config.table,
            "mode": config.mode,
            "skipped": True,
            "inserted": 0,
            "deleted": 0,
            "batches": 0,
        }

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

        # Read refs configuration from data_sources.yml
        settings = get_settings()
        refs_config = {}
        try:
            with open(settings.data_sources_config, "r", encoding="utf-8") as f:
                data_sources = yaml.safe_load(f)

            # Extract refs for current domain (annuity_performance)
            domain = "annuity_performance"  # TODO: could be passed from discover_files_op context
            refs_config = data_sources.get("domains", {}).get(domain, {}).get("refs", {})
        except Exception as e:
            context.log.warning(f"Could not load refs config: {e}, using defaults")

        # Get plans configuration with fallbacks
        plans_config = refs_config.get("plans", {})
        plans_schema = plans_config.get("schema")  # None if not specified
        plans_table = plans_config.get("table", "年金计划")  # fallback to hardcoded
        plans_key = plans_config.get("key", ["年金计划号"])  # fallback
        plans_updatable = plans_config.get(
            "updatable", ["计划全称", "计划类型", "客户名称", "company_id"]
        )

        # Get portfolios configuration with fallbacks
        portfolios_config = refs_config.get("portfolios", {})
        portfolios_schema = portfolios_config.get("schema")  # None if not specified
        portfolios_table = portfolios_config.get("table", "组合计划")  # fallback to hardcoded
        portfolios_key = portfolios_config.get("key", ["组合代码"])  # fallback
        portfolios_updatable = portfolios_config.get(
            "updatable", ["组合名称", "组合类型", "运作开始日"]
        )

        # Execute backfill for plans
        if ("plans" in config.targets or "all" in config.targets) and plan_candidates:
            try:
                # Begin a savepoint for plans operation
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SAVEPOINT plans_backfill")

                if config.mode == "insert_missing":
                    plan_result = insert_missing(
                        table=plans_table,
                        key_cols=plans_key,
                        rows=plan_candidates,
                        conn=conn,
                        chunk_size=config.chunk_size,
                        schema=plans_schema,  # NEW: pass schema
                    )
                elif config.mode == "fill_null_only":
                    plan_result = fill_null_only(
                        table=plans_table,
                        key_cols=plans_key,
                        rows=plan_candidates,
                        updatable_cols=plans_updatable,
                        conn=conn,
                        schema=plans_schema,  # NEW: pass schema
                    )
                else:
                    raise DataWarehouseLoaderError(f"Unsupported backfill mode: {config.mode}")

                # Release savepoint on success
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("RELEASE SAVEPOINT plans_backfill")

                result["operations"].append({"table": plans_table, **plan_result})
                context.log.info(f"Plans backfill completed successfully: {plans_table}")

            except Exception as plans_error:
                context.log.warning(f"Plans backfill failed: {plans_error}")
                # Rollback to savepoint on failure
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("ROLLBACK TO SAVEPOINT plans_backfill")
                            cursor.execute("RELEASE SAVEPOINT plans_backfill")
                    except Exception:
                        pass

                # Add error result but continue with portfolios
                result["operations"].append({
                    "table": plans_table,
                    "error": str(plans_error),
                    "inserted": 0,
                    "batches": 0
                })

        # Execute backfill for portfolios
        if ("portfolios" in config.targets or "all" in config.targets) and portfolio_candidates:
            try:
                # Begin a savepoint for portfolios operation
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("SAVEPOINT portfolios_backfill")

                if config.mode == "insert_missing":
                    portfolio_result = insert_missing(
                        table=portfolios_table,
                        key_cols=portfolios_key,
                        rows=portfolio_candidates,
                        conn=conn,
                        chunk_size=config.chunk_size,
                        schema=portfolios_schema,  # NEW: pass schema
                    )
                elif config.mode == "fill_null_only":
                    portfolio_result = fill_null_only(
                        table=portfolios_table,
                        key_cols=portfolios_key,
                        rows=portfolio_candidates,
                        updatable_cols=portfolios_updatable,
                        conn=conn,
                        schema=portfolios_schema,  # NEW: pass schema
                    )
                else:
                    raise DataWarehouseLoaderError(f"Unsupported backfill mode: {config.mode}")

                # Release savepoint on success
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("RELEASE SAVEPOINT portfolios_backfill")

                result["operations"].append({"table": portfolios_table, **portfolio_result})
                context.log.info(f"Portfolios backfill completed successfully: {portfolios_table}")

            except Exception as portfolios_error:
                context.log.warning(f"Portfolios backfill failed: {portfolios_error}")
                # Rollback to savepoint on failure
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("ROLLBACK TO SAVEPOINT portfolios_backfill")
                            cursor.execute("RELEASE SAVEPOINT portfolios_backfill")
                    except Exception:
                        pass

                # Add error result
                result["operations"].append({
                    "table": portfolios_table,
                    "error": str(portfolios_error),
                    "inserted": 0,
                    "batches": 0
                })

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

        # Final commit for successful operations
        if conn and not config.plan_only:
            try:
                conn.commit()
                context.log.info("Reference backfill transaction committed")
            except Exception as final_commit_error:
                context.log.warning(f"Final commit warning: {final_commit_error}")

        return result

    except Exception as e:
        context.log.error(f"Reference backfill failed: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()


@op
def gate_after_backfill(
    context: OpExecutionContext,
    processed_rows: List[Dict[str, Any]],
    backfill_summary: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Dependency gate to ensure backfill completes before fact loading.

    This op simply forwards processed_rows, but establishes an explicit
    dependency on backfill_refs_op so that load_op cannot start before
    reference backfill has finished (important when FK constraints exist).
    """
    ops = backfill_summary.get("operations", []) if isinstance(backfill_summary, dict) else []
    context.log.info(
        f"Backfill completed; gating fact load. operations={len(ops)}"
    )
    return processed_rows


class QueueProcessingConfig(Config):
    """Configuration for company lookup queue processing operation."""

    batch_size: int = 50
    plan_only: bool = True

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """Validate batch size is positive and reasonable."""
        if v < 1:
            raise ValueError("Batch size must be at least 1")
        if v > 500:  # Reasonable upper bound to avoid memory issues
            raise ValueError("Batch size cannot exceed 500")
        return v


@op
def process_company_lookup_queue_op(
    context: OpExecutionContext,
    config: QueueProcessingConfig,
) -> Dict[str, Any]:
    """
    Process pending company lookup requests from the queue using EQC API.

    Dequeues pending requests in batches, performs EQC lookups,
    caches successful results, and updates request status appropriately.
    Designed for scheduled/async execution scenarios.

    Args:
        context: Dagster execution context
        config: Queue processing configuration

    Returns:
        Dictionary with processing statistics
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

            # Import enrichment components (lazy import to avoid circular dependencies)
            from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
            from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
            from work_data_hub.io.connectors.eqc_client import EQCClient
            from work_data_hub.io.loader.company_enrichment_loader import CompanyEnrichmentLoader

            settings = get_settings()

            # Primary DSN retrieval with fallback for test compatibility
            dsn = None
            # Primary: consolidated accessor
            if hasattr(settings, "get_database_connection_string"):
                try:
                    dsn = settings.get_database_connection_string()
                except Exception:
                    dsn = None
            if not isinstance(dsn, str) or not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            context.log.info(
                f"Connecting to database for queue processing "
                f"(batch_size: {config.batch_size})"
            )

            # CRITICAL: Only catch psycopg2.connect failures
            try:
                conn = psycopg2.connect(dsn)  # type: ignore  # Bare connection, no context manager
            except Exception as e:
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. Check WDH_DATABASE__* environment variables."
                ) from e

            # Setup enrichment service components
            loader = CompanyEnrichmentLoader(conn)
            queue = LookupQueue(conn)
            eqc_client = EQCClient()  # Uses settings for auth

            enrichment_service = CompanyEnrichmentService(
                loader=loader,
                queue=queue,
                eqc_client=eqc_client,
                sync_lookup_budget=0  # No sync budget for queue processing
            )

            # Process the queue
            processed_count = enrichment_service.process_lookup_queue(batch_size=config.batch_size)

            # Get final queue status
            queue_status = enrichment_service.get_queue_status()

            result = {
                "processed_count": processed_count,
                "batch_size": config.batch_size,
                "plan_only": config.plan_only,
                "queue_status": queue_status,
            }

        else:
            # Plan-only: simulate queue processing
            context.log.info(
                f"Queue processing plan - batch_size: {config.batch_size} (no database operations)"
            )
            result = {
                "processed_count": 0,
                "batch_size": config.batch_size,
                "plan_only": config.plan_only,
                "queue_status": {"pending": 0, "processing": 0, "done": 0, "failed": 0},
            }

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            f"Queue processing completed ({mode_text}) - "
            f"processed: {result['processed_count']}, "
            f"batch_size: {result['batch_size']}, "
            f"pending: {result['queue_status'].get('pending', 0)}, "
            f"failed: {result['queue_status'].get('failed', 0)}"
        )

        return result

    except Exception as e:
        context.log.error(f"Queue processing operation failed: {e}")
        raise
    finally:
        # CRITICAL: Clean up bare connection in finally
        if conn is not None:
            conn.close()
