"""Integration tests for Story 1.7 Alembic migrations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.integration
def test_core_tables_exist(test_db_with_migrations: str) -> None:
    """Migrations should create the schema described in Story 1.7."""
    engine = create_engine(test_db_with_migrations, future=True)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert {"pipeline_executions", "data_quality_metrics"}.issubset(tables)

    with engine.begin() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        # Updated to latest migration revision (includes upsert constraints)
        assert revision == "20251206_000001"


@pytest.mark.integration
def test_insert_round_trip(test_db_with_migrations: str) -> None:
    """Pipelines should be able to insert audit + metric rows."""
    engine = create_engine(test_db_with_migrations, future=True)
    execution_id = str(uuid.uuid4())
    metric_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO pipeline_executions (
                    execution_id,
                    pipeline_name,
                    status,
                    started_at,
                    completed_at,
                    input_file,
                    row_counts,
                    error_details
                )
                VALUES (
                    :execution_id,
                    :pipeline_name,
                    :status,
                    :started_at,
                    :completed_at,
                    :input_file,
                    :row_counts,
                    :error_details
                )
                """
            ),
            {
                "execution_id": execution_id,
                "pipeline_name": "test_pipeline",
                "status": "success",
                "started_at": now,
                "completed_at": now,
                "input_file": "tests/data/input.csv",
                "row_counts": '{"rows_input": 10, "rows_output": 9}',
                "error_details": None,
            },
        )

        connection.execute(
            text(
                """
                INSERT INTO data_quality_metrics (
                    metric_id,
                    execution_id,
                    pipeline_name,
                    metric_type,
                    metric_value,
                    recorded_at,
                    metadata
                )
                VALUES (
                    :metric_id,
                    :execution_id,
                    :pipeline_name,
                    :metric_type,
                    :metric_value,
                    :recorded_at,
                    :metadata
                )
                """
            ),
            {
                "metric_id": metric_id,
                "execution_id": execution_id,
                "pipeline_name": "test_pipeline",
                "metric_type": "rows_output",
                "metric_value": 9,
                "recorded_at": now,
                "metadata": '{"stage": "silver"}',
            },
        )

        inserted = connection.execute(
            text(
                """
                SELECT dq.metric_value, pe.status
                FROM data_quality_metrics dq
                JOIN pipeline_executions pe
                ON dq.execution_id = pe.execution_id
                WHERE dq.metric_id = :metric_id
                """
            ),
            {"metric_id": metric_id},
        ).one()

        assert inserted.metric_value == 9
        assert inserted.status == "success"
