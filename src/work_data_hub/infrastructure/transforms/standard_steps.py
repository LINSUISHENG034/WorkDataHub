"""
Standard pipeline transformation steps.

Story 5.6: Implement Standard Pipeline Steps
Architecture Decision AD-010: Infrastructure Layer & Pipeline Composition

This module provides standard, reusable transformation steps migrated from
domain/pipelines/steps/ (Story 1.12) to the infrastructure layer.

Steps:
- MappingStep: Column renaming
- ReplacementStep: Value replacement in columns
- CalculationStep: Calculated fields using vectorized operations
- FilterStep: Row filtering based on boolean conditions
- DropStep: Column removal
- RenameStep: Alias for MappingStep (semantic clarity)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext

from .base import TransformStep

logger = structlog.get_logger(__name__)


class MappingStep(TransformStep):
    """
    Rename DataFrame columns based on configuration.

    Migrated from domain/pipelines/steps/mapping_step.py (Story 1.12).

    Example:
        >>> step = MappingStep({'月度': 'report_date', '计划代码': 'plan_code'})
        >>> df_out = step.apply(df_in, context)
    """

    def __init__(self, column_mapping: Dict[str, str]) -> None:
        """
        Initialize the mapping step with column name mappings.

        Args:
            column_mapping: Dictionary mapping old_column_name -> new_column_name

        Raises:
            TypeError: If column_mapping is not a dictionary
            ValueError: If column_mapping is empty
        """
        if not isinstance(column_mapping, dict):
            raise TypeError(
                f"column_mapping must be a dict, got {type(column_mapping).__name__}"
            )
        if not column_mapping:
            raise ValueError("column_mapping cannot be empty")
        self._column_mapping = column_mapping

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "MappingStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Rename columns using Pandas vectorized operation."""
        log = logger.bind(step=self.name, pipeline=context.pipeline_name)

        existing_columns = set(df.columns)
        effective_mapping = {
            old: new
            for old, new in self._column_mapping.items()
            if old in existing_columns
        }

        missing = set(self._column_mapping.keys()) - existing_columns
        if missing:
            log.warning("columns_not_found", missing=sorted(missing))

        if not effective_mapping:
            return df.copy()

        result = df.rename(columns=effective_mapping)
        log.info("columns_renamed", count=len(effective_mapping))
        return result


class ReplacementStep(TransformStep):
    """
    Replace values in columns based on mapping.

    Migrated from domain/pipelines/steps/replacement_step.py (Story 1.12).

    Example:
        >>> step = ReplacementStep({
        ...     'status': {'draft': 'pending', 'old': 'archived'}
        ... })
        >>> df_out = step.apply(df_in, context)
    """

    def __init__(self, column_mapping: Dict[str, Dict[Any, Any]]) -> None:
        """
        Initialize the replacement step with value mappings.

        Args:
            column_mapping: Dictionary mapping column_name -> {old_value: new_value}

        Raises:
            TypeError: If column_mapping is not a dictionary
            ValueError: If column_mapping is empty
        """
        if not isinstance(column_mapping, dict):
            raise TypeError("column_mapping must be a dict of column->mapping")
        if not column_mapping:
            raise ValueError("column_mapping cannot be empty")
        self._column_mapping = column_mapping

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "ReplacementStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Replace values using Pandas vectorized operation."""
        log = logger.bind(step=self.name, pipeline=context.pipeline_name)
        result = df.copy()
        total_replacements = 0

        for column, mapping in self._column_mapping.items():
            if column not in result.columns:
                log.warning("column_not_found", column=column)
                continue
            before = result[column].copy()
            result[column] = result[column].replace(mapping)
            changed = (before != result[column]).sum()
            total_replacements += int(changed)

        log.info("values_replaced", total=total_replacements)
        return result


# Type alias for calculation functions
CalculationFunc = Callable[[pd.DataFrame], Union[pd.Series, Any]]


class CalculationStep(TransformStep):
    """
    Add calculated fields using vectorized callables.

    Migrated from domain/pipelines/steps/calculated_field_step.py (Story 1.12).

    Each callable receives the full DataFrame and must return a Series
    aligned on the DataFrame's index.

    Example:
        >>> step = CalculationStep({
        ...     'total': lambda df: df['a'] + df['b'],
        ...     'ratio': lambda df: df['x'] / df['y']
        ... })
        >>> df_out = step.apply(df_in, context)
    """

    def __init__(self, calculations: Dict[str, CalculationFunc]) -> None:
        """
        Initialize the calculation step with field definitions.

        Args:
            calculations: Dictionary mapping field_name -> calculation_function

        Raises:
            ValueError: If calculations is empty
            TypeError: If any calculation is not callable
        """
        if not calculations:
            raise ValueError("calculations cannot be empty")
        for field_name, calc_func in calculations.items():
            if not callable(calc_func):
                raise TypeError(
                    f"Calculation for field '{field_name}' must be callable, "
                    f"got {type(calc_func).__name__}"
                )
        self._calculations = calculations

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "CalculationStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Add calculated fields to DataFrame."""
        log = logger.bind(step=self.name, pipeline=context.pipeline_name)
        result = df.copy()

        for field, func in self._calculations.items():
            try:
                series = func(result)
            except Exception as exc:  # noqa: BLE001
                log.error("calculation_failed", field=field, error=str(exc))
                raise
            result[field] = series
            log.info("calculated_field", field=field)

        return result


# Type alias for filter functions
FilterFunc = Callable[[pd.DataFrame], Union[pd.Series, bool]]


class FilterStep(TransformStep):
    """
    Filter rows based on boolean conditions.

    Migrated from domain/pipelines/steps/filter_step.py (Story 1.12).

    The predicate must return a boolean Series; rows with False/NaN are dropped.
    Errors surface (fail fast) with logged context.

    Example:
        >>> step = FilterStep(lambda df: df['value'] > 0)
        >>> df_out = step.apply(df_in, context)
    """

    def __init__(
        self,
        predicate: FilterFunc,
        description: str = "custom filter",
    ) -> None:
        """
        Initialize the filter step with a predicate function.

        Args:
            predicate: Function that receives DataFrame and returns boolean Series
            description: Human-readable description for logging

        Raises:
            TypeError: If predicate is not callable
        """
        if not callable(predicate):
            raise TypeError(
                f"predicate must be callable, got {type(predicate).__name__}"
            )
        self._predicate = predicate
        self._description = description

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "FilterStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Filter rows based on predicate."""
        log = logger.bind(
            step=self.name,
            pipeline=context.pipeline_name,
            filter_description=self._description,
        )

        mask = self._predicate(df)
        if mask is None:
            raise ValueError("Filter predicate returned None")
        if hasattr(mask, "shape") and mask.shape[0] != df.shape[0]:
            raise ValueError("Filter predicate length mismatch")

        before = len(df)
        result = df[mask].copy()
        log.info("rows_filtered", before=before, after=len(result))
        return result


class DropStep(TransformStep):
    """
    Drop specified columns from DataFrame.

    Example:
        >>> step = DropStep(['temp_col', 'debug_col'])
        >>> df_out = step.apply(df_in, context)
    """

    def __init__(self, columns: List[str]) -> None:
        """
        Initialize the drop step with columns to remove.

        Args:
            columns: List of column names to drop

        Raises:
            ValueError: If columns is empty
        """
        if not columns:
            raise ValueError("columns cannot be empty")
        self._columns = columns

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "DropStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Drop specified columns from DataFrame."""
        log = logger.bind(step=self.name, pipeline=context.pipeline_name)

        existing = [c for c in self._columns if c in df.columns]
        if not existing:
            log.info("no_columns_to_drop")
            return df.copy()

        result = df.drop(columns=existing)
        log.info("columns_dropped", count=len(existing), columns=existing)
        return result


class RenameStep(TransformStep):
    """
    Alias for MappingStep - rename columns based on mapping.

    Provided for semantic clarity when the intent is renaming rather than mapping.

    Example:
        >>> step = RenameStep({'old_name': 'new_name'})
        >>> df_out = step.apply(df_in, context)
    """

    def __init__(self, rename_mapping: Dict[str, str]) -> None:
        """
        Initialize the rename step with column mappings.

        Args:
            rename_mapping: Dictionary mapping old_name -> new_name
        """
        self._mapping_step = MappingStep(rename_mapping)

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "RenameStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Rename columns using underlying MappingStep."""
        return self._mapping_step.apply(df, context)


def coerce_numeric_columns(
    dataframe: pd.DataFrame,
    columns: Sequence[str],
    *,
    cleaner: Callable[[Any, str], Optional[float]],
) -> Dict[str, List[int]]:
    """
    Clean and coerce numeric columns using provided cleaner.

    Returns a mapping of column name -> list of row indices that failed cleaning.
    """
    invalid_rows: Dict[str, List[int]] = {}
    for column in columns:
        if column not in dataframe.columns:
            continue
        series = dataframe[column]
        cleaned_values: List[float | None] = []
        column_invalid_indices: List[int] = []
        for idx, value in series.items():
            try:
                cleaned = cleaner(value, column)
            except ValueError:
                cleaned = None
                column_invalid_indices.append(idx)
            cleaned_values.append(cleaned)

        converted = pd.to_numeric(cleaned_values, errors="coerce")
        dataframe[column] = converted

        if column_invalid_indices:
            invalid_rows[column] = column_invalid_indices
    return invalid_rows
