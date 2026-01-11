"""Domain processing pipeline ops (Story 7.1).

This module contains ops for domain-specific data processing:
- ProcessingConfig: Configuration for processing operations
- process_sandbox_trustee_performance_op: Process trustee performance data
- process_annuity_performance_op: Process annuity performance data
- process_annuity_income_op: Process annuity income data
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from dagster import Config, OpExecutionContext, op
from pydantic import field_validator

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.annuity_income.service import (
    process_with_enrichment as process_annuity_income_with_enrichment,
)
from work_data_hub.domain.annuity_performance.service import (
    process_with_enrichment,
)
from work_data_hub.domain.sandbox_trustee_performance.service import process
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

from ._internal import _PSYCOPG2_NOT_LOADED, psycopg2

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainServiceEntry:
    """Registry entry for a domain's processing service.

    This dataclass encapsulates the metadata and function needed to process
    data for a specific domain. It enables a configuration-driven approach where
    new domains can be added by registering entries instead of creating new
    op functions.

    Attributes:
        service_fn: Callable that processes rows and returns models/results.
            Expected signature: (rows: List[Dict], data_source: str, **kwargs) -> Any
        supports_enrichment: Whether the domain supports company enrichment
            (EQC lookup, cache queries, etc.)
        domain_name: Human-readable domain name for logging and error messages

    Example:
        >>> entry = DomainServiceEntry(
        ...     service_fn=process_with_enrichment,
        ...     supports_enrichment=True,
        ...     domain_name="Annuity Performance (规模明细)"
        ... )
        >>> result = entry.service_fn(rows, data_source="file.xlsx")
    """

    service_fn: Callable[[List[Dict[str, Any]], str], Any]
    supports_enrichment: bool = False
    domain_name: str = ""


# Domain Service Registry (Story 7.4-3)
# Maps domain keys to their processing service functions and metadata.
# This registry enables the generic process_domain_op to delegate to the
# appropriate domain service without hardcoded if/elif chains.
DOMAIN_SERVICE_REGISTRY: Dict[str, DomainServiceEntry] = {
    "annuity_performance": DomainServiceEntry(
        service_fn=process_with_enrichment,
        supports_enrichment=True,
        domain_name="Annuity Performance (规模明细)",
    ),
    "annuity_income": DomainServiceEntry(
        service_fn=process_annuity_income_with_enrichment,
        supports_enrichment=False,  # No EQC enrichment (uses sync_lookup_budget param)
        domain_name="Annuity Income (收入明细)",
    ),
    "sandbox_trustee_performance": DomainServiceEntry(
        service_fn=process,
        supports_enrichment=False,
        domain_name="Sandbox Trustee Performance",
    ),
}


class ProcessingConfig(Config):
    """Configuration for processing operations with optional enrichment."""

    enrichment_enabled: bool = False
    enrichment_sync_budget: int = 0
    # Story 6.2-P17: EqcLookupConfig serialized dict (preferred SSOT).
    # Kept optional for transition; if missing, we derive from legacy fields.
    eqc_lookup_config: Optional[Dict[str, Any]] = None
    export_unknown_names: bool = True
    plan_only: bool = True
    use_pipeline: Optional[bool] = (
        None  # CLI override for pipeline framework (None=respect setting)
    )
    # Story 7.5-5: Session ID for unified failure logging
    session_id: Optional[str] = None

    @field_validator("enrichment_sync_budget")
    @classmethod
    def validate_sync_budget(cls, v: int) -> int:
        """Validate sync budget is non-negative."""
        if v < 0:
            raise ValueError("Sync budget must be non-negative")
        return v


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
    # Use module-level psycopg2 reference (lazy-loaded)
    global psycopg2

    # Use first file path for data_source metadata
    file_path = file_paths[0] if file_paths else "unknown"

    # Conditional enrichment service setup
    enrichment_service = None
    observer = None
    conn = None
    settings = get_settings()

    try:
        # GUARD: Only setup enrichment in execute mode AND when explicitly enabled
        # Story 6.2-P16: Fixed condition
        # Enrichment requires BOTH CLI and settings to enable
        use_enrichment = (
            (not config.plan_only)
            and config.enrichment_enabled
            and settings.enrich_enabled
        )

        if use_enrichment:
            # Import enrichment components (lazy import to avoid circular dependencies)
            from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
            from work_data_hub.domain.company_enrichment.observability import (
                EnrichmentObserver,
            )
            from work_data_hub.domain.company_enrichment.service import (
                CompanyEnrichmentService,
            )
            from work_data_hub.infrastructure.enrichment.csv_exporter import (
                export_unknown_companies,
            )
            from work_data_hub.io.connectors.eqc_client import EQCClient
            from work_data_hub.io.loader.company_enrichment_loader import (
                CompanyEnrichmentLoader,
            )

            # Lazy import psycopg2 for database connection
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

        # Story 6.2-P17: Rehydrate EqcLookupConfig from dict (SSOT).
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig

        if config.eqc_lookup_config is not None:
            eqc_config = EqcLookupConfig.from_dict(config.eqc_lookup_config)
        else:
            context.log.warning(
                "eqc_lookup_config missing; deriving from legacy enrichment_* fields",
                extra={
                    "enrichment_enabled": config.enrichment_enabled,
                    "enrichment_sync_budget": config.enrichment_sync_budget,
                },
            )
            eqc_config = EqcLookupConfig(
                enabled=config.enrichment_enabled,
                sync_budget=max(config.enrichment_sync_budget, 0),
                auto_create_provider=config.enrichment_enabled,
                export_unknown_names=config.export_unknown_names,
                auto_refresh_token=True,
            )

        # Guard: if enrichment isn't active,
        # force-disable EQC to prevent any provider init/calls.
        if not use_enrichment:
            eqc_config = EqcLookupConfig.disabled()

        # Call service with enrichment metadata support
        # Story 6.2-P17: Pass eqc_config instead of sync_lookup_budget
        # Story 7.5-5: Pass session_id for unified failure logging
        result = process_with_enrichment(
            excel_rows,
            data_source=file_path,
            eqc_config=eqc_config,
            enrichment_service=enrichment_service,
            export_unknown_names=eqc_config.export_unknown_names,
            session_id=config.session_id,
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
            from work_data_hub.infrastructure.enrichment.csv_exporter import (
                export_unknown_companies,
            )

            enrichment_stats = observer.get_stats()
            context.log.info(
                "Enrichment stats",
                extra={"enrichment_stats": enrichment_stats.to_dict()},
            )
            if observer.has_unknown_companies() and settings.enrichment_export_unknowns:
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
        # Story 7.5-5: Pass session_id for unified failure logging
        processing_result = process_annuity_income_with_enrichment(
            excel_rows, data_source=file_path, session_id=config.session_id
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


@op
def process_annual_award_op(
    context: OpExecutionContext,
    config: ProcessingConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    Process annual award (当年中标) data and return validated records as dicts.

    Handles Chinese 企年受托中标/企年投资中标 Excel data.
    This domain merges legacy TrusteeAwardCleaner and InvesteeAwardCleaner.

    Args:
        context: Dagster execution context
        config: Processing configuration including plan_only settings
        excel_rows: Raw Excel row data
        file_paths: List of file paths (uses first one for data_source metadata)

    Returns:
        List of processed record dictionaries (JSON-serializable)
    """
    from datetime import datetime, timezone

    import pandas as pd

    from work_data_hub.domain.annual_award.helpers import convert_dataframe_to_models
    from work_data_hub.domain.annual_award.pipeline_builder import (
        build_bronze_to_silver_pipeline,
    )
    from work_data_hub.domain.pipelines.types import PipelineContext
    from work_data_hub.infrastructure.enrichment import EqcLookupConfig
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

    file_path = file_paths[0] if file_paths else "unknown"

    # Initialize mapping_repository for DB cache lookup (follows annuity_performance pattern)
    mapping_repository = None
    repo_connection = None
    try:
        from sqlalchemy import create_engine

        settings = get_settings()
        engine = create_engine(settings.get_database_connection_string())
        repo_connection = engine.connect()
        mapping_repository = CompanyMappingRepository(repo_connection)
    except Exception as e:
        context.log.warning(
            "Failed to initialize CompanyMappingRepository; proceeding without DB cache: %s",
            str(e),
        )
        mapping_repository = None
        repo_connection = None

    try:
        # Convert rows to DataFrame
        df = pd.DataFrame(excel_rows)

        # Story 6.2-P17: Rehydrate EqcLookupConfig from ProcessingConfig (SSOT)
        # Follows annuity_performance pattern for EQC query and backflow
        if config.eqc_lookup_config is not None:
            eqc_config = EqcLookupConfig.from_dict(config.eqc_lookup_config)
        else:
            # Derive from legacy enrichment_* fields
            eqc_config = EqcLookupConfig(
                enabled=config.enrichment_enabled,
                sync_budget=max(config.enrichment_sync_budget, 0),
                auto_create_provider=config.enrichment_enabled,
                export_unknown_names=config.export_unknown_names,
                auto_refresh_token=True,
            )

        # Build and execute pipeline with company_id resolution
        # Pass mapping_repository for DB cache lookup (enrichment_index)
        # Pass db_connection for plan code enrichment (customer_plan_contract)
        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=eqc_config,
            mapping_repository=mapping_repository,
            db_connection=repo_connection,
        )
        pipeline_context = PipelineContext(
            pipeline_name="bronze_to_silver",
            execution_id=f"annual_award-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(timezone.utc),
            config={"domain": "annual_award"},
            domain="annual_award",
            run_id=f"annual_award-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            extra={"data_source": file_path},
        )

        result_df = pipeline.execute(df, pipeline_context)

        # Convert to models and then to dicts
        records, failed_count = convert_dataframe_to_models(result_df)

        result_dicts = [
            model.model_dump(mode="json", by_alias=True, exclude_none=True)
            for model in records
        ]

        # Enhanced logging with execution mode
        mode_text = "EXECUTED" if not config.plan_only else "PLAN-ONLY"
        context.log.info(
            "Domain processing completed (%s) - source: %s, input_rows: %s, "
            "output_records: %s, failed: %s, domain: annual_award",
            mode_text,
            file_path,
            len(excel_rows),
            len(result_dicts),
            failed_count,
        )

        return result_dicts

    except Exception as e:
        context.log.error(f"Domain processing failed: {e}")
        raise
    finally:
        # CRITICAL: Commit to persist backflow data to enrichment_index, then cleanup
        if repo_connection is not None:
            try:
                repo_connection.commit()
            except Exception:
                repo_connection.rollback()
            repo_connection.close()
