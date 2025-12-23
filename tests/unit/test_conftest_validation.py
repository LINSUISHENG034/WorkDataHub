"""Unit tests for conftest.py database validation logic."""

import os
import pytest
from tests.conftest import _validate_test_database


class TestValidateTestDatabase:
    """Test suite for _validate_test_database safety check."""

    @pytest.mark.parametrize(
        "dsn",
        [
            "postgresql://localhost/work_data_hub_test",
            "postgresql://user:pass@localhost:5432/tmp_wdh",
            "postgresql://localhost/postgres_test_123",
            "postgresql://localhost/work_data_hub_test_abc123",
            "postgresql://localhost/testdb",
            "postgresql://localhost/dev_database",
            "postgresql://localhost/local_db",
            "postgresql://localhost/sandbox_env",
        ],
    )
    def test_validate_test_database_valid_names(self, dsn: str):
        """Test that test/tmp/dev/local/sandbox database names pass validation."""
        # Should not raise any exception
        assert _validate_test_database(dsn) is True

    @pytest.mark.parametrize(
        "dsn,expected_db_name",
        [
            ("postgresql://localhost/work_data_hub", "work_data_hub"),
            ("postgresql://localhost/production", "production"),
            ("postgresql://localhost/my_app", "my_app"),
        ],
    )
    def test_validate_test_database_production_name_raises(
        self, dsn: str, expected_db_name: str
    ):
        """Test that production database names raise RuntimeError."""
        with pytest.raises(
            RuntimeError, match="Refusing to run tests against non-test database"
        ):
            _validate_test_database(dsn)

    @pytest.mark.parametrize(
        "dsn",
        [
            "postgresql://localhost/WORK_DATA_HUB_TEST",
            "postgresql://localhost/TMP_wdh",
            "postgresql://localhost/Test_Database",
            "postgresql://localhost/DEV_ENV",
        ],
    )
    def test_validate_test_database_case_insensitive(self, dsn: str):
        """Test that validation is case-insensitive for maximum safety."""
        # Should not raise any exception
        assert _validate_test_database(dsn) is True

    def test_validate_test_database_with_override(self, monkeypatch):
        """Test that WDH_SKIP_DB_VALIDATION=1 bypasses validation."""
        monkeypatch.setenv("WDH_SKIP_DB_VALIDATION", "1")
        # Production database name should be allowed with override
        assert _validate_test_database("postgresql://localhost/work_data_hub") is True

    def test_validate_test_database_without_override(self):
        """Test that validation enforces test pattern by default."""
        # Ensure override is not set
        os.environ.pop("WDH_SKIP_DB_VALIDATION", None)
        with pytest.raises(RuntimeError):
            _validate_test_database("postgresql://localhost/production_db")

    @pytest.mark.parametrize(
        "dsn",
        [
            "postgresql://localhost/",  # Empty database name
            "postgresql://localhost",  # No database path
        ],
    )
    def test_validate_test_database_edge_cases(self, dsn: str):
        """Test edge cases like empty/missing database name."""
        # Empty database name should fail (doesn't match test pattern)
        with pytest.raises(RuntimeError):
            _validate_test_database(dsn)
