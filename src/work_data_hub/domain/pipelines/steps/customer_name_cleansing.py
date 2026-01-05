"""
Customer name cleansing step for cleaning company/customer names.

This module provides a reusable transformation step that cleans
customer names by removing common suffixes and normalizing format.

.. deprecated:: 2026-01-05
    The clean_company_name function now delegates to normalize_customer_name
    from infrastructure.cleansing.normalizers for unified behavior.
"""

import warnings
from typing import Any, Dict, List

import structlog

from work_data_hub.domain.pipelines.types import Row, StepResult, TransformStep
from work_data_hub.infrastructure.cleansing.normalizers import (
    normalize_customer_name,
)

logger = structlog.get_logger(__name__)


def clean_company_name(name: str) -> str:
    """
    Basic company name cleaning.

    .. deprecated:: 2026-01-05
        This function now delegates to normalize_customer_name from
        infrastructure.cleansing.normalizers for unified behavior.

    Args:
        name: The company name to clean

    Returns:
        Cleaned company name

    Example:
        >>> clean_company_name("某某公司及下属子企业")
        '某某公司'
    """
    if not name:
        return ""

    warnings.warn(
        "clean_company_name is deprecated. "
        "Use normalize_customer_name from infrastructure.cleansing.normalizers instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return normalize_customer_name(name)


class CustomerNameCleansingStep(TransformStep):
    """
    Clean customer names and create account name field.

    Applies customer name cleaning logic from legacy cleaner:
    - Copy 客户名称 to 年金账户名 (preserve original)
    - Clean 客户名称 using clean_company_name function

    This step is domain-agnostic and can be configured to work
    with different source and target field names.

    Example:
        >>> step = CustomerNameCleansingStep()
        >>> result = step.apply({"客户名称": "某公司已转出"}, {})
        >>> result.row["客户名称"]
        '某公司'
        >>> result.row["年金账户名"]
        '某公司已转出'
    """

    def __init__(
        self,
        source_field: str = "客户名称",
        account_name_field: str = "年金账户名",
    ) -> None:
        """
        Initialize with optional custom field names.

        Args:
            source_field: The field containing the customer name to clean.
                         Defaults to "客户名称" for legacy compatibility.
            account_name_field: The field to copy original name to.
                               Defaults to "年金账户名" for legacy compatibility.
        """
        self._source_field = source_field
        self._account_name_field = account_name_field

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "customer_name_cleansing"

    @property
    def source_field(self) -> str:
        """Return the source field name."""
        return self._source_field

    @property
    def account_name_field(self) -> str:
        """Return the account name field name."""
        return self._account_name_field

    def apply(self, row: Row, context: Dict[str, Any]) -> StepResult:
        """
        Apply customer name cleansing.

        Args:
            row: The input row dictionary to transform
            context: Pipeline context (unused by this step)

        Returns:
            StepResult with cleaned customer name and preserved account name
        """
        try:
            updated_row = {**row}
            warnings: List[str] = []

            if self._source_field in updated_row:
                original_name = updated_row[self._source_field]

                # Step 1: Copy to account name field (preserve original)
                updated_row[self._account_name_field] = original_name

                # Step 2: Clean customer name
                if isinstance(original_name, str):
                    cleaned_name = clean_company_name(original_name)
                    updated_row[self._source_field] = cleaned_name

                    if cleaned_name != original_name:
                        warnings.append(
                            f"Cleaned customer name: {original_name} -> {cleaned_name}"
                        )

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"name_cleanings": len(warnings)},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Customer name cleansing failed: {e}"])
