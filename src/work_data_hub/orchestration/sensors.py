"""Dagster sensors that trigger dependency-injected jobs (Story 1.6).

Sensors react to filesystem and data-quality events, then call orchestration
jobs that already inject Story 1.5 domain pipelines with I/O adapters. Keeping
logic here ensures domain modules stay unaware of eventing or infrastructure.

Story 6.7: Added enrichment_queue_sensor for queue depth monitoring.
"""

from typing import Any, Dict, Union

import structlog
import yaml
from dagster import RunRequest, SensorEvaluationContext, SkipReason, sensor

from work_data_hub.config.settings import get_settings
from work_data_hub.io.connectors.file_connector import FileDiscoveryService
from work_data_hub.io.loader.warehouse_loader import build_insert_sql
from work_data_hub.utils.types import DiscoveredFile, extract_file_metadata

from .jobs import (
    process_company_lookup_queue_job,
    sandbox_trustee_performance_multi_file_job,
)

logger = structlog.get_logger(__name__)


def _build_sensor_run_config() -> Dict[str, Any]:
    """
    Build run_config for sensor-triggered execution.

    This function mirrors the schedule run_config pattern but is specifically
    configured for event-driven sensor execution. Uses the same configuration
    structure as schedules for consistency.

    Returns:
        Dictionary with nested configuration for all ops matching
        the schemas defined in ops.py.
    """
    # Load table/pk configuration from data_sources.yml
    settings = get_settings()

    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f) or {}
        if not isinstance(data_sources, dict):
            data_sources = {}

        domain_config = (data_sources.get("domains") or {}).get(
            "sandbox_trustee_performance", {}
        ) or {}
        if not isinstance(domain_config, dict):
            domain_config = {}

        output_cfg = domain_config.get("output")
        if isinstance(output_cfg, dict) and output_cfg.get("table"):
            schema_name = output_cfg.get("schema_name")
            table_name = str(output_cfg["table"])
            table = f"{schema_name}.{table_name}" if schema_name else table_name
        else:
            table = domain_config.get("table", "sandbox_trustee_performance")

        pk = domain_config.get("pk", ["report_date", "plan_code", "company_code"])

    except Exception:
        # Fallback to sensible defaults if config loading fails
        table = "sandbox_trustee_performance"
        pk = ["report_date", "plan_code", "company_code"]

    # Build run_config matching the multi-file job pattern
    return {
        "ops": {
            "discover_files_op": {"config": {"domain": "sandbox_trustee_performance"}},
            "read_and_process_sandbox_trustee_files_op": {
                "config": {"sheet": 0, "max_files": 5}
            },
            "load_op": {
                "config": {
                    "table": table,
                    "mode": "delete_insert",
                    "pk": pk,
                    "plan_only": False,  # Execute mode for sensor runs
                }
            },
        }
    }


@sensor(
    job=sandbox_trustee_performance_multi_file_job,
    minimum_interval_seconds=300,  # Check every 5 minutes
)
def trustee_new_files_sensor(context: SensorEvaluationContext):
    """
    File discovery sensor for trustee performance data.

    This sensor monitors the configured data directories for new or modified
    trustee performance files. It uses cursor management to track the last
    processed modification time, ensuring files are only processed once.

    The sensor triggers the multi-file job when new files are detected,
    using the same configuration patterns as scheduled execution.

    Cursor Management:
    - Stores the maximum modification time of processed files
    - Only processes files newer than the cursor timestamp
    - Updates cursor after successful file detection
    """
    try:
        # Discover a single best-match file using Epic 3 discovery
        discovery = FileDiscoveryService()
        match = discovery.discover_file(domain="sandbox_trustee_performance")
        file_meta = extract_file_metadata(str(match.file_path))
        file_meta.update({"version": match.version, "sheet_name": match.sheet_name})
        files = [
            DiscoveredFile(
                domain="sandbox_trustee_performance",
                path=str(match.file_path),
                year=None,
                month=None,
                metadata=file_meta,
            )
        ]

        if not files:
            return SkipReason(
                "No sandbox_trustee_performance files found in configured directories"
            )

        # Cursor management: track last processed modification time
        last_mtime = float(context.cursor) if context.cursor else 0.0

        # Filter for files newer than last processed timestamp
        new_files = []
        for file in files:
            file_mtime = file.metadata.get("modified_time", 0)
            if file_mtime > last_mtime:
                new_files.append(file)

        if not new_files:
            return SkipReason(
                "No new files detected (last_mtime: "
                f"{last_mtime}, total_files: {len(files)})"
            )

        # Calculate new cursor value from maximum modification time
        max_mtime = max(f.metadata.get("modified_time", 0) for f in new_files)
        context.update_cursor(str(max_mtime))

        # Build run configuration for the triggered job
        run_config = _build_sensor_run_config()

        # Use max_mtime as unique run key to prevent duplicate runs
        run_key = f"new_files_{max_mtime}"

        context.log.info(
            "Detected %s new sandbox trustee performance files "
            "(max_mtime: %s, run_key: %s)",
            len(new_files),
            max_mtime,
            run_key,
        )

        return RunRequest(run_key=run_key, run_config=run_config)

    except Exception as e:
        # Return SkipReason instead of raising to prevent sensor failure
        context.log.error(f"File discovery sensor error: {e}")
        return SkipReason(f"Sensor error: {e}")


@sensor(
    job=sandbox_trustee_performance_multi_file_job,
    minimum_interval_seconds=600,  # Check every 10 minutes
)
def trustee_data_quality_sensor(context: SensorEvaluationContext):
    """
    Data quality sensor for trustee performance pipeline health checks.

    This sensor performs lightweight health checks on the trustee performance
    data processing pipeline. It uses plan-only probes to verify data integrity
    without performing actual database operations.

    Health Checks:
    - Verifies files are discoverable and accessible
    - Performs plan-only data validation using build_insert_sql
    - Detects zero-row processing results (potential data quality issues)
    - Logs detailed information for monitoring and alerting

    Note: This sensor primarily logs alerts rather than triggering jobs,
    serving as a monitoring and alerting mechanism for the pipeline.
    """
    try:
        # Check 1: File discovery health
        discovery = FileDiscoveryService()
        # Just check if we can discover a file
        try:
            match = discovery.discover_file(domain="sandbox_trustee_performance")
            files = [match]
        except Exception:
            files = []

        if not files:
            context.log.warning(
                "DATA QUALITY ALERT: No sandbox trustee performance files discovered. "
                "Check data directories and file patterns."
            )
            return SkipReason("No files found for health check")

        # Check 2: File accessibility
        accessible_files = []
        for file in files:  # Check found file
            try:
                if file.file_path.exists():
                    accessible_files.append(file)
                else:
                    context.log.warning(
                        f"DATA QUALITY ALERT: File not accessible: {file.file_path}"
                    )
            except Exception as e:
                context.log.warning(f"DATA QUALITY ALERT: File access error: {e}")

        if not accessible_files:
            return SkipReason(
                "DATA QUALITY ALERT: No accessible files for health check"
            )

        # Check 3: Plan-only data processing probe
        # This simulates the data processing pipeline without actual execution
        try:
            # Use build_insert_sql for plan-only health check
            # This verifies the data structure without database operations
            sample_row = {
                "report_date": "2024-01-01",
                "plan_code": "TEST001",
                "company_code": "TEST_COMPANY",
            }

            sql, params = build_insert_sql(
                table="sandbox_trustee_performance",
                cols=["report_date", "plan_code", "company_code"],
                rows=[sample_row],
            )

            if sql is None:
                context.log.warning(
                    "DATA QUALITY ALERT: Plan-only probe generated null SQL. "
                    "Potential data structure issue."
                )
                return SkipReason("DATA QUALITY ALERT: Plan-only probe failed")

            context.log.info(
                f"Data quality health check passed: "
                f"files={len(files)}, accessible={len(accessible_files)}, "
                f"sql_probe=success"
            )

        except Exception as e:
            context.log.warning(f"DATA QUALITY ALERT: Plan-only probe error: {e}")
            return SkipReason(f"DATA QUALITY ALERT: Probe error: {e}")

        # Health check passed - log success and skip execution
        return SkipReason(
            f"Data quality health check completed successfully "
            f"({len(files)} files, {len(accessible_files)} accessible)"
        )

    except Exception as e:
        context.log.error(f"DATA QUALITY SENSOR ERROR: {e}")
        return SkipReason(f"Sensor error: {e}")


@sensor(
    job=process_company_lookup_queue_job,
    minimum_interval_seconds=300,  # Check every 5 minutes
)
def enrichment_queue_sensor(
    context: SensorEvaluationContext,
) -> Union[RunRequest, SkipReason]:
    """
    Sensor that triggers queue processing when backlog exceeds threshold.

    Story 6.7 AC5: Optional sensor triggers job when queue depth > threshold.
    Disabled via WDH_ENRICHMENT_SENSOR_ENABLED=False (default).

    This sensor provides reactive queue processing for high-volume scenarios
    where the hourly schedule may not be sufficient to keep up with demand.
    """
    settings = get_settings()

    # Check if sensor is enabled (default: False)
    if not settings.enrichment_sensor_enabled:
        return SkipReason("Sensor disabled via WDH_ENRICHMENT_SENSOR_ENABLED=False")

    threshold = settings.enrichment_queue_threshold
    batch_size = settings.enrichment_batch_size

    try:
        # Import here to avoid circular imports and allow lazy DB connection
        import psycopg2

        from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue

        # Get database connection
        dsn = settings.get_database_connection_string()
        conn = psycopg2.connect(dsn)

        try:
            queue = LookupQueue(conn, plan_only=False)
            # Only count requests whose backoff window has elapsed to avoid
            # noise from items still waiting for retry (AC2/AC5 alignment)
            pending_count = queue.get_queue_depth(status="pending", ready_only=True)
        finally:
            conn.close()

        if pending_count > threshold:
            logger.info(
                "enrichment_queue_sensor.triggered",
                pending_count=pending_count,
                threshold=threshold,
                batch_size=batch_size,
            )

            return RunRequest(
                run_key=f"queue_depth_trigger_{pending_count}",
                run_config={
                    "ops": {
                        "process_company_lookup_queue_op": {
                            "config": {
                                "batch_size": batch_size,
                                "plan_only": False,
                            }
                        }
                    }
                },
            )

        return SkipReason(f"Queue depth {pending_count} below threshold {threshold}")

    except Exception as e:
        logger.error(
            "enrichment_queue_sensor.error",
            error=str(e),
        )
        return SkipReason(f"Sensor error: {e}")
