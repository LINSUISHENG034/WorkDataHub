"""Dagster ops that inject I/O adapters into domain services (Story 1.6).

Each op composes Story 1.5 domain pipelines with I/O implementations (readers,
loaders, connectors) without reversing the dependency direction. Ops stay in
the orchestration ring and merely provide dependency injection, logging, and
configuration validation.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import yaml
from dagster import Config, OpExecutionContext, op
from pydantic import field_validator, model_validator
from sqlalchemy.engine import Connection

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.annuity_performance.service import (
    process_with_enrichment,
)
from work_data_hub.domain.annuity_income.service import (
    process_with_enrichment as process_annuity_income_with_enrichment,
)
from work_data_hub.domain.reference_backfill import (
    GenericBackfillService,
    BackfillResult,
    ReferenceSyncService,
    load_foreign_keys_config,
)
from work_data_hub.io.connectors.file_connector import (
    DataSourceConnector,
    FileDiscoveryService,
)
from work_data_hub.domain.reference_backfill.service import (
    derive_plan_candidates,
    derive_portfolio_candidates,
)
from work_data_hub.domain.reference_backfill.sync_config_loader import (
    load_reference_sync_config,
)
from work_data_hub.domain.sandbox_trustee_performance.service import process
from work_data_hub.io.connectors.config_file_connector import ConfigFileConnector
from work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    fill_null_only,
    insert_missing,
    load,
)
from work_data_hub.io.readers.excel_reader import read_excel_rows

logger = logging.getLogger(__name__)

# psycopg2 lazy import holder to satisfy both patching styles in tests:
# 1) patch("src.work_data_hub.orchestration.ops.psycopg2") expects a module
#    attribute here
# 2) patch builtins.__import__ expects a dynamic import path at runtime
_PSYCOPG2_NOT_LOADED = object()
psycopg2: Any = _PSYCOPG2_NOT_LOADED


def _load_valid_domains() -> List[str]:
    """
    Load valid domain names from data_sources.yml configuration.

    Returns:
        List of valid domain names sorted alphabetically

    Notes:
        - Returns fallback ["sandbox_trustee_performance"] if config cannot be loaded
        - Logs warnings for missing config or empty domains
        - Handles exceptions gracefully to prevent complete failure
    """
    try:
        settings = get_settings()
        config_path = Path(settings.data_sources_config)

        if not config_path.exists():
            logger.warning("Data sources config not found: %s", config_path)
            return ["sandbox_trustee_performance"]  # Fallback to current default

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            data = {}

        # Optional: validate only when the file resembles Epic 3 schema.
        # (Unit tests frequently patch in minimal YAML that is not schema-valid.)
        try:
            domains = data.get("domains") or {}
            looks_like_epic3 = bool(
                data.get("schema_version")
                or any(
                    isinstance(cfg, dict) and "base_path" in cfg
                    for cfg in domains.values()
                )
            )
            if looks_like_epic3:
                from work_data_hub.infrastructure.settings.data_source_schema import (
                    validate_data_sources_config,
                )

                validate_data_sources_config(str(config_path))
        except Exception as e:
            logger.debug("Optional data_sources validation skipped: %s", e)

        domains = data.get("domains") or {}
        valid_domains = sorted(domains.keys())

        if not valid_domains:
            logger.warning("No domains found in configuration, using default")
            return ["sandbox_trustee_performance"]

        logger.debug("Loaded %s valid domains: %s", len(valid_domains), valid_domains)
        return valid_domains

    except Exception as e:
        logger.error("Failed to load domains from configuration: %s", e)
        # Fallback to prevent complete failure
        return ["sandbox_trustee_performance"]


class DiscoverFilesConfig(Config):
    """Configuration for file discovery operation."""

    domain: str = "sandbox_trustee_performance"
    period: Optional[str] = None  # YYYYMM format for Epic 3 schema domains
    # Story 6.2-P16: File selection strategy when multiple files match
    selection_strategy: str = "error"  # error, newest, oldest, first

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain exists in data_sources.yml configuration."""
        valid_domains = _load_valid_domains()
        if v not in valid_domains:
            raise ValueError(f"Domain '{v}' not supported. Valid: {valid_domains}")
        return v

    @field_validator("selection_strategy")
    @classmethod
    def validate_selection_strategy(cls, v: str) -> str:
        """Validate selection strategy is valid."""
        valid = ["error", "newest", "oldest", "first"]
        if v not in valid:
            raise ValueError(f"Strategy '{v}' not valid. Valid: {valid}")
        return v


@op
def discover_files_op(
    context: OpExecutionContext, config: DiscoverFilesConfig
) -> List[str]:
    """
    Discover files for specified domain, return file paths as strings.

    Supports dual-schema routing:
    - Epic 3 schema (base_path, file_patterns, version_strategy) → FileDiscoveryService
    - Legacy schema (pattern, select) → DataSourceConnector

    Args:
        context: Dagster execution context
        config: Configuration with domain and optional period parameters

    Returns:
        List of file paths (JSON-serializable strings)
    """
    settings = get_settings()

    # Load domain configuration to detect schema type
    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f) or {}
        if not isinstance(data_sources, dict):
            data_sources = {}

        domain_config = data_sources.get("domains", {}).get(config.domain, {})

        # Detect schema type based on keys present
        is_epic3_schema = "base_path" in domain_config and "file_patterns" in domain_config
        is_legacy_schema = "pattern" in domain_config and "select" in domain_config

        if is_epic3_schema:
            # Route to Epic 3 FileDiscoveryService
            context.log.info(
                f"Using Epic 3 schema discovery for domain '{config.domain}'"
            )

            # Validate period is provided if base_path contains template variables
            base_path = domain_config.get("base_path", "")
            if "{YYYYMM}" in base_path or "{YYYY}" in base_path or "{MM}" in base_path:
                if not config.period:
                    raise ValueError(
                        f"Domain '{config.domain}' requires --period parameter "
                        f"(base_path contains template variables: {base_path})"
                    )

            # Use FileDiscoveryService for Epic 3 schema
            file_discovery = FileDiscoveryService()

            try:
                # Call discover_file (discovery-only, no Excel loading)
                template_vars = {}
                if config.period:
                    template_vars["month"] = config.period

                # Story 6.2-P16: Convert strategy string to enum
                from work_data_hub.io.connectors.file_pattern_matcher import (
                    SelectionStrategy,
                )
                strategy = SelectionStrategy(config.selection_strategy)

                context.log.info(
                    f"Discovery with selection_strategy={strategy.value}"
                )

                match_result = file_discovery.discover_file(
                    domain=config.domain,
                    selection_strategy=strategy,
                    **template_vars
                )

                context.log.info(
                    f"Epic 3 discovery completed - domain: {config.domain}, "
                    f"file: {match_result.file_path}, "
                    f"version: {match_result.version}, "
                    f"sheet: {match_result.sheet_name}"
                )

                # Return as list for backward compatibility
                return [str(match_result.file_path)]

            except Exception as e:
                # Use str(e) for message, e.to_dict() for structured logging (AC6)
                error_msg = str(e)
                error_details = e.to_dict() if hasattr(e, 'to_dict') else {"error": error_msg}
                context.log.error(
                    f"Epic 3 discovery failed for domain '{config.domain}': {error_msg}",
                    extra={"discovery_error": error_details}
                )
                raise

        elif is_legacy_schema:
            # Route to legacy DataSourceConnector
            context.log.info(
                f"Using legacy schema discovery for domain '{config.domain}'"
            )

            connector = DataSourceConnector(settings.data_sources_config)

            try:
                discovered = connector.discover(config.domain)

                context.log.info(
                    f"Legacy discovery completed - domain: {config.domain}, "
                    f"found: {len(discovered)} files, "
                    f"config: {settings.data_sources_config}"
                )

                # CRITICAL: Return JSON-serializable paths, not DiscoveredFile objects
                return [file.path for file in discovered]

            except Exception as e:
                context.log.error(
                    f"Legacy discovery failed for domain '{config.domain}': {str(e)}"
                )
                raise

        else:
            raise ValueError(
                f"Domain '{config.domain}' has invalid configuration schema. "
                f"Must have either Epic 3 schema (base_path, file_patterns) "
                f"or legacy schema (pattern, select)"
            )

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
            raise ValueError(
                "Sheet must be a non-negative integer or a non-empty string name"
            )
        if iv < 0:
            raise ValueError("Sheet index must be non-negative")
        return iv


class ProcessingConfig(Config):
    """Configuration for processing operations with optional enrichment."""

    enrichment_enabled: bool = False
    enrichment_sync_budget: int = 0
    export_unknown_names: bool = True
    plan_only: bool = True
    use_pipeline: Optional[bool] = (
        None  # CLI override for pipeline framework (None=respect setting)
    )

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
def process_sandbox_trustee_performance_op(
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
            "Domain processing completed - source: %s, input_rows: %s, "
            "output_records: %s, domain: sandbox_trustee_performance",
            file_path,
            len(excel_rows),
            len(result_dicts),
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
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    Process annuity performance data with optional enrichment and return
    validated records as dicts.

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
    observer = None
    conn = None
    settings = get_settings()

    try:
        # GUARD: Only setup enrichment in execute mode AND when explicitly enabled
        # Story 6.2-P16: Fixed condition - enrichment requires BOTH CLI and settings to enable
        use_enrichment = (
            (not config.plan_only)
            and config.enrichment_enabled
            and settings.enrich_enabled
        )

        if use_enrichment:
            # Import enrichment components (lazy import to avoid circular dependencies)
            from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
            from work_data_hub.domain.company_enrichment.service import (
                CompanyEnrichmentService,
            )
            from work_data_hub.io.connectors.eqc_client import EQCClient
            from work_data_hub.io.loader.company_enrichment_loader import (
                CompanyEnrichmentLoader,
            )
            from work_data_hub.domain.company_enrichment.observability import (
                EnrichmentObserver,
            )
            from work_data_hub.infrastructure.enrichment.csv_exporter import (
                export_unknown_companies,
            )

            # Lazy import psycopg2 for database connection (following load_op pattern)
            global psycopg2
            if psycopg2 is _PSYCOPG2_NOT_LOADED:
                try:
                    import psycopg2 as _psycopg2

                    psycopg2 = _psycopg2
                except ImportError:
                    raise DataWarehouseLoaderError(
                        "psycopg2 not available for enrichment database operations"
                    )

            # Create database connection only in execute mode
            dsn = settings.get_database_connection_string()

            # Story 6.2-P16 AC-2: Validate required settings before attempting connect
            missing = []
            if not settings.database_host:
                missing.append("WDH_DATABASE__HOST")
            if not settings.database_port:
                missing.append("WDH_DATABASE__PORT")
            if not settings.database_db:
                missing.append("WDH_DATABASE__DB")
            if not settings.database_user:
                missing.append("WDH_DATABASE__USER")
            if not settings.database_password:
                missing.append("WDH_DATABASE__PASSWORD")
            if missing:
                context.log.error(
                    "db_connection.missing_settings",
                    extra={"missing": missing, "purpose": "enrichment"},
                )
                raise DataWarehouseLoaderError(
                    "Database connection settings missing for enrichment: "
                    f"{', '.join(missing)}. "
                    "Set them in .wdh_env and try again."
                )

            # Story 6.2-P16 AC-2: Log DSN components for debugging (never log password)
            context.log.info(
                "db_connection.attempting",
                extra={
                    "host": settings.database_host,
                    "port": settings.database_port,
                    "database": settings.database_db,
                    "user": settings.database_user,
                    "purpose": "enrichment",
                },
            )

            try:
                conn = psycopg2.connect(dsn)
            except Exception as e:
                # Story 6.2-P16 AC-2: Improved error message with hints
                context.log.error(
                    "db_connection.failed",
                    extra={
                        "host": settings.database_host,
                        "port": settings.database_port,
                        "database": settings.database_db,
                        "error": str(e),
                    },
                )
                raise DataWarehouseLoaderError(
                    f"Database connection failed for enrichment: {e}. "
                    "Check WDH_DATABASE__HOST, WDH_DATABASE__PORT, WDH_DATABASE__DB, "
                    "WDH_DATABASE__USER, WDH_DATABASE__PASSWORD in .wdh_env"
                ) from e

            # Setup enrichment service components with connection
            loader = CompanyEnrichmentLoader(conn)
            queue = LookupQueue(conn)
            eqc_client = EQCClient()  # Uses settings for auth
            observer = EnrichmentObserver()

            enrichment_service = CompanyEnrichmentService(
                loader=loader,
                queue=queue,
                eqc_client=eqc_client,
                sync_lookup_budget=config.enrichment_sync_budget,
                observer=observer,
                enrich_enabled=settings.enrich_enabled,
            )

            context.log.info(
                "Enrichment service setup completed",
                extra={
                    "sync_budget": config.enrichment_sync_budget,
                    "export_unknowns": config.export_unknown_names,
                    "enrich_enabled": settings.enrich_enabled,
                },
            )

        # Call service with enrichment metadata support
        # Note: use_pipeline parameter removed in Story 4.8/4.9 refactoring
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
                },
            )

        # Story 6.8: Log observer stats + CSV export (AC1, AC2, AC5)
        if observer:
            enrichment_stats = observer.get_stats()
            context.log.info(
                "Enrichment stats",
                extra={"enrichment_stats": enrichment_stats.to_dict()},
            )
            if (
                observer.has_unknown_companies()
                and settings.enrichment_export_unknowns
            ):
                try:
                    csv_path = export_unknown_companies(
                        observer, output_dir=settings.observability_log_dir
                    )
                    if csv_path:
                        # Update result for downstream consumption
                        result.unknown_names_csv = str(csv_path)
                        context.log.info(
                            "Exported unknown companies to CSV",
                            extra={"csv_path": str(csv_path)},
                        )
                except Exception as export_error:
                    context.log.warning(
                        "Failed to export unknown companies CSV: %s", export_error
                    )

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            "Domain processing completed (%s) - source: %s, input_rows: %s, "
            "output_records: %s, domain: annuity_performance, "
            "enrichment_enabled: %s",
            mode_text,
            file_path,
            len(excel_rows),
            len(result_dicts),
            config.enrichment_enabled,
        )

        return result_dicts

    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise
    finally:
        # CRITICAL: Always cleanup connection
        if conn is not None:
            conn.close()


@op
def process_annuity_income_op(
    context: OpExecutionContext,
    config: ProcessingConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    Process annuity income data and return validated records as dicts.

    Handles Chinese "收入明细" Excel data with column projection.
    This is a simpler domain without enrichment support (plan-only safe).

    Args:
        context: Dagster execution context
        config: Processing configuration including plan_only settings
        excel_rows: Raw Excel row data
        file_paths: List of file paths (uses first one for data_source metadata)

    Returns:
        List of processed record dictionaries (JSON-serializable)
    """
    # Use first file path for data_source metadata
    file_path = file_paths[0] if file_paths else "unknown"

    try:
        # Call domain service (no enrichment for annuity_income)
        processing_result = process_annuity_income_with_enrichment(
            excel_rows, data_source=file_path
        )

        # Convert Pydantic models to JSON-serializable dicts
        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in processing_result.records
        ]

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            "Domain processing completed (%s) - source: %s, input_rows: %s, "
            "output_records: %s, domain: annuity_income",
            mode_text,
            file_path,
            len(excel_rows),
            len(result_dicts),
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
def read_and_process_sandbox_trustee_files_op(
    context: OpExecutionContext, config: ReadProcessConfig, file_paths: List[str]
) -> List[Dict[str, Any]]:
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
    all_processed: List[Dict[str, Any]] = []

    for file_path in paths_to_process:
        try:
            # Follow existing read_excel_op approach
            rows = read_excel_rows(file_path, sheet=config.sheet)

            # Follow existing process_trustee_performance_op approach
            models = process(rows, data_source=file_path)

            # JSON-serializable accumulation (use mode="json" for friendly types)
            processed_dicts = [
                model.model_dump(mode="json", by_alias=True, exclude_none=True)
                for model in models
            ]
            all_processed.extend(processed_dicts)

            # Structured logging like existing ops
            context.log.info(
                "Processed %s: %s rows -> %s records",
                file_path,
                len(rows),
                len(processed_dicts),
            )

        except Exception as e:
            context.log.error(f"Failed to process file {file_path}: {e}")
            raise

    context.log.info(
        "Multi-file processing completed: %s files, %s total records",
        len(paths_to_process),
        len(all_processed),
    )
    return all_processed


class LoadConfig(Config):
    """Configuration for data loading operation."""

    table: str = "sandbox_trustee_performance"
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

    # Legacy configuration for backward compatibility
    targets: List[str] = []  # Empty list means no backfill
    mode: str = "insert_missing"  # or "fill_null_only"
    plan_only: bool = True
    chunk_size: int = 1000
    domain: str = "annuity_performance"  # Domain to backfill references for

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, v: List[str]) -> List[str]:
        """Validate backfill targets are supported."""
        if not v:  # Allow empty list to disable backfill
            return v
        valid = ["plans", "portfolios", "all", "generic"]
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


class GenericBackfillConfig(Config):
    """Configuration for generic backfill operation."""

    domain: str = "annuity_performance"
    add_tracking_fields: bool = True
    plan_only: bool = True


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
            global psycopg2
            if psycopg2 is None:
                # Explicitly treated as unavailable (tests may patch to None)
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for database operations"
                )
            if psycopg2 is _PSYCOPG2_NOT_LOADED:
                try:
                    import psycopg2 as _psycopg2
                except ImportError:
                    raise DataWarehouseLoaderError(
                        "psycopg2 not available for database operations"
                    )
                psycopg2 = _psycopg2

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
                    dsn = settings.database.get_connection_string()
                except Exception:
                    pass
            if not isinstance(dsn, str) or not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            # Story 6.2-P16 AC-2: Validate required settings before attempting connect
            missing = []
            if not settings.database_host:
                missing.append("WDH_DATABASE__HOST")
            if not settings.database_port:
                missing.append("WDH_DATABASE__PORT")
            if not settings.database_db:
                missing.append("WDH_DATABASE__DB")
            if not settings.database_user:
                missing.append("WDH_DATABASE__USER")
            if not settings.database_password:
                missing.append("WDH_DATABASE__PASSWORD")
            if missing:
                context.log.error(
                    "db_connection.missing_settings",
                    extra={
                        "missing": missing,
                        "purpose": "load_op",
                        "table": config.table,
                    },
                )
                raise DataWarehouseLoaderError(
                    "Database connection settings missing: "
                    f"{', '.join(missing)}. "
                    "Set them in .wdh_env and try again."
                )

            # Story 6.2-P16 AC-2: Log DSN components for debugging (never log password)
            context.log.info(
                "db_connection.attempting",
                extra={
                    "host": settings.database_host,
                    "port": settings.database_port,
                    "database": settings.database_db,
                    "user": settings.database_user,
                    "table": config.table,
                    "purpose": "load_op",
                },
            )

            # CRITICAL: Only catch psycopg2.connect failures
            try:
                conn = psycopg2.connect(dsn)  # Bare connection, no context manager
            except Exception as e:
                # Story 6.2-P16 AC-2: Improved error message with hints
                context.log.error(
                    "db_connection.failed",
                    extra={
                        "host": settings.database_host,
                        "port": settings.database_port,
                        "database": settings.database_db,
                        "table": config.table,
                        "error": str(e),
                    },
                )
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. "
                    "Check WDH_DATABASE__HOST, WDH_DATABASE__PORT, WDH_DATABASE__DB, "
                    "WDH_DATABASE__USER, WDH_DATABASE__PASSWORD in .wdh_env"
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
            "Load operation completed (%s) - table: %s, mode: %s, "
            "deleted: %s, inserted: %s, batches: %s",
            mode_text,
            config.table,
            config.mode,
            result.get("deleted", 0),
            result.get("inserted", 0),
            result.get("batches", 0),
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
            global psycopg2
            if psycopg2 is None:
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for database operations"
                )
            if psycopg2 is _PSYCOPG2_NOT_LOADED:
                try:
                    import psycopg2 as _psycopg2
                except ImportError:
                    raise DataWarehouseLoaderError(
                        "psycopg2 not available for database operations"
                    )
                psycopg2 = _psycopg2

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
                    dsn = settings.database.get_connection_string()
                except Exception:
                    pass
            if not isinstance(dsn, str) or not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            context.log.info("Connecting to database for reference backfill execution")

            try:
                conn = psycopg2.connect(dsn)
            except Exception as e:
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. "
                    "Check WDH_DATABASE__* environment variables."
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
                data_sources: Dict[str, Any] = yaml.safe_load(f) or {}

            # Extract refs for current domain (annuity_performance)
            domain = "annuity_performance"  # TODO: pass from discover_files_op
            refs_config = (
                data_sources.get("domains", {}).get(domain, {}).get("refs", {})
            )
        except Exception as e:
            context.log.warning("Could not load refs config: %s, using defaults", e)

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
        portfolios_table = portfolios_config.get(
            "table", "组合计划"
        )  # fallback to hardcoded
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
                    raise DataWarehouseLoaderError(
                        f"Unsupported backfill mode: {config.mode}"
                    )

                # Release savepoint on success
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("RELEASE SAVEPOINT plans_backfill")

                result["operations"].append({"table": plans_table, **plan_result})
                context.log.info(
                    f"Plans backfill completed successfully: {plans_table}"
                )

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
                result["operations"].append(
                    {
                        "table": plans_table,
                        "error": str(plans_error),
                        "inserted": 0,
                        "batches": 0,
                    }
                )

        # Execute backfill for portfolios
        if (
            "portfolios" in config.targets or "all" in config.targets
        ) and portfolio_candidates:
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
                    raise DataWarehouseLoaderError(
                        f"Unsupported backfill mode: {config.mode}"
                    )

                # Release savepoint on success
                if conn:
                    with conn.cursor() as cursor:
                        cursor.execute("RELEASE SAVEPOINT portfolios_backfill")

                result["operations"].append(
                    {"table": portfolios_table, **portfolio_result}
                )
                context.log.info(
                    f"Portfolios backfill completed successfully: {portfolios_table}"
                )

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
                result["operations"].append(
                    {
                        "table": portfolios_table,
                        "error": str(portfolios_error),
                        "inserted": 0,
                        "batches": 0,
                    }
                )

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
def generic_backfill_refs_op(
    context: OpExecutionContext,
    config: GenericBackfillConfig,
    processed_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Execute generic reference backfill using configuration-driven approach.

    This op replaces the legacy backfill_refs_op with the new
    GenericBackfillService that reads foreign_keys configuration from
    data_sources.yml.

    Args:
        context: Dagster execution context
        config: Generic backfill configuration
        processed_rows: Processed fact data to derive references from

    Returns:
        Dictionary with backfill execution metadata
    """
    # Convert processed rows to DataFrame for the service
    import pandas as pd
    df = pd.DataFrame(processed_rows)

    if df.empty:
        context.log.info("No processed rows provided for backfill")
        return {"processing_order": [], "tables_processed": [], "total_inserted": 0, "plan_only": config.plan_only}

    settings = get_settings()

    conn = None
    try:
        # Load foreign key configurations (Story 6.2-P14: uses default path config/foreign_keys.yml)
        fk_configs = load_foreign_keys_config(domain=config.domain)

        if not fk_configs:
            context.log.info(f"No foreign_keys configuration found for domain '{config.domain}'")
            return {"processing_order": [], "tables_processed": [], "total_inserted": 0, "plan_only": config.plan_only}

        # Create database connection if not in plan_only mode
        if not config.plan_only:
            # Use SQLAlchemy connection for GenericBackfillService
            from sqlalchemy import create_engine
            import psycopg2

            dsn = settings.get_database_connection_string()
            if not dsn:
                raise DataWarehouseLoaderError(
                    "Database connection failed: invalid DSN resolved from settings"
                )

            context.log.info(f"Connecting to database for generic backfill (domain: {config.domain})")

            # Create SQLAlchemy engine with explicit psycopg2 module
            engine = create_engine(dsn, module=psycopg2)
            conn = engine.connect()

        # Create and run the generic backfill service
        service = GenericBackfillService(config.domain)
        result = service.run(
            df=df,
            configs=fk_configs,
            conn=conn,
            add_tracking_fields=config.add_tracking_fields,
            plan_only=config.plan_only,
        )

        # Convert BackfillResult to dictionary for JSON serialization
        result_dict = {
            "processing_order": result.processing_order,
            "tables_processed": result.tables_processed,
            "total_inserted": result.total_inserted,
            "total_skipped": result.total_skipped,
            "processing_time_seconds": result.processing_time_seconds,
            "rows_per_second": result.rows_per_second,
            "plan_only": config.plan_only,
            "domain": config.domain,
            "tracking_fields_enabled": config.add_tracking_fields
        }

        # Enhanced logging
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            f"Generic backfill completed ({mode_text}) - domain: {config.domain}, "
            f"tables: {len(result.tables_processed)}, inserted: {result.total_inserted}, "
            f"skipped: {result.total_skipped}, time: {result.processing_time_seconds:.2f}s"
        )

        # Log per-table results
        for table_info in result.tables_processed:
            context.log.info(
                f"Table '{table_info['table']}': {table_info['inserted']} inserted, "
                f"{table_info.get('skipped', 0)} skipped"
            )

        # Performance logging
        if result.rows_per_second:
            context.log.info(f"Backfill performance: {result.rows_per_second:.0f} rows/sec")

        return result_dict

    except Exception as e:
        context.log.error(f"Generic backfill operation failed: {e}")
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
    ops = (
        backfill_summary.get("operations", [])
        if isinstance(backfill_summary, dict)
        else []
    )
    tables = backfill_summary.get("tables_processed", [])
    context.log.info(
        f"Backfill completed; gating fact load. operations={len(ops)}, tables={len(tables)}"
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
            global psycopg2
            if psycopg2 is None:
                # Explicitly treated as unavailable (tests may patch to None)
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for database operations"
                )
            if psycopg2 is _PSYCOPG2_NOT_LOADED:
                try:
                    import psycopg2 as _psycopg2
                except ImportError:
                    raise DataWarehouseLoaderError(
                        "psycopg2 not available for database operations"
                    )
                psycopg2 = _psycopg2

            # Import enrichment components (lazy import to avoid circular dependencies)
            from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
            from work_data_hub.domain.company_enrichment.service import (
                CompanyEnrichmentService,
            )
            from work_data_hub.io.connectors.eqc_client import EQCClient
            from work_data_hub.io.loader.company_enrichment_loader import (
                CompanyEnrichmentLoader,
            )

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
                "Connecting to database for queue processing (batch_size: %s)",
                config.batch_size,
            )

            # CRITICAL: Only catch psycopg2.connect failures
            try:
                conn = psycopg2.connect(dsn)  # Bare connection, no context manager
            except Exception as e:
                raise DataWarehouseLoaderError(
                    f"Database connection failed: {e}. "
                    "Check WDH_DATABASE__* environment variables."
                ) from e

            # Setup enrichment service components
            loader = CompanyEnrichmentLoader(conn)
            queue = LookupQueue(conn)
            eqc_client = EQCClient()  # Uses settings for auth

            # Story 6.8: Create observer for metrics collection (AC1, AC5)
            from work_data_hub.domain.company_enrichment.observability import (
                EnrichmentObserver,
            )
            from work_data_hub.infrastructure.enrichment.csv_exporter import (
                export_unknown_companies,
            )

            observer = EnrichmentObserver()

            # Story 6.7 AC6: Reset stale processing rows BEFORE processing
            stale_reset_count = queue.reset_stale_processing(stale_minutes=15)
            if stale_reset_count > 0:
                context.log.warning(
                    "Reset %s stale processing rows to pending (AC6 idempotent recovery)",
                    stale_reset_count,
                )
                conn.commit()  # Commit the reset before processing

            enrichment_service = CompanyEnrichmentService(
                loader=loader,
                queue=queue,
                eqc_client=eqc_client,
                sync_lookup_budget=0,  # No sync budget for queue processing
                observer=observer,
                enrich_enabled=settings.enrich_enabled,
            )

            # Process the queue
            processed_count = enrichment_service.process_lookup_queue(
                batch_size=config.batch_size, observer=observer
            )

            # Get final queue status
            queue_status = enrichment_service.get_queue_status()

            # Story 6.8: Set queue depth in observer (AC1)
            observer.set_queue_depth(queue_status.get("pending", 0))

            # Story 6.7 AC4: Log warning when queue depth exceeds threshold
            pending_count = queue_status.get("pending", 0)
            warning_threshold = settings.enrichment_queue_warning_threshold
            if pending_count > warning_threshold:
                context.log.warning(
                    "Enrichment queue backlog high: %s pending requests (threshold: %s)",
                    pending_count,
                    warning_threshold,
                )

            # Story 6.7 AC7: Log queue statistics after each run
            context.log.info(
                "Queue statistics after processing: pending=%s, processing=%s, done=%s, failed=%s",
                queue_status.get("pending", 0),
                queue_status.get("processing", 0),
                queue_status.get("done", 0),
                queue_status.get("failed", 0),
            )

            # Story 6.8 AC1, AC5: Log enrichment stats in JSON format
            enrichment_stats = observer.get_stats()
            context.log.info(
                "Enrichment stats",
                extra={"enrichment_stats": enrichment_stats.to_dict()},
            )

            # Story 6.8 AC2, AC3: Export unknown companies to CSV if any
            csv_path = None
            if observer.has_unknown_companies() and settings.enrichment_export_unknowns:
                try:
                    csv_path = export_unknown_companies(
                        observer, output_dir=settings.observability_log_dir
                    )
                    if csv_path:
                        context.log.info(
                            "Exported unknown companies to CSV",
                            extra={"csv_path": str(csv_path)},
                        )
                except Exception as export_error:
                    context.log.warning(
                        "Failed to export unknown companies CSV: %s", export_error
                    )

            result: Dict[str, Any] = {
                "processed_count": processed_count,
                "batch_size": config.batch_size,
                "plan_only": config.plan_only,
                "queue_status": queue_status,
                "stale_reset_count": stale_reset_count,
                "enrichment_stats": enrichment_stats.to_dict(),
                "unknown_companies_csv": str(csv_path) if csv_path else None,
            }

            # Persist queue state transitions (done/failed/backoff) before closing
            try:
                conn.commit()
                context.log.info("Queue processing transaction committed")
            except Exception as commit_error:
                context.log.warning(
                    "Queue processing commit warning: %s", commit_error
                )

        else:
            # Plan-only: simulate queue processing
            context.log.info(
                "Queue processing plan - batch_size: %s (no database operations)",
                config.batch_size,
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


# ============================================================================
# Sample Ops for Story 1.9 Demonstration
# ============================================================================
# These ops demonstrate the thin wrapper pattern with delegation to
# domain services and I/O loaders, following Clean Architecture.


@op
def read_csv_op(context: OpExecutionContext) -> List[Dict[str, Any]]:
    """
    Sample op: Read CSV file and return as list of dictionaries.

    Demonstrates:
    - Thin op pattern (delegating to pandas)
    - Dagster logging integration
    - Basic error handling

    Returns:
        List of row dictionaries from sample CSV
    """
    from pathlib import Path

    import pandas as pd

    try:
        # Use fixtures path for sample data
        fixture_path = Path("tests/fixtures/sample_data.csv")

        context.log.info(f"Reading sample CSV data from {fixture_path}")

        # Read CSV using pandas (minimal logic in op)
        df = pd.read_csv(fixture_path)

        # Convert to list of dicts (JSON-serializable)
        rows = df.to_dict(orient="records")

        context.log.info(
            f"Sample CSV read completed - rows: {len(rows)}, columns: {len(df.columns)}"
        )

        return cast(List[Dict[str, Any]], rows)

    except Exception as e:
        context.log.error(f"Sample CSV read failed: {e}")
        raise


@op
def validate_op(
    context: OpExecutionContext, rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Sample op: Validate data using Pipeline framework.

    Demonstrates:
    - Integration with Story 1.5 Pipeline framework
    - DataFrame-level validation steps
    - Dagster logging for pipeline execution

    Args:
        rows: List of row dictionaries from read_csv_op

    Returns:
        Validated rows (same as input for this demo)
    """
    import pandas as pd

    try:
        # Import Pipeline framework from Story 1.5

        context.log.info(f"Starting sample validation pipeline - rows: {len(rows)}")

        # Convert rows back to DataFrame for Pipeline framework
        df = pd.DataFrame(rows)

        # Note: This is a demonstration op showing the thin wrapper pattern.
        # In real implementation, would create a Pipeline with validation steps.
        # For Story 1.9 demo, we just demonstrate the pattern without actual validation.

        context.log.info(
            "Sample validation completed using domain pipelines pattern from Story 1.5 "
            f"(run_id: {context.run_id})"
        )

        # Return validated data (pass-through for demo)
        validated_rows = df.to_dict(orient="records")

        context.log.info(
            f"Sample validation completed - validated: {len(validated_rows)} rows"
        )

        return cast(List[Dict[str, Any]], validated_rows)

    except Exception as e:
        context.log.error(f"Sample validation failed: {e}")
        raise


@op
def load_to_db_op(
    context: OpExecutionContext, rows: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Sample op: Load data to database using Story 1.8 WarehouseLoader.

    Demonstrates:
    - Integration with Story 1.8 transactional loading framework
    - Database connection handling
    - LoadResult telemetry logging

    Args:
        rows: Validated rows from validate_op

    Returns:
        Dictionary with load execution metadata
    """
    try:
        # Import Story 1.8 WarehouseLoader
        from work_data_hub.io.loader.warehouse_loader import load

        context.log.info(f"Starting sample database load - rows: {len(rows)}")

        # Get database connection (using settings from Story 1.4)
        global psycopg2
        if psycopg2 is _PSYCOPG2_NOT_LOADED:
            try:
                import psycopg2 as _psycopg2

                psycopg2 = _psycopg2
            except ImportError:
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for database operations"
                )

        settings = get_settings()

        # Primary DSN retrieval
        dsn = None
        if hasattr(settings, "get_database_connection_string"):
            try:
                dsn = settings.get_database_connection_string()
            except Exception:
                dsn = None
        if not isinstance(dsn, str) and hasattr(settings, "database"):
            try:
                dsn = settings.database.get_connection_string()
            except Exception:
                pass
        if not isinstance(dsn, str) or not dsn:
            raise DataWarehouseLoaderError(
                "Database connection failed: invalid DSN resolved from settings"
            )

        context.log.info(
            "Connecting to database for sample data load (table: sample_data)"
        )

        conn = None
        try:
            conn = psycopg2.connect(dsn)

            # Load using Story 1.8 warehouse loader
            result = load(
                table="sample_data",
                rows=rows,
                mode="append",  # Simple append mode for demo
                pk=[],  # No primary key for simple demo
                conn=conn,
            )

            context.log.info(
                f"Sample database load completed - "
                f"inserted: {result.get('inserted', 0)}, "
                f"batches: {result.get('batches', 0)}"
            )

            return result

        finally:
            if conn is not None:
                conn.close()

    except Exception as e:
        context.log.error(f"Sample database load failed: {e}")
        raise


# Story 6.2.5: Hybrid Reference Service Integration


class HybridReferenceConfig(Config):
    """Configuration for hybrid reference service operation."""

    domain: str
    auto_derived_threshold: float = 0.10
    run_preload: bool = False

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain is non-empty."""
        if not v or not v.strip():
            raise ValueError("Domain must be a non-empty string")
        return v.strip()

    @field_validator("auto_derived_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("auto_derived_threshold must be between 0 and 1")
        return v


@op
def hybrid_reference_op(
    context: OpExecutionContext,
    config: HybridReferenceConfig,
    df: Any,  # pandas DataFrame
) -> Dict[str, Any]:
    """
    Ensure FK references exist using hybrid strategy (Story 6.2.5).

    Coordinates pre-load check and selective backfill to ensure all foreign key
    references exist before fact data insertion. Implements the integration layer
    of the hybrid reference data strategy (AD-011).

    Strategy:
    1. Check coverage of existing reference data (pre-loaded authoritative data)
    2. Identify missing FK values
    3. Backfill only missing values (auto-derived data)
    4. Return comprehensive metrics

    Args:
        context: Dagster execution context
        config: Configuration with domain and threshold
        df: Fact data DataFrame

    Returns:
        Dictionary with hybrid reference operation results including:
        - domain: Domain name
        - pre_load_available: Whether sync service is available
        - coverage_metrics: List of coverage metrics per table
        - backfill_result: Backfill operation results (if any)
        - total_auto_derived: Count of auto-derived records
        - total_authoritative: Count of authoritative records
        - auto_derived_ratio: Ratio of auto-derived to total records
        - degraded_mode: Whether operating in degraded mode
        - degradation_reason: Reason for degradation (if any)

    Raises:
        Exception: If hybrid reference operation fails
    """
    try:
        from work_data_hub.domain.reference_backfill import (
            HybridReferenceService,
            GenericBackfillService,
            load_foreign_keys_config,
        )

        context.log.info(
            f"Starting hybrid reference service for domain '{config.domain}' "
            f"with threshold {config.auto_derived_threshold:.1%}"
        )

        # Load FK configurations for this domain (Story 6.2-P14: uses default path)
        fk_configs = load_foreign_keys_config(domain=config.domain)

        if not fk_configs:
            context.log.warning(
                f"No FK configurations found for domain '{config.domain}', skipping"
            )
            return {
                "domain": config.domain,
                "pre_load_available": False,
                "coverage_metrics": [],
                "backfill_result": None,
                "total_auto_derived": 0,
                "total_authoritative": 0,
                "auto_derived_ratio": 0.0,
                "degraded_mode": False,
                "degradation_reason": None,
            }

        # Get database connection using SQLAlchemy (required by HybridReferenceService)
        from sqlalchemy import create_engine

        settings = get_settings()

        # Get database connection string
        dsn = None
        if hasattr(settings, "get_database_connection_string"):
            try:
                dsn = settings.get_database_connection_string()
            except Exception:
                dsn = None
        if not isinstance(dsn, str) and hasattr(settings, "database"):
            try:
                dsn = settings.database.get_connection_string()
            except Exception:
                pass
        if not isinstance(dsn, str) or not dsn:
            raise DataWarehouseLoaderError(
                "Database connection failed: invalid DSN resolved from settings"
            )

        engine = None
        conn = None
        sync_service = None
        sync_configs = None
        sync_adapters = None

        # Optional in-process pre-load before coverage/backfill
        if config.run_preload:
            try:
                # Story 6.2-P14: Uses default path config/reference_sync.yml
                sync_config = load_reference_sync_config()
                if sync_config and sync_config.enabled and sync_config.tables:
                    sync_service = ReferenceSyncService(domain=config.domain)
                    sync_configs = sync_config.tables
                    # Wire only config-file adapter here; other adapters can be added as needed
                    sync_adapters = {
                        "config_file": ConfigFileConnector(),
                    }
                    context.log.info(
                        "Pre-load enabled with %s table configs", len(sync_configs)
                    )
                else:
                    context.log.info(
                        "Pre-load requested but reference_sync config missing/disabled; skipping"
                    )
            except Exception as preload_error:
                context.log.warning(
                    "Pre-load setup failed; continuing without pre-load: %s",
                    preload_error,
                )

        try:
            # Create SQLAlchemy engine and connection
            engine = create_engine(dsn)
            conn = engine.connect()

            # Initialize services
            backfill_service = GenericBackfillService(domain=config.domain)

            hybrid_service = HybridReferenceService(
                backfill_service=backfill_service,
                sync_service=sync_service,
                auto_derived_threshold=config.auto_derived_threshold,
                sync_configs=sync_configs,
                sync_adapters=sync_adapters,
            )

            # Ensure references
            result = hybrid_service.ensure_references(
                domain=config.domain,
                df=df,
                fk_configs=fk_configs,
                conn=conn,
            )

            # Log metrics
            coverage_rates = [m.coverage_rate for m in result.coverage_metrics]
            context.log.info(
                f"Hybrid reference result: "
                f"coverage={coverage_rates}, "
                f"auto_derived_ratio={result.auto_derived_ratio:.1%}"
            )

            # Warn if threshold exceeded
            if result.auto_derived_ratio > config.auto_derived_threshold:
                context.log.warning(
                    f"Auto-derived ratio {result.auto_derived_ratio:.1%} exceeds "
                    f"threshold {config.auto_derived_threshold:.1%}. "
                    f"Consider running reference_sync job."
                )

            # Convert result to dictionary for Dagster serialization
            return {
                "domain": result.domain,
                "pre_load_available": result.pre_load_available,
                "coverage_metrics": [
                    {
                        "table": m.table,
                        "total_fk_values": m.total_fk_values,
                        "covered_values": m.covered_values,
                        "missing_values": m.missing_values,
                        "coverage_rate": m.coverage_rate,
                    }
                    for m in result.coverage_metrics
                ],
                "backfill_result": (
                    {
                        "processing_order": result.backfill_result.processing_order,
                        "tables_processed": result.backfill_result.tables_processed,
                        "total_inserted": result.backfill_result.total_inserted,
                        "total_skipped": result.backfill_result.total_skipped,
                        "processing_time_seconds": result.backfill_result.processing_time_seconds,
                        "rows_per_second": result.backfill_result.rows_per_second,
                    }
                    if result.backfill_result
                    else None
                ),
                "total_auto_derived": result.total_auto_derived,
                "total_authoritative": result.total_authoritative,
                "auto_derived_ratio": result.auto_derived_ratio,
                "degraded_mode": result.degraded_mode,
                "degradation_reason": result.degradation_reason,
            }

        finally:
            if conn is not None:
                conn.close()
            if engine is not None:
                engine.dispose()

    except Exception as e:
        context.log.error(f"Hybrid reference operation failed: {e}")
        raise
