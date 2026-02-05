"""Unit tests for contract sync SCD Type 2 logic.

Story 7.6-12: SCD Type 2 Implementation Fix
AC-1: Status Change Detection
AC-2: Version Creation
AC-4: Idempotency
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class MockContractRecord:
    """Mock contract record for testing status change detection."""

    contract_status: str
    is_strategic: bool
    is_existing: bool


class TestHasStatusChanged:
    """Tests for has_status_changed() detection function (AC-1)."""

    def test_contract_status_change_detected(self):
        """Change in contract_status should trigger version creation."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = MockContractRecord(
            contract_status="正常", is_strategic=False, is_existing=True
        )
        new = MockContractRecord(
            contract_status="停缴", is_strategic=False, is_existing=True
        )

        assert has_status_changed(old, new) is True

    def test_is_strategic_change_detected(self):
        """Change in is_strategic should trigger version creation."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = MockContractRecord(
            contract_status="正常", is_strategic=False, is_existing=True
        )
        new = MockContractRecord(
            contract_status="正常", is_strategic=True, is_existing=True
        )

        assert has_status_changed(old, new) is True

    def test_is_existing_change_detected(self):
        """Change in is_existing should trigger version creation."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = MockContractRecord(
            contract_status="正常", is_strategic=False, is_existing=False
        )
        new = MockContractRecord(
            contract_status="正常", is_strategic=False, is_existing=True
        )

        assert has_status_changed(old, new) is True

    def test_no_change_returns_false(self):
        """No change in tracked fields should return False."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = MockContractRecord(
            contract_status="正常", is_strategic=True, is_existing=True
        )
        new = MockContractRecord(
            contract_status="正常", is_strategic=True, is_existing=True
        )

        assert has_status_changed(old, new) is False

    def test_multiple_changes_detected(self):
        """Multiple field changes should still return True."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = MockContractRecord(
            contract_status="正常", is_strategic=False, is_existing=False
        )
        new = MockContractRecord(
            contract_status="停缴", is_strategic=True, is_existing=True
        )

        assert has_status_changed(old, new) is True


class TestStatusChangeDetectionWithDict:
    """Tests for has_status_changed() with dict inputs (SQL result format)."""

    def test_dict_input_contract_status_change(self):
        """Dict inputs should work for status change detection."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": "正常", "is_strategic": False, "is_existing": True}
        new = {"contract_status": "停缴", "is_strategic": False, "is_existing": True}

        assert has_status_changed(old, new) is True

    def test_dict_input_no_change(self):
        """Dict inputs with no change should return False."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": "正常", "is_strategic": True, "is_existing": True}
        new = {"contract_status": "正常", "is_strategic": True, "is_existing": True}

        assert has_status_changed(old, new) is False


class TestStatusChangeDetectionWithNullValues:
    """Tests for has_status_changed() with NULL/None values (M-2 edge cases)."""

    def test_both_none_returns_false(self):
        """Both values None should return False (no change)."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": None, "is_strategic": None, "is_existing": None}
        new = {"contract_status": None, "is_strategic": None, "is_existing": None}

        assert has_status_changed(old, new) is False

    def test_none_to_value_returns_true(self):
        """Change from None to value should return True."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": None, "is_strategic": None, "is_existing": None}
        new = {"contract_status": "正常", "is_strategic": False, "is_existing": True}

        assert has_status_changed(old, new) is True

    def test_value_to_none_returns_true(self):
        """Change from value to None should return True."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": "正常", "is_strategic": True, "is_existing": True}
        new = {"contract_status": None, "is_strategic": None, "is_existing": None}

        assert has_status_changed(old, new) is True

    def test_missing_key_treated_as_none(self):
        """Missing dict key should be treated as None."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {}  # All keys missing
        new = {}  # All keys missing

        assert has_status_changed(old, new) is False

    def test_partial_none_change_detected(self):
        """Change in one field with others None should be detected."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": "正常", "is_strategic": None, "is_existing": None}
        new = {"contract_status": "停缴", "is_strategic": None, "is_existing": None}

        assert has_status_changed(old, new) is True


class TestApplyRatchetRule:
    """Tests for apply_ratchet_rule() - Story 7.6-15 Ratchet Rule Implementation.

    Business Rule (Principle 3 - 只增不减):
    - Can upgrade: FALSE → TRUE (triggers SCD update)
    - Cannot downgrade: TRUE → FALSE (no SCD update, keep strategic status)
    """

    def test_ratchet_rule_prevents_downgrade(self):
        """Strategic customer AUM drops → remains strategic, no SCD update (AC-1)."""
        from work_data_hub.customer_mdm.contract_sync import apply_ratchet_rule

        # Strategic customer (is_strategic_db=True) with calculated downgrade
        final_status, should_update = apply_ratchet_rule(
            is_strategic_db=True,
            is_strategic_calculated=False,
        )

        # Ratchet rule: keep strategic status, no SCD update
        assert final_status is True
        assert should_update is False

    def test_ratchet_rule_allows_upgrade(self):
        """Non-strategic customer AUM rises → becomes strategic, SCD update (AC-1)."""
        from work_data_hub.customer_mdm.contract_sync import apply_ratchet_rule

        # Non-strategic customer (is_strategic_db=False) with calculated upgrade
        final_status, should_update = apply_ratchet_rule(
            is_strategic_db=False,
            is_strategic_calculated=True,
        )

        # Upgrade allowed: new strategic status, trigger SCD update
        assert final_status is True
        assert should_update is True

    def test_ratchet_rule_no_change_strategic(self):
        """Strategic customer remains strategic → no SCD update."""
        from work_data_hub.customer_mdm.contract_sync import apply_ratchet_rule

        final_status, should_update = apply_ratchet_rule(
            is_strategic_db=True,
            is_strategic_calculated=True,
        )

        assert final_status is True
        assert should_update is False

    def test_ratchet_rule_no_change_non_strategic(self):
        """Non-strategic customer remains non-strategic → no SCD update."""
        from work_data_hub.customer_mdm.contract_sync import apply_ratchet_rule

        final_status, should_update = apply_ratchet_rule(
            is_strategic_db=False,
            is_strategic_calculated=False,
        )

        assert final_status is False
        assert should_update is False

    def test_ratchet_rule_with_none_db_value(self):
        """New customer (None in DB) with strategic calculation → upgrade."""
        from work_data_hub.customer_mdm.contract_sync import apply_ratchet_rule

        final_status, should_update = apply_ratchet_rule(
            is_strategic_db=None,
            is_strategic_calculated=True,
        )

        # New customer becoming strategic should trigger update
        assert final_status is True
        assert should_update is True

    def test_ratchet_rule_with_none_db_non_strategic(self):
        """New customer (None in DB) with non-strategic calculation → no update."""
        from work_data_hub.customer_mdm.contract_sync import apply_ratchet_rule

        final_status, should_update = apply_ratchet_rule(
            is_strategic_db=None,
            is_strategic_calculated=False,
        )

        # New non-strategic customer, no status change to trigger
        assert final_status is False
        assert should_update is False


class TestContractStatusChangeDetection:
    """Tests for contract_status change detection with Ratchet Rule (AC-5).

    Story 7.6-15: Verify contract_status changes are detected correctly
    while is_strategic follows the Ratchet Rule.
    """

    def test_contract_status_change_正常_to_停缴(self):
        """Contract status change from 正常 to 停缴 should be detected."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": "正常", "is_strategic": True, "is_existing": True}
        new = {"contract_status": "停缴", "is_strategic": True, "is_existing": True}

        assert has_status_changed(old, new) is True

    def test_contract_status_change_停缴_to_正常(self):
        """Contract status change from 停缴 to 正常 should be detected."""
        from work_data_hub.customer_mdm.contract_sync import has_status_changed

        old = {"contract_status": "停缴", "is_strategic": False, "is_existing": True}
        new = {"contract_status": "正常", "is_strategic": False, "is_existing": True}

        assert has_status_changed(old, new) is True

    def test_strategic_downgrade_with_contract_status_change(self):
        """Contract status change detected even with strategic downgrade.

        Ratchet Rule applies to is_strategic, but contract_status changes
        should still be detected independently.
        """
        from work_data_hub.customer_mdm.contract_sync import (
            apply_ratchet_rule,
            has_status_changed,
        )

        # Strategic customer with AUM drop (would downgrade)
        # but also has contract_status change
        old = {"contract_status": "正常", "is_strategic": True, "is_existing": True}
        new = {"contract_status": "停缴", "is_strategic": False, "is_existing": True}

        # has_status_changed detects the contract_status change
        assert has_status_changed(old, new) is True

        # But Ratchet Rule prevents is_strategic downgrade
        final_status, should_update = apply_ratchet_rule(
            is_strategic_db=True,
            is_strategic_calculated=False,
        )
        assert final_status is True  # Kept strategic
        assert should_update is False  # No SCD update for is_strategic
