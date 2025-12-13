import builtins
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

import work_data_hub.io.loader.company_mapping_loader as loader


@pytest.fixture(autouse=True)
def _reset_fetch(monkeypatch):
    # Ensure no accidental use of real Postgres/MySQL
    monkeypatch.setenv("WDH_LEGACY_HOST", "test-host")
    monkeypatch.setenv("WDH_LEGACY_USER", "test-user")
    monkeypatch.setenv("WDH_LEGACY_PASSWORD", "test-pass")
    monkeypatch.setenv("WDH_LEGACY_DATABASE", "legacy")
    yield


def _mock_fetch(records: List[Dict[str, Any]]):
    """Helper to mock _fetch_from_postgres to return given records."""

    def _fake(table: str, schema: str, columns: List[str], description: str, connection_env_prefix: str = "WDH_LEGACY"):
        return records

    return _fake


def test_extract_company_id2_mapping_prefers_postgres(monkeypatch):
    records = [{"年金账户号": "ACC1", "company_id": "C1"}, {"年金账户号": "ACC2", "company_id": "C2"}]
    monkeypatch.setattr(loader, "_fetch_from_postgres", _mock_fetch(records))
    # Guard MySqlDBManager use
    monkeypatch.setattr(loader, "MySqlDBManager", None)

    result = loader._extract_company_id2_mapping()

    assert result == {"ACC1": "C1", "ACC2": "C2"}


def test_extract_company_id4_mapping_prefers_postgres(monkeypatch):
    records = [{"company_name": "Foo", "company_id": "ID1"}]
    monkeypatch.setattr(loader, "_fetch_from_postgres", _mock_fetch(records))
    monkeypatch.setattr(loader, "MySqlDBManager", None)

    result = loader._extract_company_id4_mapping()

    assert result == {"Foo": "ID1"}


def test_extract_company_id5_mapping_prefers_postgres(monkeypatch):
    records = [{"年金账户名": "AcctA", "company_id": "ID5"}]
    monkeypatch.setattr(loader, "_fetch_from_postgres", _mock_fetch(records))
    monkeypatch.setattr(loader, "MySqlDBManager", None)

    result = loader._extract_company_id5_mapping()

    assert result == {"AcctA": "ID5"}


def test_extract_company_id5_mapping_falls_back_to_mysql(monkeypatch):
    # Simulate postgres failure -> empty list, then fallback MySQL path
    monkeypatch.setattr(loader, "_fetch_from_postgres", _mock_fetch([]))

    class FakeCursor:
        def __init__(self):
            self.closed = False

        def execute(self, sql):
            self.sql = sql

        def fetchall(self):
            return [("acct", "CID")]

        def close(self):
            self.closed = True

    class FakeMySql:
        def __init__(self, database: str):
            self.database = database
            self.cursor = FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(loader, "MySqlDBManager", FakeMySql)

    result = loader._extract_company_id5_mapping()

    assert result == {"acct": "CID"}

