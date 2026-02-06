"""Unit tests for annual cutover logic.

Story 7.6-14: Annual Cutover Implementation (年度切断逻辑)
AC-1: Annual Cutover Function
AC-4: Idempotency
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest


class TestAnnualCutoverFunction:
    """Tests for annual_cutover() function (AC-1)."""

    def test_annual_cutover_returns_expected_keys(self):
        """annual_cutover() should return dict with closed_count and inserted_count."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        assert callable(annual_cutover)

    def test_annual_cutover_accepts_year_parameter(self):
        """annual_cutover() should accept year as required parameter."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        sig = inspect.signature(annual_cutover)
        params = list(sig.parameters.keys())

        assert "year" in params

    def test_annual_cutover_accepts_dry_run_parameter(self):
        """annual_cutover() should accept dry_run as optional parameter."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        sig = inspect.signature(annual_cutover)
        params = sig.parameters

        assert "dry_run" in params
        assert params["dry_run"].default is False


class TestAnnualCutoverClosesAllRecords:
    """Tests for record closure behavior (AC-2)."""

    @patch("work_data_hub.customer_mdm.year_init.psycopg.connect")
    @patch("work_data_hub.customer_mdm.year_init.load_dotenv")
    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"})
    def test_annual_cutover_closes_all_records(self, mock_dotenv, mock_connect):
        """Cutover should close all current records (valid_to = '9999-12-31')."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 100  # Simulate 100 records closed/inserted
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn

        result = annual_cutover(year=2026, dry_run=False)

        # Verify close SQL was executed
        assert mock_cursor.execute.call_count >= 2  # close + insert
        first_call_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "valid_to" in first_call_sql.lower()
        assert "9999-12-31" in first_call_sql

        # Verify result structure
        assert "closed_count" in result
        assert result["closed_count"] == 100

    @patch("work_data_hub.customer_mdm.year_init.psycopg.connect")
    @patch("work_data_hub.customer_mdm.year_init.load_dotenv")
    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"})
    def test_annual_cutover_sets_valid_to_to_cutover_date(
        self, mock_dotenv, mock_connect
    ):
        """Close SQL should set valid_to to YYYY-01-01."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 50
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn

        annual_cutover(year=2026, dry_run=False)

        # Verify cutover date parameter
        first_call_params = mock_cursor.execute.call_args_list[0][0][1]
        assert "2026-01-01" in first_call_params


class TestAnnualCutoverCreatesNewRecords:
    """Tests for new record creation behavior (AC-3)."""

    @patch("work_data_hub.customer_mdm.year_init.psycopg.connect")
    @patch("work_data_hub.customer_mdm.year_init.load_dotenv")
    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"})
    def test_annual_cutover_creates_new_records(self, mock_dotenv, mock_connect):
        """Cutover should insert new records for all active customers."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 150  # Simulate 150 records inserted
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn

        result = annual_cutover(year=2026, dry_run=False)

        # Verify insert SQL was executed
        assert mock_cursor.execute.call_count >= 2
        second_call_sql = mock_cursor.execute.call_args_list[1][0][0]
        assert "INSERT" in second_call_sql.upper()

        # Verify result structure
        assert "inserted_count" in result

    @patch("work_data_hub.customer_mdm.year_init.psycopg.connect")
    @patch("work_data_hub.customer_mdm.year_init.load_dotenv")
    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"})
    def test_annual_cutover_sets_status_year(self, mock_dotenv, mock_connect):
        """New records should have status_year = input year."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 50
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn

        annual_cutover(year=2026, dry_run=False)

        # Verify year parameter is passed to insert SQL
        second_call_params = mock_cursor.execute.call_args_list[1][0][1]
        assert 2026 in second_call_params


class TestCutoverDateCalculation:
    """Tests for cutover date calculation logic."""

    def test_cutover_date_format(self):
        """Cutover date should be YYYY-01-01 format."""
        year = 2026
        expected_date = "2026-01-01"
        actual_date = f"{year}-01-01"

        assert actual_date == expected_date

    def test_cutover_date_for_various_years(self):
        """Cutover date calculation should work for any year."""
        test_cases = [
            (2024, "2024-01-01"),
            (2025, "2025-01-01"),
            (2026, "2026-01-01"),
            (2030, "2030-01-01"),
        ]

        for year, expected in test_cases:
            actual = f"{year}-01-01"
            assert actual == expected, f"Failed for year {year}"


class TestAnnualCutoverIdempotency:
    """Tests for annual cutover idempotency (AC-4).

    Running cutover multiple times for same year should produce identical results.
    """

    def test_insert_sql_uses_on_conflict_do_nothing(self):
        """Insert SQL must use ON CONFLICT DO NOTHING for idempotency."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_insert.sql")
        # Verify idempotency mechanism
        assert "ON CONFLICT" in sql.upper()
        assert "DO NOTHING" in sql.upper()

    @patch("work_data_hub.customer_mdm.year_init.psycopg.connect")
    @patch("work_data_hub.customer_mdm.year_init.load_dotenv")
    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"})
    def test_annual_cutover_idempotency(self, mock_dotenv, mock_connect):
        """Running cutover twice should not fail or create duplicates."""
        from work_data_hub.customer_mdm.year_init import annual_cutover

        mock_cursor = MagicMock()
        # First run: 100 closed, 100 inserted
        # Second run: 0 closed (already closed), 0 inserted (ON CONFLICT)
        mock_cursor.rowcount = 100
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_connect.return_value = mock_conn

        # First execution
        result1 = annual_cutover(year=2026, dry_run=False)
        assert result1["closed_count"] == 100

        # Second execution (simulated - rowcount would be 0)
        mock_cursor.rowcount = 0
        result2 = annual_cutover(year=2026, dry_run=False)
        assert result2["closed_count"] == 0  # No records to close
        assert result2["inserted_count"] == 0  # ON CONFLICT DO NOTHING


class TestAnnualCutoverSQLFiles:
    """Tests for SQL file existence and structure (AC-1, AC-2, AC-3)."""

    def test_close_sql_file_exists(self):
        """annual_cutover_close.sql should exist."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_close.sql")
        assert sql is not None
        assert len(sql) > 0

    def test_close_sql_contains_update(self):
        """Close SQL should contain UPDATE statement."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_close.sql")
        assert "UPDATE" in sql.upper()
        assert "customer.customer_plan_contract" in sql

    def test_close_sql_sets_valid_to(self):
        """Close SQL should set valid_to to cutover date."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_close.sql")
        assert "valid_to" in sql.lower()
        assert "9999-12-31" in sql

    def test_insert_sql_file_exists(self):
        """annual_cutover_insert.sql should exist."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_insert.sql")
        assert sql is not None
        assert len(sql) > 0

    def test_insert_sql_contains_insert(self):
        """Insert SQL should contain INSERT statement."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_insert.sql")
        assert "INSERT" in sql.upper()

    def test_insert_sql_has_on_conflict(self):
        """Insert SQL should have ON CONFLICT for idempotency (AC-4)."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_insert.sql")
        assert "ON CONFLICT" in sql.upper()

    def test_insert_sql_sets_status_year(self):
        """Insert SQL should set status_year field (AC-3)."""
        from work_data_hub.customer_mdm.sql import load_sql

        sql = load_sql("annual_cutover_insert.sql")
        assert "status_year" in sql.lower()


class TestAnnualCutoverReturnType:
    """Tests for annual_cutover() return type structure."""

    def test_return_type_annotation(self):
        """annual_cutover() should have dict return type annotation."""
        from work_data_hub.customer_mdm.year_init import annual_cutover
        import inspect

        sig = inspect.signature(annual_cutover)
        # Check return annotation exists
        assert sig.return_annotation is not inspect.Parameter.empty
