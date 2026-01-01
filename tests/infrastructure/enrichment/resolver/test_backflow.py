"""Tests for backflow plan_code support (Story 7.5-1)."""

import pandas as pd
import pytest
from unittest.mock import MagicMock

from work_data_hub.infrastructure.enrichment.resolver.backflow import (
    backflow_new_mappings,
)
from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
    InsertBatchResult,
)
from work_data_hub.infrastructure.enrichment.types import ResolutionStrategy


@pytest.fixture
def mock_repository():
    """Create mock CompanyMappingRepository."""
    mock = MagicMock(spec=CompanyMappingRepository)
    mock.insert_batch_with_conflict_check.return_value = InsertBatchResult(
        inserted_count=1, skipped_count=0, conflicts=[]
    )
    return mock


@pytest.fixture
def default_strategy():
    """Create default ResolutionStrategy."""
    return ResolutionStrategy()


def test_backflow_plan_code_mapping(mock_repository, default_strategy):
    """Verify plan_code mappings are written to enrichment_index."""
    df = pd.DataFrame(
        {
            "计划代码": ["S6544"],
            "年金账户号": ["ACC001"],
            "客户名称": ["中关村发展集团"],
            "年金账户名": ["中关村年金账户"],
            "company_id": ["600093406"],
        }
    )

    result = backflow_new_mappings(df, [0], default_strategy, mock_repository)

    # Assert insert was called
    mock_repository.insert_batch_with_conflict_check.assert_called_once()
    call_args = mock_repository.insert_batch_with_conflict_check.call_args[0][0]

    # Find plan_code mapping (P1)
    plan_mapping = next(m for m in call_args if m["match_type"] == "plan")
    assert plan_mapping["alias_name"] == "S6544"
    assert plan_mapping["priority"] == 1
    assert plan_mapping["source"] == "pipeline_backflow"
    assert plan_mapping["canonical_id"] == "600093406"


def test_backflow_skips_temp_id_for_plan_code(mock_repository, default_strategy):
    """Verify temp IDs (starting with IN) are skipped for plan_code."""
    df = pd.DataFrame(
        {
            "计划代码": ["S6544"],
            "年金账户号": ["ACC001"],
            "客户名称": [""],
            "年金账户名": [""],
            "company_id": ["IN7KZNPWPCVQXJ6AY7"],  # Temp ID
        }
    )

    result = backflow_new_mappings(df, [0], default_strategy, mock_repository)

    # Assert insert was NOT called (temp ID skipped)
    mock_repository.insert_batch_with_conflict_check.assert_not_called()
    assert result == {"inserted": 0, "skipped": 0, "conflicts": 0}


def test_backflow_skips_empty_plan_code(mock_repository, default_strategy):
    """Verify empty/null plan_code values are skipped without exception."""
    df = pd.DataFrame(
        {
            "计划代码": ["", None, "  "],
            "年金账户号": ["ACC001", "ACC002", "ACC003"],
            "客户名称": ["公司A", "公司B", "公司C"],
            "年金账户名": ["账户A", "账户B", "账户C"],
            "company_id": ["600001", "600002", "600003"],
        }
    )

    # Should not raise exception
    result = backflow_new_mappings(df, [0, 1, 2], default_strategy, mock_repository)

    # Other fields (account, name, account_name) should still be backflowed
    mock_repository.insert_batch_with_conflict_check.assert_called_once()
    call_args = mock_repository.insert_batch_with_conflict_check.call_args[0][0]

    # No plan_code mappings should exist
    plan_mappings = [m for m in call_args if m["match_type"] == "plan"]
    assert len(plan_mappings) == 0
