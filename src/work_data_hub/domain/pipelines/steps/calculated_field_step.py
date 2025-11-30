"""
Generic DataFrame calculated field step for configuration-driven field calculations.

Story 1.12: Implement Standard Domain Generic Steps
Architecture Decision #9: Standard Domain Architecture Pattern

This step provides a reusable, configuration-driven approach to adding
calculated fields to DataFrames using lambda functions or callable objects.

Example Usage:
    >>> from work_data_hub.domain.pipelines.steps import DataFrameCalculatedFieldStep
    >>>
    >>> calculated_fields = {
    ...     'annualized_return': lambda df: df['investment_income'] / df['ending_assets'],
    ...     'asset_change': lambda df: df['ending_assets'] - df['beginning_assets']
    ... }
    >>> step = DataFrameCalculatedFieldStep(calculated_fields)
    >>> df_out = step.execute(df_in, context)
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Union

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext

logger = structlog.get_logger(__name__)

# Type alias for calculation functions
CalculationFunc = Callable[[pd.DataFrame], Union[pd.Series, Any]]


class DataFrameCalculatedFieldStep:
    """
    Generic step that adds calculated fields using lambda functions or vectorized operations.

    This step implements the DataFrameStep protocol and enables vectorized
    calculations by passing the entire DataFrame to calculation functions.

    Attributes:
        calculated_fields: Dictionary mapping field names to calculation functions.

    Pass Criteria (AC-1.12.3):
        - Accepts dict mapping field_name -> calculation_function
        - Calculation functions receive entire DataFrame (enabling vectorized operations)
        - Handles errors gracefully (e.g., division by zero, missing columns)
        - Returns new DataFrame with additional calculated columns
    """

    def __init__(self, calculated_fields: Dict[str, CalculationFunc]) -> None:
        """
        Initialize the calculated field step with field definitions.

        Args:
            calculated_fields: Dictionary mapping field_name -> calculation_function.
                              Each function receives the DataFrame and returns a Series or scalar.
                              Example: {'total': lambda df: df['a'] + df['b']}

        Raises:
            TypeError: If calculated_fields is not a dictionary.
            ValueError: If calculated_fields is empty.
            TypeError: If any calculation is not callable.
        """
        if not isinstance(calculated_fields, dict):
            raise TypeError(
                f"calculated_fields must be a dict, got {type(calculated_fields).__name__}"
            )
        if not calculated_fields:
            raise ValueError("calculated_fields cannot be empty")

        # Validate all calculations are callable
        for field_name, calc_func in calculated_fields.items():
            if not callable(calc_func):
                raise TypeError(
                    f"Calculation for field '{field_name}' must be callable, "
                    f"got {type(calc_func).__name__}"
                )

        self._calculated_fields = calculated_fields

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "DataFrameCalculatedFieldStep"

    def execute(
        self,
        dataframe: pd.DataFrame,
        context: PipelineContext,
    ) -> pd.DataFrame:
        """
        Add calculated fields to the DataFrame.

        Args:
            dataframe: Input DataFrame to transform.
            context: Pipeline execution context.

        Returns:
            New DataFrame with additional calculated columns.
            Original DataFrame is not modified.
        """
        log = logger.bind(
            step=self.name,
            pipeline=context.pipeline_name,
            execution_id=context.execution_id,
        )

        # Create a copy to ensure immutability
        result = dataframe.copy()

        successful_fields: list[str] = []
        failed_fields: list[str] = []

        for field_name, calc_func in self._calculated_fields.items():
            try:
                # Execute the calculation function with the DataFrame
                calculated_value = calc_func(result)
                result[field_name] = calculated_value
                successful_fields.append(field_name)

                log.debug(
                    "calculated_field_added",
                    field_name=field_name,
                )

            except KeyError as e:
                # Missing column referenced in calculation
                failed_fields.append(field_name)
                log.error(
                    "calculated_field_failed_missing_column",
                    field_name=field_name,
                    missing_column=str(e),
                    error_type="KeyError",
                )

            except ZeroDivisionError:
                # Division by zero - pandas handles this with inf/nan, but log it
                failed_fields.append(field_name)
                log.error(
                    "calculated_field_failed_division_by_zero",
                    field_name=field_name,
                    error_type="ZeroDivisionError",
                )

            except Exception as e:
                # Catch-all for other calculation errors
                failed_fields.append(field_name)
                log.error(
                    "calculated_field_failed",
                    field_name=field_name,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )

        log.info(
            "calculated_fields_complete",
            successful_count=len(successful_fields),
            failed_count=len(failed_fields),
            successful_fields=successful_fields,
            failed_fields=failed_fields if failed_fields else None,
        )

        return result
