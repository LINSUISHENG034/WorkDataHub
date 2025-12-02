"""Test fixtures for infrastructure.validation tests."""

from __future__ import annotations

from typing import List

import pandas as pd
import pytest

from work_data_hub.infrastructure.validation import ValidationErrorDetail


@pytest.fixture
def sample_error_details() -> List[ValidationErrorDetail]:
    """Sample validation error details for testing."""
    return [
        ValidationErrorDetail(
            row_index=0,
            field_name="月度",
            error_type="ValueError",
            error_message="Cannot parse 'INVALID' as date",
            original_value="INVALID",
        ),
        ValidationErrorDetail(
            row_index=5,
            field_name="期末资产规模",
            error_type="ValueError",
            error_message="Value must be >= 0",
            original_value=-1000.50,
        ),
        ValidationErrorDetail(
            row_index=10,
            field_name="计划代码",
            error_type="type_error",
            error_message="Expected string",
            original_value=12345,
        ),
    ]


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Sample DataFrame for testing."""
    return pd.DataFrame(
        {
            "月度": ["2024-01", "2024-02", "2024-03"],
            "计划代码": ["A001", "A002", "A003"],
            "客户名称": ["客户A", "客户B", "客户C"],
            "期末资产规模": [1000.0, 2000.0, 3000.0],
        }
    )


@pytest.fixture
def failed_dataframe() -> pd.DataFrame:
    """Sample DataFrame with failed rows for testing."""
    return pd.DataFrame(
        {
            "月度": ["INVALID", "BAD_DATE"],
            "计划代码": ["A001", "A002"],
            "客户名称": ["客户A", "客户B"],
            "期末资产规模": [-100.0, None],
        }
    )


@pytest.fixture
def empty_error_details() -> List[ValidationErrorDetail]:
    """Empty list of error details."""
    return []


@pytest.fixture
def high_error_rate_details() -> List[ValidationErrorDetail]:
    """Error details representing >10% error rate (15 errors for 100 rows)."""
    return [
        ValidationErrorDetail(
            row_index=i,
            field_name="field",
            error_type="type_error",
            error_message="Test error",
            original_value=f"value_{i}",
        )
        for i in range(15)
    ]


@pytest.fixture
def low_error_rate_details() -> List[ValidationErrorDetail]:
    """Error details representing <10% error rate (5 errors for 100 rows)."""
    return [
        ValidationErrorDetail(
            row_index=i,
            field_name="field",
            error_type="type_error",
            error_message="Test error",
            original_value=f"value_{i}",
        )
        for i in range(5)
    ]
