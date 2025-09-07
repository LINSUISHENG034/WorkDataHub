"""
This module contains a specific test case to reproduce and expose a bug
in the exception handling of the trustee performance service.
"""

import pytest

from src.work_data_hub.domain.trustee_performance.service import _transform_single_row


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

    # We expect this call to crash with a TypeError due to the bug,
    # instead of raising a clean, expected pydantic.ValidationError.
    _transform_single_row(bug_trigger_row, data_source="bug_test", row_index=0)