"""
Tests for Dagster Definitions module in WorkDataHub orchestration.

This module tests the repository definitions to ensure all components
(jobs, schedules, sensors) are properly registered for Dagster discovery.
"""

from dagster import Definitions, JobDefinition, ScheduleDefinition, SensorDefinition

from src.work_data_hub.orchestration.repository import defs


class TestDefinitionsModule:
    """Test Definitions module registration and structure."""

    def test_definitions_object_exists(self):
        """Test that the defs object exists and is a Definitions instance."""
        assert defs is not None
        assert isinstance(defs, Definitions)

    def test_jobs_are_registered(self):
        """Test that all expected jobs are registered in definitions."""
        # Get all jobs from the definitions object
        jobs = defs.jobs
        job_names = [job.name for job in jobs]

        # Verify expected jobs are present
        expected_jobs = ["trustee_performance_job", "trustee_performance_multi_file_job"]

        for expected_job in expected_jobs:
            assert expected_job in job_names, f"Job '{expected_job}' not found in definitions"

        # Verify jobs are actual JobDefinition objects
        for job in jobs:
            assert isinstance(job, JobDefinition)

    def test_schedules_are_registered(self):
        """Test that all expected schedules are registered in definitions."""
        # Get all schedules from the definitions object
        schedules = defs.schedules
        schedule_names = [schedule.name for schedule in schedules]

        # Verify expected schedules are present
        expected_schedules = ["trustee_daily_schedule"]

        for expected_schedule in expected_schedules:
            assert expected_schedule in schedule_names, (
                f"Schedule '{expected_schedule}' not found in definitions"
            )

        # Verify schedules are actual ScheduleDefinition objects
        for schedule in schedules:
            assert isinstance(schedule, ScheduleDefinition)

    def test_sensors_are_registered(self):
        """Test that all expected sensors are registered in definitions."""
        # Get all sensors from the definitions object
        sensors = defs.sensors
        sensor_names = [sensor.name for sensor in sensors]

        # Verify expected sensors are present
        expected_sensors = ["trustee_new_files_sensor", "trustee_data_quality_sensor"]

        for expected_sensor in expected_sensors:
            assert expected_sensor in sensor_names, (
                f"Sensor '{expected_sensor}' not found in definitions"
            )

        # Verify sensors are actual SensorDefinition objects
        for sensor in sensors:
            assert isinstance(sensor, SensorDefinition)

    def test_schedule_job_relationships(self):
        """Test that schedules are properly linked to their target jobs."""
        schedules = defs.schedules
        jobs = defs.jobs
        job_names = [job.name for job in jobs]

        for schedule in schedules:
            if schedule.name == "trustee_daily_schedule":
                # Verify schedule targets the correct job
                assert schedule.job_name == "trustee_performance_multi_file_job"
                assert schedule.job_name in job_names

    def test_sensor_job_relationships(self):
        """Test that sensors are properly linked to their target jobs."""
        sensors = defs.sensors
        jobs = defs.jobs
        job_names = [job.name for job in jobs]

        for sensor in sensors:
            if sensor.name in ["trustee_new_files_sensor", "trustee_data_quality_sensor"]:
                # Verify sensor targets the correct job
                assert sensor.job_name == "sample_trustee_performance_multi_file_job"
                assert sensor.job_name in job_names

    def test_definitions_completeness(self):
        """Test that all defined components are included in definitions."""
        # Verify we have the expected number of components
        assert len(defs.jobs) == 2  # sample_trustee_performance_job, sample_trustee_performance_multi_file_job
        assert len(defs.schedules) == 1  # trustee_daily_schedule
        assert len(defs.sensors) == 2  # trustee_new_files_sensor, trustee_data_quality_sensor

    def test_schedule_configuration(self):
        """Test schedule configuration properties."""
        schedules = defs.schedules

        for schedule in schedules:
            if schedule.name == "trustee_daily_schedule":
                # Verify schedule configuration
                assert schedule.cron_schedule == "0 2 * * *"  # 02:00 daily
                assert schedule.execution_timezone == "Asia/Shanghai"
                assert schedule.job_name == "sample_trustee_performance_multi_file_job"

    def test_sensor_configuration(self):
        """Test sensor configuration properties."""
        sensors = defs.sensors

        for sensor in sensors:
            if sensor.name == "trustee_new_files_sensor":
                # Verify file discovery sensor configuration
                assert sensor.minimum_interval_seconds == 300  # 5 minutes
                assert sensor.job_name == "sample_trustee_performance_multi_file_job"
            elif sensor.name == "trustee_data_quality_sensor":
                # Verify data quality sensor configuration
                assert sensor.minimum_interval_seconds == 600  # 10 minutes
                assert sensor.job_name == "sample_trustee_performance_multi_file_job"

    def test_definitions_import_lightweight(self):
        """Test that definitions import is lightweight and doesn't fail."""
        # This test ensures that importing the definitions module
        # doesn't perform heavy I/O operations or fail due to missing files

        # The fact that we can import and instantiate the defs object
        # without errors indicates that the imports are working correctly
        assert defs is not None

        # Verify that we can access all components without errors
        jobs_count = len(defs.jobs)
        schedules_count = len(defs.schedules)
        sensors_count = len(defs.sensors)

        assert jobs_count > 0
        assert schedules_count > 0
        assert sensors_count > 0


class TestDefinitionsIntegration:
    """Test integration aspects of the Definitions module."""

    def test_job_name_consistency(self):
        """Test that job names are consistent across the definitions."""
        jobs = defs.jobs
        schedules = defs.schedules
        sensors = defs.sensors

        # Collect all job names referenced by schedules and sensors
        referenced_job_names = set()

        for schedule in schedules:
            referenced_job_names.add(schedule.job_name)

        for sensor in sensors:
            referenced_job_names.add(sensor.job_name)

        # Collect all actual job names
        actual_job_names = {job.name for job in jobs}

        # Verify all referenced jobs actually exist
        for ref_job_name in referenced_job_names:
            assert ref_job_name in actual_job_names, (
                f"Referenced job '{ref_job_name}' not found in definitions"
            )

    def test_unique_component_names(self):
        """Test that all component names are unique within their categories."""
        # Job names should be unique
        job_names = [job.name for job in defs.jobs]
        assert len(job_names) == len(set(job_names)), "Duplicate job names found"

        # Schedule names should be unique
        schedule_names = [schedule.name for schedule in defs.schedules]
        assert len(schedule_names) == len(set(schedule_names)), "Duplicate schedule names found"

        # Sensor names should be unique
        sensor_names = [sensor.name for sensor in defs.sensors]
        assert len(sensor_names) == len(set(sensor_names)), "Duplicate sensor names found"
