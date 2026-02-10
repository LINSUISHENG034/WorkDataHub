"""Unit tests for Customer MDM snapshot refresh helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from work_data_hub.customer_mdm import snapshot_refresh as module


class DummyCursor:
    """Minimal cursor stub for SQL capture tests."""

    def __init__(self, fetchone_values: list[tuple[int]] | None = None) -> None:
        self.queries: list[str] = []
        self._fetchone_values = list(fetchone_values or [])
        self.rowcount = 0

    def execute(self, sql: str, params: dict | None = None) -> None:
        self.queries.append(str(sql))

    def fetchone(self) -> tuple[int]:
        return self._fetchone_values.pop(0)

    def __enter__(self) -> "DummyCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class DummyConn:
    """Minimal connection stub for context manager usage."""

    def __init__(self, cursor: DummyCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> DummyCursor:
        return self._cursor

    def commit(self) -> None:
        return None

    def __enter__(self) -> "DummyConn":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_period_to_snapshot_month_valid() -> None:
    assert module.period_to_snapshot_month("202402") == "2024-02-29"


def test_period_to_snapshot_month_invalid() -> None:
    with pytest.raises(ValueError):
        module.period_to_snapshot_month("2026")
    with pytest.raises(ValueError):
        module.period_to_snapshot_month("202613")


def test_refresh_plan_snapshot_uses_aggregated_aum_by_product_line() -> None:
    cursor = DummyCursor()

    module._refresh_plan_snapshot(cursor, "2026-01-31", 2026)

    sql = cursor.queries[0]
    assert "SUM(s.期末资产规模)" in sql
    assert "s.计划代码 = c.plan_code" in sql
    assert "s.产品线代码 = c.product_line_code" in sql


def test_refresh_monthly_snapshot_dry_run_uses_tuple_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = DummyCursor(fetchone_values=[(3,), (5,)])
    conn = DummyConn(cursor)

    monkeypatch.setenv("DATABASE_URL", "postgresql://test")

    with (
        patch.object(module, "load_dotenv"),
        patch.object(module.psycopg, "connect", return_value=conn),
    ):
        result = module.refresh_monthly_snapshot(period="202601", dry_run=True)

    assert "COUNT(DISTINCT (company_id, product_line_code))" in cursor.queries[0]
    assert result == {
        "product_line_upserted": 0,
        "plan_upserted": 0,
    }
