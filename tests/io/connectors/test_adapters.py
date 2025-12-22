import sys
import types

import pandas as pd
import pytest

from work_data_hub.domain.reference_backfill.sync_models import ReferenceSyncTableConfig
from work_data_hub.io.connectors.adapter_factory import AdapterFactory
from work_data_hub.io.connectors.mysql_source_adapter import MySQLSourceAdapter
from work_data_hub.io.connectors.postgres_source_adapter import PostgresSourceAdapter


@pytest.fixture(autouse=True)
def _clear_adapter_cache():
    AdapterFactory.clear_cache()
    yield
    AdapterFactory.clear_cache()


def test_postgres_fetch_maps_columns_and_incremental(monkeypatch):
    adapter = PostgresSourceAdapter(connection_env_prefix="WDH_LEGACY")
    captured = {}

    def fake_exec(query, params, source_config, table_config):
        captured["query"] = query
        captured["params"] = params
        captured["source_config"] = source_config
        captured["table_config"] = table_config
        return pd.DataFrame([{"plan_code": "A1", "plan_name": "Foo"}])

    monkeypatch.setattr(adapter, "_execute_query_with_retry", fake_exec)

    cfg = ReferenceSyncTableConfig(
        name="plan",
        target_table="年金计划",
        target_schema="business",
        source_type="postgres",
        source_config={
            "schema": "enterprise",
            "table": "annuity_plan",
            "columns": [
                {"source": "plan_code", "target": "年金计划号"},
                {"source": "plan_name", "target": "计划名称"},
            ],
            "incremental": {
                "where": "updated_at >= :last_synced_at",
                "updated_at_column": "updated_at",
            },
        },
        sync_mode="upsert",
        primary_key="年金计划号",
    )

    df = adapter.fetch_data(cfg, state={"last_synced_at": "2025-01-01"})

    assert list(df.columns) == ["年金计划号", "计划名称"]
    assert captured["params"]["last_synced_at"] == "2025-01-01"
    assert "WHERE updated_at >= %(last_synced_at)s" in captured["query"]
    assert "enterprise" in captured["query"]


def test_postgres_env_prefix_fallback(monkeypatch):
    # Only legacy prefix provided -> should still be picked up
    monkeypatch.setenv("WDH_LEGACY_PG_HOST", "legacy-host")
    monkeypatch.setenv("WDH_LEGACY_PG_USER", "legacy-user")
    monkeypatch.setenv("WDH_LEGACY_PG_PASSWORD", "legacy-pass")
    monkeypatch.setenv("WDH_LEGACY_PG_DATABASE", "legacy-db")

    adapter = PostgresSourceAdapter(connection_env_prefix="WDH_LEGACY")

    assert adapter.host == "legacy-host"
    assert adapter.user == "legacy-user"
    assert adapter.password == "legacy-pass"
    assert adapter.database == "legacy-db"


def test_mysql_adapter_wraps_legacy(monkeypatch):
    calls = {}

    class FakeLegacy:
        def __init__(self, **kwargs):
            calls["init_kwargs"] = kwargs

        def fetch_data(self, request, state=None):
            calls["request"] = request
            calls["state"] = state
            return pd.DataFrame([{"col_a": "x"}])

    monkeypatch.setattr(
        sys.modules["work_data_hub.io.connectors.mysql_source_adapter"],
        "LegacyMySQLConnector",
        FakeLegacy,
    )

    adapter = MySQLSourceAdapter()
    cfg = ReferenceSyncTableConfig(
        name="plan",
        target_table="t",
        target_schema="business",
        source_type="legacy_mysql",
        source_config={
            "table": "legacy_table",
            "columns": [{"source": "col_a", "target": "列A"}],
        },
        sync_mode="upsert",
        primary_key="列A",
    )

    df = adapter.fetch_data(cfg, state={"k": "v"})

    assert list(df.columns) == ["列A"]
    assert calls["request"]["table"] == "legacy_table"
    assert calls["state"] == {"k": "v"}


def test_adapter_factory_creates_and_caches(monkeypatch):
    fake_pg_instances = []
    fake_mysql_instances = []
    fake_config_instances = []

    class FakePg:
        def __init__(self, **kwargs):
            fake_pg_instances.append(kwargs)

    class FakeMysql:
        def __init__(self, **kwargs):
            fake_mysql_instances.append(kwargs)

    class FakeConfig:
        def __init__(self, **kwargs):
            fake_config_instances.append(kwargs)

    # Patch import targets used inside AdapterFactory.create
    monkeypatch.setitem(
        sys.modules,
        "work_data_hub.io.connectors.postgres_source_adapter",
        types.SimpleNamespace(PostgresSourceAdapter=FakePg),
    )
    monkeypatch.setitem(
        sys.modules,
        "work_data_hub.io.connectors.mysql_source_adapter",
        types.SimpleNamespace(MySQLSourceAdapter=FakeMysql),
    )
    monkeypatch.setitem(
        sys.modules,
        "work_data_hub.io.connectors.config_file_connector",
        types.SimpleNamespace(ConfigFileConnector=FakeConfig),
    )

    pg1 = AdapterFactory.create("postgres", connection_env_prefix="WDH_LEGACY")
    pg2 = AdapterFactory.create("postgres", connection_env_prefix="WDH_LEGACY")
    assert pg1 is pg2  # cached

    pg3 = AdapterFactory.create("postgres", connection_env_prefix="OTHER")
    assert pg3 is not pg1
    assert fake_pg_instances[0]["connection_env_prefix"] == "WDH_LEGACY"
    assert fake_pg_instances[1]["connection_env_prefix"] == "OTHER"

    mysql = AdapterFactory.create("legacy_mysql")
    assert fake_mysql_instances  # created

    cfg = AdapterFactory.create("config_file")
    assert fake_config_instances  # created
