"""Unit tests for shared mapping constants.

Story 5.5.4: Validates extracted shared mappings are correctly defined
and maintain backward compatibility with domain-specific usage.
"""

import pytest

from work_data_hub.infrastructure.mappings import (
    BUSINESS_TYPE_CODE_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)


class TestBusinessTypeCodeMapping:
    """Tests for BUSINESS_TYPE_CODE_MAPPING."""

    def test_mapping_is_dict(self) -> None:
        assert isinstance(BUSINESS_TYPE_CODE_MAPPING, dict)

    def test_mapping_has_expected_keys(self) -> None:
        expected_keys = {
            "企年投资",
            "企年受托",
            "职年投资",
            "职年受托",
            "自有险资",
            "直投",
            "三方",
            "团养",
            "企康",
            "企业年金",
            "职业年金",
            "其他",
        }
        assert set(BUSINESS_TYPE_CODE_MAPPING.keys()) == expected_keys

    def test_mapping_values_are_product_line_codes(self) -> None:
        for value in BUSINESS_TYPE_CODE_MAPPING.values():
            assert value.startswith("PL"), f"Expected PL prefix, got {value}"

    def test_specific_mappings(self) -> None:
        assert BUSINESS_TYPE_CODE_MAPPING["企年投资"] == "PL201"
        assert BUSINESS_TYPE_CODE_MAPPING["职年受托"] == "PL204"
        assert BUSINESS_TYPE_CODE_MAPPING["其他"] == "PL301"


class TestDefaultPortfolioCodeMapping:
    """Tests for DEFAULT_PORTFOLIO_CODE_MAPPING."""

    def test_mapping_is_dict(self) -> None:
        assert isinstance(DEFAULT_PORTFOLIO_CODE_MAPPING, dict)

    def test_mapping_has_expected_keys(self) -> None:
        expected_keys = {"集合计划", "单一计划", "职业年金"}
        assert set(DEFAULT_PORTFOLIO_CODE_MAPPING.keys()) == expected_keys

    def test_mapping_values_are_qtan_codes(self) -> None:
        for value in DEFAULT_PORTFOLIO_CODE_MAPPING.values():
            assert value.startswith("QTAN"), f"Expected QTAN prefix, got {value}"

    def test_specific_mappings(self) -> None:
        assert DEFAULT_PORTFOLIO_CODE_MAPPING["集合计划"] == "QTAN001"
        assert DEFAULT_PORTFOLIO_CODE_MAPPING["单一计划"] == "QTAN002"
        assert DEFAULT_PORTFOLIO_CODE_MAPPING["职业年金"] == "QTAN003"


class TestPortfolioQtan003BusinessTypes:
    """Tests for PORTFOLIO_QTAN003_BUSINESS_TYPES."""

    def test_is_sequence(self) -> None:
        assert hasattr(PORTFOLIO_QTAN003_BUSINESS_TYPES, "__iter__")

    def test_contains_expected_types(self) -> None:
        assert "职年受托" in PORTFOLIO_QTAN003_BUSINESS_TYPES
        assert "职年投资" in PORTFOLIO_QTAN003_BUSINESS_TYPES

    def test_length(self) -> None:
        assert len(PORTFOLIO_QTAN003_BUSINESS_TYPES) == 2


class TestCompanyBranchMapping:
    """Tests for COMPANY_BRANCH_MAPPING."""

    def test_mapping_is_dict(self) -> None:
        assert isinstance(COMPANY_BRANCH_MAPPING, dict)

    def test_mapping_values_are_institution_codes(self) -> None:
        for value in COMPANY_BRANCH_MAPPING.values():
            assert value.startswith("G"), f"Expected G prefix, got {value}"

    def test_standard_mappings(self) -> None:
        """Test standard mappings shared across all domains."""
        assert COMPANY_BRANCH_MAPPING["总部"] == "G00"
        assert COMPANY_BRANCH_MAPPING["北京"] == "G01"
        assert COMPANY_BRANCH_MAPPING["上海"] == "G02"
        assert COMPANY_BRANCH_MAPPING["深圳"] == "G05"
        assert COMPANY_BRANCH_MAPPING["山东"] == "G21"

    def test_legacy_overrides_included(self) -> None:
        """Test legacy overrides from annuity_income are included (Story 5.5-1 gap)."""
        # These 6 legacy overrides were missing from annuity_performance
        assert COMPANY_BRANCH_MAPPING["内蒙"] == "G31"
        assert COMPANY_BRANCH_MAPPING["战略"] == "G37"
        assert COMPANY_BRANCH_MAPPING["中国"] == "G37"
        assert COMPANY_BRANCH_MAPPING["济南"] == "G21"
        assert COMPANY_BRANCH_MAPPING["北京其他"] == "G37"
        assert COMPANY_BRANCH_MAPPING["北分"] == "G37"

    def test_mapping_count(self) -> None:
        """Verify total mapping count includes legacy overrides."""
        # 20 standard + 6 legacy = 26 total
        assert len(COMPANY_BRANCH_MAPPING) == 26


class TestMappingImportCompatibility:
    """Tests to ensure mappings can be imported from both locations."""

    def test_import_from_annuity_performance(self) -> None:
        """Verify annuity_performance can still access mappings."""
        from work_data_hub.domain.annuity_performance.constants import (
            BUSINESS_TYPE_CODE_MAPPING as AP_MAPPING,
        )

        assert AP_MAPPING == BUSINESS_TYPE_CODE_MAPPING

    def test_import_from_annuity_income(self) -> None:
        """Verify annuity_income can still access mappings."""
        from work_data_hub.domain.annuity_income.constants import (
            BUSINESS_TYPE_CODE_MAPPING as AI_MAPPING,
        )

        assert AI_MAPPING == BUSINESS_TYPE_CODE_MAPPING
