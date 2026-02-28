"""Phase I: Snapshot refresh SQL contracts.

Validate that snapshot refresh builds executable SQL with required business
semantics (status evaluation, AUM aggregation, and idempotent upsert).
"""

from __future__ import annotations

import pytest

from work_data_hub.customer_mdm.snapshot_refresh import (
    _refresh_plan_snapshot,
    _refresh_product_line_snapshot,
)

pytestmark = pytest.mark.slice_test


class _CaptureCursor:
    def __init__(self, rowcount: int = 3) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.rowcount = rowcount

    def execute(self, sql: str, params: dict[str, object]) -> None:
        self.calls.append((sql, params))


def test_i1_product_line_snapshot_sql_contract() -> None:
    cursor = _CaptureCursor(rowcount=7)
    affected = _refresh_product_line_snapshot(
        cursor,
        snapshot_month="2025-10-31",
        snapshot_year=2025,
    )

    assert affected == 7
    assert len(cursor.calls) == 1

    sql, params = cursor.calls[0]
    assert 'INSERT INTO customer."客户业务月度快照"' in sql
    assert "ON CONFLICT (snapshot_month, company_id, product_line_code)" in sql
    assert 'FROM customer."客户年金计划" c' in sql
    assert "FROM business.规模明细 s" in sql
    assert "SUM(s.期末资产规模)" in sql
    assert "DATE_TRUNC('month', %(snapshot_month)s::date)" in sql
    assert "EXISTS (" in sql  # config-driven status SQL fragments are embedded

    assert params["snapshot_month"] == "2025-10-31"
    assert params["snapshot_year"] == 2025


def test_i2_plan_snapshot_sql_contract() -> None:
    cursor = _CaptureCursor(rowcount=11)
    affected = _refresh_plan_snapshot(
        cursor,
        snapshot_month="2025-10-31",
        snapshot_year=2025,
    )

    assert affected == 11
    assert len(cursor.calls) == 1

    sql, params = cursor.calls[0]
    assert 'INSERT INTO customer."客户计划月度快照"' in sql
    assert (
        "ON CONFLICT (snapshot_month, company_id, plan_code, product_line_code)" in sql
    )
    assert 'FROM customer."客户年金计划" c' in sql
    assert "FROM business.规模明细 s" in sql
    assert "s.计划代码 = c.plan_code" in sql
    assert "SUM(s.期末资产规模)" in sql
    assert "EXISTS (" in sql

    assert params["snapshot_month"] == "2025-10-31"
    assert params["snapshot_year"] == 2025
