"""Shared helper functions used across multiple domains.

Extracted from domain-specific helpers as part of Story 5.5.4 to reduce
code duplication and establish reusable utilities.

Usage:
    from work_data_hub.infrastructure.helpers import normalize_month
"""

from __future__ import annotations

from work_data_hub.infrastructure.constants import (
    MAX_MONTH,
    MAX_VALID_YEAR,
    MIN_MONTH,
    MIN_VALID_YEAR,
    YYYYMM_LENGTH,
)


def normalize_month(month: str) -> str:
    """
    Validate YYYYMM format and return zero-padded text.

    Args:
        month: A string representing a month in YYYYMM format

    Returns:
        The validated month string in YYYYMM format

    Raises:
        ValueError: If month is None, not 6 digits, or has invalid year/month values

    Examples:
        >>> normalize_month("202412")
        '202412'
        >>> normalize_month("202401")
        '202401'
    """
    if month is None:
        raise ValueError("month is required (YYYYMM)")

    text = str(month).strip()
    if len(text) != YYYYMM_LENGTH or not text.isdigit():
        raise ValueError(
            f"month must be a {YYYYMM_LENGTH}-digit string in YYYYMM format"
        )

    yyyy = int(text[:4])
    mm = int(text[4:])
    if yyyy < MIN_VALID_YEAR or yyyy > MAX_VALID_YEAR:
        raise ValueError(
            f"month year component must be between {MIN_VALID_YEAR} and {MAX_VALID_YEAR}"
        )
    if mm < MIN_MONTH or mm > MAX_MONTH:
        raise ValueError(
            f"month component must be between {MIN_MONTH:02d} and {MAX_MONTH:02d}"
        )
    return text


__all__ = [
    "normalize_month",
]
