"""Unit tests for strategic customer identification logic.

Story 7.6-11: Customer Status Field Enhancement
AC-1: Implement strategic customer identification logic
AC-4: Implement complete contract status logic with 12-month rolling window
"""

from __future__ import annotations

import pytest


class TestStrategicCustomerThreshold:
    """Tests for AUM threshold-based strategic customer identification."""

    def test_customer_above_threshold_is_strategic(self):
        """Customer with AUM >= 500M should be strategic."""
        from work_data_hub.customer_mdm.strategic import is_strategic_by_threshold

        # 500M yuan = 500,000,000
        assert is_strategic_by_threshold(500_000_000) is True
        assert is_strategic_by_threshold(600_000_000) is True

    def test_customer_below_threshold_is_not_strategic(self):
        """Customer with AUM < 500M should not be strategic."""
        from work_data_hub.customer_mdm.strategic import is_strategic_by_threshold

        assert is_strategic_by_threshold(499_999_999) is False
        assert is_strategic_by_threshold(100_000_000) is False
        assert is_strategic_by_threshold(0) is False

    def test_threshold_is_configurable(self):
        """Threshold should be loaded from config."""
        from work_data_hub.customer_mdm.strategic import get_strategic_threshold

        threshold = get_strategic_threshold()
        assert threshold == 500_000_000

    def test_negative_aum_is_not_strategic(self):
        """Negative AUM should not be strategic."""
        from work_data_hub.customer_mdm.strategic import is_strategic_by_threshold

        assert is_strategic_by_threshold(-1000) is False
        assert is_strategic_by_threshold(-500_000_000) is False

    def test_float_precision_boundary(self):
        """Float values near threshold boundary should be handled correctly."""
        from work_data_hub.customer_mdm.strategic import is_strategic_by_threshold

        # Just below threshold (float)
        assert is_strategic_by_threshold(499_999_999.99) is False
        # At threshold (float)
        assert is_strategic_by_threshold(500_000_000.00) is True
        # Just above threshold (float)
        assert is_strategic_by_threshold(500_000_000.01) is True


class TestStrategicWhitelist:
    """Tests for whitelist-based strategic customer identification."""

    def test_top_n_per_branch_is_configurable(self):
        """Top N value should be loaded from config."""
        from work_data_hub.customer_mdm.strategic import get_whitelist_top_n

        top_n = get_whitelist_top_n()
        assert top_n == 10


class TestConfigCache:
    """Tests for configuration caching behavior."""

    def test_clear_config_cache(self):
        """Config cache should be clearable."""
        from work_data_hub.customer_mdm.strategic import (
            clear_config_cache,
            get_strategic_threshold,
        )

        # Load config (populates cache)
        get_strategic_threshold()

        # Clear cache
        clear_config_cache()

        # Should still work after clearing
        threshold = get_strategic_threshold()
        assert threshold == 500_000_000


class TestContractStatusV2:
    """Tests for contract status v2 logic (12-month rolling window)."""

    def test_active_with_contribution_is_normal(self):
        """AUM > 0 AND has contribution → 正常."""
        from work_data_hub.customer_mdm.contract_sync import determine_contract_status

        assert determine_contract_status(1000000, has_contribution_12m=True) == "正常"

    def test_active_without_contribution_is_suspended(self):
        """AUM > 0 AND no contribution → 停缴."""
        from work_data_hub.customer_mdm.contract_sync import determine_contract_status

        assert determine_contract_status(1000000, has_contribution_12m=False) == "停缴"

    def test_zero_aum_is_suspended(self):
        """AUM = 0 → 停缴 regardless of contribution."""
        from work_data_hub.customer_mdm.contract_sync import determine_contract_status

        assert determine_contract_status(0, has_contribution_12m=True) == "停缴"
        assert determine_contract_status(0, has_contribution_12m=False) == "停缴"

    def test_default_has_contribution_is_true(self):
        """Default behavior assumes contribution exists (backward compat)."""
        from work_data_hub.customer_mdm.contract_sync import determine_contract_status

        # Without explicit has_contribution_12m, defaults to True
        assert determine_contract_status(1000000) == "正常"

    def test_negative_aum_is_suspended(self):
        """Negative AUM should be treated as suspended."""
        from work_data_hub.customer_mdm.contract_sync import determine_contract_status

        assert determine_contract_status(-1000, has_contribution_12m=True) == "停缴"
        assert determine_contract_status(-1000, has_contribution_12m=False) == "停缴"

    def test_float_aum_boundary(self):
        """Float AUM values near zero should be handled correctly."""
        from work_data_hub.customer_mdm.contract_sync import determine_contract_status

        # Very small positive AUM with contribution → 正常
        assert determine_contract_status(0.01, has_contribution_12m=True) == "正常"
        # Zero AUM → 停缴
        assert determine_contract_status(0.0, has_contribution_12m=True) == "停缴"
