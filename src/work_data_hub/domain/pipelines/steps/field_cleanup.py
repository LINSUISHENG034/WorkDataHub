"""
Field cleanup step for removing invalid columns and finalizing records.

This module provides a reusable transformation step that removes
specified columns from the data and prepares records for final output.
"""

from typing import Any, Dict, List

import structlog

from work_data_hub.domain.pipelines.types import Row, StepResult, TransformStep

logger = structlog.get_logger(__name__)


class FieldCleanupStep(TransformStep):
    """
    Remove invalid columns and finalize record structure.

    Removes specified columns from the data. Default configuration
    removes the same columns dropped in legacy cleaner:
    ['备注', '子企业号', '子企业名称', '集团企业客户号', '集团企业客户名称']

    This step is domain-agnostic and can be configured to remove
    any set of columns from the data.

    Example:
        >>> step = FieldCleanupStep()
        >>> result = step.apply({"客户名称": "某公司", "备注": "test"}, {})
        >>> "备注" in result.row
        False
    """

    # Default columns to drop (matches legacy cleaner behavior)
    DEFAULT_COLUMNS_TO_DROP = [
        "备注",
        "子企业号",
        "子企业名称",
        "集团企业客户号",
        "集团企业客户名称",
    ]

    def __init__(self, columns_to_drop: List[str] | None = None) -> None:
        """
        Initialize with columns to drop.

        Args:
            columns_to_drop: List of column names to remove from output.
                            If None, uses DEFAULT_COLUMNS_TO_DROP.
        """
        self._columns_to_drop = columns_to_drop or self.DEFAULT_COLUMNS_TO_DROP.copy()

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "field_cleanup"

    @property
    def columns_to_drop(self) -> List[str]:
        """Return the columns configured to be dropped."""
        return self._columns_to_drop

    def apply(self, row: Row, context: Dict[str, Any]) -> StepResult:
        """
        Remove invalid fields from final record.

        Args:
            row: The input row dictionary to transform
            context: Pipeline context (unused by this step)

        Returns:
            StepResult with specified fields removed
        """
        try:
            updated_row = {**row}
            warnings: List[str] = []
            dropped_count = 0

            # Remove specified columns (exact match from legacy)
            for col_name in self._columns_to_drop:
                if col_name in updated_row:
                    updated_row.pop(col_name)
                    dropped_count += 1
                    warnings.append(f"Dropped invalid field: {col_name}")

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"dropped_fields": dropped_count},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Field cleanup failed: {e}"])
