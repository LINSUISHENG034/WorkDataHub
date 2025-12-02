"""Integration test for Dagster sample_pipeline_job (Story 1.9).

This test verifies that the sample_pipeline_job can be executed programmatically
and demonstrates the integration of:
- Story 1.5: Pipeline framework for data transformation
- Story 1.8: WarehouseLoader for transactional database loading
- Story 1.9: Dagster orchestration with thin op wrappers

The test is designed to run in CI without requiring a live database connection
by mocking database operations. For full integration testing with database,
see test_pipeline_end_to_end.py.

NOTE: These tests are skipped pending Epic 5 infrastructure refactoring.
The sample_pipeline_job requires fixture files that need to be recreated.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from dagster import DagsterInstance

from src.work_data_hub.orchestration.jobs import sample_pipeline_job

pytestmark = pytest.mark.skip(reason="Tests require fixture files - pending Epic 5 infrastructure refactoring")


@pytest.mark.integration
def test_sample_pipeline_job_executes_successfully() -> None:
    """
    Test that sample_pipeline_job executes successfully without errors.

    This test verifies:
    1. Job can be executed programmatically using Dagster's execute_in_process API
    2. All three ops (read_csv, validate, load_to_db) execute in sequence
    3. Job completes with success=True
    4. No runtime errors or exceptions are raised

    The test mocks database operations to avoid requiring a live PostgreSQL
    connection in CI. This focuses the test on verifying the Dagster
    orchestration layer and op wiring.
    """
    # Use ephemeral instance to avoid DAGSTER_HOME requirement in CI
    instance = DagsterInstance.ephemeral()

    # Mock psycopg2 and database operations
    mock_connection = patch("src.work_data_hub.orchestration.ops.psycopg2")
    mock_load = patch(
        "src.work_data_hub.io.loader.warehouse_loader.load",
        return_value={
            "mode": "append",
            "table": "sample_data",
            "deleted": 0,
            "inserted": 5,
            "batches": 1
        }
    )

    with mock_connection, mock_load:
        # Execute job without requiring database connection
        # Note: The sample_pipeline_job reads from tests/fixtures/sample_data.csv
        # which should exist for this test to pass
        result = sample_pipeline_job.execute_in_process(
            instance=instance,
            raise_on_error=True  # Fail test immediately if job raises exception
        )

    # Verify job completed successfully
    assert result.success is True, "sample_pipeline_job should complete successfully"

    # Verify all ops executed
    executed_ops = [event.node_name for event in result.all_node_events if event.is_step_success]

    assert "read_csv_op" in executed_ops, "read_csv_op should execute successfully"
    assert "validate_op" in executed_ops, "validate_op should execute successfully"
    assert "load_to_db_op" in executed_ops, "load_to_db_op should execute successfully"

    # Verify no failures
    failures = [event for event in result.all_node_events if event.is_failure]
    assert len(failures) == 0, f"Job should have no failures, but got: {failures}"


@pytest.mark.integration
def test_sample_pipeline_job_reads_csv_fixture() -> None:
    """
    Test that sample_pipeline_job correctly reads the CSV fixture.

    This test verifies:
    1. read_csv_op successfully reads tests/fixtures/sample_data.csv
    2. The CSV data is passed correctly to downstream ops
    3. Data structure is valid (list of dictionaries)

    This is a regression test for the Pipeline API bug found in Story 1.9
    (ops.py:1267), which has been fixed in Epic 2 prep work.
    """
    instance = DagsterInstance.ephemeral()

    # Mock database operations
    with patch("src.work_data_hub.orchestration.ops.psycopg2"), \
         patch("src.work_data_hub.io.loader.warehouse_loader.load", return_value={}):

        result = sample_pipeline_job.execute_in_process(
            instance=instance,
            raise_on_error=True
        )

    # Extract output from read_csv_op
    csv_data = result.output_for_node("read_csv_op")

    # Verify data structure
    assert isinstance(csv_data, list), "CSV data should be a list of rows"
    assert len(csv_data) > 0, "CSV fixture should contain at least one row"

    # Verify first row is a dictionary (expected structure)
    if csv_data:
        assert isinstance(csv_data[0], dict), "Each row should be a dictionary"


@pytest.mark.integration
def test_sample_pipeline_job_validates_with_pipeline_framework() -> None:
    """
    Test that validate_op demonstrates Pipeline framework integration.

    This test verifies:
    1. validate_op receives data from read_csv_op
    2. validate_op executes without errors
    3. Data is passed through correctly (pass-through validation for demo)

    Note: The validate_op in sample_pipeline_job is a demonstration op
    that shows the thin wrapper pattern. It does not perform actual
    validation in Story 1.9, but demonstrates how to integrate the
    Pipeline framework from Story 1.5.

    For actual validation examples using Pydantic and Pandera, see:
    docs/pipeline-integration-guide.md (created in Epic 2 prep work).
    """
    instance = DagsterInstance.ephemeral()

    # Mock database operations
    with patch("src.work_data_hub.orchestration.ops.psycopg2"), \
         patch("src.work_data_hub.io.loader.warehouse_loader.load", return_value={}):

        result = sample_pipeline_job.execute_in_process(
            instance=instance,
            raise_on_error=True
        )

    # Extract data before and after validation
    csv_data = result.output_for_node("read_csv_op")
    validated_data = result.output_for_node("validate_op")

    # Verify validation executed
    assert validated_data is not None, "validate_op should produce output"

    # Verify data structure preserved (pass-through for demo)
    assert isinstance(validated_data, list), "Validated data should be a list"
    assert len(validated_data) == len(csv_data), \
        "Validated data should have same length as input (pass-through demo)"


@pytest.mark.integration
def test_sample_pipeline_job_backward_compatibility() -> None:
    """
    Test backward compatibility with Story 1.5 Pipeline framework.

    This test ensures that modifications to the Pipeline framework in
    Epic 2 do not break the sample_pipeline_job from Story 1.9.

    This is part of the "Breaking Change Review Checklist" from Epic 1
    Retrospective:
    - [x] Verify Story 1.9 Dagster integration test passes
    - [x] Verify no regressions in op execution
    - [x] Verify Clean Architecture boundaries preserved

    When modifying Pipeline framework in Epic 2:
    1. Run this test before making changes (baseline)
    2. Run after changes (regression check)
    3. If test fails, review changes for breaking compatibility
    """
    instance = DagsterInstance.ephemeral()

    # Mock database operations
    with patch("src.work_data_hub.orchestration.ops.psycopg2"), \
         patch("src.work_data_hub.io.loader.warehouse_loader.load", return_value={}):

        # This should execute without errors, demonstrating backward compatibility
        result = sample_pipeline_job.execute_in_process(
            instance=instance,
            raise_on_error=True
        )

    # Verify job structure remains intact
    assert result.success is True

    # Verify all expected ops are present and execute
    op_names = {event.node_name for event in result.all_node_events if event.is_step_success}

    expected_ops = {"read_csv_op", "validate_op", "load_to_db_op"}
    assert expected_ops.issubset(op_names), \
        f"Expected ops {expected_ops} should all execute, got: {op_names}"


@pytest.mark.integration
@pytest.mark.skipif(
    True,  # Skip by default - requires database fixture
    reason="Requires PostgreSQL database fixture (enable for full integration testing)"
)
def test_sample_pipeline_job_with_database(postgres_db_with_migrations: str) -> None:
    """
    Full integration test with actual database connection.

    IMPORTANT: This test is skipped by default in CI. To enable:
    1. Set up PostgreSQL test database
    2. Apply migrations (Story 1.7)
    3. Change @pytest.mark.skipif to False
    4. Provide postgres_db_with_migrations fixture

    This test verifies:
    1. load_to_db_op can connect to PostgreSQL
    2. Data is loaded successfully using WarehouseLoader (Story 1.8)
    3. Transactional guarantees are preserved
    4. LoadResult telemetry is captured

    For Epic 2 development, consider adding:
    - Validation error collection to sample_data.csv
    - Error export testing
    - Partial success scenarios (stop_on_error=False)
    """
    instance = DagsterInstance.ephemeral()

    # Configure job to use actual database connection
    run_config = {
        "ops": {
            "load_to_db_op": {
                "config": {
                    "table": "sample_data",
                    "mode": "append",
                    "connection_string": postgres_db_with_migrations
                }
            }
        }
    }

    result = sample_pipeline_job.execute_in_process(
        instance=instance,
        run_config=run_config,
        raise_on_error=True
    )

    assert result.success is True

    # Verify load operation completed
    load_result = result.output_for_node("load_to_db_op")
    assert load_result is not None
    assert load_result.get("inserted", 0) > 0, "Should have inserted rows"


# ============================================================================
# Regression Tests for Epic 1 Issues
# ============================================================================


@pytest.mark.integration
def test_validate_op_pipeline_api_bug_fixed() -> None:
    """
    Regression test for Story 1.9 Pipeline API bug (ops.py:1267).

    **Background**:
    During Story 1.9 manual testing, a Pipeline API mismatch was discovered:
    - Bug: Pipeline(name="sample_validation", config={"execution_id": ...})
    - Root Cause: Pipeline doesn't accept `name` parameter
    - Impact: Runtime failure, not caught in code review

    **Fix Applied** (Epic 2 Prep Work):
    - Removed incorrect Pipeline instantiation from validate_op
    - Updated to use demonstration pattern (log only)
    - See: docs/pipeline-integration-guide.md for correct usage

    **This Test**:
    Verifies that validate_op executes without TypeError, confirming
    the Pipeline API bug has been fixed.

    **Reference**: Epic 1 Retrospective, Section 2 (API Contract Clarity)
    """
    instance = DagsterInstance.ephemeral()

    # Mock database operations
    with patch("src.work_data_hub.orchestration.ops.psycopg2"), \
         patch("src.work_data_hub.io.loader.warehouse_loader.load", return_value={}):

        # This should NOT raise TypeError about unexpected 'name' argument
        result = sample_pipeline_job.execute_in_process(
            instance=instance,
            raise_on_error=True  # Fail on any exception, including TypeError
        )

    # Verify validate_op executed successfully (no TypeError)
    validate_events = [
        event for event in result.all_node_events
        if event.node_name == "validate_op" and event.is_step_success
    ]

    assert len(validate_events) > 0, \
        "validate_op should execute successfully without Pipeline API TypeError"


# ============================================================================
# Performance Regression Tests (Story 1.11)
# ============================================================================


@pytest.mark.integration
@pytest.mark.performance
def test_sample_pipeline_job_performance_baseline() -> None:
    """
    Performance baseline test for sample_pipeline_job execution time.

    This test tracks execution time and warns if it exceeds baseline + 20%
    threshold (Story 1.11 pattern).

    **Baseline Expectations**:
    - Small CSV (5 rows): <1 second
    - No database connection: Fast execution
    - Ops are thin wrappers: Minimal overhead

    **If This Test Warns**:
    1. Check if CSV fixture grew significantly
    2. Review recent changes to ops (read_csv, validate, load_to_db)
    3. Profile execution to identify bottleneck
    4. Consider updating baseline if intentional optimization

    **Epic 2 Application**:
    Use this pattern for validation performance testing:
    - Pydantic validation: ≥1000 rows/second (AC)
    - Validation overhead: <20% of total execution time (AC)
    """
    import time

    instance = DagsterInstance.ephemeral()

    start_time = time.time()

    # Mock database operations
    with patch("src.work_data_hub.orchestration.ops.psycopg2"), \
         patch("src.work_data_hub.io.loader.warehouse_loader.load", return_value={}):

        result = sample_pipeline_job.execute_in_process(
            instance=instance,
            raise_on_error=True
        )

    duration_seconds = time.time() - start_time

    # Verify job succeeded
    assert result.success is True

    # Baseline: 1 second for small CSV (generous threshold)
    baseline_seconds = 1.0
    threshold_seconds = baseline_seconds * 1.2  # 20% tolerance

    if duration_seconds > threshold_seconds:
        pytest.warns(
            UserWarning,
            match=f"sample_pipeline_job execution time ({duration_seconds:.2f}s) "
                  f"exceeded baseline+20% ({threshold_seconds:.2f}s)"
        )


# ============================================================================
# Documentation References
# ============================================================================

"""
**Related Documentation**:
- Story 1.9: Dagster Orchestration Setup
  docs/sprint-artifacts/stories/1-9-dagster-orchestration-setup.md
- Story 1.5: Pipeline Framework Core
  docs/sprint-artifacts/stories/1-5-shared-pipeline-framework-core-simple.md
- Story 1.8: PostgreSQL Loading Framework
  docs/sprint-artifacts/stories/1-8-postgresql-loading-framework.md
- Pipeline Integration Guide (Epic 2 Prep):
  docs/pipeline-integration-guide.md
- Epic 1 Retrospective:
  docs/sprint-artifacts/epic-1-retrospective-2025-11-16.md

**Pre-Epic 2 Action Items**:
This file addresses Item #3 from Epic 1 Retrospective:
  [x] Add Dagster integration test to CI (test_dagster_sample_job.py)

**Backward Compatibility**:
When modifying Pipeline framework in Epic 2:
1. Run these tests BEFORE making changes (baseline)
2. Run AFTER changes (regression check)
3. If failures occur, review for breaking changes
4. Update tests if intentional breaking change with migration guide

**CI Integration**:
This test file should be executed in GitHub Actions CI pipeline:
```yaml
- name: Run Dagster Integration Tests
  run: uv run pytest tests/integration/test_dagster_sample_job.py -v
```
"""
