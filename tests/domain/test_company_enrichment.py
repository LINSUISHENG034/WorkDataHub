"""
Comprehensive unit tests for company enrichment domain.

Tests validate that the new company ID resolution system exactly matches
the behavior of the legacy _update_company_id method from data_cleaner.py,
including priority logic, edge cases, and Chinese character handling.
"""

import pytest
from datetime import datetime, timezone

from src.work_data_hub.domain.company_enrichment.models import (
    CompanyMappingRecord,
    CompanyMappingQuery,
    CompanyResolutionResult
)
from src.work_data_hub.domain.company_enrichment.service import (
    resolve_company_id,
    build_mapping_lookup,
    validate_mapping_consistency
)


class TestCompanyMappingModels:
    """Test Pydantic models for company enrichment domain."""

    def test_company_mapping_record_validation(self):
        """Test CompanyMappingRecord validation rules."""
        # Valid record
        record = CompanyMappingRecord(
            alias_name="AN001",
            canonical_id="614810477",
            match_type="plan",
            priority=1
        )
        assert record.alias_name == "AN001"
        assert record.canonical_id == "614810477"
        assert record.match_type == "plan"
        assert record.priority == 1
        assert record.source == "internal"  # default value
        assert isinstance(record.updated_at, datetime)

    def test_company_mapping_record_validation_errors(self):
        """Test CompanyMappingRecord validation failures."""
        # Empty alias_name should fail
        with pytest.raises(ValueError):
            CompanyMappingRecord(
                alias_name="",
                canonical_id="614810477",
                match_type="plan",
                priority=1
            )

        # Invalid priority should fail
        with pytest.raises(ValueError):
            CompanyMappingRecord(
                alias_name="AN001",
                canonical_id="614810477",
                match_type="plan",
                priority=10  # Out of range 1-5
            )

        # Invalid match_type should fail
        with pytest.raises(ValueError):
            CompanyMappingRecord(
                alias_name="AN001",
                canonical_id="614810477",
                match_type="invalid_type",
                priority=1
            )

    def test_company_mapping_query_normalization(self):
        """Test CompanyMappingQuery field normalization."""
        query = CompanyMappingQuery(
            plan_code="  AN001  ",  # Should be stripped
            account_number="",  # Should become None
            customer_name="中国平安保险股份有限公司",
            account_name=None
        )

        assert query.plan_code == "AN001"
        assert query.account_number is None  # Empty string normalized to None
        assert query.customer_name == "中国平安保险股份有限公司"
        assert query.account_name is None

    def test_company_resolution_result_validation(self):
        """Test CompanyResolutionResult validation."""
        result = CompanyResolutionResult(
            company_id="614810477",
            match_type="plan",
            source_value="AN001",
            priority=1
        )

        assert result.company_id == "614810477"
        assert result.match_type == "plan"
        assert result.source_value == "AN001"
        assert result.priority == 1


class TestResolveCompanyId:
    """
    Test the resolve_company_id function matches legacy _update_company_id exactly.

    These tests replicate the exact priority logic from AnnuityPerformanceCleaner._clean_method
    (lines 203-227 in data_cleaner.py).
    """

    def test_priority_based_resolution(self):
        """Test that priority order matches legacy _update_company_id exactly."""
        mappings = [
            CompanyMappingRecord(alias_name="AN001", canonical_id="614810477", match_type="plan", priority=1),
            CompanyMappingRecord(alias_name="GM123456", canonical_id="608349737", match_type="account", priority=2),
            CompanyMappingRecord(alias_name="测试企业A", canonical_id="614810477", match_type="name", priority=4),
        ]

        # Plan code should take priority over customer name
        query = CompanyMappingQuery(plan_code="AN001", customer_name="测试企业A")
        result = resolve_company_id(mappings, query)

        assert result.company_id == "614810477"
        assert result.match_type == "plan"
        assert result.source_value == "AN001"
        assert result.priority == 1

    def test_step_by_step_priority_fallback(self):
        """Test each step of the 5-layer priority system."""
        mappings = [
            # Priority 1: plan
            CompanyMappingRecord(alias_name="AN001", canonical_id="111111111", match_type="plan", priority=1),
            # Priority 2: account
            CompanyMappingRecord(alias_name="GM123456", canonical_id="222222222", match_type="account", priority=2),
            # Priority 3: hardcode (uses plan_code as key)
            CompanyMappingRecord(alias_name="FP0001", canonical_id="333333333", match_type="hardcode", priority=3),
            # Priority 4: name
            CompanyMappingRecord(alias_name="测试企业", canonical_id="444444444", match_type="name", priority=4),
            # Priority 5: account_name
            CompanyMappingRecord(alias_name="测试账户", canonical_id="555555555", match_type="account_name", priority=5),
        ]

        # Test 1: Only plan_code matches -> priority 1
        query = CompanyMappingQuery(plan_code="AN001")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "111111111"
        assert result.match_type == "plan"

        # Test 2: No plan_code, account_number matches -> priority 2
        query = CompanyMappingQuery(account_number="GM123456")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "222222222"
        assert result.match_type == "account"

        # Test 3: No plan/account, hardcode matches (uses plan_code as key) -> priority 3
        query = CompanyMappingQuery(plan_code="FP0001", customer_name="some name")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "333333333"
        assert result.match_type == "hardcode"

        # Test 4: Only customer_name matches -> priority 4
        query = CompanyMappingQuery(customer_name="测试企业")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "444444444"
        assert result.match_type == "name"

        # Test 5: Only account_name matches -> priority 5
        query = CompanyMappingQuery(account_name="测试账户", customer_name="has value")  # customer_name has value so no default
        result = resolve_company_id(mappings, query)
        assert result.company_id == "555555555"
        assert result.match_type == "account_name"

    def test_chinese_character_handling(self):
        """Test proper handling of Chinese company names."""
        mappings = [
            CompanyMappingRecord(
                alias_name="中国平安保险股份有限公司",
                canonical_id="614810477",
                match_type="name",
                priority=4
            ),
            CompanyMappingRecord(
                alias_name="上海银行股份有限公司",
                canonical_id="608349737",
                match_type="account_name",
                priority=5
            )
        ]

        # Test exact Chinese character match
        query = CompanyMappingQuery(customer_name="中国平安保险股份有限公司")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "614810477"
        assert result.match_type == "name"
        assert result.source_value == "中国平安保险股份有限公司"

        # Test account name with Chinese characters
        query = CompanyMappingQuery(
            account_name="上海银行股份有限公司",
            customer_name="has value"  # Prevent default fallback
        )
        result = resolve_company_id(mappings, query)
        assert result.company_id == "608349737"
        assert result.match_type == "account_name"

        # Test no match with different Chinese characters
        query = CompanyMappingQuery(customer_name="不存在的公司名称")
        result = resolve_company_id(mappings, query)
        assert result.company_id is None
        assert result.match_type is None

    def test_default_fallback_logic(self):
        """Test default fallback when customer_name is empty."""
        mappings = []  # No mappings available

        # Test None customer_name triggers default
        query = CompanyMappingQuery(customer_name=None)
        result = resolve_company_id(mappings, query)
        assert result.company_id == "600866980"
        assert result.match_type == "default"
        assert result.source_value is None

        # Test empty string customer_name triggers default
        query = CompanyMappingQuery(customer_name="")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "600866980"
        assert result.match_type == "default"

        # Test whitespace-only customer_name (should be normalized to None/empty and trigger default)
        query = CompanyMappingQuery(customer_name="   ")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "600866980"
        assert result.match_type == "default"

    def test_null_vs_empty_handling(self):
        """Test proper handling of null vs empty string values."""
        mappings = []

        # None should trigger default
        query = CompanyMappingQuery(customer_name=None)
        result = resolve_company_id(mappings, query)
        assert result.company_id == "600866980"

        # Empty string should also trigger default
        query = CompanyMappingQuery(customer_name="")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "600866980"

        # Non-empty customer_name should NOT trigger default
        query = CompanyMappingQuery(customer_name="some company")
        result = resolve_company_id(mappings, query)
        assert result.company_id is None  # No match found, but no default applied

    def test_hardcode_mapping_uses_plan_code_as_key(self):
        """Test that hardcode mappings use plan_code as the lookup key."""
        # This replicates the legacy COMPANY_ID3_MAPPING behavior where
        # hardcode lookups use plan_code as the key, not a separate field
        mappings = [
            CompanyMappingRecord(alias_name="FP0001", canonical_id="614810477", match_type="hardcode", priority=3),
            CompanyMappingRecord(alias_name="P0809", canonical_id="608349737", match_type="hardcode", priority=3),
        ]

        # Hardcode lookup uses plan_code as key
        query = CompanyMappingQuery(plan_code="FP0001", customer_name="some name")
        result = resolve_company_id(mappings, query)

        assert result.company_id == "614810477"
        assert result.match_type == "hardcode"
        assert result.source_value == "FP0001"

    def test_exact_string_matching(self):
        """Test that matching is exact and case-sensitive."""
        mappings = [
            CompanyMappingRecord(alias_name="AN001", canonical_id="614810477", match_type="plan", priority=1),
        ]

        # Exact match should work
        query = CompanyMappingQuery(plan_code="AN001")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "614810477"

        # Case mismatch should not work, but will trigger default fallback since customer_name is None
        query = CompanyMappingQuery(plan_code="an001")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "600866980"  # Default fallback behavior
        assert result.match_type == "default"

        # Partial match should not work, will also trigger default fallback
        query = CompanyMappingQuery(plan_code="AN")
        result = resolve_company_id(mappings, query)
        assert result.company_id == "600866980"  # Default fallback behavior

    def test_complex_real_world_scenario(self):
        """Test complex scenario mimicking real legacy data."""
        mappings = [
            # Real hardcoded mappings from COMPANY_ID3_MAPPING
            CompanyMappingRecord(alias_name="FP0001", canonical_id="614810477", match_type="hardcode", priority=3),
            CompanyMappingRecord(alias_name="FP0002", canonical_id="614810477", match_type="hardcode", priority=3),
            CompanyMappingRecord(alias_name="P0809", canonical_id="608349737", match_type="hardcode", priority=3),

            # Plan mappings
            CompanyMappingRecord(alias_name="AN001", canonical_id="111111111", match_type="plan", priority=1),

            # Chinese company name mappings
            CompanyMappingRecord(alias_name="中国人寿保险股份有限公司", canonical_id="222222222", match_type="name", priority=4),
        ]

        # Test 1: Plan takes priority over hardcode
        query = CompanyMappingQuery(
            plan_code="AN001",  # Should match plan mapping
            customer_name="中国人寿保险股份有限公司"  # Should NOT be used due to priority
        )
        result = resolve_company_id(mappings, query)
        assert result.company_id == "111111111"  # From plan, not name
        assert result.match_type == "plan"

        # Test 2: Hardcode mapping when no plan match
        query = CompanyMappingQuery(
            plan_code="FP0001",  # Should match hardcode mapping
            customer_name="中国人寿保险股份有限公司"
        )
        result = resolve_company_id(mappings, query)
        assert result.company_id == "614810477"  # From hardcode
        assert result.match_type == "hardcode"

        # Test 3: Chinese name mapping when no higher priority matches
        query = CompanyMappingQuery(
            customer_name="中国人寿保险股份有限公司"
        )
        result = resolve_company_id(mappings, query)
        assert result.company_id == "222222222"  # From name
        assert result.match_type == "name"


class TestBuildMappingLookup:
    """Test the build_mapping_lookup helper function."""

    def test_build_mapping_lookup_structure(self):
        """Test that lookup structure is built correctly."""
        mappings = [
            CompanyMappingRecord(alias_name="AN001", canonical_id="111", match_type="plan", priority=1),
            CompanyMappingRecord(alias_name="AN002", canonical_id="222", match_type="plan", priority=1),
            CompanyMappingRecord(alias_name="GM123", canonical_id="333", match_type="account", priority=2),
        ]

        lookup = build_mapping_lookup(mappings)

        expected = {
            "plan": {"AN001": "111", "AN002": "222"},
            "account": {"GM123": "333"}
        }

        assert lookup == expected

    def test_build_mapping_lookup_empty(self):
        """Test lookup with empty mappings."""
        lookup = build_mapping_lookup([])
        assert lookup == {}


class TestValidateMappingConsistency:
    """Test the validate_mapping_consistency function."""

    def test_no_warnings_for_clean_data(self):
        """Test that clean data produces no warnings."""
        mappings = [
            CompanyMappingRecord(alias_name="AN001", canonical_id="111", match_type="plan", priority=1),
            CompanyMappingRecord(alias_name="GM123", canonical_id="222", match_type="account", priority=2),
        ]

        warnings = validate_mapping_consistency(mappings)
        assert warnings == []

    def test_conflict_detection(self):
        """Test detection of conflicting mappings."""
        mappings = [
            CompanyMappingRecord(alias_name="AN001", canonical_id="111", match_type="plan", priority=1),
            CompanyMappingRecord(alias_name="AN001", canonical_id="222", match_type="plan", priority=1),  # Conflict!
        ]

        warnings = validate_mapping_consistency(mappings)
        assert len(warnings) == 1
        assert "Conflicting mappings" in warnings[0]
        assert "AN001" in warnings[0]

    def test_priority_mismatch_detection(self):
        """Test detection of priority mismatches."""
        mappings = [
            CompanyMappingRecord(alias_name="AN001", canonical_id="111", match_type="plan", priority=2),  # Should be 1!
        ]

        warnings = validate_mapping_consistency(mappings)
        assert len(warnings) == 1
        assert "Priority mismatch" in warnings[0]
        assert "plan" in warnings[0]
        assert "expected 1" in warnings[0]