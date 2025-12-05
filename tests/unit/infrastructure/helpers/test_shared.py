"""Unit tests for shared helper functions.

Story 5.5.4: Validates extracted shared helpers are correctly implemented
and maintain backward compatibility with domain-specific usage.
"""

import pytest

from work_data_hub.infrastructure.helpers import normalize_month


class TestNormalizeMonth:
    """Tests for normalize_month function."""

    def test_valid_month_format(self) -> None:
        """Test valid YYYYMM format returns unchanged."""
        assert normalize_month("202412") == "202412"
        assert normalize_month("202401") == "202401"
        assert normalize_month("200001") == "200001"
        assert normalize_month("210012") == "210012"

    def test_strips_whitespace(self) -> None:
        """Test whitespace is stripped from input."""
        assert normalize_month("  202412  ") == "202412"
        assert normalize_month("202412 ") == "202412"
        assert normalize_month(" 202412") == "202412"

    def test_none_raises_value_error(self) -> None:
        """Test None input raises ValueError."""
        with pytest.raises(ValueError, match="month is required"):
            normalize_month(None)  # type: ignore[arg-type]

    def test_invalid_length_raises_value_error(self) -> None:
        """Test non-6-digit input raises ValueError."""
        with pytest.raises(ValueError, match="6-digit string"):
            normalize_month("2024")
        with pytest.raises(ValueError, match="6-digit string"):
            normalize_month("20241201")
        with pytest.raises(ValueError, match="6-digit string"):
            normalize_month("")

    def test_non_digit_raises_value_error(self) -> None:
        """Test non-digit input raises ValueError."""
        with pytest.raises(ValueError, match="6-digit string"):
            normalize_month("2024ab")
        with pytest.raises(ValueError, match="6-digit string"):
            normalize_month("abcdef")

    def test_year_out_of_range_raises_value_error(self) -> None:
        """Test year outside 2000-2100 raises ValueError."""
        with pytest.raises(ValueError, match="year component must be between"):
            normalize_month("199912")
        with pytest.raises(ValueError, match="year component must be between"):
            normalize_month("210112")

    def test_month_out_of_range_raises_value_error(self) -> None:
        """Test month outside 01-12 raises ValueError."""
        with pytest.raises(ValueError, match="month component must be between"):
            normalize_month("202400")
        with pytest.raises(ValueError, match="month component must be between"):
            normalize_month("202413")

    def test_boundary_months(self) -> None:
        """Test boundary month values."""
        assert normalize_month("202401") == "202401"  # January
        assert normalize_month("202412") == "202412"  # December

    def test_boundary_years(self) -> None:
        """Test boundary year values."""
        assert normalize_month("200001") == "200001"  # Min year
        assert normalize_month("210001") == "210001"  # Max year


class TestHelperImportCompatibility:
    """Tests to ensure helpers can be imported from both locations."""

    def test_import_from_annuity_performance(self) -> None:
        """Verify annuity_performance can still access normalize_month."""
        from work_data_hub.domain.annuity_performance.helpers import (
            normalize_month as ap_normalize,
        )

        assert ap_normalize("202412") == "202412"

    def test_import_from_annuity_income(self) -> None:
        """Verify annuity_income can still access normalize_month."""
        from work_data_hub.domain.annuity_income.helpers import (
            normalize_month as ai_normalize,
        )

        assert ai_normalize("202412") == "202412"

    def test_same_function_reference(self) -> None:
        """Verify both domains use the same function."""
        from work_data_hub.domain.annuity_income.helpers import (
            normalize_month as ai_normalize,
        )
        from work_data_hub.domain.annuity_performance.helpers import (
            normalize_month as ap_normalize,
        )

        # Both should reference the same function from infrastructure
        assert ai_normalize is ap_normalize
