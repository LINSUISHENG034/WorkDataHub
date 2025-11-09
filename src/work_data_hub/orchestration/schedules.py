"""
Dagster schedules for WorkDataHub orchestration.

This module defines production schedules for automated data processing jobs.
Schedules follow the same configuration patterns as the existing build_run_config
function to ensure consistency across CLI and scheduled execution modes.
"""

from typing import Any, Dict

import yaml
from dagster import schedule

from ..config.settings import get_settings
from .jobs import sample_trustee_performance_multi_file_job


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
