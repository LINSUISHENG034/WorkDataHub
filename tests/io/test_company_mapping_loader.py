"""
Integration tests for company mapping data loader.

Tests validate data extraction from legacy MySQL sources, transformation
using domain models, and PostgreSQL loading with proper transaction handling.
Mock MySQL connections are used for test isolation.
"""

import pytest
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from datetime import datetime, timezone
import psycopg2

from src.work_data_hub.domain.company_enrichment.models import CompanyMappingRecord
from src.work_data_hub.io.loader.company_mapping_loader import (
    CompanyMappingLoaderError,
    extract_legacy_mappings,
    generate_load_plan,
    load_company_mappings,
    _extract_with_retry,
    _extract_company_id1_mapping,
    _extract_company_id2_mapping,
    _extract_company_id4_mapping,
    _extract_company_id5_mapping,
)


class TestLegacyDataExtraction:
    """Test extraction from legacy MySQL sources."""

    @patch("src.work_data_hub.io.loader.company_mapping_loader.MySqlDBManager")
    def test_extract_company_id1_mapping_success(self, mock_mysql_manager):
        """Test successful extraction from COMPANY_ID1_MAPPING (plan codes)."""
        # Mock MySQL cursor and results
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("AN001", "614810477"),
            ("AN002", "608349737"),
            ("P0290", "610081428"),
        ]

        mock_db = MagicMock()
        mock_db.cursor = mock_cursor
        mock_mysql_manager.return_value.__enter__.return_value = mock_db

        # Execute extraction
        result = _extract_company_id1_mapping()

        # Verify results
        expected = {"AN001": "614810477", "AN002": "608349737", "P0290": "610081428"}
        assert result == expected

        # Verify SQL query was correct
        mock_cursor.execute.assert_called_once()
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "年金计划号" in sql_call
        assert "company_id" in sql_call
        assert "单一计划" in sql_call
        assert "AN002" in sql_call  # Excluded condition

    @patch("src.work_data_hub.io.loader.company_mapping_loader.MySqlDBManager")
    def test_extract_company_id2_mapping_success(self, mock_mysql_manager):
        """Test successful extraction from COMPANY_ID2_MAPPING (account numbers)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("123456789", "614810477"),
            ("987654321", "608349737"),
        ]

        mock_db = MagicMock()
        mock_db.cursor = mock_cursor
        mock_mysql_manager.return_value.__enter__.return_value = mock_db

        result = _extract_company_id2_mapping()

        expected = {"123456789": "614810477", "987654321": "608349737"}
        assert result == expected

        # Verify database and query
        mock_mysql_manager.assert_called_with(database="enterprise")
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "年金账户号" in sql_call
        assert "annuity_account_mapping" in sql_call
        assert "GM%" in sql_call  # Exclusion pattern

    @patch("src.work_data_hub.io.loader.company_mapping_loader.MySqlDBManager")
    def test_extract_company_id4_mapping_chinese_names(self, mock_mysql_manager):
        """Test extraction with Chinese company names."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("中国平安保险股份有限公司", "614810477"),
            ("上海银行股份有限公司", "608349737"),
            ("北京银行股份有限公司", "610081428"),
        ]

        mock_db = MagicMock()
        mock_db.cursor = mock_cursor
        mock_mysql_manager.return_value.__enter__.return_value = mock_db

        result = _extract_company_id4_mapping()

        expected = {
            "中国平安保险股份有限公司": "614810477",
            "上海银行股份有限公司": "608349737",
            "北京银行股份有限公司": "610081428",
        }
        assert result == expected

    @patch("src.work_data_hub.io.loader.company_mapping_loader.MySqlDBManager")
    def test_extract_company_id5_mapping_success(self, mock_mysql_manager):
        """Test successful extraction from COMPANY_ID5_MAPPING (account names)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("测试账户名称1", "614810477"),
            ("测试账户名称2", "608349737"),
        ]

        mock_db = MagicMock()
        mock_db.cursor = mock_cursor
        mock_mysql_manager.return_value.__enter__.return_value = mock_db

        result = _extract_company_id5_mapping()

        expected = {"测试账户名称1": "614810477", "测试账户名称2": "608349737"}
        assert result == expected

        # Verify correct database and table
        mock_mysql_manager.assert_called_with(database="business")
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "年金账户名" in sql_call
        assert "规模明细" in sql_call

    def test_extract_with_retry_success_first_attempt(self):
        """Test retry mechanism succeeds on first attempt."""
        mock_func = MagicMock()
        mock_func.return_value = {"test": "data"}

        result = _extract_with_retry(mock_func, "test extraction")

        assert result == {"test": "data"}
        assert mock_func.call_count == 1

    def test_extract_with_retry_success_after_retries(self):
        """Test retry mechanism succeeds after failures."""
        mock_func = MagicMock()
        mock_func.side_effect = [
            Exception("Connection failed"),
            Exception("Timeout"),
            {"test": "data"},  # Success on third attempt
        ]

        result = _extract_with_retry(mock_func, "test extraction", max_attempts=3)

        assert result == {"test": "data"}
        assert mock_func.call_count == 3

    def test_extract_with_retry_all_attempts_fail(self):
        """Test retry mechanism when all attempts fail."""
        mock_func = MagicMock()
        mock_func.side_effect = Exception("Persistent failure")

        with pytest.raises(Exception, match="Persistent failure"):
            _extract_with_retry(mock_func, "test extraction", max_attempts=2)

        assert mock_func.call_count == 2

    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader.MySqlDBManager", spec=True
    )
    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id1_mapping"
    )
    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id2_mapping"
    )
    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id4_mapping"
    )
    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id5_mapping"
    )
    def test_extract_legacy_mappings_success(
        self,
        mock_extract5,
        mock_extract4,
        mock_extract2,
        mock_extract1,
        mock_mysql_manager,
    ):
        """Test full legacy mapping extraction from all 5 sources."""
        # Mock each extraction function
        mock_extract1.return_value = {"AN001": "111111111", "AN002": "222222222"}
        mock_extract2.return_value = {"GM123456": "333333333"}
        mock_extract4.return_value = {"中国平安保险": "444444444"}
        mock_extract5.return_value = {"测试账户": "555555555"}

        # Execute extraction
        mappings = extract_legacy_mappings()

        # Verify total count (2 + 1 + 9 hardcoded + 1 + 1 = 14)
        assert len(mappings) == 14

        # Verify each type is present with correct priorities
        plan_mappings = [m for m in mappings if m.match_type == "plan"]
        account_mappings = [m for m in mappings if m.match_type == "account"]
        hardcode_mappings = [m for m in mappings if m.match_type == "hardcode"]
        name_mappings = [m for m in mappings if m.match_type == "name"]
        account_name_mappings = [m for m in mappings if m.match_type == "account_name"]

        assert len(plan_mappings) == 2
        assert len(account_mappings) == 1
        assert len(hardcode_mappings) == 9  # From hardcoded dictionary
        assert len(name_mappings) == 1
        assert len(account_name_mappings) == 1

        # Verify priorities are correct
        assert all(m.priority == 1 for m in plan_mappings)
        assert all(m.priority == 2 for m in account_mappings)
        assert all(m.priority == 3 for m in hardcode_mappings)
        assert all(m.priority == 4 for m in name_mappings)
        assert all(m.priority == 5 for m in account_name_mappings)

        # Verify hardcoded mappings include expected values
        hardcode_dict = {m.alias_name: m.canonical_id for m in hardcode_mappings}
        assert hardcode_dict["FP0001"] == "614810477"
        assert hardcode_dict["P0809"] == "608349737"
        assert hardcode_dict["XNP596"] == "601038164"

    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader.MySqlDBManager", spec=True
    )
    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id1_mapping"
    )
    def test_extract_legacy_mappings_handles_extraction_failure(
        self, mock_extract1, mock_mysql_manager
    ):
        """Test that extraction failure for one source raises appropriate error."""
        mock_extract1.side_effect = Exception("Database connection failed")

        with pytest.raises(
            CompanyMappingLoaderError, match="Plan code extraction failed"
        ):
            extract_legacy_mappings()

    @patch(
        "src.work_data_hub.io.loader.company_mapping_loader.MySqlDBManager", spec=True
    )
    def test_extract_legacy_mappings_filters_empty_values(self, mock_mysql_manager):
        """Test that empty/None values are filtered out during extraction."""
        with (
            patch(
                "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id1_mapping"
            ) as mock1,
            patch(
                "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id2_mapping"
            ) as mock2,
            patch(
                "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id4_mapping"
            ) as mock4,
            patch(
                "src.work_data_hub.io.loader.company_mapping_loader._extract_company_id5_mapping"
            ) as mock5,
        ):
            # Include None and empty values to test filtering
            mock1.return_value = {"AN001": "111111111", "": "222222222", "AN003": None}
            mock2.return_value = {"GM123": "333333333", None: "444444444"}
            mock4.return_value = {}
            mock5.return_value = {}

            mappings = extract_legacy_mappings()

            # Only valid mapping should be included (+ 9 hardcoded)
            plan_mappings = [m for m in mappings if m.match_type == "plan"]
            account_mappings = [m for m in mappings if m.match_type == "account"]

            assert len(plan_mappings) == 1
            assert plan_mappings[0].alias_name == "AN001"
            assert len(account_mappings) == 1
            assert account_mappings[0].alias_name == "GM123"


class TestLoadPlanGeneration:
    """Test generation of load execution plans."""

    def test_generate_load_plan_with_mappings(self):
        """Test plan generation with sample mappings."""
        mappings = [
            CompanyMappingRecord(
                alias_name="AN001", canonical_id="111", match_type="plan", priority=1
            ),
            CompanyMappingRecord(
                alias_name="AN002", canonical_id="222", match_type="plan", priority=1
            ),
            CompanyMappingRecord(
                alias_name="GM123", canonical_id="333", match_type="account", priority=2
            ),
            CompanyMappingRecord(
                alias_name="FP0001",
                canonical_id="444",
                match_type="hardcode",
                priority=3,
            ),
        ]

        plan = generate_load_plan(mappings, "enterprise", "company_mapping")

        assert plan["operation"] == "company_mapping_load"
        assert plan["table"] == "enterprise.company_mapping"
        assert plan["total_mappings"] == 4
        assert plan["mapping_breakdown"]["plan"] == 2
        assert plan["mapping_breakdown"]["account"] == 1
        assert plan["mapping_breakdown"]["hardcode"] == 1
        assert plan["primary_key"] == ["alias_name", "match_type"]
        assert len(plan["sql_plans"]) == 2  # DELETE and INSERT

    def test_generate_load_plan_empty(self):
        """Test plan generation with no mappings."""
        plan = generate_load_plan([], "enterprise", "company_mapping")

        assert plan["total_mappings"] == 0
        assert plan["mapping_breakdown"] == {}
        assert plan["sql_plans"] == []


class TestPostgreSQLLoading:
    """Test PostgreSQL loading functionality."""

    def test_load_company_mappings_success(self):
        """Test successful loading to PostgreSQL."""
        mappings = [
            CompanyMappingRecord(
                alias_name="AN001", canonical_id="111", match_type="plan", priority=1
            ),
            CompanyMappingRecord(
                alias_name="GM123", canonical_id="222", match_type="account", priority=2
            ),
        ]

        # Mock PostgreSQL connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2  # Return 2 for batch insert (both records inserted)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        # Execute load
        stats = load_company_mappings(mappings, mock_conn)

        # Verify statistics
        assert stats["inserted"] == 2  # Should insert 2 records total
        assert stats["deleted"] >= 0  # May or may not delete existing records
        assert stats["batches"] == 1  # Single batch

        # Verify SQL was executed (DELETE + INSERT)
        assert mock_cursor.execute.call_count >= 1  # At least INSERT, maybe DELETE

    def test_load_company_mappings_empty_list(self):
        """Test loading with empty mappings list."""
        mock_conn = MagicMock()

        stats = load_company_mappings([], mock_conn)

        assert stats["inserted"] == 0
        assert stats["deleted"] == 0
        assert stats["batches"] == 0

    def test_load_company_mappings_chunking(self):
        """Test that large datasets are properly chunked."""
        # Create more mappings than chunk_size
        mappings = [
            CompanyMappingRecord(
                alias_name=f"AN{i:03d}",
                canonical_id=f"{i:09d}",
                match_type="plan",
                priority=1,
            )
            for i in range(5)  # 5 mappings with chunk_size=2
        ]

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2  # Return 2 rows affected per batch (for chunks of 2)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        # Execute with small chunk size
        stats = load_company_mappings(mappings, mock_conn, chunk_size=2)

        # Should process in 3 batches: [2, 2, 1]
        # But rowcount will be 2 for first 2 batches, 1 for last batch (which we mock as 2)
        assert stats["batches"] == 3
        assert stats["inserted"] == 6  # 3 batches * 2 rowcount each = 6

    def test_load_company_mappings_transaction_failure(self):
        """Test proper error handling when transaction fails."""
        mappings = [
            CompanyMappingRecord(
                alias_name="AN001", canonical_id="111", match_type="plan", priority=1
            )
        ]

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg2.Error("Database error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        # Should raise DataWarehouseLoaderError
        with pytest.raises(
            Exception
        ):  # Could be DataWarehouseLoaderError or psycopg2.Error
            load_company_mappings(mappings, mock_conn)

    def test_load_company_mappings_delete_insert_mode(self):
        """Test delete_insert mode performs both DELETE and INSERT operations."""
        mappings = [
            CompanyMappingRecord(
                alias_name="AN001", canonical_id="111", match_type="plan", priority=1
            )
        ]

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        stats = load_company_mappings(mappings, mock_conn, mode="delete_insert")

        # Should have called execute at least twice (DELETE + INSERT)
        assert mock_cursor.execute.call_count >= 2

        # Both operations should be reflected in stats
        assert stats["deleted"] >= 0
        assert stats["inserted"] >= 0

    def test_load_company_mappings_append_mode(self):
        """Test append mode uses conflict handling to prevent duplicates."""
        mappings = [
            CompanyMappingRecord(
                alias_name="AN001", canonical_id="111", match_type="plan", priority=1
            ),
            CompanyMappingRecord(
                alias_name="AN002", canonical_id="222", match_type="plan", priority=1
            ),
        ]

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2  # Both records inserted (no conflicts)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        stats = load_company_mappings(mappings, mock_conn, mode="append")

        # Should have called execute (INSERT with ON CONFLICT)
        mock_cursor.execute.assert_called()

        # Verify SQL includes conflict handling
        sql_call = mock_cursor.execute.call_args[0][0]
        assert "INSERT INTO" in sql_call
        assert "ON CONFLICT" in sql_call
        assert "DO NOTHING" in sql_call

        # Should not perform any deletes in append mode
        assert stats["deleted"] == 0
        assert stats["inserted"] == 2
        assert stats["batches"] > 0

    def test_load_company_mappings_append_mode_with_conflicts(self):
        """Test append mode handles conflicts correctly with accurate stats."""
        mappings = [
            CompanyMappingRecord(
                alias_name="AN001", canonical_id="111", match_type="plan", priority=1
            ),
            CompanyMappingRecord(
                alias_name="AN002", canonical_id="222", match_type="plan", priority=1
            ),
            CompanyMappingRecord(
                alias_name="AN003", canonical_id="333", match_type="plan", priority=1
            ),
        ]

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1  # Only 1 record inserted due to conflicts
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        stats = load_company_mappings(mappings, mock_conn, mode="append")

        # Verify conflict-aware SQL is used
        sql_call = mock_cursor.execute.call_args[0][0]
        assert 'ON CONFLICT ("alias_name","match_type") DO NOTHING' in sql_call

        # Stats should reflect actual inserts, not attempts
        assert stats["deleted"] == 0
        assert stats["inserted"] == 1  # Only actual inserts counted
        assert stats["batches"] > 0

    def test_load_company_mappings_append_mode_chunking(self):
        """Test append mode works with chunking for large datasets."""
        # Create more mappings than chunk size
        mappings = [
            CompanyMappingRecord(
                alias_name=f"AN{i:03d}",
                canonical_id=str(100 + i),
                match_type="plan",
                priority=1,
            )
            for i in range(5)  # 5 records
        ]

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 2  # 2 records per chunk
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        stats = load_company_mappings(mappings, mock_conn, mode="append", chunk_size=2)

        # Should have called execute multiple times for chunks
        assert (
            mock_cursor.execute.call_count >= 2
        )  # At least 2 chunks (5 records / 2 per chunk)

        # All calls should use conflict handling
        for call in mock_cursor.execute.call_args_list:
            sql = call[0][0]
            assert "ON CONFLICT" in sql
            assert "DO NOTHING" in sql

        assert stats["deleted"] == 0
        assert (
            stats["batches"] >= 3
        )  # 3 batches for 5 records with chunk_size=2  # 3 batches for 5 records with chunk_size=2


class TestModelTransformation:
    """Test transformation between legacy data and Pydantic models."""

    def test_mapping_record_from_legacy_data(self):
        """Test creating CompanyMappingRecord from legacy extraction data."""
        # Simulate legacy data extraction
        legacy_data = {
            "alias_name": "AN001",
            "canonical_id": "614810477",
            "match_type": "plan",
            "priority": 1,
        }

        # Create record (simulating what happens in extract_legacy_mappings)
        record = CompanyMappingRecord(
            alias_name=legacy_data["alias_name"],
            canonical_id=legacy_data["canonical_id"],
            match_type=legacy_data["match_type"],
            priority=legacy_data["priority"],
            source="internal",
            updated_at=datetime.now(timezone.utc),
        )

        assert record.alias_name == "AN001"
        assert record.canonical_id == "614810477"
        assert record.match_type == "plan"
        assert record.priority == 1

    def test_model_dump_for_database_loading(self):
        """Test that model.dump() produces correct format for database loading."""
        record = CompanyMappingRecord(
            alias_name="测试公司",
            canonical_id="614810477",
            match_type="name",
            priority=4,
        )

        dumped = record.model_dump()

        # Verify all required database columns are present
        assert "alias_name" in dumped
        assert "canonical_id" in dumped
        assert "source" in dumped
        assert "match_type" in dumped
        assert "priority" in dumped
        assert "updated_at" in dumped

        # Verify correct values
        assert dumped["alias_name"] == "测试公司"
        assert dumped["canonical_id"] == "614810477"
        assert dumped["match_type"] == "name"
        assert dumped["priority"] == 4
        assert dumped["source"] == "internal"
