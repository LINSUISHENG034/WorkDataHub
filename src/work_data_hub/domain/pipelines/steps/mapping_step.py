"""
Generic DataFrame column mapping step for configuration-driven column renaming.

Story 1.12: Implement Standard Domain Generic Steps
Architecture Decision #9: Standard Domain Architecture Pattern

This step provides a reusable, configuration-driven approach to renaming
DataFrame columns, eliminating the need for domain-specific custom steps
for simple column mapping operations.

Example Usage:
    >>> from work_data_hub.domain.pipelines.steps import DataFrameMappingStep
    >>>
    >>> column_mapping = {
    ...     '月度': 'report_date',
    ...     '计划代码': 'plan_code',
    ...     '客户名称': 'customer_name'
    ... }
    >>> step = DataFrameMappingStep(column_mapping)
    >>> df_out = step.execute(df_in, context)
"""

from __future__ import annotations

from typing import Dict

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext

logger = structlog.get_logger(__name__)


class DataFrameMappingStep:
    """
    Generic step that renames DataFrame columns based on configuration.

    This step implements the DataFrameStep protocol and uses Pandas vectorized
    operations (df.rename) for optimal performance.

    Attributes:
        column_mapping: Dictionary mapping old column names to new column names.

    Pass Criteria (AC-1.12.1):
        - Implements DataFrameStep protocol (name property, execute method)
        - Uses df.rename(columns=mapping) (Pandas vectorized operation)
        - Handles missing columns gracefully: log warning, skip rename
        - Returns new DataFrame (does not mutate input)
    """

    def __init__(self, column_mapping: Dict[str, str]) -> None:
        """
        Initialize the mapping step with column name mappings.

        Args:
            column_mapping: Dictionary mapping old_column_name -> new_column_name.
                           Example: {'月度': 'report_date', '计划代码': 'plan_code'}

        Raises:
            TypeError: If column_mapping is not a dictionary.
            ValueError: If column_mapping is empty.
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
        return "DataFrameMappingStep"

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        """
        Rename DataFrame columns based on the configured mapping.

        Args:
            dataframe: Input DataFrame to transform.
            context: Pipeline execution context.

        Returns:
            New DataFrame with renamed columns. Original DataFrame is not modified.
        """
        log = logger.bind(
            step=self.name,
            pipeline=context.pipeline_name,
            execution_id=context.execution_id,
        )

        # Identify which columns exist in the DataFrame
        existing_columns = set(dataframe.columns)
        mapping_columns = set(self._column_mapping.keys())

        # Find missing columns (in mapping but not in DataFrame)
        missing_columns = mapping_columns - existing_columns
        if missing_columns:
            log.warning(
                "columns_not_found_in_dataframe",
                missing_columns=sorted(missing_columns),
                available_columns=sorted(existing_columns),
            )

        # Build effective mapping (only columns that exist)
        effective_mapping = {
            old: new
            for old, new in self._column_mapping.items()
            if old in existing_columns
        }

        if not effective_mapping:
            log.info("no_columns_to_rename", reason="no matching columns found")
            return dataframe.copy()

        # Perform the rename using Pandas vectorized operation
        result = dataframe.rename(columns=effective_mapping)

        log.info(
            "columns_renamed",
            renamed_count=len(effective_mapping),
            renamed_columns=list(effective_mapping.keys()),
        )

        return result
