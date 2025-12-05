"""
Validation pipeline steps for schema enforcement.

Migrated from domain annuity_performance pipeline_steps to infrastructure to
enable reuse across domains.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaError as PanderaSchemaError

from work_data_hub.domain.annuity_performance.schemas import (
    BronzeAnnuitySchema,
    GoldAnnuitySchema,
    bronze_summary_to_dict,
    gold_summary_to_dict,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from work_data_hub.domain.pipelines.exceptions import PipelineStepError
from work_data_hub.domain.pipelines.types import PipelineContext


class BronzeSchemaValidationStep:
    """Story 2.2: DataFrame-level validation for Bronze schema."""

    def __init__(self, failure_threshold: float = 0.10):
        self.failure_threshold = failure_threshold

    @property
    def name(self) -> str:
        return "bronze_schema_validation"

    @pa.check_io(df1=BronzeAnnuitySchema, lazy=True)
    def _validate_with_decorator(self, df1: pd.DataFrame) -> pd.DataFrame:
        return df1

    def execute(
        self, dataframe: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
        try:
            validated_df, summary = validate_bronze_dataframe(
                dataframe, failure_threshold=self.failure_threshold
            )
        except PanderaSchemaError as exc:
            raise PipelineStepError(str(exc), step_name=self.name) from exc

        if hasattr(context, "metadata"):
            summary_dict = bronze_summary_to_dict(summary)
            context.metadata.setdefault("bronze_schema_validation", summary_dict)
        return validated_df


class GoldSchemaValidationStep:
    """Story 2.2: Gold-layer schema validation before database projection."""

    def __init__(self, project_columns: bool = True):
        self.project_columns = project_columns

    @property
    def name(self) -> str:
        return "gold_schema_validation"

    @pa.check_io(df1=GoldAnnuitySchema, lazy=True)
    def _validate_with_decorator(self, df1: pd.DataFrame) -> pd.DataFrame:
        return df1

    def execute(
        self, dataframe: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
        try:
            validated_df, summary = validate_gold_dataframe(
                dataframe, project_columns=self.project_columns
            )
        except PanderaSchemaError as exc:
            raise PipelineStepError(str(exc), step_name=self.name) from exc

        if hasattr(context, "metadata"):
            summary_dict = gold_summary_to_dict(summary)
            context.metadata.setdefault("gold_schema_validation", summary_dict)
        return validated_df


__all__ = [
    "BronzeSchemaValidationStep",
    "GoldSchemaValidationStep",
]
