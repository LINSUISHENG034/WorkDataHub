"""
Shared validators and constants for domain model data cleansing.

This module provides common validation functions and constants used across
multiple domain models to eliminate code duplication and ensure consistency.

Created in Story 7.3-2 to consolidate duplicate validators from
annuity_performance and annuity_income domain models.

Reference: docs/sprint-artifacts/stories/7.3-2-extract-shared-validators.md
"""

from typing import Any, List, Optional

from work_data_hub.infrastructure.cleansing.registry import (
    get_cleansing_registry,
)

# ============================================================================
# Shared Constants
# ============================================================================

# Company name cleansing rules
DEFAULT_COMPANY_RULES = ["trim_whitespace", "normalize_company_name"]

# Numeric field cleansing rules (minimal common subset)
# Note: annuity_performance includes "handle_percentage_conversion",
# but annuity_income does not. Domain-specific rules should be added
# via fallback_rules parameter.
DEFAULT_NUMERIC_RULES: List[Any] = [
    "standardize_null_values",
    "remove_currency_symbols",
    "clean_comma_separated_number",
]

# Date validation constants (Story 7.1-16)
MIN_YYYYMM_VALUE = 200000  # Minimum valid YYYYMM value (January 2000)
MAX_YYYYMM_VALUE = 999999  # Maximum valid YYYYMM value
MAX_DATE_RANGE_DAYS = 3650  # Approximately 10 years


# ============================================================================
# Shared Validator Functions
# ============================================================================


def apply_domain_rules(
    value: Any,
    field_name: str,
    domain: str,
    fallback_rules: Optional[List[Any]] = None,
) -> Any:
    """Apply cleansing rules from registry for a specific domain.

    This generic function applies domain-specific cleansing rules from the
    cleansing registry. If no domain-specific rules are found, it falls back
    to the provided fallback_rules.

    Args:
        value: The value to cleanse
        field_name: Field name for rule lookup
        domain: Domain name for registry lookup (e.g., "annuity_performance")
        fallback_rules: Default rules if no domain-specific rules found

    Returns:
        Cleansed value

    Example:
        >>> cleaned = apply_domain_rules(
        ...     " ACME Corp ",
        ...     "客户名称",
        ...     "annuity_performance",
        ...     fallback_rules=["trim_whitespace"]
        ... )
    """
    registry = get_cleansing_registry()
    rules = registry.get_domain_rules(domain, field_name)
    if not rules:
        rules = fallback_rules or []
    if not rules:
        return value
    return registry.apply_rules(value, rules, field_name=field_name)


def clean_code_field(v: Any) -> Optional[str]:
    """Bronze layer code field cleaner.

    Removes whitespace from code fields, returns None for empty strings.
    Used for fields like 组合代码, 计划代码, 公司代码, 机构代码, 产品线代码, etc.

    Args:
        v: Input value (string, number, etc.)

    Returns:
        Cleaned string or None if input was None or empty after stripping

    Examples:
        >>> clean_code_field("  ABC123  ")
        'ABC123'
        >>> clean_code_field(12345)
        '12345'
        >>> clean_code_field("   ")
        None
        >>> clean_code_field(None)
        None
    """
    if v is None:
        return None
    s_val = str(v).strip()
    return s_val if s_val else None


def normalize_plan_code(v: Optional[str], allow_null: bool = False) -> Optional[str]:
    """Gold layer plan code normalizer.

    Normalizes plan codes by:
    - Converting to uppercase
    - Removing hyphens, underscores, spaces
    - Keeping dots and Chinese parentheses

    Args:
        v: Input plan code
        allow_null: If True, allows None values; if False (default), None is rejected
                    Default is False to preserve annuity_income strict behavior.

    Returns:
        Normalized plan code or None (if allow_null=True)

    Raises:
        ValueError: If normalized code is empty or only special characters

    Examples:
        >>> normalize_plan_code("abc-def")
        'ABCDEF'
        >>> normalize_plan_code("ABC _-DEF")
        'ABCDEF'
        >>> normalize_plan_code("ABC（DEF）")
        'ABC（DEF）'
        >>> normalize_plan_code(None, allow_null=True)
        None
        >>> normalize_plan_code(None, allow_null=False)
        Traceback (most recent call last):
            ...
        ValueError: Plan code cannot be None
    """
    if v is None:
        if allow_null:
            return v
        raise ValueError("Plan code cannot be None")

    normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
    if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
        raise ValueError(f"Plan code cannot be empty after normalization: {v}")
    return normalized


def normalize_company_id(v: Optional[str]) -> Optional[str]:
    """Validate and normalize company_id format.

    Valid formats:
    - Numeric ID: e.g., "614810477"
    - Temp ID: "IN<16-char-Base32>", e.g., "INABCDEFGHIJKLMNOP"

    Args:
        v: Input company_id

    Returns:
        Uppercase company_id or None if input was None

    Raises:
        ValueError: If company_id is empty after stripping whitespace

    Examples:
        >>> normalize_company_id("abc123")
        'ABC123'
        >>> normalize_company_id(None)
        None
        >>> normalize_company_id("   ")
        Traceback (most recent call last):
            ...
        ValueError: company_id cannot be empty
    """
    if v is None:
        return v
    normalized = v.upper()
    if not normalized.strip():
        raise ValueError(f"company_id cannot be empty: {v}")
    return normalized


def clean_customer_name(
    v: Any,
    field_name: str,
    domain: str,
    fallback_rules: Optional[List[Any]] = None,
) -> Optional[str]:
    """Gold layer customer name cleaner with domain rules.

    Applies domain-specific cleansing rules from the registry, falling back
    to DEFAULT_COMPANY_RULES if no domain-specific rules are configured.

    Args:
        v: Input customer name
        field_name: Field name for rule lookup (typically "客户名称")
        domain: Domain name for registry lookup
        fallback_rules: Optional custom rules; defaults to DEFAULT_COMPANY_RULES

    Returns:
        Cleansed customer name or None if input was None

    Raises:
        ValueError: If cleansing fails

    Examples:
        >>> clean_customer_name(
        ...     " ACME Corp ",
        ...     "客户名称",
        ...     "annuity_performance"
        ... )
        'ACME Corp'
    """
    if v is None:
        return v

    if fallback_rules is None:
        fallback_rules = DEFAULT_COMPANY_RULES

    try:
        return apply_domain_rules(v, field_name, domain, fallback_rules)
    except Exception as e:
        raise ValueError(
            f"Field '{field_name}': Cannot clean company name '{v}'. Error: {e}"
        )
