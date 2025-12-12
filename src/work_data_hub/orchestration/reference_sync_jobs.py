"""
Dagster jobs for reference sync operations.

Story 6.2.4: Pre-load reference data from authoritative sources.
"""

from dagster import job

from .reference_sync_ops import reference_sync_op


@job
def reference_sync_job():
    """
    Job for syncing reference data from authoritative sources.

    Story 6.2.4: Implements pre-load layer of hybrid reference data strategy.
    Syncs data from Legacy MySQL and config files to reference tables.
    """
    reference_sync_op()
