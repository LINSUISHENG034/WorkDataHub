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

from work_data_hub.domain.reference_backfill.generic_service import (
    GenericBackfillService,
    BackfillResult,
)
from work_data_hub.domain.reference_backfill.models import (
    ForeignKeyConfig,
    BackfillColumnMapping,
)


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
                backfill_columns=[BackfillColumnMapping(source="a", target="a")],
            ),
            ForeignKeyConfig(
                name="fk_b",
                source_column="col_b",
                target_table="table_b",
                target_key="key_b",
                backfill_columns=[BackfillColumnMapping(source="b", target="b")],
            ),
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
                backfill_columns=[BackfillColumnMapping(source="p", target="p")],
            ),
            ForeignKeyConfig(
                name="fk_plan",
                source_column="plan_code",
                target_table="plan",
                target_key="plan_key",
                backfill_columns=[BackfillColumnMapping(source="pl", target="pl")],
            ),
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
                backfill_columns=[BackfillColumnMapping(source="c", target="c")],
            ),
            ForeignKeyConfig(
                name="fk_b",
                source_column="col_b",
                target_table="table_b",
                target_key="key_b",
                depends_on=["fk_a"],
                backfill_columns=[BackfillColumnMapping(source="b", target="b")],
            ),
            ForeignKeyConfig(
                name="fk_a",
                source_column="col_a",
                target_table="table_a",
                target_key="key_a",
                backfill_columns=[BackfillColumnMapping(source="a", target="a")],
            ),
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
                backfill_columns=[BackfillColumnMapping(source="a", target="a")],
            ),
            ForeignKeyConfig(
                name="fk_b",
                source_column="col_b",
                target_table="table_b",
                target_key="key_b",
                depends_on=["fk_a"],
                backfill_columns=[BackfillColumnMapping(source="b", target="b")],
            ),
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
                backfill_columns=[BackfillColumnMapping(source="a", target="a")],
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
                BackfillColumnMapping(source="计划名称", target="计划名称"),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "计划名称": "Plan A", "其他列": "value1"},
                {"计划代码": "P002", "计划名称": "Plan B", "其他列": "value2"},
                {
                    "计划代码": "P001",
                    "计划名称": "Plan A",
                    "其他列": "value3",
                },  # Duplicate
            ]
        )

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
                BackfillColumnMapping(
                    source="可选列", target="可选目标列", optional=True
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001"},
                {"计划代码": "P002", "可选列": "value"},
            ]
        )

        candidates_df = service.derive_candidates(df, config)

        assert len(candidates_df) == 2
        # Optional column should be None for records where it's missing
        assert (
            candidates_df.loc[candidates_df["年金计划号"] == "P001", "可选目标列"].iloc[
                0
            ]
            is None
        )

    def test_missing_source_column(self):
        """Test handling when source column is missing."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="不存在的列",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[BackfillColumnMapping(source="a", target="a")],
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
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号")
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": None},
                {"计划代码": "P001"},
                {"计划代码": pd.NA},
                {"计划代码": "P002"},
            ]
        )

        candidates_df = service.derive_candidates(df, config)

        assert len(candidates_df) == 2
        assert set(candidates_df["年金计划号"]) == {"P001", "P002"}


class TestBackfillTable:
    """Test table backfill operations."""

    @patch("work_data_hub.domain.reference_backfill.generic_service.datetime")
    def test_add_tracking_fields(self, mock_datetime):
        """Test tracking field addition."""
        from datetime import datetime, timezone

        mock_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        service = GenericBackfillService("test_domain")

        df = pd.DataFrame([{"key": "value1"}, {"key": "value2"}])

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
                BackfillColumnMapping(source="value_col", target="value"),
            ],
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
        assert mock_conn.execute.call_count == 2
        # Second call should be the INSERT
        call_args = mock_conn.execute.call_args_list[1]
        assert "ON CONFLICT" in str(call_args[0][0]) and "DO NOTHING" in str(
            call_args[0][0]
        )

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
                BackfillColumnMapping(source="value_col", target="value"),
            ],
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
            Mock(rowcount=1),
        ]

        candidates_df = pd.DataFrame(
            [
                {"primary_key": "key1", "value": "value1", "_source": "auto_derived"},
                {"primary_key": "key2", "value": "value2", "_source": "auto_derived"},
            ]
        )

        inserted = service.backfill_table(
            candidates_df, config, mock_conn, add_tracking_fields=False
        )

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
        mock_conn.execute.side_effect = [
            mock_existing,
            mock_insert,
            mock_existing,
            mock_insert,
        ]

        # Create configurations with dependencies
        fk_plan = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="计划名称", target="计划名称", optional=True
                ),
            ],
        )

        fk_portfolio = ForeignKeyConfig(
            name="fk_portfolio",
            source_column="组合代码",
            target_table="组合计划",
            target_key="组合代码",
            depends_on=["fk_plan"],
            backfill_columns=[
                BackfillColumnMapping(source="组合代码", target="组合代码"),
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
            ],
        )

        # Create test data
        df = pd.DataFrame(
            [
                {"计划代码": "P001", "计划名称": "Plan A", "组合代码": "PF001"},
                {"计划代码": "P002", "计划名称": "Plan B", "组合代码": "PF002"},
            ]
        )

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
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号")
            ],
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


# Story 6.2-P15: Complex Mapping Backfill Enhancement Tests
from work_data_hub.domain.reference_backfill.models import (
    AggregationType,
    AggregationConfig,
)


class TestAggregationConfigValidation:
    """Test aggregation configuration validation."""

    def test_max_by_requires_order_column(self):
        """max_by type must have order_column defined."""
        with pytest.raises(ValueError) as exc_info:
            AggregationConfig(type="max_by")
        assert "order_column is required when type is 'max_by'" in str(exc_info.value)

    def test_max_by_with_order_column(self):
        """max_by with order_column should succeed."""
        config = AggregationConfig(type="max_by", order_column="期末资产规模")
        assert config.type == AggregationType.MAX_BY
        assert config.order_column == "期末资产规模"

    def test_concat_distinct_defaults(self):
        """concat_distinct should have sensible defaults."""
        config = AggregationConfig(type="concat_distinct")
        assert config.type == AggregationType.CONCAT_DISTINCT
        assert config.separator == "+"
        assert config.sort is True

    def test_concat_distinct_custom_separator(self):
        """concat_distinct can have custom separator."""
        config = AggregationConfig(type="concat_distinct", separator=",", sort=False)
        assert config.separator == ","
        assert config.sort is False


class TestMaxByAggregation:
    """Test max_by aggregation strategy."""

    def test_max_by_selects_record_with_max_value(self):
        """max_by should select value from row with maximum order_column."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="max_by", order_column="期末资产规模"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "机构代码": "ORG-A", "期末资产规模": 1000.0},
                {
                    "计划代码": "P001",
                    "机构代码": "ORG-B",
                    "期末资产规模": 5000.0,
                },  # MAX
                {"计划代码": "P001", "机构代码": "ORG-C", "期末资产规模": 2000.0},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["主拓代码"] == "ORG-B"

    def test_max_by_fallback_when_all_order_column_null(self):
        """max_by should fallback to first when all order_column values are NULL."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="max_by", order_column="期末资产规模"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "机构代码": "ORG-A", "期末资产规模": None},
                {"计划代码": "P001", "机构代码": "ORG-B", "期末资产规模": None},
            ]
        )

        candidates = service.derive_candidates(df, config)
        # Should fallback to first value (ORG-A)
        assert candidates.iloc[0]["主拓代码"] == "ORG-A"

    def test_max_by_fallback_when_order_column_missing(self):
        """max_by should fallback to first when order_column doesn't exist."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="max_by", order_column="不存在的列"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "机构代码": "ORG-X"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["主拓代码"] == "ORG-X"

    def test_max_by_handles_mixed_null_values(self):
        """max_by should correctly handle mixed NULL/non-NULL order_column values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="max_by", order_column="期末资产规模"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "机构代码": "ORG-A", "期末资产规模": None},
                {
                    "计划代码": "P001",
                    "机构代码": "ORG-B",
                    "期末资产规模": 5000.0,
                },  # Only non-NULL
                {"计划代码": "P001", "机构代码": "ORG-C", "期末资产规模": None},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["主拓代码"] == "ORG-B"

    def test_max_by_handles_mixed_type_order_column(self):
        """max_by should handle mixed numeric/string order_column values without crashing."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="max_by", order_column="期末资产规模"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "机构代码": "ORG-A", "期末资产规模": "N/A"},
                {"计划代码": "P001", "机构代码": "ORG-B", "期末资产规模": 2000.0},
                {"计划代码": "P001", "机构代码": "ORG-C", "期末资产规模": "5000"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["主拓代码"] == "ORG-C"


class TestConcatDistinctAggregation:
    """Test concat_distinct aggregation strategy."""

    def test_concat_distinct_joins_unique_values(self):
        """concat_distinct should concatenate distinct values with separator."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="业务类型",
                    target="管理资格",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="concat_distinct", separator="+", sort=True
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "业务类型": "受托"},
                {"计划代码": "P001", "业务类型": "账管"},
                {"计划代码": "P001", "业务类型": "投管"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        # Sorted: 受托 < 投管 < 账管 (by Chinese character order)
        assert candidates.iloc[0]["管理资格"] == "受托+投管+账管"

    def test_concat_distinct_removes_duplicates(self):
        """concat_distinct should only include unique values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="业务类型",
                    target="管理资格",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="concat_distinct", separator="+"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "业务类型": "受托"},
                {"计划代码": "P001", "业务类型": "受托"},  # Duplicate
                {"计划代码": "P001", "业务类型": "账管"},
                {"计划代码": "P001", "业务类型": "受托"},  # Duplicate
            ]
        )

        candidates = service.derive_candidates(df, config)
        result = candidates.iloc[0]["管理资格"]
        assert "受托" in result
        assert "账管" in result
        assert result.count("受托") == 1  # Only one occurrence

    def test_concat_distinct_empty_when_all_null(self):
        """concat_distinct should return empty string when all values are NULL."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="业务类型",
                    target="管理资格",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="concat_distinct", separator="+"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "业务类型": None},
                {"计划代码": "P001", "业务类型": None},
            ]
        )

        candidates = service.derive_candidates(df, config)
        # optional=True means None is used for empty result after post-processing
        assert (
            candidates.iloc[0]["管理资格"] is None
            or candidates.iloc[0]["管理资格"] == ""
        )

    def test_concat_distinct_custom_separator(self):
        """concat_distinct should use custom separator."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="业务类型",
                    target="管理资格",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="concat_distinct", separator=",", sort=False
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "业务类型": "A"},
                {"计划代码": "P001", "业务类型": "B"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        result = candidates.iloc[0]["管理资格"]
        assert "," in result
        assert "A" in result
        assert "B" in result


class TestAggregationEdgeCases:
    """Test edge cases for aggregation strategies."""

    def test_empty_dataframe(self):
        """Aggregation should handle empty DataFrame gracefully."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    aggregation=AggregationConfig(
                        type="max_by", order_column="期末资产规模"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(columns=["计划代码", "机构代码", "期末资产规模"])
        candidates = service.derive_candidates(df, config)
        assert candidates.empty

    def test_multiple_groups_with_different_aggregations(self):
        """Should correctly apply aggregations across multiple groups."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="max_by", order_column="期末资产规模"
                    ),
                ),
                BackfillColumnMapping(
                    source="业务类型",
                    target="管理资格",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="concat_distinct", separator="+", sort=True
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                # Plan P001
                {
                    "计划代码": "P001",
                    "机构代码": "ORG-A",
                    "业务类型": "受托",
                    "期末资产规模": 1000.0,
                },
                {
                    "计划代码": "P001",
                    "机构代码": "ORG-B",
                    "业务类型": "账管",
                    "期末资产规模": 5000.0,
                },
                {
                    "计划代码": "P001",
                    "机构代码": "ORG-C",
                    "业务类型": "投管",
                    "期末资产规模": 2000.0,
                },
                # Plan P002
                {
                    "计划代码": "P002",
                    "机构代码": "ORG-X",
                    "业务类型": "托管",
                    "期末资产规模": 3000.0,
                },
            ]
        )

        candidates = service.derive_candidates(df, config)

        p001 = candidates[candidates["年金计划号"] == "P001"].iloc[0]
        p002 = candidates[candidates["年金计划号"] == "P002"].iloc[0]

        # P001: ORG-B has max asset scale (5000)
        assert p001["主拓代码"] == "ORG-B"
        # P001: 3 distinct business types
        assert p001["管理资格"] == "受托+投管+账管"

        # P002: Only one record
        assert p002["主拓代码"] == "ORG-X"
        assert p002["管理资格"] == "托管"

    def test_backward_compatibility_no_aggregation(self):
        """Columns without aggregation should still use default 'first' behavior."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="计划名称", target="计划名称"
                ),  # No aggregation
            ],
        )

        df = pd.DataFrame(
            [
                {"计划代码": "P001", "计划名称": "Plan A"},
                {"计划代码": "P001", "计划名称": "Plan B"},  # Duplicate plan code
            ]
        )

        candidates = service.derive_candidates(df, config)
        # Should use first value
        assert candidates.iloc[0]["计划名称"] == "Plan A"

    def test_multiple_groups_mixed_null_order_column(self):
        """Test max_by with multiple groups where some have all-NULL order_column."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(
                    source="机构代码",
                    target="主拓代码",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="max_by", order_column="期末资产规模"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                # P001: has valid order_column values
                {"计划代码": "P001", "机构代码": "ORG-A", "期末资产规模": 1000.0},
                {
                    "计划代码": "P001",
                    "机构代码": "ORG-B",
                    "期末资产规模": 5000.0,
                },  # MAX
                # P002: all order_column values are NULL - should fallback to first
                {"计划代码": "P002", "机构代码": "ORG-X", "期末资产规模": None},
                {"计划代码": "P002", "机构代码": "ORG-Y", "期末资产规模": None},
            ]
        )

        candidates = service.derive_candidates(df, config)

        p001 = candidates[candidates["年金计划号"] == "P001"].iloc[0]
        p002 = candidates[candidates["年金计划号"] == "P002"].iloc[0]

        # P001: ORG-B has max asset scale
        assert p001["主拓代码"] == "ORG-B"
        # P002: fallback to first (ORG-X) since all order_column are NULL
        assert p002["主拓代码"] == "ORG-X"


# Story 6.2-P18: Advanced Aggregation Capabilities Tests


class TestAdvancedAggregationConfigValidation:
    """Test validation for new aggregation types (Story 6.2-P18)."""

    def test_template_requires_template_field(self):
        """template type must have template string defined."""
        with pytest.raises(ValueError) as exc_info:
            AggregationConfig(type="template")
        assert "template is required when type is 'template'" in str(exc_info.value)

    def test_template_with_template_string(self):
        """template with template string should succeed."""
        config = AggregationConfig(type="template", template="新建客户_{月度}")
        assert config.type == AggregationType.TEMPLATE
        assert config.template == "新建客户_{月度}"

    def test_template_with_explicit_fields(self):
        """template can have explicit template_fields list."""
        config = AggregationConfig(
            type="template",
            template="客户_{客户名称}_{月度}",
            template_fields=["客户名称", "月度"],
        )
        assert config.template_fields == ["客户名称", "月度"]

    def test_lambda_requires_code_field(self):
        """lambda type must have code string defined."""
        with pytest.raises(ValueError) as exc_info:
            AggregationConfig(type="lambda")
        assert "code is required when type is 'lambda'" in str(exc_info.value)

    def test_lambda_with_code_string(self):
        """lambda with code string should succeed."""
        config = AggregationConfig(
            type="lambda", code='lambda g: g["月度"].iloc[0][:4]'
        )
        assert config.type == AggregationType.LAMBDA
        assert config.code == 'lambda g: g["月度"].iloc[0][:4]'

    def test_count_distinct_no_extra_fields_required(self):
        """count_distinct should not require extra fields."""
        config = AggregationConfig(type="count_distinct")
        assert config.type == AggregationType.COUNT_DISTINCT


class TestTemplateAggregation:
    """Test template aggregation strategy (Story 6.2-P18)."""

    def test_template_basic_substitution(self):
        """template should substitute field placeholders with first non-null values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="月度",
                    target="年金客户标签",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="template", template="新建客户_{月度}"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "月度": "202501"},
                {"company_id": "C001", "月度": "202502"},
                {"company_id": "C002", "月度": "202503"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        c001 = candidates[candidates["company_id"] == "C001"].iloc[0]
        c002 = candidates[candidates["company_id"] == "C002"].iloc[0]

        assert c001["年金客户标签"] == "新建客户_202501"
        assert c002["年金客户标签"] == "新建客户_202503"

    def test_template_multiple_placeholders(self):
        """template should handle multiple field placeholders."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="月度",
                    target="复合标签",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="template",
                        template="客户_{客户名称}_{月度}",
                        template_fields=["客户名称", "月度"],
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "客户名称": "测试公司", "月度": "202501"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["复合标签"] == "客户_测试公司_202501"

    def test_template_missing_field_raises_error(self):
        """template should raise ValueError when field is missing from DataFrame."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="月度",
                    target="标签",
                    aggregation=AggregationConfig(
                        type="template", template="标签_{不存在的字段}"
                    ),
                ),
            ],
        )

        df = pd.DataFrame([{"company_id": "C001", "月度": "202501"}])

        with pytest.raises(ValueError) as exc_info:
            service.derive_candidates(df, config)
        assert "missing fields" in str(exc_info.value).lower()

    def test_template_null_field_uses_empty_string(self):
        """template should use empty string for NULL field values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="月度",
                    target="标签",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="template", template="前缀_{月度}_后缀"
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "月度": None},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["标签"] == "前缀__后缀"


class TestCountDistinctAggregation:
    """Test count_distinct aggregation strategy (Story 6.2-P18)."""

    def test_count_distinct_basic(self):
        """count_distinct should count unique non-null values per group."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="计划代码",
                    target="关联计划数",
                    optional=True,
                    aggregation=AggregationConfig(type="count_distinct"),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "计划代码": "P001"},
                {"company_id": "C001", "计划代码": "P002"},
                {"company_id": "C001", "计划代码": "P003"},
                {"company_id": "C002", "计划代码": "P001"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        c001 = candidates[candidates["company_id"] == "C001"].iloc[0]
        c002 = candidates[candidates["company_id"] == "C002"].iloc[0]

        assert c001["关联计划数"] == 3
        assert c002["关联计划数"] == 1

    def test_count_distinct_ignores_duplicates(self):
        """count_distinct should not count duplicate values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="计划代码",
                    target="关联计划数",
                    optional=True,
                    aggregation=AggregationConfig(type="count_distinct"),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "计划代码": "P001"},
                {"company_id": "C001", "计划代码": "P001"},  # Duplicate
                {"company_id": "C001", "计划代码": "P002"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["关联计划数"] == 2

    def test_count_distinct_ignores_nulls(self):
        """count_distinct should not count NULL values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="计划代码",
                    target="关联计划数",
                    optional=True,
                    aggregation=AggregationConfig(type="count_distinct"),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "计划代码": "P001"},
                {"company_id": "C001", "计划代码": None},
                {"company_id": "C001", "计划代码": "P002"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["关联计划数"] == 2

    def test_count_distinct_missing_column_returns_empty(self):
        """count_distinct should return 0 when source column is missing."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="不存在的列",
                    target="关联计划数",
                    optional=True,
                    aggregation=AggregationConfig(type="count_distinct"),
                ),
            ],
        )

        df = pd.DataFrame([{"company_id": "C001"}])

        candidates = service.derive_candidates(df, config)
        # Missing column should result in None for optional field
        assert candidates.iloc[0]["关联计划数"] is None or pd.isna(
            candidates.iloc[0]["关联计划数"]
        )


class TestLambdaAggregation:
    """Test lambda aggregation strategy (Story 6.2-P18)."""

    def test_lambda_basic_expression(self):
        """lambda should execute custom expression on each group."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="月度",
                    target="年份",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="lambda",
                        code='lambda g: g["月度"].iloc[0][:4]',
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "月度": "202501"},
                {"company_id": "C001", "月度": "202502"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["年份"] == "2025"

    def test_lambda_syntax_error_raises_value_error(self):
        """Lambda with syntax error should raise during eval."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="月度",
                    target="标签",
                    aggregation=AggregationConfig(
                        type="lambda",
                        code="lambda g: g['月度'].iloc[0",  # Missing bracket
                    ),
                ),
            ],
        )

        df = pd.DataFrame([{"company_id": "C001", "月度": "202501"}])

        with pytest.raises(SyntaxError):
            service.derive_candidates(df, config)

    def test_lambda_execution_error_raises_exception(self):
        """Lambda runtime error should propagate as exception."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="月度",
                    target="标签",
                    aggregation=AggregationConfig(
                        type="lambda",
                        code='lambda g: g["不存在的列"].iloc[0]',  # KeyError
                    ),
                ),
            ],
        )

        df = pd.DataFrame([{"company_id": "C001", "月度": "202501"}])

        with pytest.raises(KeyError):
            service.derive_candidates(df, config)

    def test_count_distinct_ignores_blank_strings(self):
        """count_distinct should not count empty/blank string values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="计划代码",
                    target="关联计划数",
                    optional=True,
                    aggregation=AggregationConfig(type="count_distinct"),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "计划代码": "P001"},
                {"company_id": "C001", "计划代码": ""},  # Blank
                {"company_id": "C001", "计划代码": "   "},  # Whitespace only
                {"company_id": "C001", "计划代码": "P002"},
            ]
        )

        candidates = service.derive_candidates(df, config)
        # Should only count P001, P002 (blanks excluded)
        assert candidates.iloc[0]["关联计划数"] == 2


class TestJsonbAppendAggregation:
    """Test JSONB_APPEND aggregation type."""

    def test_aggregate_jsonb_append_generates_list(self):
        """JSONB_APPEND aggregation should generate Python list values."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="month",
                    target="tags",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="jsonb_append",
                        code='lambda g: [g["month"].iloc[0][:4] + "中标"]',
                    ),
                ),
            ],
        )

        df = pd.DataFrame(
            [
                {"company_id": "C001", "month": "202511"},
                {"company_id": "C001", "month": "202510"},
                {"company_id": "C002", "month": "202511"},
            ]
        )

        candidates = service.derive_candidates(df, config)

        assert candidates.iloc[0]["tags"] == '["2025中标"]'
        assert candidates.iloc[1]["tags"] == '["2025中标"]'
        assert isinstance(candidates.iloc[0]["tags"], str)

    def test_aggregate_jsonb_append_returns_empty_list_on_none(self):
        """JSONB_APPEND should return empty list when lambda returns None."""
        service = GenericBackfillService("test_domain")

        config = ForeignKeyConfig(
            name="fk_customer",
            source_column="company_id",
            target_table="年金关联公司",
            target_key="company_id",
            backfill_columns=[
                BackfillColumnMapping(source="company_id", target="company_id"),
                BackfillColumnMapping(
                    source="month",
                    target="tags",
                    optional=True,
                    aggregation=AggregationConfig(
                        type="jsonb_append",
                        code="lambda g: None",
                    ),
                ),
            ],
        )

        df = pd.DataFrame([{"company_id": "C001", "month": "202511"}])

        candidates = service.derive_candidates(df, config)
        assert candidates.iloc[0]["tags"] == "[]"
