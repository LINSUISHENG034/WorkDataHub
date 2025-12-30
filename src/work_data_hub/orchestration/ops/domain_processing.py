"""Generic domain processing op (Story 7.4-3).

This module provides a generic domain processing op that uses the
DOMAIN_SERVICE_REGISTRY pattern to delegate to appropriate domain services
without hardcoded if/elif chains.
"""

import logging
from typing import Any, Dict, List, Optional

from dagster import Config, OpExecutionContext, op
from pydantic import field_validator

from work_data_hub.config.settings import get_settings
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

from ._internal import _PSYCOPG2_NOT_LOADED, psycopg2
from .pipeline_ops import DOMAIN_SERVICE_REGISTRY

logger = logging.getLogger(__name__)


class ProcessDomainOpConfig(Config):
    """Configuration for generic domain processing op (Story 7.4-3).

    Extends ProcessingConfig with domain selection. The eqc_lookup_config
    field is the Single Source of Truth (SSOT) for EQC behavior (Story 6.2-P17).

    Attributes:
        domain: Domain key for registry lookup (e.g., "annuity_performance")
        enrichment_enabled: Whether to enable company enrichment (default: False)
        enrichment_sync_budget: Budget for synchronous EQC lookups (default: 0)
        eqc_lookup_config: Serialized EqcLookupConfig dict (SSOT for EQC behavior)
        export_unknown_names: Whether to export unknown company names (default: True)
        plan_only: If True, skip database writes (default: True)
        use_pipeline: CLI override for pipeline framework (None=respect setting)
    """

    domain: str
    enrichment_enabled: bool = False
    enrichment_sync_budget: int = 0
    eqc_lookup_config: Optional[Dict[str, Any]] = None
    export_unknown_names: bool = True
    plan_only: bool = True
    use_pipeline: Optional[bool] = None

    @field_validator("enrichment_sync_budget")
    @classmethod
    def validate_sync_budget(cls, v: int) -> int:
        """Validate sync budget is non-negative."""
        if v < 0:
            raise ValueError("Sync budget must be non-negative")
        return v


@op
def process_domain_op(
    context: OpExecutionContext,
    config: ProcessDomainOpConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """Generic domain processing op that delegates to registered domain service.

    This op implements the registry pattern (Story 7.4-3) to eliminate the need
    for separate process_{domain}_op functions. It looks up the domain service
    from DOMAIN_SERVICE_REGISTRY and invokes processing with appropriate
    configuration.

    The op handles interface differences between domain services:
    - annuity_performance: Requires eqc_config for enrichment support
    - annuity_income: Uses sync_lookup_budget param, no eqc_config
    - sandbox_trustee_performance: Minimal interface (rows + data_source only)

    Args:
        context: Dagster execution context
        config: ProcessDomainOpConfig with domain selection and enrichment settings
        excel_rows: Raw Excel row data
        file_paths: List of file paths (uses first one for data_source metadata)

    Returns:
        List of processed record dictionaries (JSON-serializable)

    Raises:
        ValueError: If domain is not found in DOMAIN_SERVICE_REGISTRY

    Example:
        >>> config = ProcessDomainOpConfig(domain="annuity_performance")
        >>> result = process_domain_op(context, config, rows, paths)
    """
    # Use module-level psycopg2 reference (lazy-loaded)
    global psycopg2

    # Look up domain service from registry
    domain = config.domain
    entry = DOMAIN_SERVICE_REGISTRY.get(domain)

    if not entry:
        supported = ", ".join(sorted(DOMAIN_SERVICE_REGISTRY.keys()))
        raise ValueError(f"Unknown domain: {domain}. Supported domains: {supported}")

    # Use first file path for data_source metadata
    file_path = file_paths[0] if file_paths else "unknown"

    # Conditional enrichment service setup
    # CRITICAL: Reuse pattern from pipeline_ops.py (see Enrichment Setup Reference)
    enrichment_service = None
    observer = None
    conn = None
    settings = get_settings()

    try:
        # GUARD: Only setup enrichment in execute mode AND when explicitly enabled
        use_enrichment = (
            (not config.plan_only)
            and config.enrichment_enabled
            and entry.supports_enrichment
            and settings.enrich_enabled
        )

        if use_enrichment:
            # Import enrichment components (lazy import to avoid circular deps)
            from work_data_hub.domain.company_enrichment.lookup_queue import (
                LookupQueue,
            )
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

            # Validate required settings before attempting connect
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

            # Log DSN components for debugging (never log password)
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
                    "domain": domain,
                    "sync_budget": config.enrichment_sync_budget,
                    "export_unknowns": config.export_unknown_names,
                    "enrich_enabled": settings.enrich_enabled,
                },
            )

        # Interface adaptation: Call service with domain-specific parameters
        # (See Known Complexity section in story Dev Notes)
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig

        if domain == "annuity_performance":
            # Rehydrate EqcLookupConfig from dict (SSOT)
            if config.eqc_lookup_config is not None:
                eqc_config = EqcLookupConfig.from_dict(config.eqc_lookup_config)
            else:
                context.log.warning(
                    "eqc_lookup_config missing; deriving from legacy fields",
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

            # Guard: if enrichment isn't active, force-disable EQC
            if not use_enrichment:
                eqc_config = EqcLookupConfig.disabled()

            result = entry.service_fn(
                excel_rows,
                data_source=file_path,
                eqc_config=eqc_config,
                enrichment_service=enrichment_service,
                export_unknown_names=eqc_config.export_unknown_names,
            )

        elif domain == "annuity_income":
            # Uses sync_lookup_budget, not eqc_config
            result = entry.service_fn(
                excel_rows,
                data_source=file_path,
                sync_lookup_budget=config.enrichment_sync_budget,
                export_unknown_names=config.export_unknown_names,
            )

        else:
            # sandbox_trustee_performance - minimal interface
            result = entry.service_fn(excel_rows, data_source=file_path)

        # Normalize output to List[Dict[str, Any]]
        # ProcessingResultWithEnrichment has .records attribute
        if hasattr(result, "records"):
            result_dicts = [
                record.model_dump(mode="json", by_alias=True, exclude_none=True)
                for record in result.records
            ]
        elif isinstance(result, list):
            # Direct model list (sandbox_trustee_performance)
            result_dicts = [
                model.model_dump(mode="json", by_alias=True, exclude_none=True)
                for model in result
            ]
        else:
            raise TypeError(
                f"Unexpected result type from {domain} service: {type(result)}"
            )

        # Log enrichment statistics if enrichment was used
        if enrichment_service and hasattr(result, "enrichment_stats"):
            stats = result.enrichment_stats
            if stats.total_records > 0:
                context.log.info(
                    "Enrichment completed",
                    extra={
                        "total": stats.total_records,
                        "internal_hits": stats.success_internal,
                        "external_hits": stats.success_external,
                        "pending": stats.pending_lookup,
                        "temp_assigned": stats.temp_assigned,
                        "failed": stats.failed,
                        "budget_used": stats.sync_budget_used,
                        "csv_exported": bool(result.unknown_names_csv),
                    },
                )

        # Log observer stats + CSV export (if applicable)
        if observer:
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
                    if csv_path and hasattr(result, "unknown_names_csv"):
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
            "output_records: %s, domain: %s, enrichment_enabled: %s",
            mode_text,
            file_path,
            len(excel_rows),
            len(result_dicts),
            entry.domain_name,
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
