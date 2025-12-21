"""Company enrichment ops (Story 7.1).

This module contains ops for company enrichment queue processing:
- QueueProcessingConfig: Configuration for queue processing
- process_company_lookup_queue_op: Process pending company lookup requests
"""

import logging
from typing import Any, Dict

from dagster import Config, OpExecutionContext, op
from pydantic import field_validator

from work_data_hub.config.settings import get_settings
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

from ._internal import _PSYCOPG2_NOT_LOADED, psycopg2

logger = logging.getLogger(__name__)


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
    # Use module-level psycopg2 reference
    global psycopg2

    conn = None
    try:
        if not config.plan_only:
            # Lazy import psycopg2 into module-global for test compatibility
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
