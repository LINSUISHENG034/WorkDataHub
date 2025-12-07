"""
Test fixtures for infrastructure.enrichment module tests.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock

from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    ResolutionStrategy,
)


@pytest.fixture
def sample_plan_override_mapping():
    """Sample plan override mapping for testing."""
    return {
        "FP0001": "614810477",
        "FP0002": "614810477",
        "FP0003": "610081428",
        "P0809": "608349737",
        "SC002": "604809109",
    }


@pytest.fixture
def sample_dataframe():
    """Sample DataFrame for testing resolution."""
    return pd.DataFrame(
        {
            "计划代码": ["FP0001", "FP0002", "UNKNOWN", "P0809", None],
            "客户名称": ["公司A", "公司B", "中国平安保险公司", "公司D", "公司E"],
            "年金账户名": ["账户1", "账户2", "账户3", "账户4", "账户5"],
            "公司代码": [None, "existing_123", None, None, "existing_456"],
        }
    )


@pytest.fixture
def resolver_with_overrides(sample_plan_override_mapping):
    """CompanyIdResolver with explicit YAML overrides (plan only)."""
    return CompanyIdResolver(
        yaml_overrides={
            "plan": sample_plan_override_mapping,
            "account": {},
            "hardcode": {},
            "name": {},
            "account_name": {},
        }
    )


@pytest.fixture
def resolver_standalone():
    """CompanyIdResolver without any dependencies."""
    return CompanyIdResolver()


@pytest.fixture
def default_strategy():
    """Default resolution strategy."""
    return ResolutionStrategy()


@pytest.fixture
def mock_enrichment_service():
    """Mock CompanyEnrichmentService for testing."""
    mock_service = MagicMock()

    # Configure mock to return a result with company_id
    mock_result = MagicMock()
    mock_result.company_id = "mock_company_123"
    mock_service.resolve_company_id.return_value = mock_result

    return mock_service


@pytest.fixture
def large_dataframe():
    """Large DataFrame for performance testing (1000 rows)."""
    import random

    plan_codes = ["FP0001", "FP0002", "FP0003", "UNKNOWN", None]
    customer_names = [
        "中国平安保险公司",
        "中国人寿保险公司",
        "太平洋保险公司",
        "新华保险公司",
        "泰康保险公司",
    ]

    return pd.DataFrame(
        {
            "计划代码": [random.choice(plan_codes) for _ in range(1000)],
            "客户名称": [random.choice(customer_names) for _ in range(1000)],
            "年金账户名": [f"账户{i}" for i in range(1000)],
            "公司代码": [None] * 1000,
        }
    )


@pytest.fixture
def very_large_dataframe():
    """Very large DataFrame for memory testing (10000 rows)."""
    import random

    plan_codes = ["FP0001", "FP0002", "FP0003", "UNKNOWN", None]
    customer_names = [
        "中国平安保险公司",
        "中国人寿保险公司",
        "太平洋保险公司",
        "新华保险公司",
        "泰康保险公司",
    ]

    return pd.DataFrame(
        {
            "计划代码": [random.choice(plan_codes) for _ in range(10000)],
            "客户名称": [random.choice(customer_names) for _ in range(10000)],
            "年金账户名": [f"账户{i}" for i in range(10000)],
            "公司代码": [None] * 10000,
        }
    )
