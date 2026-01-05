"""
Legacy-compatible company name normalization for temporary ID generation.

This module provides name normalization functions that ensure consistent
temporary ID generation across different name variants.

.. deprecated:: 2026-01-05
    Use `normalize_customer_name` from `infrastructure.cleansing.normalizers` instead.
    The `normalize_for_temp_id` function is maintained for backwards compatibility
    but will be removed in a future version.

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- Refactor: docs/specific/customer/customer-name-normalization-refactor.md
"""

import base64
import hashlib
import hmac
import warnings

from work_data_hub.infrastructure.cleansing.normalizers import (
    normalize_customer_name,
)

# Legacy constants kept for backwards compatibility (some external code may reference them)
# These are now defined in infrastructure.cleansing.normalizers.customer_name


def normalize_for_temp_id(company_name: str) -> str:
    """
    Normalize company name for temporary ID generation.

    .. deprecated:: 2026-01-05
        Use `normalize_customer_name` from `infrastructure.cleansing.normalizers`
        instead. This function is maintained for backwards compatibility.

    Args:
        company_name: Raw company name to normalize.

    Returns:
        Normalized company name suitable for hashing.

    Examples:
        >>> normalize_for_temp_id("中国平安 ")
        '中国平安'
        >>> normalize_for_temp_id("中国平安-已转出")
        '中国平安'
    """
    warnings.warn(
        "normalize_for_temp_id is deprecated. "
        "Use normalize_customer_name from infrastructure.cleansing.normalizers instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return normalize_customer_name(company_name)


def generate_temp_company_id(customer_name: str, salt: str) -> str:
    """
    Generate stable temporary company ID with legacy-compatible normalization.

    Format: IN<16-char-Base32> (no underscore separator)
    Algorithm: HMAC-SHA1

    The customer name is normalized before hashing to ensure consistent
    ID generation across name variants.

    Note: Base32 charset (A-Z, 2-7) doesn't include underscore, so "IN" prefix
    is unambiguous without a separator. This matches existing database data.

    Args:
        customer_name: Customer name to generate ID for.
        salt: Salt for HMAC (from WDH_ALIAS_SALT environment variable).

    Returns:
        Temporary ID in format "IN<16-char-Base32>" (18 characters total).

    Examples:
        >>> generate_temp_company_id("中国平安", "test_salt")
        'IN...'  # 18 characters total
        >>> # Same input produces same output
        >>> id1 = generate_temp_company_id("中国平安", "salt")
        >>> id2 = generate_temp_company_id("中国平安", "salt")
        >>> id1 == id2
        True
    """
    # CRITICAL: Normalize before hashing!
    normalized = normalize_for_temp_id(customer_name)

    # Handle empty normalized name
    if not normalized:
        normalized = "__empty__"

    digest = hmac.new(
        salt.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    # Take first 10 bytes and encode as Base32 (produces 16 characters)
    encoded = base64.b32encode(digest[:10]).decode("ascii")

    return f"IN{encoded}"
