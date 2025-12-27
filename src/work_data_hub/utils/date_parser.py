"""
Unified date parsing utilities for WorkDataHub.

This module provides centralized date parsing functionality to handle various
Chinese date formats commonly found in Excel files and business data.
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Callable, Hashable, List, Optional, Pattern, Tuple, Union

import pandas as pd

logger = logging.getLogger(__name__)

# 2-digit year parsing pivot (Story 7.1-16)
# Years < 50 are treated as 20xx, years >= 50 are treated as 19xx
TWO_DIGIT_YEAR_PIVOT = 50
CENTURY_2000 = 2000
CENTURY_1900 = 1900
ONE_HUNDRED = 100

SUPPORTED_FORMATS = (
    "YYYYMM, YYYYMMDD, YYYY年MM月, YYYY年MM月DD日, "
    "YYYY-MM, YYYY-MM-DD, YY年MM月 (2-digit year)"
)

DateParser = Callable[[str, re.Match[str]], date]


def _normalize_fullwidth_digits(value: str) -> str:
    """Convert full-width digits (０-９) to half-width equivalents."""
    translation_table = str.maketrans("０１２３４５６７８９", "0123456789")
    return value.translate(translation_table)


def _validate_date_range(
    parsed: date, min_year: int = 2000, max_year: int = 2030
) -> date:
    """Ensure parsed date falls within allowed range."""
    if not (min_year <= parsed.year <= max_year):
        raise ValueError(
            f"Date {parsed.year}-{parsed.month:02d} outside valid range "
            f"{min_year}-{max_year}"
        )
    return parsed


def _format_supported_error(value: Union[str, int, date, datetime, None]) -> str:
    return f"Cannot parse '{value}' as date. Supported formats: {SUPPORTED_FORMATS}"


def parse_yyyymm_or_chinese(value: Union[str, int, date, datetime, None]) -> date:
    """
    Parse various Chinese and ISO date formats into a Python ``date``.

    Supported inputs:
    - Integer/strings such as ``202501`` or ``20250115``
    - Chinese formats: ``2025年1月`` or ``2025年1月1日`` (full-width digits allowed)
    - ISO formats: ``2025-01`` (defaults to first day) or ``2025-01-01``
    - Date/datetime objects (validated passthrough)
    """
    if value is None:
        raise ValueError(_format_supported_error(value))

    if isinstance(value, datetime):
        return _validate_date_range(value.date())

    if isinstance(value, date):
        return _validate_date_range(value)

    raw = str(value).strip()
    if not raw:
        raise ValueError(_format_supported_error(value))

    normalized = _normalize_fullwidth_digits(raw)

    for pattern, parser in _DATE_PATTERNS:
        match = pattern.match(normalized)
        if not match:
            continue
        try:
            parsed = parser(normalized, match)
            return _validate_date_range(parsed)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(_format_supported_error(value)) from exc

    raise ValueError(_format_supported_error(value))


def parse_chinese_date(value: Union[str, int, date, None]) -> Optional[date]:
    """
    Backwards-compatible wrapper returning ``None`` for un-parseable values.

    Existing code that previously expected ``None`` on invalid inputs can keep
    using this helper, while newer code should prefer ``parse_yyyymm_or_chinese``.
    """
    if value is None:
        return None
    try:
        return parse_yyyymm_or_chinese(value)
    except ValueError:
        logger.debug("Unable to parse date value %r", value)
        return None


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


def parse_report_period(report_period: str) -> Optional[Tuple[int, int]]:
    """
    Parse year and month from common report period formats.
    """
    if not report_period:
        return None

    patterns = [
        r"(\d{4})[年\-/](\d{1,2})",  # 2024年11月 / 2024-11 / 2024/11
        r"(\d{4})(\d{2})",  # 202411
        r"(\d{2})年(\d{1,2})",  # 24年11月
    ]

    for pattern in patterns:
        match = re.search(pattern, report_period)
        if not match:
            continue
        try:
            year, month = int(match.group(1)), int(match.group(2))
            if year < TWO_DIGIT_YEAR_PIVOT:
                year += CENTURY_2000
            elif TWO_DIGIT_YEAR_PIVOT <= year < ONE_HUNDRED:
                year += CENTURY_1900
            return (year, month)
        except ValueError:
            continue

    return None


def parse_report_date(value: Union[str, int, date, None]) -> Optional[date]:
    """
    Parse a single value into a date using the shared Chinese date parser.
    """
    if value is None:
        return None

    try:
        parsed = parse_chinese_date(value)
        if parsed is None:
            return None
        # parse_chinese_date already returns a date object (or None)
        # The previous logic with hasattr(parsed, "date") was redundant as
        # parse_chinese_date returns date objects (which includes datetime objects)
        # and we just want the date part if it is a datetime, or the date itself.
        if isinstance(parsed, datetime):
            return parsed.date()
        return parsed
    except Exception:  # pragma: no cover - defensive logging
        logger.debug("Unable to parse report date value %r", value)
        return None


def parse_bronze_dates(series: pd.Series) -> Tuple[pd.Series, List[Hashable]]:
    """
    Parse date column using shared date parser; return parsed series and invalid
    indices.
    """
    parsed_values: List[Any] = []
    invalid_rows: List[Hashable] = []
    for idx, value in series.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            parsed_values.append(pd.NaT)
            continue

        try:
            parsed = parse_yyyymm_or_chinese(value)
            parsed_values.append(pd.Timestamp(parsed))
        except (ValueError, TypeError):
            parsed_values.append(pd.NaT)
            invalid_rows.append(idx)
    return pd.Series(parsed_values, index=series.index), invalid_rows


def _parse_digits(value: str, fmt: str) -> date:
    """Parse digit-based strings via datetime.strptime."""
    return datetime.strptime(value, fmt).date()


def _parse_year_month_day(match: re.Match[str]) -> date:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    return date(year, month, day)


def _parse_year_month(match: re.Match[str]) -> date:
    year = int(match.group(1))
    month = int(match.group(2))
    return date(year, month, 1)


def _parse_two_digit_year_month(match: re.Match[str]) -> date:
    year = int(match.group(1))
    month = int(match.group(2))
    if year < TWO_DIGIT_YEAR_PIVOT:
        year += CENTURY_2000
    else:
        year += CENTURY_1900
    return date(year, month, 1)


def _parse_two_digit_year_month_day(match: re.Match[str]) -> date:
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))
    if year < TWO_DIGIT_YEAR_PIVOT:
        year += CENTURY_2000
    else:
        year += CENTURY_1900
    return date(year, month, day)


_DATE_PATTERNS: list[Tuple[Pattern[str], DateParser]] = [
    (re.compile(r"^\d{8}$"), lambda value, _: _parse_digits(value, "%Y%m%d")),
    (re.compile(r"^\d{6}$"), lambda value, _: _parse_digits(f"{value}01", "%Y%m%d")),
    (
        re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        lambda value, _: _parse_digits(value, "%Y-%m-%d"),
    ),
    (
        re.compile(r"^\d{4}-\d{2}$"),
        lambda value, _: _parse_digits(f"{value}-01", "%Y-%m-%d"),
    ),
    (
        re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$"),
        lambda _, match: _parse_year_month_day(match),
    ),
    (
        re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})$"),
        lambda _, match: _parse_year_month_day(match),
    ),
    (re.compile(r"^(\d{4})年(\d{1,2})月$"), lambda _, match: _parse_year_month(match)),
    (
        re.compile(r"^(\d{2})年(\d{1,2})月(\d{1,2})日$"),
        lambda _, match: _parse_two_digit_year_month_day(match),
    ),
    (
        re.compile(r"^(\d{2})年(\d{1,2})月$"),
        lambda _, match: _parse_two_digit_year_month(match),
    ),
]
