"""
Service functions for deriving reference candidates from processed fact data.

This module provides pure functions for extracting unique reference table
candidates from processed annuity performance fact data. The functions
handle deduplication, field mapping, and data validation.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import AnnuityPlanCandidate, PortfolioCandidate

logger = logging.getLogger(__name__)


def derive_plan_candidates(
    processed_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Derive unique annuity plan candidates from processed fact data with
    enhanced business logic.

    Enhanced derivation logic:
    - 客户名称: Most frequent value with tie-breaking by maximum 期末资产规模
    - 主拓代码, 主拓机构: From the row with maximum 期末资产规模
    - 备注: Date formatted as YYMM_新建 from 月度 field
    - 管理资格: Filtered business types in specific order joined with '+'

    Args:
        processed_rows: List of processed annuity performance fact dictionaries

    Returns:
        List of dictionaries ready for insertion into 年金计划 table

    Raises:
        ValueError: If input data is invalid
    """
    if not processed_rows:
        logger.info("No processed rows provided for plan candidate derivation")
        return []

    if not isinstance(processed_rows, list):
        raise ValueError("Processed rows must be a list")

    # Group by plan code for aggregation
    grouped_data = defaultdict(list)
    for row in processed_rows:
        plan_code = row.get("计划代码")
        if plan_code:
            plan_code = str(plan_code).strip()
            if plan_code:
                grouped_data[plan_code].append(row)

    candidates = []
    for plan_code, rows in grouped_data.items():
        try:
            # Find the row with maximum 期末资产规模 for tie-break and 主拓派生
            max_row = _row_with_max_numeric(rows, "期末资产规模")
            # Pick first non-null 月度 for remark
            month_value = next(
                (r.get("月度") for r in rows if r.get("月度") is not None), None
            )

            candidate = {
                # FIXED: Use only the actual database field, remove duplicate 计划代码
                "年金计划号": plan_code,
                # BUSINESS RULE: Most frequent 客户名称, tie-break by max 期末资产规模
                "客户名称": _get_most_frequent_with_tiebreak(
                    rows, "客户名称", "期末资产规模"
                ),
                # BUSINESS RULE: From row with max 期末资产规模
                # 主拓代码 <- 该行的 机构代码； 主拓机构 <- 该行的 机构名称
                "主拓代码": (
                    str(max_row.get("机构代码")).strip()
                    if max_row and max_row.get("机构代码")
                    else None
                ),
                "主拓机构": (
                    str(max_row.get("机构名称")).strip()
                    if max_row and max_row.get("机构名称")
                    else None
                ),
                # BUSINESS RULE: Format as YYMM_新建 from 月度 (first non-null)
                "备注": _format_remark_from_date(month_value),
                # BUSINESS RULE: Filter and order business types (FIXED: use
                # actual database field)
                "管理资格": _format_qualification_from_business_types(
                    {row.get("业务类型") for row in rows}
                ),
                # Standard fields from first available row
                "计划全称": next(
                    (row.get("计划名称") for row in rows if row.get("计划名称")), None
                ),
                "计划类型": next(
                    (row.get("计划类型") for row in rows if row.get("计划类型")), None
                ),
                "company_id": next(
                    (row.get("company_id") for row in rows if row.get("company_id")),
                    None,
                ),
            }
            candidates.append(candidate)

        except Exception as e:
            logger.warning("Error processing plan %s candidates: %s", plan_code, e)
            continue

    logger.info(
        f"Derived {len(candidates)} enhanced plan candidates "
        f"from {len(processed_rows)} processed rows"
    )

    return candidates


def _get_most_frequent_with_tiebreak(
    rows: List[Dict[str, Any]], value_col: str, tiebreak_col: str
) -> Optional[str]:
    """
    Find most frequent value in value_col, break ties with max tiebreak_col.

    Uses deterministic tie-breaking logic:
    1. Find all values with maximum frequency
    2. If multiple values tied for max frequency, select the one from
       the row with the maximum tiebreak_col value

    Args:
        rows: List of row dictionaries to analyze
        value_col: Column name to find most frequent value for
        tiebreak_col: Column name to use for tie-breaking (numeric)

    Returns:
        Most frequent value, or None if no valid values found
    """
    if not rows:
        return None

    # Extract non-null values
    values = [row.get(value_col) for row in rows if row.get(value_col)]
    if not values:
        return None

    # Count frequencies
    counts = Counter(values)
    max_freq = max(counts.values())

    # Get all values with max frequency
    tied_values = [val for val, freq in counts.items() if freq == max_freq]

    if len(tied_values) == 1:
        return tied_values[0]

    # Tie-breaking: find rows with tied values, get max tiebreak_col
    tied_rows = [row for row in rows if row.get(value_col) in tied_values]

    # CRITICAL: Handle numeric conversion and comparison safely
    max_row = max(tied_rows, key=lambda r: _safe_numeric(r.get(tiebreak_col)))
    return max_row.get(value_col)


def _get_value_from_max_row(
    rows: List[Dict[str, Any]], max_col: str, target_col: str
) -> Optional[str]:
    """
    Get target_col value from the row with maximum max_col value.

    Args:
        rows: List of row dictionaries to analyze
        max_col: Column to find maximum value for (numeric)
        target_col: Column to extract value from the max row

    Returns:
        target_col value from max row, or None if no valid rows
    """
    if not rows:
        return None

    # Find row with maximum value in max_col
    valid_rows = [row for row in rows if row.get(max_col) is not None]
    if not valid_rows:
        return None

    max_row = max(valid_rows, key=lambda r: _safe_numeric(r.get(max_col)))
    return max_row.get(target_col)


def _row_with_max_numeric(
    rows: List[Dict[str, Any]], max_col: str
) -> Optional[Dict[str, Any]]:
    """Return the row having maximum numeric value in max_col.

    Falls back to first row when conversion fails for all.
    """
    if not rows:
        return None
    valid = [r for r in rows if r.get(max_col) is not None]
    if not valid:
        return rows[0]
    return max(valid, key=lambda r: _safe_numeric(r.get(max_col)))


def _format_remark_from_date(date_input: Any) -> Optional[str]:
    """
    Convert date input to YYMM_新建 format.

    Handles various input formats:
    - datetime objects
    - YYYYMM integer/string format
    - ISO date strings
    - Other parseable date formats

    Args:
        date_input: Date in various formats

    Returns:
        Formatted string as "YYMM_新建" or None if parsing fails
    """
    if not date_input:
        return None

    try:
        # Handle datetime objects directly
        if hasattr(date_input, "year") and hasattr(date_input, "month"):
            dt_obj = date_input
        # Handle string/int YYYYMM format (202411 -> 2024-11)
        elif str(date_input).isdigit() and len(str(date_input)) == 6:
            year_month = str(date_input)
            year = int(year_month[:4])
            month = int(year_month[4:6])
            dt_obj = datetime(year, month, 1)
        # Handle other date string formats
        else:
            # Try to parse as date string
            date_str = str(date_input).strip()
            if not date_str:
                return None
            # Simple parsing for common formats
            if "-" in date_str:
                parts = date_str.split("-")
                if len(parts) >= 2:
                    year = int(parts[0])
                    month = int(parts[1])
                    dt_obj = datetime(year, month, 1)
                else:
                    return None
            else:
                return None

        # Format as YYMM_新建
        return f"{dt_obj.year % 100:02d}{dt_obj.month:02d}_新建"

    except (ValueError, TypeError, AttributeError):
        logger.debug(f"Failed to parse date input: {date_input}")
        return None  # Graceful degradation


def _format_qualification_from_business_types(business_types_set: set) -> Optional[str]:
    """
    Filter business types and join in specific order.

    BUSINESS RULE: Only include specific business types in predefined order.
    Order must be preserved as specified in business requirements.

    Args:
        business_types_set: Set of business type strings

    Returns:
        Filtered business types joined with '+', or None if no valid types
    """
    if not business_types_set:
        return None

    # Remove None values and empty strings from the set
    cleaned_set = {bt for bt in business_types_set if bt and str(bt).strip()}
    if not cleaned_set:
        return None

    # BUSINESS RULE: Specific order must be preserved
    ALLOWED_ORDER = ["企年受托", "企年投资", "职年受托", "职年投资"]

    # PATTERN: Iterate through order list, not input set
    filtered = [bt for bt in ALLOWED_ORDER if bt in cleaned_set]

    return "+".join(filtered) if filtered else None


def _safe_numeric(value: Any) -> float:
    """
    Safely convert value to numeric for comparison, handling edge cases.

    Args:
        value: Value to convert to numeric

    Returns:
        Numeric value, or negative infinity if conversion fails
    """
    if value is None:
        return float("-inf")

    try:
        # Handle string representations of numbers
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return float("-inf")

        return float(value)
    except (ValueError, TypeError):
        return float("-inf")  # Ensures failed conversions sort last


def derive_portfolio_candidates(
    processed_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Derive unique portfolio candidates from processed fact data with
    enhanced business logic.

    Business rules for portfolio derivation:
    - 年金计划号: From 计划代码 field in fact data
    - 组合代码: From 组合代码 field in fact data (primary key)
    - 组合名称: From 组合名称 field in fact data
    - 组合类型: From 组合类型 field in fact data
    - 备注: Generated from 月度 field, formatted as "YYMM_新建"
    - 运作开始日: Not derived, remains NULL

    Args:
        processed_rows: List of processed annuity performance fact dictionaries

    Returns:
        List of dictionaries ready for insertion into 组合计划 table

    Raises:
        ValueError: If input data is invalid
    """
    if not processed_rows:
        logger.info("No processed rows provided for portfolio candidate derivation")
        return []

    if not isinstance(processed_rows, list):
        raise ValueError("Processed rows must be a list")

    # Group by portfolio code for aggregation
    grouped_data = defaultdict(list)
    for row in processed_rows:
        portfolio_code = row.get("组合代码")
        if portfolio_code:
            portfolio_code = str(portfolio_code).strip()
            if portfolio_code:
                grouped_data[portfolio_code].append(row)

    candidates = []
    for portfolio_code, rows in grouped_data.items():
        try:
            # Pick first non-null 月度 for remark generation
            month_value = next(
                (r.get("月度") for r in rows if r.get("月度") is not None), None
            )

            # Get plan code from first available row
            plan_code = next(
                (r.get("计划代码") for r in rows if r.get("计划代码")), None
            )
            if not plan_code:
                logger.debug(
                    f"Portfolio {portfolio_code}: skipping due to missing 计划代码"
                )
                continue

            candidate = {
                # Primary key
                "组合代码": portfolio_code,
                # Foreign key to 年金计划 table
                "年金计划号": str(plan_code).strip(),
                # Portfolio attributes from first available non-null values
                "组合名称": next(
                    (row.get("组合名称") for row in rows if row.get("组合名称")), None
                ),
                "组合类型": next(
                    (row.get("组合类型") for row in rows if row.get("组合类型")), None
                ),
                # BUSINESS RULE: Format as YYMM_新建 from 月度 (first non-null)
                "备注": _format_remark_from_date(month_value),
                # Not derived from fact data, remains NULL for backfill
                "运作开始日": None,
            }
            candidates.append(candidate)

        except Exception as e:
            logger.warning(
                f"Error processing portfolio {portfolio_code} candidates: {e}"
            )
            continue

    logger.info(
        f"Derived {len(candidates)} enhanced portfolio candidates "
        f"from {len(processed_rows)} processed rows"
    )

    return candidates


def validate_plan_candidates(
    candidates: List[Dict[str, Any]],
) -> List[AnnuityPlanCandidate]:
    """
    Validate plan candidates using Pydantic models.

    Args:
        candidates: List of plan candidate dictionaries

    Returns:
        List of validated AnnuityPlanCandidate models

    Raises:
        ValidationError: If validation fails for any candidate
    """
    validated = []
    for i, candidate in enumerate(candidates):
        try:
            validated.append(AnnuityPlanCandidate(**candidate))
        except Exception as e:
            logger.error(f"Plan candidate {i} validation failed: {e}")
            raise

    return validated


def validate_portfolio_candidates(
    candidates: List[Dict[str, Any]],
) -> List[PortfolioCandidate]:
    """
    Validate portfolio candidates using Pydantic models.

    Args:
        candidates: List of portfolio candidate dictionaries

    Returns:
        List of validated PortfolioCandidate models

    Raises:
        ValidationError: If validation fails for any candidate
    """
    validated = []
    for i, candidate in enumerate(candidates):
        try:
            validated.append(PortfolioCandidate(**candidate))
        except Exception as e:
            logger.error(f"Portfolio candidate {i} validation failed: {e}")
            raise

    return validated
