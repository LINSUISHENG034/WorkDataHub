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
