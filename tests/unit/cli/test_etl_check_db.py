"""Unit tests for ETL --check-db diagnostics (Story 6.2-P16)."""

import sys
import types

import pytest

from work_data_hub.cli import etl as etl_module
from work_data_hub.cli.etl import diagnostics as diagnostics_module


@pytest.mark.unit
class TestEtlCheckDbDiagnostics:
    def test_check_db_reports_missing_settings(self, monkeypatch, capsys):
        class Settings:
            database_host = "localhost"
            database_port = 5432
            database_db = "wdh"
            database_user = "user"
            database_password = ""  # missing

            def get_database_connection_string(self) -> str:
                return "dbname=wdh user=user"

        monkeypatch.setattr(diagnostics_module, "get_settings", lambda: Settings())

        rc = etl_module._check_database_connection()
        out = capsys.readouterr().out

        assert rc == 1
        assert "Missing required settings" in out
        assert "WDH_DATABASE__PASSWORD" in out

    def test_check_db_handles_connection_failure(self, monkeypatch, capsys):
        class Settings:
            database_host = "localhost"
            database_port = 5432
            database_db = "wdh"
            database_user = "user"
            database_password = "pw"

            def get_database_connection_string(self) -> str:
                return "dbname=wdh user=user password=pw"

        def connect(_dsn: str):
            raise Exception("boom")

        monkeypatch.setattr(diagnostics_module, "get_settings", lambda: Settings())
        monkeypatch.setitem(
            sys.modules, "psycopg2", types.SimpleNamespace(connect=connect)
        )

        rc = etl_module._check_database_connection()
        out = capsys.readouterr().out

        assert rc == 1
        assert "Connection error" in out
        assert "Troubleshooting hints" in out
