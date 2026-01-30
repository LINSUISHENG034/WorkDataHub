"""End-to-end integration tests for Customer MDM pipeline.

Story 7.6-10: Integration Testing & Documentation
AC-1: Create integration test suite for full Customer MDM pipeline

Tests cover the complete data flow:
ETL → Contract Sync → Snapshot Refresh → BI Views

Uses deterministic test data fixtures for predictable assertions.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.conftest import _validate_test_database
from tests.integration.customer_mdm.conftest import use_test_database


@pytest.mark.integration
class TestCustomerMdmEndToEnd:
    """End-to-end tests for Customer MDM pipeline data flow."""

    def test_contract_sync_populates_customer_plan_contract(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1: Verify contract sync creates records from 规模明细.

        Tests that sync_contract_status():
        - Reads from business.规模明细
        - Inserts into customer.customer_plan_contract
        - Uses correct contract status logic (AUM > 0 → 正常)
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        with use_test_database(customer_mdm_test_db):
            result = sync_contract_status(period=test_period, dry_run=False)

        # Assert: Check sync results
        assert result["inserted"] > 0, "Contract sync should insert records"
        assert result["total"] > 0, "Contract sync should process source records"

        # Verify data in target table
        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            # Count records by company_id (filter to test data only)
            count_result = conn.execute(
                text(
                    """
                    SELECT company_id, COUNT(*) as contract_count
                    FROM customer.customer_plan_contract
                    WHERE company_id LIKE 'TEST_%'
                    GROUP BY company_id
                    ORDER BY company_id
                    """
                )
            )
            contracts_by_company = {row[0]: row[1] for row in count_result}

            # TEST_C001 should have 2 contracts (P001/QN01, P002/QN02)
            assert contracts_by_company.get("TEST_C001") == 2
            # TEST_C004 should have 2 contracts (P005/QN01, P006/QN01)
            assert contracts_by_company.get("TEST_C004") == 2

            # Verify contract status logic
            status_result = conn.execute(
                text(
                    """
                    SELECT company_id, contract_status
                    FROM customer.customer_plan_contract
                    WHERE company_id IN ('TEST_C001', 'TEST_C003')
                    ORDER BY company_id
                    """
                )
            )
            statuses = {row[0]: row[1] for row in status_result}

            # TEST_C001 has AUM > 0, so should be 正常
            assert statuses.get("TEST_C001") == "正常"
            # TEST_C003 has AUM = 0, so should be 停缴
            assert statuses.get("TEST_C003") == "停缴"

    def test_snapshot_refresh_aggregates_to_product_line_level(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1: Verify snapshot refresh aggregates contract data.

        Tests that refresh_monthly_snapshot():
        - Reads from customer.customer_plan_contract
        - Aggregates to (company_id, product_line_code) level
        - Calculates AUM from business.规模明细
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import (
            refresh_monthly_snapshot,
            sync_contract_status,
        )

        with use_test_database(customer_mdm_test_db):
            # First run contract sync to populate source table
            sync_contract_status(period=test_period, dry_run=False)
            # Run snapshot refresh
            result = refresh_monthly_snapshot(period=test_period, dry_run=False)

        # Assert: Check refresh results
        assert result["upserted"] > 0, "Snapshot refresh should upsert records"

        # Verify aggregation level
        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            # TEST_C004 has 2 plans in same product line, should aggregate to 1 row
            c004_result = conn.execute(
                text(
                    """
                    SELECT
                        company_id,
                        product_line_code,
                        plan_count,
                        aum_balance
                    FROM customer.fct_customer_business_monthly_status
                    WHERE company_id = 'TEST_C004'
                    """
                )
            )
            c004_rows = list(c004_result)

            assert len(c004_rows) == 1, "TEST_C004 should have 1 aggregated row"
            row = c004_rows[0]
            assert row[2] == 2, "plan_count should be 2 (P005, P006)"
            assert row[3] == 1000000.00, "AUM should be 750000 + 250000"

    def test_bi_views_reflect_snapshot_data(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1: Verify BI star schema views expose snapshot data.

        Tests that BI views:
        - bi.dim_customer shows customers with contracts
        - bi.dim_time reflects snapshot periods
        - bi.fct_customer_monthly_summary exposes fact data
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import (
            refresh_monthly_snapshot,
            sync_contract_status,
        )

        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)
            refresh_monthly_snapshot(period=test_period, dry_run=False)

        # Query BI views
        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            # Check dim_customer has our test customers
            dim_customer_result = conn.execute(
                text("SELECT COUNT(*) FROM bi.dim_customer")
            )
            customer_count = dim_customer_result.scalar()
            assert customer_count > 0, "bi.dim_customer should have customers"

            # Check dim_time has our test period
            dim_time_result = conn.execute(
                text(
                    """
                    SELECT year, month_number
                    FROM bi.dim_time
                    WHERE year = 2026 AND month_number = 1
                    """
                )
            )
            time_rows = list(dim_time_result)
            assert len(time_rows) == 1, "bi.dim_time should have 2026-01"

            # Check fct view reflects our data
            fct_result = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM bi.fct_customer_monthly_summary
                    """
                )
            )
            fct_count = fct_result.scalar()
            assert fct_count > 0, "bi.fct_customer_monthly_summary should have data"


@pytest.mark.integration
class TestContractSyncIdempotency:
    """Tests for contract sync idempotency guarantees."""

    def test_contract_sync_is_idempotent(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1: Verify running contract sync twice produces same result.

        Idempotency is critical for retry safety and hook re-execution.
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        with use_test_database(customer_mdm_test_db):
            # First run
            result1 = sync_contract_status(period=test_period, dry_run=False)
            # Second run (should be idempotent via ON CONFLICT DO NOTHING)
            result2 = sync_contract_status(period=test_period, dry_run=False)

        # First run inserts, second run inserts 0 (already exists)
        assert result1["inserted"] > 0, "First run should insert records"
        assert result2["inserted"] == 0, "Second run should insert 0 (idempotent)"

        # Total source records should be same
        assert result1["total"] == result2["total"]


@pytest.mark.integration
class TestSnapshotRefreshIdempotency:
    """Tests for snapshot refresh idempotency guarantees."""

    def test_snapshot_refresh_is_idempotent(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1: Verify running snapshot refresh twice produces same data.

        Uses ON CONFLICT DO UPDATE for idempotent writes.
        """
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import (
            refresh_monthly_snapshot,
            sync_contract_status,
        )

        with use_test_database(customer_mdm_test_db):
            # Setup: Run contract sync first
            sync_contract_status(period=test_period, dry_run=False)
            # First refresh
            result1 = refresh_monthly_snapshot(period=test_period, dry_run=False)
            # Second refresh (should upsert same records)
            result2 = refresh_monthly_snapshot(period=test_period, dry_run=False)

        # Both runs should process same total records
        assert result1["total"] == result2["total"]

        # Verify data is identical after both runs
        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            count_result = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM customer.fct_customer_business_monthly_status
                    """
                )
            )
            final_count = count_result.scalar()

            # Should have same count as first run (no duplicates)
            assert final_count == result1["upserted"]
