"""
Reference pipeline implementation demonstrating Story 1.5 patterns.

The reference pipeline chains three simple steps:
    1. AddColumnStep    – adds a derived column based on arithmetic operations
    2. FilterRowsStep   – filters rows by a threshold while keeping immutability
    3. AggregateStep    – aggregates filtered data to prove chaining semantics

The example is intentionally lightweight so downstream stories can copy the
pattern when adding richer domain-specific pipelines.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from .core import Pipeline
from .pipeline_config import PipelineConfig, StepConfig
from .types import DataFrameStep, PipelineContext


class AddColumnStep(DataFrameStep):
    """Add a derived column based on an arithmetic expression."""

    def __init__(self, output_column: str, left: str, right: str):
        self._name = "add_column"
        self.output_column = output_column
        self.left = left
        self.right = right

    @property
    def name(self) -> str:
        return self._name

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        updated = dataframe.copy(deep=True)
        updated[self.output_column] = updated[self.left] + updated[self.right]
        return updated


class FilterRowsStep(DataFrameStep):
    """Filter rows on a column and threshold."""

    def __init__(self, column: str, min_value: float):
        self._name = "filter_rows"
        self.column = column
        self.min_value = min_value

    @property
    def name(self) -> str:
        return self._name

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        filtered = dataframe[dataframe[self.column] >= self.min_value]
        return filtered.reset_index(drop=True)


class AggregateStep(DataFrameStep):
    """Aggregate rows grouped by a key column."""

    def __init__(self, group_by: str, metric_column: str, output_column: str):
        self._name = "aggregate_rows"
        self.group_by = group_by
        self.metric_column = metric_column
        self.output_column = output_column

    @property
    def name(self) -> str:
        return self._name

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        aggregated = (
            dataframe.groupby(self.group_by)[self.metric_column]
            .sum()
            .reset_index()
            .rename(columns={self.metric_column: self.output_column})
        )
        return aggregated


def build_reference_pipeline(min_total: float = 10.0) -> Pipeline:
    """
    Construct the reference pipeline with configuration metadata.

    Args:
        min_total: Threshold applied by FilterRowsStep
    """
    steps = [
        AddColumnStep(output_column="total", left="revenue", right="expenses"),
        FilterRowsStep(column="total", min_value=min_total),
        AggregateStep(
            group_by="region",
            metric_column="total",
            output_column="region_total",
        ),
    ]

    step_configs: List[StepConfig] = [
        StepConfig(
            name="add_column",
            import_path="work_data_hub.domain.pipelines.examples.AddColumnStep",
            options={"output_column": "total", "left": "revenue", "right": "expenses"},
        ),
        StepConfig(
            name="filter_rows",
            import_path="work_data_hub.domain.pipelines.examples.FilterRowsStep",
            options={"column": "total", "min_value": min_total},
        ),
        StepConfig(
            name="aggregate_rows",
            import_path="work_data_hub.domain.pipelines.examples.AggregateStep",
            options={
                "group_by": "region",
                "metric_column": "total",
                "output_column": "region_total",
            },
        ),
    ]

    config = PipelineConfig(
        name="reference_sample_pipeline",
        steps=step_configs,
        stop_on_error=True,
    )

    return Pipeline(steps=steps, config=config)


__all__ = [
    "AddColumnStep",
    "FilterRowsStep",
    "AggregateStep",
    "build_reference_pipeline",
]
