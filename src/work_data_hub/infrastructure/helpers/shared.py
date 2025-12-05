"""Shared helper functions used across multiple domains.

Extracted from domain-specific helpers as part of Story 5.5.4 to reduce
code duplication and establish reusable utilities.

Usage:
    from work_data_hub.infrastructure.helpers import normalize_month
"""

from __future__ import annotations


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
    if len(text) != 6 or not text.isdigit():
        raise ValueError("month must be a 6-digit string in YYYYMM format")

    yyyy = int(text[:4])
    mm = int(text[4:])
    if yyyy < 2000 or yyyy > 2100:
        raise ValueError("month year component must be between 2000 and 2100")
    if mm < 1 or mm > 12:
        raise ValueError("month component must be between 01 and 12")
    return text


__all__ = [
    "normalize_month",
]
