"""
Unified date parsing utilities for WorkDataHub.

This module provides centralized date parsing functionality to handle various
Chinese date formats commonly found in Excel files and business data.
"""

import logging
import re
from datetime import date
from typing import Optional, Union

logger = logging.getLogger(__name__)


def parse_chinese_date(value: Union[str, int, date, None]) -> Optional[date]:
    """
    Parse various Chinese date formats into a standardized date object.

    Handles common formats found in Chinese Excel files:
    - Integer format: 202411 → date(2024, 11, 1)
    - Chinese format: "2024年11月" → date(2024, 11, 1)
    - Two-digit years: "24年11月" → date(2024, 11, 1)
    - Standard formats: "2024-11-01", "2024/11/01"
    - Already date objects are returned as-is

    Args:
        value: Date value to parse (str, int, date, or None)

    Returns:
        Parsed date object or None if parsing fails/value is None

    Raises:
        ValueError: If the input format is recognized but contains invalid date values

    Example:
        >>> parse_chinese_date(202411)
        datetime.date(2024, 11, 1)
        >>> parse_chinese_date("2024年11月")
        datetime.date(2024, 11, 1)
        >>> parse_chinese_date("24年11月")
        datetime.date(2024, 11, 1)
    """
    if value is None:
        return None

    if isinstance(value, date):
        return value

    # Convert to string for pattern matching
    str_value = str(value).strip()
    if not str_value:
        return None

    try:
        # Pattern 1: Integer format like 202411 (YYYYMM)
        if isinstance(value, int) or str_value.isdigit():
            int_value = int(str_value)
            if 200000 <= int_value <= 999999:  # Valid YYYYMM range
                year = int_value // 100
                month = int_value % 100
                if 1 <= month <= 12:
                    return date(year, month, 1)
                else:
                    raise ValueError(f"Invalid month in integer date: {month}")

        # Pattern 2: Chinese format like "2024年11月" or "24年11月"
        chinese_pattern = r"^(\d{2,4})年(\d{1,2})月?$"
        match = re.match(chinese_pattern, str_value)
        if match:
            year_str, month_str = match.groups()
            year = int(year_str)
            month = int(month_str)

            # Handle 2-digit years (assume 20xx)
            if year < 100:
                year += 2000

            if 1 <= month <= 12:
                return date(year, month, 1)
            else:
                raise ValueError(f"Invalid month in Chinese date: {month}")

        # Pattern 3: Standard date formats
        # Try common separators: -, /, .
        for separator in ["-", "/", "."]:
            parts = str_value.split(separator)
            if len(parts) == 3:
                try:
                    # Assume YYYY-MM-DD format
                    year, month, day = map(int, parts)
                    if year < 100:  # Handle 2-digit years
                        year += 2000
                    return date(year, month, day)
                except (ValueError, TypeError):
                    continue

        # Pattern 4: YYYY-MM format (assume day 1)
        for separator in ["-", "/", "."]:
            parts = str_value.split(separator)
            if len(parts) == 2:
                try:
                    year, month = map(int, parts)
                    if year < 100:  # Handle 2-digit years
                        year += 2000
                    if 1 <= month <= 12:
                        return date(year, month, 1)
                except (ValueError, TypeError):
                    continue

        # If no patterns match, log and return None
        logger.debug(f"Unable to parse date format: {repr(str_value)}")
        return None

    except (ValueError, TypeError) as e:
        logger.warning(f"Date parsing failed for value {repr(value)}: {e}")
        raise ValueError(f"Invalid date value: {value}") from e


def extract_year_month_from_date(
    value: Union[str, int, date, None],
) -> tuple[Optional[int], Optional[int]]:
    """
    Extract year and month from various date formats.

    Args:
        value: Date value to extract from

    Returns:
        Tuple of (year, month) or (None, None) if extraction fails

    Example:
        >>> extract_year_month_from_date(202411)
        (2024, 11)
        >>> extract_year_month_from_date("2024年11月")
        (2024, 11)
    """
    parsed_date = parse_chinese_date(value)
    if parsed_date:
        return parsed_date.year, parsed_date.month
    return None, None


def format_date_as_chinese(date_obj: date) -> str:
    """
    Format a date object as Chinese date string.

    Args:
        date_obj: Date to format

    Returns:
        Chinese formatted date string like "2024年11月"

    Example:
        >>> format_date_as_chinese(date(2024, 11, 1))
        '2024年11月'
    """
    return f"{date_obj.year}年{date_obj.month}月"


def normalize_date_for_database(value: Union[str, int, date, None]) -> Optional[str]:
    """
    Normalize any date format to standard database format (YYYY-MM-DD).

    Args:
        value: Date value to normalize

    Returns:
        ISO format date string or None if parsing fails

    Example:
        >>> normalize_date_for_database(202411)
        '2024-11-01'
        >>> normalize_date_for_database("24年11月")
        '2024-11-01'
    """
    parsed_date = parse_chinese_date(value)
    if parsed_date:
        return parsed_date.isoformat()
    return None
