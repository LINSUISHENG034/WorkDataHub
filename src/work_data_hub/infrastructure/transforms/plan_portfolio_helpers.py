"""Shared transform helpers for plan code and portfolio code normalization.

Story 7.4-6: Extracted from domain-specific pipeline_builder.py files
to establish single source of truth for cross-domain transformations.

Canonical implementation chosen: annuity_performance approach
- More robust type handling via _clean_portfolio_code() helper
- Better empty mask handling (isna() | == "")
- Preserves numeric portfolio codes (12345 → "12345")
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from work_data_hub.infrastructure.mappings import (
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    PLAN_CODE_DEFAULTS,
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)


def apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes based on plan type (legacy parity).

    Empty/null plan codes get defaults based on plan type:
    - 集合计划 → "AN001"
    - 单一计划 → "AN002"

    Args:
        df: DataFrame with '计划代码' and optionally '计划类型' columns.

    Returns:
        Series with normalized plan codes.
    """
    if "计划代码" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["计划代码"].copy()

    if "计划类型" in df.columns:
        # Empty/null plan codes get defaults based on plan type
        # Note: Legacy only checks for isna() and empty string, NOT string "None"
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, PLAN_CODE_DEFAULTS["集合计划"])
        result = result.mask(single_mask, PLAN_CODE_DEFAULTS["单一计划"])

    return result


def apply_portfolio_code_defaults(
    df: pd.DataFrame,
    portfolio_col: str = "组合代码",
    business_type_col: str = "业务类型",
    plan_type_col: str = "计划类型",
) -> pd.Series:
    """Apply default portfolio codes based on business type and plan type.

    Improvements over Legacy (annuity_performance approach):
    1. Preserves numeric portfolio codes (e.g., 12345 stays 12345, not NaN)
    2. Handles mixed data types robustly via _clean_portfolio_code() helper
    3. Strips whitespace and handles edge cases
    4. Better data type consistency

    Default logic:
    - 职年受托/职年投资 → 'QTAN003' (highest priority)
    - 职业年金 → 'QTAN003' (already handled, skip in loop)
    - Other plan types → DEFAULT_PORTFOLIO_CODE_MAPPING

    Args:
        df: DataFrame with portfolio, business type, and plan type columns.
        portfolio_col: Name of portfolio code column (default: "组合代码").
        business_type_col: Name of business type column (default: "业务类型").
        plan_type_col: Name of plan type column (default: "计划类型").

    Returns:
        Series with normalized portfolio codes.
    """
    if portfolio_col not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df[portfolio_col].copy()

    # Improved processing: handle each value type appropriately
    result = result.apply(lambda x: _clean_portfolio_code(x))

    # Apply defaults based on business type and plan type
    empty_mask = result.isna() | (result == "")

    if business_type_col in df.columns:
        # QTAN003 for 职年受托/职年投资 (highest priority)
        qtan003_mask = empty_mask & df[business_type_col].isin(
            PORTFOLIO_QTAN003_BUSINESS_TYPES
        )
        result = result.mask(qtan003_mask, "QTAN003")

    if plan_type_col in df.columns:
        # Default based on plan type for remaining empty values
        still_empty = result.isna() | (result == "")
        for plan_type, default_code in DEFAULT_PORTFOLIO_CODE_MAPPING.items():
            if plan_type != "职业年金":  # Already handled by QTAN003
                type_mask = still_empty & (df[plan_type_col] == plan_type)
                result = result.mask(type_mask, default_code)

    return result


def _clean_portfolio_code(value) -> Optional[str]:  # noqa: PLR0911
    """Clean and normalize portfolio code value.

    Handles:
    - None values
    - Numeric values (preserves them as strings)
    - String values (strips whitespace, removes 'F' prefix)

    Args:
        value: Raw portfolio code value

    Returns:
        Cleaned portfolio code or None if invalid
    """
    # Handle None/NA values and unsupported types (bool, list, dict, etc.)
    try:
        if pd.isna(value):
            return None
    except (ValueError, TypeError):
        # pd.isna can fail on certain types like empty lists
        return None

    if isinstance(value, bool):
        return None

    # Handle numeric values - preserve them as strings
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    # Handle string values
    if isinstance(value, str):
        cleaned = value.strip()
        # Remove 'F' or 'f' prefix if present (Legacy behavior, case-insensitive)
        if cleaned and cleaned.upper().startswith("F"):
            cleaned = cleaned[1:]
        return cleaned or None

    # Return None for any other type
    return None


__all__ = [
    "apply_plan_code_defaults",
    "apply_portfolio_code_defaults",
    "_clean_portfolio_code",  # Exported for testing purposes
]
