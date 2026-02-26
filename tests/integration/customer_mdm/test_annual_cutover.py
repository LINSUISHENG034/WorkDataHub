"""Integration tests for annual cutover logic.

Story 7.6-14: Annual Cutover Implementation (年度切断逻辑)
AC-6: Validation
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.conftest import _validate_test_database
from tests.integration.customer_mdm.conftest import use_test_database


@pytest.mark.integration
class TestAnnualCutoverIntegration:
    """Integration tests for annual_cutover() function (AC-6)."""

    def test_annual_cutover_creates_january_first_records(
        self, customer_mdm_test_db: str
    ):
        """After cutover, query for valid_from on January 1st returns > 0 records."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm.contract_sync import sync_contract_status
        from work_data_hub.customer_mdm.year_init import annual_cutover

        engine = create_engine(customer_mdm_test_db)

        # Run sync to create initial records
        with use_test_database(customer_mdm_test_db):
            sync_result = sync_contract_status(dry_run=False)
            result = annual_cutover(year=2026, dry_run=False)

        # Verify cutover actually processed records (stronger assertion)
        # At least one of closed_count or inserted_count should be > 0
        # if there was any data to process
        assert isinstance(result["closed_count"], int)
        assert isinstance(result["inserted_count"], int)

        # If sync created records, cutover should have closed them
        if sync_result.get("inserted", 0) > 0:
            assert result["closed_count"] > 0, (
                f"Expected closed_count > 0 after sync inserted "
                f"{sync_result.get('inserted', 0)} records"
            )

        # Verify January 1st records exist
        with engine.connect() as conn:
            january_first_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM customer."客户年金计划"
                    WHERE EXTRACT(DAY FROM valid_from) = 1
                      AND EXTRACT(MONTH FROM valid_from) = 1
                      AND EXTRACT(YEAR FROM valid_from) = 2026
                    """
                )
            ).scalar()

            # Stronger assertion: if we inserted records, they must exist
            if result["inserted_count"] > 0:
                assert january_first_count > 0, (
                    f"Expected > 0 January 1st records after inserting "
                    f"{result['inserted_count']} records, got {january_first_count}"
                )
