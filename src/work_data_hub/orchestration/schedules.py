"""Dagster schedules that remain in the orchestration boundary (Story 1.6).

Schedules only configure how and when jobs run; they never introduce domain or
I/O logic directly. Instead they call the same dependency-injected jobs that
wire Story 1.5 pipelines to I/O adapters, preserving the inward dependency flow.

Story 6.7: Added async_enrichment_schedule for hourly queue processing.
"""

from typing import Any, Dict, Optional

import structlog
import yaml
from dagster import RunRequest, ScheduleEvaluationContext, schedule

from work_data_hub.config.settings import get_settings

from .jobs import process_company_lookup_queue_job, sample_trustee_performance_multi_file_job
from .reference_sync_jobs import reference_sync_job

logger = structlog.get_logger(__name__)


def _build_schedule_run_config() -> Dict[str, Any]:
    """
    Build run_config from data_sources.yml for scheduled execution.

    This function mirrors the build_run_config pattern from jobs.py but is
    specifically configured for production scheduled runs with:
    - Fixed domain: sample_trustee_performance
    - Multi-file processing enabled (max_files=5)
    - Execute mode (plan_only=False)
    - Delete-insert mode for data consistency

    Returns:
        Dictionary with nested configuration for all ops matching
        the schemas defined in ops.py (DiscoverFilesConfig,
        ReadProcessConfig, LoadConfig).
    """
    # Load table/pk configuration from data_sources.yml
    settings = get_settings()

    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f)

        domain_config = data_sources.get("domains", {}).get(
            "sample_trustee_performance", {}
        )
        table = domain_config.get("table", "sample_trustee_performance")
        pk = domain_config.get("pk", ["report_date", "plan_code", "company_code"])

    except Exception as e:
        # Fallback to sensible defaults if config loading fails
        print(f"Warning: Could not load data sources config: {e}")
        table = "sample_trustee_performance"
        pk = ["report_date", "plan_code", "company_code"]

    # Build run_config matching the multi-file job pattern
    return {
        "ops": {
            "discover_files_op": {"config": {"domain": "sample_trustee_performance"}},
            "read_and_process_sample_trustee_files_op": {
                "config": {"sheet": 0, "max_files": 5}
            },
            "load_op": {
                "config": {
                    "table": table,
                    "mode": "delete_insert",
                    "pk": pk,
                    "plan_only": False,  # Execute mode for scheduled runs
                }
            },
        }
    }


@schedule(
    cron_schedule="0 2 * * *",  # 02:00 daily
    job=sample_trustee_performance_multi_file_job,
    execution_timezone="Asia/Shanghai",
)
def trustee_daily_schedule(_context):
    """
    Daily schedule for trustee performance data processing.

    Runs at 02:00 Asia/Shanghai timezone to process sample trustee performance
    files using the multi-file job with production configuration:
    - Discovers sample_trustee_performance files from configured directories
    - Processes up to 5 Excel files with combined operations
    - Loads data using delete_insert mode for data consistency

    The schedule uses the same configuration patterns as the CLI interface
    to ensure consistent behavior between manual and automated execution.
    """
    return _build_schedule_run_config()


@schedule(
    cron_schedule="0 * * * *",  # Every hour at minute 0
    job=process_company_lookup_queue_job,
    execution_timezone="Asia/Shanghai",
)
def async_enrichment_schedule(
    context: ScheduleEvaluationContext,
) -> Optional[RunRequest]:
    """
    Hourly schedule for async enrichment queue processing.

    Story 6.7 AC1: Runs process_company_lookup_queue_job hourly.
    Story 6.7 AC9: Disabled via WDH_ASYNC_ENRICHMENT_ENABLED=False.

    Processes pending company lookup requests from the enrichment queue
    using EQC API with exponential backoff retry logic.
    """
    settings = get_settings()

    # AC9: Check if async enrichment is enabled
    if not settings.async_enrichment_enabled:
        logger.info(
            "async_enrichment_schedule.disabled",
            reason="WDH_ASYNC_ENRICHMENT_ENABLED=False",
        )
        return None  # Skip this run

    batch_size = settings.enrichment_batch_size

    logger.info(
        "async_enrichment_schedule.triggered",
        scheduled_time=context.scheduled_execution_time.isoformat()
        if context.scheduled_execution_time
        else "unknown",
        batch_size=batch_size,
    )

    return RunRequest(
        run_key=f"async_enrichment_{context.scheduled_execution_time.isoformat()}"
        if context.scheduled_execution_time
        else "async_enrichment_manual",
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


@schedule(
    cron_schedule="0 1 * * *",  # 01:00 daily
    job=reference_sync_job,
    execution_timezone="Asia/Shanghai",
)
def reference_sync_schedule(
    context: ScheduleEvaluationContext,
) -> Optional[RunRequest]:
    """
    Daily schedule for reference data pre-load sync.

    Story 6.2.4: Syncs reference data from authoritative sources
    before fact processing to maximize pre-load coverage.

    Runs at 01:00 Asia/Shanghai timezone to sync:
    - 年金计划 from Legacy MySQL
    - 组合计划 from Legacy MySQL
    - 组织架构 from Legacy MySQL (incremental)
    - 产品线 from config file
    """
    settings = get_settings()

    # Check if reference sync is enabled
    if not settings.reference_sync_enabled:
        logger.info(
            "reference_sync_schedule.disabled",
            reason="WDH_REFERENCE_SYNC_ENABLED=False",
        )
        return None

    logger.info(
        "reference_sync_schedule.triggered",
        scheduled_time=context.scheduled_execution_time.isoformat()
        if context.scheduled_execution_time
        else "unknown",
    )

    return RunRequest(
        run_key=f"reference_sync_{context.scheduled_execution_time.isoformat()}"
        if context.scheduled_execution_time
        else "reference_sync_manual",
        run_config={
            "ops": {
                "reference_sync_op": {
                    "config": {
                        "plan_only": False,
                    }
                }
            }
        },
    )
