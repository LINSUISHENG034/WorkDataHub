"""
This module contains a specific test case to reproduce and expose a bug
in the exception handling of the trustee performance service.
"""

import pytest
from src.work_data_hub.domain.sandbox_trustee_performance.service import (
    _transform_single_row,
)

pytestmark = pytest.mark.sandbox_domain


def test_transform_row_with_invalid_month_reproduces_bug():
    """
    This test is designed to fail, proving the bug in exception handling.

    It passes a row with an invalid month ('13') to the transformation service.
    The service correctly identifies this as a validation error internally, but
    then attempts to re-raise a Pydantic ValidationError incorrectly, causing a
    TypeError crash instead of a clean, expected validation failure.
    """
    # This row is valid in structure but has invalid data (month=13)
    # This will cause a ValidationError inside the service logic.
    bug_trigger_row = {
        "年": "2024",
        "月": "13",  # Invalid month, this should cause a validation error
        "计划代码": "BUG-PROBE",
        "公司代码": "TECH-DEBT",
    }

    # After the bug fix, this should no longer crash with TypeError.
    # Instead, the invalid month should cause _extract_report_date to return None,
    # which means the entire row gets filtered out (returns None).
    result = _transform_single_row(bug_trigger_row, data_source="bug_test", row_index=0)

    # Verify that the row is filtered out due to invalid date
    assert result is None, (
        "Row with invalid month=13 should be filtered out (return None)"
    )
