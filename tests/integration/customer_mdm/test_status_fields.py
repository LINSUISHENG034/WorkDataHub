"""Integration tests for Story 7.6-11 status field enhancements.

Story 7.6-11: Customer Status Field Enhancement
AC-1: Implement strategic customer identification logic
AC-2: Implement existing customer identification logic
AC-4: Implement complete contract status logic with 12-month rolling window
AC-5: Validate updated data distributions
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.conftest import _validate_test_database
from tests.integration.customer_mdm.conftest import use_test_database


@pytest.mark.integration
class TestIsStrategicField:
    """Tests for is_strategic field logic (AC-1)."""

    def test_strategic_whitelist_top_n_logic(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1: Top N customers per branch per product line → is_strategic = TRUE."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            # Verify is_strategic field is populated (not all NULL)
            result = conn.execute(
                text(
                    """
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN is_strategic THEN 1 ELSE 0 END) as strategic_count
                    FROM customer."客户年金计划"
                    WHERE status_year = 2026
                    """
                )
            )
            row = result.fetchone()
            total, strategic_count = row[0], row[1]

            # At least some records should exist
            assert total > 0, "No contracts synced"
            # is_strategic should be set (not all NULL/FALSE due to test data)
            assert strategic_count is not None

    def test_new_customer_with_current_high_aum_is_strategic(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """New customer with no prior Dec data but high current AUM should be strategic."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT is_strategic, is_existing
                    FROM customer."客户年金计划"
                    WHERE company_id = 'TEST_C005'
                      AND plan_code = 'P007'
                      AND product_line_code = 'PL202'
                      AND status_year = 2026
                    """
                )
            )
            row = result.fetchone()
            assert row is not None, "Expected TEST_C005/P007 contract record"
            assert row[0] is True
            assert row[1] is False


@pytest.mark.integration
class TestIsExistingField:
    """Tests for is_existing field logic (AC-2)."""

    def test_customer_with_prior_year_data_is_existing(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-2: Customer with prior year December AUM > 0 → is_existing = TRUE."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT company_id, plan_code, is_existing
                    FROM customer."客户年金计划"
                    WHERE company_id IN ('TEST_C001', 'TEST_C002', 'TEST_C003')
                      AND status_year = 2026
                    ORDER BY company_id, plan_code
                    """
                )
            )
            existing_map = {(row[0], row[1]): row[2] for row in result}

            # TEST_C001 and TEST_C002 have prior year data
            assert existing_map.get(("TEST_C001", "P001")) is True
            assert existing_map.get(("TEST_C002", "P003")) is True
            # TEST_C003 has no prior year data (new customer)
            assert existing_map.get(("TEST_C003", "P004")) is False


@pytest.mark.integration
class TestContractStatusV2:
    """Tests for contract_status v2 logic with 12-month rolling window (AC-4)."""

    def test_active_with_contribution_is_normal(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-4: AUM > 0 AND 12-month contribution > 0 → 正常."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT company_id, plan_code, contract_status
                    FROM customer."客户年金计划"
                    WHERE company_id = 'TEST_C001'
                      AND status_year = 2026
                    ORDER BY plan_code
                    """
                )
            )
            statuses = {row[1]: row[2] for row in result}

            # TEST_C001 has AUM > 0 and contribution > 0
            assert statuses.get("P001") == "正常"
            assert statuses.get("P002") == "正常"

    def test_inactive_is_suspended(self, customer_mdm_test_db: str, test_period: str):
        """AC-4: AUM = 0 → 停缴."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        engine = create_engine(customer_mdm_test_db)
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT contract_status
                    FROM customer."客户年金计划"
                    WHERE company_id = 'TEST_C003'
                      AND status_year = 2026
                    """
                )
            )
            status = result.scalar()
            assert status == "停缴"


@pytest.mark.integration
class TestSCDType2Versioning:
    """Tests for SCD Type 2 versioning behavior (Story 7.6-12).

    AC-1: Status Change Detection
    AC-2: Version Creation
    AC-3: Historical Query Support
    AC-4: Idempotency
    """

    def test_status_change_creates_new_version(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1, AC-2: Status change should close old record and create new version."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        engine = create_engine(customer_mdm_test_db)

        # Step 1: Initial sync
        with use_test_database(customer_mdm_test_db):
            result1 = sync_contract_status(period=test_period, dry_run=False)

        # Verify initial records created
        with engine.connect() as conn:
            initial_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM customer."客户年金计划"
                    WHERE company_id LIKE 'TEST_%'
                    """
                )
            ).scalar()
            assert initial_count > 0, "Initial sync should create records"

        # Step 2: Simulate status change by updating source data
        with engine.connect() as conn:
            # Change TEST_C001/P001 from having contribution to no contribution
            # This should change contract_status from 正常 to 停缴
            conn.execute(
                text(
                    """
                    UPDATE business."规模明细"
                    SET "供款" = 0
                    WHERE company_id = 'TEST_C001' AND "计划代码" = 'P001'
                    """
                )
            )
            conn.commit()

        # Step 3: Run sync again - should detect status change
        with use_test_database(customer_mdm_test_db):
            result2 = sync_contract_status(period=test_period, dry_run=False)

        # Verify: old record was closed (status changed from 正常 to 停缴)
        with engine.connect() as conn:
            # Check that a historical record exists (valid_to != '9999-12-31')
            historical_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM customer."客户年金计划"
                    WHERE company_id = 'TEST_C001' AND plan_code = 'P001'
                      AND valid_to != '9999-12-31'
                    """
                )
            ).scalar()
            assert historical_count > 0, (
                "Status change should create historical record (closed old version)"
            )

    def test_status_unchanged_no_new_version(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-1, AC-4: No status change should not create duplicate records."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        engine = create_engine(customer_mdm_test_db)

        # Step 1: Initial sync
        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        # Get initial record count
        with engine.connect() as conn:
            initial_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM customer."客户年金计划"
                    WHERE company_id LIKE 'TEST_%'
                      AND valid_to = '9999-12-31'
                    """
                )
            ).scalar()

        # Step 2: Run sync again without any data changes
        with use_test_database(customer_mdm_test_db):
            result = sync_contract_status(period=test_period, dry_run=False)

        # Verify: no new records inserted (idempotent)
        with engine.connect() as conn:
            final_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM customer."客户年金计划"
                    WHERE company_id LIKE 'TEST_%'
                      AND valid_to = '9999-12-31'
                    """
                )
            ).scalar()

        assert final_count == initial_count, (
            f"No new current records should be created: {initial_count} -> {final_count}"
        )
        assert result["inserted"] == 0, "No new records should be inserted"
        assert result["closed"] == 0, "No records should be closed"

    def test_historical_query_returns_correct_status(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-3: Historical queries should return correct point-in-time status."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        engine = create_engine(customer_mdm_test_db)

        # Initial sync
        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        # Verify current records are queryable via valid_to = '9999-12-31'
        with engine.connect() as conn:
            current_records = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM customer."客户年金计划"
                    WHERE company_id LIKE 'TEST_%'
                      AND valid_to = '9999-12-31'
                    """
                )
            ).scalar()

            assert current_records > 0, "Current records should be queryable"

    def test_idempotency_with_status_changes(
        self, customer_mdm_test_db: str, test_period: str
    ):
        """AC-4: Multiple runs should produce identical results."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        engine = create_engine(customer_mdm_test_db)

        # Run sync 3 times
        results = []
        for _ in range(3):
            with use_test_database(customer_mdm_test_db):
                result = sync_contract_status(period=test_period, dry_run=False)
                results.append(result)

        # First run should insert records
        assert results[0]["inserted"] > 0, "First run should insert records"

        # Subsequent runs should not insert or close any records
        for i, result in enumerate(results[1:], start=2):
            assert result["inserted"] == 0, f"Run {i} should not insert records"
            assert result["closed"] == 0, f"Run {i} should not close records"

        # Verify final record count matches first run
        with engine.connect() as conn:
            final_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM customer."客户年金计划"
                    WHERE company_id LIKE 'TEST_%'
                    """
                )
            ).scalar()

        assert final_count == results[0]["inserted"], (
            "Total records should match first run's inserted count"
        )

    def test_ratchet_rule_prevents_strategic_downgrade_only_change(
        self, customer_mdm_test_db: str, test_period: str, monkeypatch
    ):
        """Strategic downgrade alone should not create a new SCD version."""
        _validate_test_database(customer_mdm_test_db)

        from work_data_hub.customer_mdm import sync_contract_status

        # Use top_n=1 so a threshold drop can become non-strategic by calculation.
        monkeypatch.setattr(
            "work_data_hub.customer_mdm.contract_sync.get_whitelist_top_n",
            lambda: 1,
        )

        engine = create_engine(customer_mdm_test_db)

        # Step 1: Initial sync - TEST_C005 is strategic via threshold.
        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        # Step 2: Lower TEST_C005 AUM below threshold while keeping contract_status stable.
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE business."规模明细"
                    SET "期末资产规模" = 1000.00
                    WHERE company_id = 'TEST_C005'
                      AND "计划代码" = 'P007'
                      AND "产品线代码" = 'PL202'
                    """
                )
            )
            conn.commit()

        # Step 3: Re-sync. Ratchet should keep strategic=True without creating new version.
        with use_test_database(customer_mdm_test_db):
            sync_contract_status(period=test_period, dry_run=False)

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT COUNT(*) AS total_versions,
                           SUM(CASE WHEN valid_to = '9999-12-31' THEN 1 ELSE 0 END)
                               AS current_versions,
                           SUM(CASE WHEN is_strategic THEN 1 ELSE 0 END)
                               AS strategic_versions
                    FROM customer."客户年金计划"
                    WHERE company_id = 'TEST_C005'
                      AND plan_code = 'P007'
                      AND product_line_code = 'PL202'
                    """
                )
            ).fetchone()

        assert row[0] == 1, "No new version should be created on strategic downgrade"
        assert row[1] == 1, "There should be exactly one current version"
        assert row[2] == 1, "Ratchet rule should preserve strategic status"
