"""
Generic DataFrame filter step for configuration-driven row filtering.

Story 1.12: Implement Standard Domain Generic Steps
Architecture Decision #9: Standard Domain Architecture Pattern

This step provides a reusable, configuration-driven approach to filtering
DataFrame rows based on boolean conditions.

Example Usage:
    >>> from work_data_hub.domain.pipelines.steps import DataFrameFilterStep
    >>>
    >>> filter_condition = lambda df: (df['ending_assets'] > 0) & (df['report_date'] >= '2025-01-01')
    >>> step = DataFrameFilterStep(filter_condition)
    >>> df_out = step.execute(df_in, context)
"""

from __future__ import annotations

from typing import Callable, Union

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext

logger = structlog.get_logger(__name__)

# Type alias for filter functions
FilterFunc = Callable[[pd.DataFrame], Union[pd.Series, bool]]


class DataFrameFilterStep:
    """
    Generic step that filters rows based on boolean conditions.

    This step implements the DataFrameStep protocol and uses Pandas boolean
    indexing for optimal performance.

    Attributes:
        filter_condition: Function that returns a boolean Series for filtering.

    Pass Criteria (AC-1.12.4):
        - Accepts lambda function returning boolean Series
        - Uses df[condition] (Pandas boolean indexing)
        - Logs number of rows filtered out
        - Returns new DataFrame (does not mutate input)
    """

    def __init__(
        self,
        filter_condition: FilterFunc,
        description: str = "custom filter",
    ) -> None:
        """
        Initialize the filter step with a filter condition.

        Args:
            filter_condition: Function that receives DataFrame and returns boolean Series.
                             Rows where the condition is True are kept.
                             Example: lambda df: df['value'] > 0
            description: Human-readable description of the filter for logging.

        Raises:
            TypeError: If filter_condition is not callable.
        """
        if not callable(filter_condition):
            raise TypeError(
                f"filter_condition must be callable, got {type(filter_condition).__name__}"
            )

        self._filter_condition = filter_condition
        self._description = description

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "DataFrameFilterStep"

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        """
        Filter DataFrame rows based on the configured condition.

        Args:
            dataframe: Input DataFrame to filter.
            context: Pipeline execution context.

        Returns:
            New DataFrame with only rows matching the condition.
            Original DataFrame is not modified.
        """
        log = logger.bind(
            step=self.name,
            pipeline=context.pipeline_name,
            execution_id=context.execution_id,
            filter_description=self._description,
        )

        rows_before = len(dataframe)

        try:
            # Apply the filter condition
            condition = self._filter_condition(dataframe)

            # Use boolean indexing (Pandas vectorized operation)
            result = dataframe[condition].copy()

            rows_after = len(result)
            rows_filtered = rows_before - rows_after

            log.info(
                "rows_filtered",
                rows_before=rows_before,
                rows_after=rows_after,
                rows_filtered_out=rows_filtered,
                filter_description=self._description,
            )

            return result

        except KeyError as e:
            # Missing column referenced in filter
            log.error(
                "filter_failed_missing_column",
                missing_column=str(e),
                error_type="KeyError",
            )
            # Return copy of original DataFrame on error
            return dataframe.copy()

        except Exception as e:
            # Catch-all for other filter errors
            log.error(
                "filter_failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            # Return copy of original DataFrame on error
            return dataframe.copy()
