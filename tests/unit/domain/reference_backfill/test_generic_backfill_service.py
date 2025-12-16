"""
Unit tests for GenericBackfillService.

Tests the generic backfill service functionality including:
- Topological sorting of dependencies
- Candidate derivation with optional columns
- Circular dependency detection
- Tracking field addition
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.engine import Connection

from work_data_hub.domain.reference_backfill.generic_service import GenericBackfillService, BackfillResult
from work_data_hub.domain.reference_backfill.models import ForeignKeyConfig, BackfillColumnMapping


class TestTopologicalSort:
    """Test topological sorting of foreign key configurations."""

    def test_no_dependencies(self):
        """Test sorting when no dependencies exist."""
        service = GenericBackfillService("test_domain")

        configs = [
            ForeignKeyConfig(
                name="fk_a",
                source_column="col_a",
                target_table="table_a",
                target_key="key_a",
                backfill_columns=[BackfillColumnMapping(source="a", target="a")]
            ),
            ForeignKeyConfig(
                name="fk_b",
                source_column="col_b",
                target_table="table_b",
                target_key="key_b",
                backfill_columns=[BackfillColumnMapping(source="b", target="b")]
            )
        ]

        sorted_configs = service._topological_sort(configs)

        # Should maintain order when no dependencies
        assert [c.name for c in sorted_configs] == ["fk_a", "fk_b"]

    def test_simple_dependency(self):
        """Test sorting with simple dependency chain."""
        service = GenericBackfillService("test_domain")

        configs = [
            ForeignKeyConfig(
                name="fk_portfolio",
                source_column="portfolio_code",
                target_table="portfolio",
                target_key="portfolio_key",
                depends_on=["fk_plan"],
                backfill_columns=[BackfillColumnMapping(source="p", target="p")]
            ),
            ForeignKeyConfig(
                name="fk_plan",
                source_column="plan_code",
                target_table="plan",
                target_key="plan_key",
                backfill_columns=[BackfillColumnMapping(source="pl", target="pl")]
            )
        ]

        sorted_configs = service._topological_sort(configs)

        # Plan should come before portfolio
        assert [c.name for c in sorted_configs] == ["fk_plan", "fk_portfolio"]

    def test_multiple_dependencies(self):
        """Test sorting with multiple dependencies."""
        service = GenericBackfillService("test_domain")

        configs = [
            ForeignKeyConfig(
                name="fk_c",
                source_column="col_c",
                target_table="table_c",
                target_key="key_c",
                depends_on=["fk_a", "fk_b"],
                backfill_columns=[BackfillColumnMapping(source="c", target="c")]
            ),
            ForeignKeyConfig(
                name="fk_b",
                source_column="col_b",
                target_table="table_b",
                target_key="key_b",
                depends_on=["fk_a"],
                backfill_columns=[BackfillColumnMapping(source="b", target="b")]
            ),
            ForeignKeyConfig(
                name="fk_a",
                source_column="col_a",
                target_table="table_a",
                target_key="key_a",
                backfill_columns=[BackfillColumnMapping(source="a", target="a")]
            )
        ]

        sorted_configs = service._topological_sort(configs)

        # Should be A -> B -> C
        assert [c.name for c in sorted_configs] == ["fk_a", "fk_b", "fk_c"]

    def test_circular_dependency(self):
        """Test circular dependency detection."""
        service = GenericBackfillService("test_domain")

        configs = [
            ForeignKeyConfig(
                name="fk_a",
                source_column="col_a",
                target_table="table_a",
                target_key="key_a",
                depends_on=["fk_b"],
                backfill_columns=[BackfillColumnMapping(source="a", target="a")]
            ),
            ForeignKeyConfig(
                name="fk_b",
                source_column="col_b",
                target_table="table_b",
                target_key="key_b",
                depends_on=["fk_a"],
                backfill_columns=[BackfillColumnMapping(source="b", target="b")]
            )
        ]

        with pytest.raises(ValueError) as exc_info:
            service._topological_sort(configs)

        assert "Circular dependency detected" in str(exc_info.value)

    def test_unknown_dependency(self):
        """Test unknown dependency detection."""
        service = GenericBackfillService("test_domain")

        configs = [
            ForeignKeyConfig(
                name="fk_a",
                source_column="col_a",
                target_table="table_a",
                target_key="key_a",
                depends_on=["fk_nonexistent"],
                backfill_columns=[BackfillColumnMapping(source="a", target="a")]
            )
        ]

        with pytest.raises(ValueError) as exc_info:
            service._topological_sort(configs)

        assert "depends on unknown key 'fk_nonexistent'" in str(exc_info.value)


class TestDeriveCandidates:
    """Test candidate derivation from fact data."""

    def test_basic_candidate_derivation(self):
        """Test basic candidate derivation."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(source="计划名称", target="计划名称")
            ]
        )

        df = pd.DataFrame([
            {"计划代码": "P001", "计划名称": "Plan A", "其他列": "value1"},
            {"计划代码": "P002", "计划名称": "Plan B", "其他列": "value2"},
            {"计划代码": "P001", "计划名称": "Plan A", "其他列": "value3"},  # Duplicate
        ])

        candidates_df = service.derive_candidates(df, config)

        assert len(candidates_df) == 2  # Two unique plans
        assert set(candidates_df["年金计划号"]) == {"P001", "P002"}
        assert "计划名称" in candidates_df.columns

    def test_optional_column_handling(self):
        """Test optional column handling."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(source="可选列", target="可选目标列", optional=True)
            ]
        )

        df = pd.DataFrame([
            {"计划代码": "P001"},
            {"计划代码": "P002", "可选列": "value"},
        ])

        candidates_df = service.derive_candidates(df, config)

        assert len(candidates_df) == 2
        # Optional column should be None for records where it's missing
        assert candidates_df.loc[candidates_df["年金计划号"] == "P001", "可选目标列"].iloc[0] is None

    def test_missing_source_column(self):
        """Test handling when source column is missing."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="不存在的列",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[BackfillColumnMapping(source="a", target="a")]
        )

        df = pd.DataFrame([{"存在的列": "value"}])

        candidates_df = service.derive_candidates(df, config)

        assert candidates_df.empty

    def test_null_source_values(self):
        """Test handling when source column has null values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[BackfillColumnMapping(source="计划代码", target="年金计划号")]
        )

        df = pd.DataFrame([
            {"计划代码": None},
            {"计划代码": "P001"},
            {"计划代码": pd.NA},
            {"计划代码": "P002"},
        ])

        candidates_df = service.derive_candidates(df, config)

        assert len(candidates_df) == 2
        assert set(candidates_df["年金计划号"]) == {"P001", "P002"}


class TestBackfillTable:
    """Test table backfill operations."""

    @patch('work_data_hub.domain.reference_backfill.generic_service.datetime')
    def test_add_tracking_fields(self, mock_datetime):
        """Test tracking field addition."""
        from datetime import datetime, timezone

        mock_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        service = GenericBackfillService("test_domain")

        df = pd.DataFrame([
            {"key": "value1"},
            {"key": "value2"}
        ])

        result_df = service._add_tracking_fields(df)

        assert "_source" in result_df.columns
        assert "_needs_review" in result_df.columns
        assert "_derived_from_domain" in result_df.columns
        assert "_derived_at" in result_df.columns

        assert all(result_df["_source"] == "auto_derived")
        assert all(result_df["_needs_review"] == True)
        assert all(result_df["_derived_from_domain"] == "test_domain")

    def test_postgresql_insert(self):
        """Test PostgreSQL insert with conflict handling."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_test",
            source_column="source_col",
            target_table="test_table",
            target_key="primary_key",
            backfill_columns=[
                BackfillColumnMapping(source="source_col", target="primary_key"),
                BackfillColumnMapping(source="value_col", target="value")
            ]
        )

        # Mock connection - use MagicMock to allow dialect attribute
        mock_conn = MagicMock()
        mock_conn.dialect.name = "postgresql"
        # Mock two execute calls: 1. check existing keys 2. insert
        mock_existing_result = Mock()
        mock_existing_result.fetchall.return_value = []  # No existing keys
        mock_insert_result = Mock()
        mock_insert_result.rowcount = 2
        mock_conn.execute.side_effect = [mock_existing_result, mock_insert_result]

        candidates_df = pd.DataFrame([
            {"primary_key": "key1", "value": "value1", "_source": "auto_derived"},
            {"primary_key": "key2", "value": "value2", "_source": "auto_derived"}
        ])

        inserted = service.backfill_table(candidates_df, config, mock_conn, add_tracking_fields=False)

        assert inserted == 2
        assert mock_conn.execute.call_count == 2
        # Second call should be the INSERT
        call_args = mock_conn.execute.call_args_list[1]
        assert "ON CONFLICT" in str(call_args[0][0]) and "DO NOTHING" in str(call_args[0][0])

    def test_generic_insert_with_existing_records(self):
        """Test generic insert with existing record filtering."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_test",
            source_column="source_col",
            target_table="test_table",
            target_key="primary_key",
            backfill_columns=[
                BackfillColumnMapping(source="source_col", target="primary_key"),
                BackfillColumnMapping(source="value_col", target="value")
            ]
        )

        # Mock connection for generic database - use MagicMock to allow dialect attribute
        mock_conn = MagicMock()
        mock_conn.dialect.name = "sqlite"  # Not postgresql or mysql
        mock_conn.execute.side_effect = [
            # First call: check existing keys (for new_keys tracking)
            Mock(fetchall=lambda: [("key1",)]),
            # Second call: check existing keys again (for generic filter)
            Mock(fetchall=lambda: [("key1",)]),
            # Third call: actual insert
            Mock(rowcount=1)
        ]

        candidates_df = pd.DataFrame([
            {"primary_key": "key1", "value": "value1", "_source": "auto_derived"},
            {"primary_key": "key2", "value": "value2", "_source": "auto_derived"}
        ])

        inserted = service.backfill_table(candidates_df, config, mock_conn, add_tracking_fields=False)

        assert inserted == 1  # Only key2 should be inserted
        assert mock_conn.execute.call_count == 3


class TestGenericBackfillServiceIntegration:
    """Integration tests for the complete backfill service."""

    def test_full_backfill_process(self):
        """Test complete backfill process with multiple tables."""
        service = GenericBackfillService("test_domain")

        # Mock connection - use MagicMock to allow dialect attribute
        mock_conn = MagicMock()
        mock_conn.dialect.name = "postgresql"
        # Mock execute to return empty existing keys then insert result
        mock_existing = Mock()
        mock_existing.fetchall.return_value = []
        mock_insert = Mock()
        mock_insert.rowcount = 1
        mock_conn.execute.side_effect = [mock_existing, mock_insert, mock_existing, mock_insert]

        # Create configurations with dependencies
        fk_plan = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(source="计划名称", target="计划名称", optional=True)
            ]
        )

        fk_portfolio = ForeignKeyConfig(
            name="fk_portfolio",
            source_column="组合代码",
            target_table="组合计划",
            target_key="组合代码",
            depends_on=["fk_plan"],
            backfill_columns=[
                BackfillColumnMapping(source="组合代码", target="组合代码"),
                BackfillColumnMapping(source="计划代码", target="年金计划号")
            ]
        )

        # Create test data
        df = pd.DataFrame([
            {"计划代码": "P001", "计划名称": "Plan A", "组合代码": "PF001"},
            {"计划代码": "P002", "计划名称": "Plan B", "组合代码": "PF002"},
        ])

        result = service.run(df, [fk_portfolio, fk_plan], mock_conn)

        # Check processing order (plan should come before portfolio)
        assert result.processing_order == ["fk_plan", "fk_portfolio"]
        assert result.total_inserted == 2  # 1 plan + 1 portfolio
        assert len(result.tables_processed) == 2

    def test_plan_only_skips_db_operations(self):
        """Plan-only mode should not require a DB connection."""
        service = GenericBackfillService("test_domain")

        fk_plan = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001"},
                {"计划代码": "P002"},
                {"计划代码": "P002"},
            ]
        )

        result = service.run(df, [fk_plan], conn=None, plan_only=True)

        assert result.processing_order == ["fk_plan"]
        assert result.total_inserted == 0
        assert result.tables_processed[0]["inserted"] == 0
        assert result.tables_processed[0]["skipped"] == 2  # two unique candidates

    def test_fill_null_only_postgresql_query(self):
        """fill_null_only should issue ON CONFLICT DO UPDATE with null guards."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_test",
            source_column="source_col",
            target_table="test_table",
            target_key="primary_key",
            mode="fill_null_only",
            backfill_columns=[
                BackfillColumnMapping(source="source_col", target="primary_key"),
                BackfillColumnMapping(source="value_col", target="value"),
            ],
        )

        mock_conn = MagicMock()
        mock_conn.dialect.name = "postgresql"
        # Mock two execute calls: 1. check existing keys 2. insert
        mock_existing_result = Mock()
        mock_existing_result.fetchall.return_value = []
        mock_insert_result = Mock()
        mock_insert_result.rowcount = 2
        mock_conn.execute.side_effect = [mock_existing_result, mock_insert_result]

        candidates_df = pd.DataFrame(
            [
                {"primary_key": "key1", "value": "value1", "_source": "auto_derived"},
                {"primary_key": "key2", "value": "value2", "_source": "auto_derived"},
            ]
        )

        inserted = service.backfill_table(
            candidates_df, config, mock_conn, add_tracking_fields=False
        )

        assert inserted == 2
        sql_text = mock_conn.execute.call_args[0][0].text
        assert "DO UPDATE" in sql_text
        assert "CASE WHEN" in sql_text
        mock_conn.commit.assert_called_once()

    def test_derive_candidates_filters_blank_strings(self):
        """Blank strings should be treated as missing values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[BackfillColumnMapping(source="计划代码", target="年金计划号")],
        )

        df = pd.DataFrame(
            [
                {"计划代码": ""},
                {"计划代码": "   "},
                {"计划代码": None},
                {"计划代码": "P001"},
            ]
        )

        candidates_df = service.derive_candidates(df, config)
        assert len(candidates_df) == 1
        assert candidates_df.iloc[0]["年金计划号"] == "P001"
