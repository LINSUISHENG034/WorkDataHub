"""
Unit tests for shared validators in infrastructure/cleansing/validators.py

Created in Story 7.3-2 to test the extracted shared validators and constants.
Reference: docs/sprint-artifacts/stories/7.3-2-extract-shared-validators.md
"""

import pytest

from work_data_hub.infrastructure.cleansing.validators import (
    DEFAULT_COMPANY_RULES,
    DEFAULT_NUMERIC_RULES,
    MAX_DATE_RANGE_DAYS,
    MAX_YYYYMM_VALUE,
    MIN_YYYYMM_VALUE,
    apply_domain_rules,
    clean_code_field,
    clean_customer_name,
    normalize_company_id,
    normalize_plan_code,
)


class TestCleanCodeField:
    """Tests for clean_code_field function."""

    def test_none_returns_none(self):
        """None input should return None."""
        assert clean_code_field(None) is None

    def test_whitespace_returns_none(self):
        """Whitespace-only string should return None."""
        assert clean_code_field("   ") is None
        assert clean_code_field("\t\n") is None
        assert clean_code_field("") is None

    def test_valid_string_stripped(self):
        """Valid string should have whitespace stripped."""
        assert clean_code_field("  ABC123  ") == "ABC123"
        assert clean_code_field("\tXYY\t") == "XYY"

    def test_numeric_converted(self):
        """Numeric input should be converted to string and stripped."""
        assert clean_code_field(12345) == "12345"
        assert clean_code_field(99.5) == "99.5"


class TestNormalizePlanCode:
    """Tests for normalize_plan_code function."""

    def test_none_with_allow_null_returns_none(self):
        """None with allow_null=True should return None."""
        assert normalize_plan_code(None, allow_null=True) is None

    def test_none_with_allow_null_false_raises(self):
        """None with allow_null=False should raise ValueError."""
        with pytest.raises(ValueError, match="Plan code cannot be None"):
            normalize_plan_code(None, allow_null=False)

    def test_uppercase_conversion(self):
        """Lowercase should be converted to uppercase."""
        assert normalize_plan_code("abc-def") == "ABCDEF"
        assert normalize_plan_code("XYZ") == "XYZ"

    def test_special_char_removal(self):
        """Hyphens, underscores, and spaces should be removed."""
        assert normalize_plan_code("ABC _-DEF") == "ABCDEF"
        assert normalize_plan_code("A-B_C D") == "ABCD"

    def test_dots_preserved(self):
        """Dots should be preserved."""
        assert normalize_plan_code("ABC.DEF") == "ABC.DEF"
        assert normalize_plan_code("a.b.c") == "A.B.C"

    def test_chinese_parentheses_preserved(self):
        """Chinese parentheses should be preserved."""
        assert normalize_plan_code("ABC（DEF）") == "ABC（DEF）"
        assert normalize_plan_code("abc（def）") == "ABC（DEF）"

    def test_empty_after_normalization_raises(self):
        """Empty or special-char-only strings should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_plan_code(" -_")
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_plan_code("...")
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_plan_code("（ ）")


class TestNormalizeCompanyId:
    """Tests for normalize_company_id function."""

    def test_none_returns_none(self):
        """None input should return None."""
        assert normalize_company_id(None) is None

    def test_uppercase_conversion(self):
        """Lowercase should be converted to uppercase."""
        assert normalize_company_id("abc123") == "ABC123"
        assert normalize_company_id("XYZ") == "XYZ"

    def test_whitespace_raises(self):
        """Whitespace-only string should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_company_id("   ")
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_company_id("\t")

    def test_valid_id_unchanged(self):
        """Valid IDs should only be uppercased."""
        assert normalize_company_id("614810477") == "614810477"
        assert normalize_company_id("INABCDEFGHIJKLMNOP") == "INABCDEFGHIJKLMNOP"


class TestCleanCustomerName:
    """Tests for clean_customer_name function."""

    def test_none_returns_none(self):
        """None input should return None."""
        result = clean_customer_name(None, "客户名称", "annuity_performance")
        assert result is None

    def test_valid_name_passed_to_rules(self):
        """Valid name should be processed by domain rules."""
        # The actual behavior depends on the cleansing registry
        # This test just verifies the function doesn't crash
        result = clean_customer_name(
            "  Test Company  ", "客户名称", "annuity_performance"
        )
        # Result should be a string (may be modified by rules)
        assert isinstance(result, str)

    def test_domain_parameter_used(self):
        """Different domains should be accepted."""
        # Verify both domains work without error
        result1 = clean_customer_name("Test", "客户名称", "annuity_performance")
        result2 = clean_customer_name("Test", "客户名称", "annuity_income")
        assert isinstance(result1, str)
        assert isinstance(result2, str)


class TestApplyDomainRules:
    """Tests for apply_domain_rules function."""

    def test_none_value_no_rules_returns_none(self):
        """None with no rules should return None."""
        result = apply_domain_rules(
            None, "test_field", "annuity_performance", fallback_rules=None
        )
        assert result is None

    def test_value_with_empty_rules_returns_unchanged(self):
        """Value with no rules should return unchanged."""
        result = apply_domain_rules(
            "test_value", "test_field", "annuity_performance", fallback_rules=None
        )
        assert result == "test_value"

    def test_fallback_rules_applied(self):
        """Fallback rules should be applied when no domain rules exist."""
        result = apply_domain_rules(
            "  test  ",
            "nonexistent_field",
            "annuity_performance",
            fallback_rules=["trim_whitespace"],
        )
        # trim_whitespace rule should be applied
        assert result == "test"

    def test_domain_parameter_accepted(self):
        """Function should accept different domain parameters."""
        # Should not raise for any valid domain
        apply_domain_rules("test", "field", "annuity_performance")
        apply_domain_rules("test", "field", "annuity_income")


class TestSharedConstants:
    """Tests for shared constants."""

    def test_default_company_rules_exists(self):
        """DEFAULT_COMPANY_RULES should be a list."""
        assert isinstance(DEFAULT_COMPANY_RULES, list)
        assert len(DEFAULT_COMPANY_RULES) > 0

    def test_default_numeric_rules_exists(self):
        """DEFAULT_NUMERIC_RULES should be a list."""
        assert isinstance(DEFAULT_NUMERIC_RULES, list)
        assert len(DEFAULT_NUMERIC_RULES) > 0

    def test_yyyymm_constants(self):
        """YYYYMM constants should have correct values."""
        assert MIN_YYYYMM_VALUE == 200000
        assert MAX_YYYYMM_VALUE == 999999

    def test_date_range_constant(self):
        """MAX_DATE_RANGE_DAYS should be approximately 10 years."""
        assert MAX_DATE_RANGE_DAYS == 3650

    def test_numeric_rules_does_not_include_percentage(self):
        """Shared DEFAULT_NUMERIC_RULES should NOT include percentage conversion."""
        # This is the minimal common subset (annuity_income version)
        rule_names = [
            rule["name"] if isinstance(rule, dict) else rule
            for rule in DEFAULT_NUMERIC_RULES
        ]
        assert "handle_percentage_conversion" not in rule_names
