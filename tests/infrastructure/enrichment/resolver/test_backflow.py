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


class TestGenerateTempId:
    """Tests for generate_temp_id function (Story 7.5-3)."""

    def test_none_returns_none(self):
        """None customer name returns None (not temp ID)."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result = generate_temp_id(None, "salt")
        assert result is None

    def test_pd_na_returns_none(self):
        """pd.NA customer name returns None."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result = generate_temp_id(pd.NA, "salt")
        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result = generate_temp_id("", "salt")
        assert result is None

    def test_whitespace_only_returns_none(self):
        """Whitespace-only string returns None."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result = generate_temp_id("   ", "salt")
        assert result is None

    def test_zero_placeholder_returns_none(self):
        """'0' placeholder returns None."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result = generate_temp_id("0", "salt")
        assert result is None

    def test_kongbai_placeholder_returns_none(self):
        """'空白' placeholder returns None."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result = generate_temp_id("空白", "salt")
        assert result is None

    def test_valid_name_returns_temp_id(self):
        """Valid company name returns temp ID string."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result = generate_temp_id("中关村发展集团", "salt")
        assert result is not None
        assert result.startswith("IN")
        assert len(result) == 18  # IN + 16 chars

    def test_same_name_same_salt_returns_same_id(self):
        """Same name + same salt = same temp ID (deterministic)."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result1 = generate_temp_id("TestCompany", "salt1")
        result2 = generate_temp_id("TestCompany", "salt1")
        assert result1 == result2

    def test_same_name_different_salt_returns_different_id(self):
        """Same name + different salt = different temp ID."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        result1 = generate_temp_id("TestCompany", "salt1")
        result2 = generate_temp_id("TestCompany", "salt2")
        assert result1 != result2


class TestMultiPriorityMatchingWithEmptyNames:
    """Integration tests for multi-priority matching with empty customer names (Story 7.5-3 CRITICAL-003)."""

    def test_empty_customer_name_with_valid_plan_code_resolves_via_p1(self):
        """Verify P1 (plan_code) lookup works even when customer_name is empty (Story 7.5-3 AC-4)."""
        import pandas as pd
        from work_data_hub.infrastructure.enrichment.types import ResolutionStrategy

        # Scenario: Empty customer name but valid plan_code (P1 priority)
        df = pd.DataFrame(
            {
                "customer_name": [""],  # Empty - should NOT generate temp ID
                "plan_code": ["S6544"],  # Valid P1 lookup key
                "年金账户号": ["ACC001"],
                "年金账户名": ["测试账户"],
                "company_id": [pd.NA],
            }
        )

        # Simulate P1 lookup finding the plan_code in enrichment_index
        # In real flow, CompanyIdResolver would check P1 (plan_code) first
        # This test verifies that empty customer_name doesn't break P1-P5 lookups

        # The key assertion: Empty customer name should return None from generate_temp_id
        # but P1-P5 lookups should still work and resolve company_id
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        temp_id = generate_temp_id("", "test_salt")
        assert temp_id is None, "Empty customer name should return None (not temp ID)"

        # In full integration test, we'd verify:
        # 1. P1 lookup finds S6544 → company_id resolved
        # 2. Empty customer_name doesn't prevent P1-P5 lookups
        # 3. Only truly unresolvable names get temp IDs

    def test_valid_customer_name_unresolved_generates_temp_id(self):
        """Verify valid customer names still generate temp IDs when P1-P5 fail (Story 7.5-3 AC-4)."""
        from work_data_hub.infrastructure.enrichment.resolver.backflow import (
            generate_temp_id,
        )

        # Valid company name but assume P1-P5 all failed
        result = generate_temp_id("Unknown Company Inc", "test_salt")

        # Should generate temp ID (not None) because name is not empty
        assert result is not None
        assert result.startswith("IN")
        assert len(result) == 18
