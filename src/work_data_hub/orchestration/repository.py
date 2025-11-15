"""
Dagster Definitions module for WorkDataHub orchestration.

This module serves as the central registry for all Dagster components
in the WorkDataHub project, enabling discovery through `dagster dev`.

The module exports a single `defs` object containing all jobs, schedules,
and sensors, following Dagster's recommended Definitions pattern for
code location registration.
"""

from dagster import Definitions

# Import jobs from the jobs module
from .jobs import (
    annuity_performance_job,
    sample_pipeline_job,
    sample_trustee_performance_job,
    sample_trustee_performance_multi_file_job,
)

# Import schedules
from .schedules import trustee_daily_schedule

# Import sensors
from .sensors import trustee_data_quality_sensor, trustee_new_files_sensor

# Central Definitions object for Dagster discovery
# This is the single source of truth for all orchestration components
defs = Definitions(
    jobs=[
        sample_pipeline_job,
        sample_trustee_performance_job,
        sample_trustee_performance_multi_file_job,
        annuity_performance_job,
    ],
    schedules=[
        trustee_daily_schedule,
    ],
    sensors=[
        trustee_new_files_sensor,
        trustee_data_quality_sensor,
    ],
)
