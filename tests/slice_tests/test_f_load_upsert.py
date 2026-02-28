"""Phase F: Final load/upsert tests (F-1 through F-5).

Verifies delete_insert mode, PK-based idempotent refresh,
and plan_only mode using conn=None.
"""

from __future__ import annotations

import pytest

from work_data_hub.io.loader.operations import load

pytestmark = pytest.mark.slice_test


def _make_rows(pk_cols, extra_cols=None):
    """Build minimal row dicts for testing."""
    rows = []
    for i in range(3):
        row = {col: f"val_{col}_{i}" for col in pk_cols}
        if extra_cols:
            for col in extra_cols:
                row[col] = f"extra_{col}_{i}"
        rows.append(row)
    return rows


# ===================================================================
# F-1: delete_insert mode (plan_only with conn=None)
# ===================================================================
class TestF1DeleteInsertMode:
    """delete_insert generates DELETE+INSERT SQL plans."""

    def test_plan_only_returns_sql_plans(self):
        rows = _make_rows(["pk1", "pk2"], ["data_col"])
        result = load(
            table="test_table",
            rows=rows,
            mode="delete_insert",
            pk=["pk1", "pk2"],
            conn=None,
        )
        assert "sql_plans" in result
        assert len(result["sql_plans"]) > 0

    def test_delete_insert_has_both_ops(self):
        rows = _make_rows(["pk1"], ["val"])
        result = load(
            table="test_table",
            rows=rows,
            mode="delete_insert",
            pk=["pk1"],
            conn=None,
        )
        op_types = [plan[0] for plan in result["sql_plans"]]
        assert "DELETE" in op_types
        assert "INSERT" in op_types

    def test_delete_insert_requires_pk(self):
        rows = _make_rows(["col1"])
        with pytest.raises(Exception):
            load(table="t", rows=rows, mode="delete_insert", pk=None, conn=None)

    def test_empty_rows_returns_early(self):
        result = load(
            table="test_table",
            rows=[],
            mode="delete_insert",
            pk=["pk1"],
            conn=None,
        )
        assert result["inserted"] == 0
        assert result["deleted"] == 0


# ===================================================================
# F-2: annuity_performance PK (月度, 业务类型, 计划类型)
# ===================================================================
class TestF2AnnuityPerformancePK:
    """PK=[月度, 业务类型, 计划类型] idempotent refresh."""

    def test_pk_columns_in_plan(self):
        pk = ["月度", "业务类型", "计划类型"]
        rows = [
            {
                "月度": "202510",
                "业务类型": "企年受托",
                "计划类型": "集合计划",
                "val": 100,
            },
            {
                "月度": "202510",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "val": 200,
            },
        ]
        result = load(
            table='"规模明细"',
            rows=rows,
            mode="delete_insert",
            pk=pk,
            conn=None,
        )
        assert "sql_plans" in result
        assert result["deleted"] == 2


# ===================================================================
# F-3: annual_award PK (上报月份, 业务类型)
# ===================================================================
class TestF3AnnualAwardPK:
    """PK=[上报月份, 业务类型] idempotent refresh."""

    def test_pk_columns_in_plan(self):
        pk = ["上报月份", "业务类型"]
        rows = [
            {"上报月份": "202510", "业务类型": "企年受托", "客户名称": "测试A"},
            {"上报月份": "202510", "业务类型": "企年投资", "客户名称": "测试B"},
        ]
        result = load(
            table='"中标客户明细"',
            rows=rows,
            mode="delete_insert",
            pk=pk,
            conn=None,
        )
        assert "sql_plans" in result
        assert result["deleted"] == 2


# ===================================================================
# F-4: annual_loss PK (上报月份, 业务类型)
# ===================================================================
class TestF4AnnualLossPK:
    """PK=[上报月份, 业务类型] idempotent refresh."""

    def test_pk_columns_in_plan(self):
        pk = ["上报月份", "业务类型"]
        rows = [
            {"上报月份": "202510", "业务类型": "企年受托", "客户名称": "流失A"},
            {"上报月份": "202510", "业务类型": "企年投资", "客户名称": "流失B"},
        ]
        result = load(
            table='"流失客户明细"',
            rows=rows,
            mode="delete_insert",
            pk=pk,
            conn=None,
        )
        assert "sql_plans" in result
        assert result["deleted"] == 2


# ===================================================================
# F-5: plan_only mode (conn=None generates SQL without executing)
# ===================================================================
class TestF5PlanOnlyMode:
    """conn=None produces sql_plans without DB interaction."""

    def test_plan_only_no_execution(self):
        rows = [{"pk": "a", "val": 1}]
        result = load(
            table="test",
            rows=rows,
            mode="delete_insert",
            pk=["pk"],
            conn=None,
        )
        assert "sql_plans" in result
        assert isinstance(result["sql_plans"], list)

    def test_plan_only_sql_contains_table_name(self):
        rows = [{"pk": "x", "data": "y"}]
        result = load(
            table="my_table",
            rows=rows,
            mode="delete_insert",
            pk=["pk"],
            conn=None,
        )
        all_sql = " ".join(plan[1] for plan in result["sql_plans"])
        assert "my_table" in all_sql
