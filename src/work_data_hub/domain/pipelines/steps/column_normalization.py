"""
Column normalization step for standardizing legacy column names.

This module provides a reusable transformation step that normalizes
column names from legacy data formats to the standard WorkDataHub format.
"""

from typing import Any, Dict, List

import structlog

from work_data_hub.domain.pipelines.types import Row, StepResult, TransformStep

logger = structlog.get_logger(__name__)


class ColumnNormalizationStep(TransformStep):
    """
    Normalize legacy column names to standardized format.

    Replicates the column renaming logic from legacy cleaner:
    - '机构' -> '机构名称'
    - '计划号' -> '计划代码'
    - '流失（含待遇支付）' -> '流失(含待遇支付)'

    This step is domain-agnostic and can be reused across different
    data pipelines that need to standardize Chinese column names.

    Example:
        >>> step = ColumnNormalizationStep()
        >>> result = step.apply({"机构": "北京分公司"}, {})
        >>> result.row["机构名称"]
        '北京分公司'
    """

    def __init__(self, column_mappings: Dict[str, str] | None = None) -> None:
        """
        Initialize with optional custom column mappings.

        Args:
            column_mappings: Custom column name mappings (old_name -> new_name).
                             If None, uses default legacy column mappings.
        """
        self._column_mappings = column_mappings or {
            "机构": "机构名称",
            "计划号": "计划代码",
            "流失（含待遇支付）": "流失(含待遇支付)",
        }

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "column_normalization"

    @property
    def column_mappings(self) -> Dict[str, str]:
        """Return the column mappings used by this step."""
        return self._column_mappings

    def apply(self, row: Row, context: Dict[str, Any]) -> StepResult:
        """
        Apply column name normalization to a row.

        Args:
            row: The input row dictionary to transform
            context: Pipeline context (unused by this step)

        Returns:
            StepResult with normalized column names
        """
        try:
            updated_row = {**row}
            warnings: List[str] = []

            # Apply column renaming
            renamed_count = 0
            for old_name, new_name in self._column_mappings.items():
                if old_name in updated_row:
                    updated_row[new_name] = updated_row.pop(old_name)
                    renamed_count += 1
                    logger.debug(f"Renamed column: {old_name} -> {new_name}")

            if renamed_count > 0:
                warnings.append(
                    f"Renamed {renamed_count} legacy column names to standard format"
                )

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"renamed_columns": renamed_count},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Column normalization failed: {e}"])
