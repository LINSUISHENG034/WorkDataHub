"""Integration test covering pipeline execution and database loading."""

from __future__ import annotations

import uuid
from typing import Any, List

import pandas as pd
import pytest
from psycopg2 import sql

from work_data_hub.domain.pipelines.pipeline_config import PipelineConfig, StepConfig
from work_data_hub.domain.pipelines.core import Pipeline
from work_data_hub.domain.pipelines.types import DataFrameStep, RowTransformStep, StepResult
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader


class AddRunMetadata(DataFrameStep):
    """Add run metadata and normalize column casing."""

    name = "add_run_metadata"

    def execute(self, df: pd.DataFrame, context: Any) -> pd.DataFrame:
        updated = df.copy()
        updated["run_id"] = context.execution_id
        updated.columns = [col.lower() for col in updated.columns]
        return updated


class ValidateAndNormalize(RowTransformStep):
    """Simple row-level validation and normalization."""

    name = "validate_and_normalize"

    def apply(self, row: dict, context: Any) -> StepResult:
        if row.get("return_rate") is None:
            raise ValueError("return_rate is required")

        normalized = dict(row)
        normalized["return_rate"] = float(normalized["return_rate"])
        return StepResult(row=normalized, warnings=[], errors=[])


@pytest.mark.integration
def test_pipeline_end_to_end_loads_into_database(postgres_db_with_migrations: str) -> None:
    """Run a minimal pipeline then load results into PostgreSQL."""
    input_df = pd.DataFrame(
        [
            {"plan_code": "P-100", "return_rate": "0.10"},
            {"plan_code": "P-200", "return_rate": "0.05"},
            {"plan_code": "P-300", "return_rate": "0.07"},
        ]
    )

    step_config = [
        StepConfig(
            name="add_run_metadata",
            import_path="tests.integration.test_pipeline_end_to_end.AddRunMetadata",
        ),
        StepConfig(
            name="validate_and_normalize",
            import_path="tests.integration.test_pipeline_end_to_end.ValidateAndNormalize",
            requires=["add_run_metadata"],
        ),
    ]
    pipeline = Pipeline(
        steps=[AddRunMetadata(), ValidateAndNormalize()],
        config=PipelineConfig(name="ci_sample_pipeline", steps=step_config, stop_on_error=True),
    )

    result = pipeline.run(input_df)
    assert result.success is True
    assert len(result.output_data) == 3
    assert set(result.output_data.columns) == {"plan_code", "return_rate", "run_id"}

    dsn = postgres_db_with_migrations
    table_name = f"pipeline_ci_{uuid.uuid4().hex[:8]}"
    loader = WarehouseLoader(connection_url=dsn, pool_size=2, batch_size=2)

    # Create target table for the load
    from psycopg2 import connect

    with connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                        plan_code TEXT PRIMARY KEY,
                        return_rate NUMERIC(8,4) NOT NULL,
                        run_id TEXT NOT NULL
                    )
                    """
                ).format(sql.Identifier(table_name))
            )

    load_result = loader.load_dataframe(
        result.output_data,
        table=table_name,
        schema="public",
        upsert_keys=["plan_code"],
    )

    assert load_result.success is True
    assert load_result.rows_inserted == 3
    assert load_result.rows_updated == 0

    with connect(dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
            assert cursor.fetchone()[0] == 3

    loader.close()
