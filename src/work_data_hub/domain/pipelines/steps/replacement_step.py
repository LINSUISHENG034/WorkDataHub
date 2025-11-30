"""
Generic DataFrame value replacement step for configuration-driven value mapping.

Story 1.12: Implement Standard Domain Generic Steps
Architecture Decision #9: Standard Domain Architecture Pattern

This step provides a reusable, configuration-driven approach to replacing
values in DataFrame columns, eliminating the need for domain-specific custom
steps for simple value mapping operations.

Example Usage:
    >>> from work_data_hub.domain.pipelines.steps import DataFrameValueReplacementStep
    >>>
    >>> value_replacements = {
    ...     'plan_code': {'OLD_CODE_A': 'NEW_CODE_A', 'OLD_CODE_B': 'NEW_CODE_B'},
    ...     'business_type': {'旧值1': '新值1', '旧值2': '新值2'}
    ... }
    >>> step = DataFrameValueReplacementStep(value_replacements)
    >>> df_out = step.execute(df_in, context)
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext

logger = structlog.get_logger(__name__)


class DataFrameValueReplacementStep:
    """
    Generic step that replaces values in specified columns based on configuration.

    This step implements the DataFrameStep protocol and uses Pandas vectorized
    operations (df.replace) for optimal performance.

    Attributes:
        value_replacements: Dictionary mapping column names to their value mappings.

    Pass Criteria (AC-1.12.2):
        - Uses df.replace(replacement_dict) (Pandas vectorized operation)
        - Supports multiple columns with different mappings
        - Values not in mapping remain unchanged
        - Returns new DataFrame (does not mutate input)
    """

    def __init__(self, value_replacements: Dict[str, Dict[Any, Any]]) -> None:
        """
        Initialize the replacement step with value mappings.

        Args:
            value_replacements: Dictionary mapping column_name -> {old_value: new_value}.
                               Example: {'status': {'draft': 'pending', 'old': 'new'}}

        Raises:
            TypeError: If value_replacements is not a dictionary.
            ValueError: If value_replacements is empty.
        """
        if not isinstance(value_replacements, dict):
            raise TypeError(
                f"value_replacements must be a dict, got {type(value_replacements).__name__}"
            )
        if not value_replacements:
            raise ValueError("value_replacements cannot be empty")

        self._value_replacements = value_replacements

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "DataFrameValueReplacementStep"

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        """
        Replace values in DataFrame columns based on the configured mappings.

        Args:
            dataframe: Input DataFrame to transform.
            context: Pipeline execution context.

        Returns:
            New DataFrame with replaced values. Original DataFrame is not modified.
        """
        log = logger.bind(
            step=self.name,
            pipeline=context.pipeline_name,
            execution_id=context.execution_id,
        )

        # Create a copy to ensure immutability
        result = dataframe.copy()

        # Identify which columns exist in the DataFrame
        existing_columns = set(dataframe.columns)
        replacement_columns = set(self._value_replacements.keys())

        # Find missing columns
        missing_columns = replacement_columns - existing_columns
        if missing_columns:
            log.warning(
                "columns_not_found_for_replacement",
                missing_columns=sorted(missing_columns),
                available_columns=sorted(existing_columns),
            )

        # Process each column that exists
        total_replacements = 0
        for column, mapping in self._value_replacements.items():
            if column not in existing_columns:
                continue

            # Count replacements before applying
            original_values = result[column].copy()

            # Apply replacement using Pandas vectorized operation
            result[column] = result[column].replace(mapping)

            # Count how many values were actually replaced
            replaced_count = (original_values != result[column]).sum()
            total_replacements += replaced_count

            if replaced_count > 0:
                log.debug(
                    "values_replaced_in_column",
                    column=column,
                    replaced_count=int(replaced_count),
                    mapping_keys=list(mapping.keys()),
                )

        log.info(
            "value_replacement_complete",
            columns_processed=len(replacement_columns - missing_columns),
            total_replacements=int(total_replacements),
        )

        return result
