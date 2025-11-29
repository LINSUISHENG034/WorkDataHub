"""
Date parsing step for standardizing date fields.

This module provides a reusable transformation step that parses
various date formats (Chinese, numeric) to a standard format.
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List

import dateutil.parser as dp
import structlog

from work_data_hub.domain.pipelines.types import Row, StepResult, TransformStep

logger = structlog.get_logger(__name__)


def parse_to_standard_date(data: Any) -> date | datetime | Any:
    """
    Convert date data to standard format - extracted from legacy common_utils.

    This function replicates the exact date parsing logic from the legacy cleaner.
    Supports various Chinese and numeric date formats.

    Args:
        data: The date value to parse (can be date, datetime, or string)

    Returns:
        Parsed date/datetime object, or original value if parsing fails

    Example:
        >>> parse_to_standard_date("2024年12月")
        datetime.datetime(2024, 12, 1, 0, 0)
        >>> parse_to_standard_date("202412")
        datetime.datetime(2024, 12, 1, 0, 0)
        >>> parse_to_standard_date("2024-12")
        datetime.datetime(2024, 12, 1, 0, 0)
    """
    if isinstance(data, (date, datetime)):
        return data
    else:
        date_string = str(data)

    try:
        # Match YYYY年MM月 or YY年MM月 format
        if re.match(r"(\d{2}|\d{4})年\d{1,2}月$", date_string):
            return datetime.strptime(date_string + "1日", "%Y年%m月%d日")

        # Match YYYY年MM月DD日 or YY年MM月DD日 format
        elif re.match(r"(\d{2}|\d{4})年\d{1,2}月\d{1,2}日$", date_string):
            return datetime.strptime(date_string, "%Y年%m月%d日")

        # Match YYYYMMDD format
        elif re.match(r"\d{8}", date_string):
            return datetime.strptime(date_string, "%Y%m%d")

        # Match YYYYMM format
        elif re.match(r"\d{6}", date_string):
            return datetime.strptime(date_string + "01", "%Y%m%d")

        # Match YYYY-MM format
        elif re.match(r"\d{4}-\d{2}", date_string):
            return datetime.strptime(date_string + "-01", "%Y-%m-%d")

        # Match other formats
        else:
            return dp.parse(date_string)

    except (ValueError, TypeError):
        return data


class DateParsingStep(TransformStep):
    """
    Parse and standardize date fields using parse_to_standard_date.

    Applies the legacy date parsing logic to specified date fields.
    Default behavior targets the '月度' field used in annuity data.

    This step is domain-agnostic and can be configured to parse
    any date field in the data.

    Example:
        >>> step = DateParsingStep()
        >>> result = step.apply({"月度": "2024年12月"}, {})
        >>> result.row["月度"]
        datetime.datetime(2024, 12, 1, 0, 0)
    """

    def __init__(self, date_fields: List[str] | None = None) -> None:
        """
        Initialize with optional custom date fields to parse.

        Args:
            date_fields: List of field names to parse as dates.
                        If None, defaults to ["月度"] for legacy compatibility.
        """
        self._date_fields = date_fields or ["月度"]

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "date_parsing"

    @property
    def date_fields(self) -> List[str]:
        """Return the date fields configured for this step."""
        return self._date_fields

    def apply(self, row: Row, context: Dict[str, Any]) -> StepResult:
        """
        Apply date parsing to configured date fields.

        Args:
            row: The input row dictionary to transform
            context: Pipeline context (unused by this step)

        Returns:
            StepResult with parsed date fields
        """
        try:
            updated_row = {**row}
            warnings: List[str] = []
            fields_processed = 0

            for field_name in self._date_fields:
                if field_name in updated_row:
                    original_value = updated_row[field_name]
                    try:
                        parsed_date = parse_to_standard_date(original_value)
                        updated_row[field_name] = parsed_date
                        fields_processed += 1

                        if str(parsed_date) != str(original_value):
                            warnings.append(
                                f"Parsed date: {original_value} -> {parsed_date}"
                            )

                    except Exception as date_error:
                        warnings.append(
                            f"Date parsing failed for '{original_value}': {date_error}"
                        )
                        # Keep original value on parsing failure

            return StepResult(
                row=updated_row,
                warnings=warnings,
                metadata={"date_fields_processed": fields_processed},
            )

        except Exception as e:
            return StepResult(row=row, errors=[f"Date parsing failed: {e}"])
