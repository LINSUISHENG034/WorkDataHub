"""
Projection step for Gold-layer validation and column alignment.

Migrated from the annuity_performance domain to infrastructure/transforms to
enable reuse and keep domain layer lean.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional, Sequence

import pandas as pd

from work_data_hub.domain.annuity_performance.constants import (
    COLUMN_ALIAS_MAPPING,
    DEFAULT_ALLOWED_GOLD_COLUMNS,
    LEGACY_COLUMNS_TO_DELETE,
)
from work_data_hub.domain.annuity_performance.schemas import (
    GoldAnnuitySchema,
    gold_summary_to_dict,
    validate_gold_dataframe,
)
from work_data_hub.domain.pipelines.exceptions import PipelineStepError
from work_data_hub.domain.pipelines.types import DataFrameStep, PipelineContext

logger = logging.getLogger(__name__)


class GoldProjectionStep(DataFrameStep):
    """Story 4.4: Project Silver output to database columns and run Gold validation."""

    def __init__(
        self,
        allowed_columns_provider: Optional[Callable[[], List[str]]] = None,
        table: str = "annuity_performance_new",
        schema: str = "public",
        legacy_columns_to_remove: Optional[Sequence[str]] = None,
    ) -> None:
        self.table = table
        self.schema = schema
        self._allowed_columns_provider = allowed_columns_provider
        self._allowed_columns: Optional[List[str]] = None
        self.legacy_columns_to_remove = (
            list(legacy_columns_to_remove) if legacy_columns_to_remove is not None
            else list(LEGACY_COLUMNS_TO_DELETE)
        )

    @property
    def name(self) -> str:
        return "gold_projection"

    def execute(
        self, dataframe: pd.DataFrame, context: PipelineContext
    ) -> pd.DataFrame:
        working_df = dataframe.copy(deep=True)
        working_df.rename(columns=COLUMN_ALIAS_MAPPING, inplace=True)
        self._ensure_annualized_column(working_df)
        legacy_removed = self._remove_legacy_columns(working_df)

        allowed_columns = self._get_allowed_columns()
        preserved = [col for col in allowed_columns if col in working_df.columns]
        removed = [col for col in working_df.columns if col not in allowed_columns]

        if removed:
            extra = {"columns": removed, "count": len(removed)}
            logger.info("gold_projection.removed_columns", extra=extra)

        if not preserved:
            raise PipelineStepError(
                "Gold projection failed: no columns remain", step_name=self.name
            )

        projected_df = working_df.loc[:, preserved].copy()
        validated_df, summary = validate_gold_dataframe(
            projected_df, project_columns=False
        )

        if hasattr(context, "metadata"):
            context.metadata["gold_projection"] = {
                "removed_columns": removed,
                "legacy_removed_columns": legacy_removed,
                "allowed_columns_count": len(allowed_columns),
            }
            context.metadata["gold_schema_validation"] = gold_summary_to_dict(summary)

        return validated_df

    def _ensure_annualized_column(self, dataframe: pd.DataFrame) -> None:
        if "年化收益率" in dataframe.columns:
            return
        if "当期收益率" in dataframe.columns:
            dataframe["年化收益率"] = dataframe["当期收益率"]
            dataframe.drop(columns=["当期收益率"], inplace=True)

    def _remove_legacy_columns(self, dataframe: pd.DataFrame) -> List[str]:
        cols_to_remove = self.legacy_columns_to_remove
        existing = [col for col in cols_to_remove if col in dataframe.columns]
        if existing:
            dataframe.drop(columns=existing, inplace=True)
        return existing

    def _get_allowed_columns(self) -> List[str]:
        if self._allowed_columns is not None:
            return self._allowed_columns

        default_provider = self._default_allowed_columns_provider
        provider = self._allowed_columns_provider or default_provider
        columns = list(provider())

        if not columns:
            raise PipelineStepError(
                "Allowed columns provider returned empty list",
                step_name=self.name,
            )

        seen = set()
        deduped: List[str] = []
        for column in columns:
            if column not in seen:
                seen.add(column)
                deduped.append(column)

        self._allowed_columns = deduped
        return self._allowed_columns

    @staticmethod
    def _default_allowed_columns_provider() -> List[str]:
        return list(DEFAULT_ALLOWED_GOLD_COLUMNS)


__all__ = ["GoldProjectionStep"]
