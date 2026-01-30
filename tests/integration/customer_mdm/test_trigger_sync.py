"""Tests for product line name sync trigger.

Story 7.6-10: Integration Testing & Documentation
AC-8: Verify product_line_name sync trigger propagates changes correctly

Tests the trigger created in Migration 011 that syncs product_line_name
from mapping."产品线" to denormalized columns in:
- customer.customer_plan_contract
- customer.fct_customer_business_monthly_status
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from tests.conftest import _validate_test_database
from tests.integration.customer_mdm.conftest import use_test_database


@pytest.mark.integration
class TestProductLineNameSyncTrigger:
    """Tests for trg_sync_product_line_name trigger on mapping.产品线."""

    def test_trigger_propagates_name_change_to_contract_table(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-8: Verify trigger updates customer_plan_contract.product_line_name.

        When 产品线.产品线 is updated, the trigger should propagate
        the new name to customer_plan_contract.
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        # Setup: Populate contract table
        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)

        with engine.begin() as conn:
            # Verify initial state: product_line_name should match 产品线
            initial_result = conn.execute(
                text(
                    """
                    SELECT DISTINCT product_line_name
                    FROM customer.customer_plan_contract
                    WHERE product_line_code = 'PL202'
                    """
                )
            )
            initial_name = initial_result.scalar()
            assert initial_name == "企年受托", (
                f"Initial name should be 企年受托, got {initial_name}"
            )

            # Act: Update product line name in mapping table
            conn.execute(
                text(
                    """
                    UPDATE mapping."产品线"
                    SET "产品线" = '企年受托(改名)'
                    WHERE "产品线代码" = 'PL202'
                    """
                )
            )

            # Assert: Trigger should have propagated the change
            updated_result = conn.execute(
                text(
                    """
                    SELECT DISTINCT product_line_name
                    FROM customer.customer_plan_contract
                    WHERE product_line_code = 'PL202'
                    """
                )
            )
            updated_name = updated_result.scalar()
            assert updated_name == "企年受托(改名)", (
                f"Trigger should update name to 企年受托(改名), got {updated_name}"
            )

            # Cleanup: Revert the name change
            conn.execute(
                text(
                    """
                    UPDATE mapping."产品线"
                    SET "产品线" = '企年受托'
                    WHERE "产品线代码" = 'PL202'
                    """
                )
            )

    def test_trigger_propagates_name_change_to_snapshot_table(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-8: Verify trigger updates fct_customer_business_monthly_status.product_line_name.

        When 产品线.产品线 is updated, the trigger should propagate
        the new name to the monthly snapshot fact table.
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import (
            refresh_monthly_snapshot,
            sync_contract_status,
        )

        # Setup: Populate both tables
        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)
            refresh_monthly_snapshot(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)

        with engine.begin() as conn:
            # Verify initial state
            initial_result = conn.execute(
                text(
                    """
                    SELECT DISTINCT product_line_name
                    FROM customer.fct_customer_business_monthly_status
                    WHERE product_line_code = 'PL202'
                    """
                )
            )
            initial_name = initial_result.scalar()
            assert initial_name == "企年受托"

            # Act: Update product line name
            conn.execute(
                text(
                    """
                    UPDATE mapping."产品线"
                    SET "产品线" = '企年受托(测试改名)'
                    WHERE "产品线代码" = 'PL202'
                    """
                )
            )

            # Assert: Trigger propagated to snapshot table
            updated_result = conn.execute(
                text(
                    """
                    SELECT DISTINCT product_line_name
                    FROM customer.fct_customer_business_monthly_status
                    WHERE product_line_code = 'PL202'
                    """
                )
            )
            updated_name = updated_result.scalar()
            assert updated_name == "企年受托(测试改名)", (
                f"Trigger should update snapshot name, got {updated_name}"
            )

            # Cleanup
            conn.execute(
                text(
                    """
                    UPDATE mapping."产品线"
                    SET "产品线" = '企年受托'
                    WHERE "产品线代码" = 'PL202'
                    """
                )
            )

    def test_trigger_only_fires_on_name_change(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-8: Verify trigger uses IS DISTINCT FROM for NULL-safe comparison.

        The trigger WHEN clause should only fire when 产品线 actually changes,
        not on unrelated updates to the mapping table.
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        # Setup: Populate contract table
        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)

        with engine.begin() as conn:
            # Get initial updated_at timestamp
            initial_ts = conn.execute(
                text(
                    """
                    SELECT MAX(updated_at)
                    FROM customer.customer_plan_contract
                    WHERE product_line_code = 'PL202'
                    """
                )
            ).scalar()

            # Act: Update a DIFFERENT column in the mapping table (NOT 产品线)
            conn.execute(
                text(
                    """
                    UPDATE mapping."产品线"
                    SET "业务大类" = '年金业务(更新)'
                    WHERE "产品线代码" = 'PL202'
                    """
                )
            )

            # Assert: Contract table should NOT have been updated
            # (trigger WHEN clause filters on 产品线 change only)
            after_ts = conn.execute(
                text(
                    """
                    SELECT MAX(updated_at)
                    FROM customer.customer_plan_contract
                    WHERE product_line_code = 'PL202'
                    """
                )
            ).scalar()

            assert initial_ts == after_ts, (
                "Trigger should not fire when 产品线 name doesn't change"
            )

            # Cleanup
            conn.execute(
                text(
                    """
                    UPDATE mapping."产品线"
                    SET "业务大类" = '年金业务'
                    WHERE "产品线代码" = 'PL202'
                    """
                )
            )
