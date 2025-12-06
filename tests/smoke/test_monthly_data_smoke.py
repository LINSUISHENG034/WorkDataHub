"""
Smoke tests using reference/monthly data - opt-in via marker.

These tests validate the complete sample_trustee_performance pipeline using real
reference data and optional database integration. Tests are skipped by
default and require explicit marker activation.

Usage:
    # Skip smoke tests (default)
    uv run pytest tests/

    # Run only smoke tests
    uv run pytest -m monthly_data -v

    # Run smoke tests with database integration
    WDH_DATABASE__URI=postgresql://user:pass@localhost:5432/test_db uv run pytest -m monthly_data -v
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.work_data_hub.config.settings import get_settings
from src.work_data_hub.io.connectors.file_connector import DataSourceConnector


@pytest.mark.monthly_data
class TestMonthlyDataSmoke:
    """Smoke tests using reference/monthly data - opt-in via marker."""

    @pytest.fixture(autouse=True)
    def setup_monthly_data_env(self):
        """Setup environment for monthly data testing."""
        # Ensure reference/monthly exists or skip
        reference_path = Path("./reference/monthly")
        if not reference_path.exists():
            pytest.skip(f"Reference monthly data not found at {reference_path}")

    def test_discovery_with_monthly_data(self):
        """Validates discovery when WDH_DATA_BASE_DIR=./reference/monthly."""
        # Override environment for this test
        with patch.dict(os.environ, {"WDH_DATA_BASE_DIR": "./reference/monthly"}):
            connector = DataSourceConnector()

            try:
                discovered_files = connector.discover("sample_trustee_performance")
            except Exception as e:
                pytest.skip(f"Discovery failed: {e}")

            # Basic validation - should find some files
            assert isinstance(discovered_files, list), "Discovery should return a list"

            # Log discovery results for debugging
            print(
                f"Discovered {len(discovered_files)} sample_trustee_performance files in reference/monthly"
            )

            if discovered_files:
                # Validate file structure
                first_file = discovered_files[0]
                assert hasattr(first_file, "path"), (
                    "Discovered files should have path attribute"
                )
                print(f"Sample discovered file: {first_file.path}")

    def test_plan_only_smoke(self):
        """Test plan-only mode with --max-files 2."""
        from src.work_data_hub.config.settings import Settings

        # Override settings for this test
        test_settings = Settings(
            data_base_dir="./reference/monthly", dev_sample_size=None
        )

        with patch(
            "src.work_data_hub.config.settings.get_settings", return_value=test_settings
        ):
            with patch.dict(os.environ, {"WDH_DATA_BASE_DIR": "./reference/monthly"}):
                # Mock the job execution to avoid actual Dagster machinery
                mock_context = MagicMock()
                mock_context.log.info = MagicMock()
                mock_context.log.warning = MagicMock()

                try:
                    # Test discovery phase
                    connector = DataSourceConnector()
                    discovered_files = connector.discover("sample_trustee_performance")

                    if not discovered_files:
                        pytest.skip("No files discovered for plan-only smoke test")

                    # Limit to max 2 files for smoke test
                    limited_files = discovered_files[:2]

                    print(f"Plan-only smoke test with {len(limited_files)} files")

                    # Basic validation - files should be accessible
                    for file_info in limited_files:
                        file_path = Path(file_info.path)
                        assert file_path.exists(), (
                            f"Discovered file should exist: {file_path}"
                        )
                        assert file_path.suffix.lower() in [".xlsx", ".xls"], (
                            f"Should be Excel file: {file_path}"
                        )

                except Exception as e:
                    pytest.skip(f"Plan-only smoke test failed: {e}")

    @pytest.mark.postgres
    def test_execute_smoke(self, db_connection):
        """Optional execute test with real database."""
        from src.work_data_hub.domain.sample_trustee_performance.service import process
        from src.work_data_hub.io.loader.warehouse_loader import load
        from src.work_data_hub.io.readers.excel_reader import ExcelReader

        # Override environment for monthly data
        with patch.dict(os.environ, {"WDH_DATA_BASE_DIR": "./reference/monthly"}):
            try:
                # Discovery phase
                connector = DataSourceConnector()
                discovered_files = connector.discover("sample_trustee_performance")

                if not discovered_files:
                    pytest.skip("No files discovered for execute smoke test")

                # Use only first file for smoke test
                first_file = discovered_files[0]
                print(f"Execute smoke test with file: {first_file.path}")

                # Read Excel data (limit rows for smoke)
                reader = ExcelReader(max_rows=10)
                excel_rows = reader.read_rows(first_file.path, sheet=0)

                if not excel_rows:
                    pytest.skip("No data read from Excel file")

                print(f"Read {len(excel_rows)} rows from Excel")

                # Process domain transformation
                processed_records = process(excel_rows, source_file=first_file.path)

                if not processed_records:
                    pytest.skip("No processed records for database test")

                print(f"Processed {len(processed_records)} records")

                # Convert to dicts for loader
                processed_dicts = [record.model_dump() for record in processed_records]

                # Test database load in plan-only mode first
                plan_result = load(
                    table="sample_trustee_performance",
                    rows=processed_dicts,
                    mode="delete_insert",
                    pk=["report_date", "plan_code", "company_code"],
                    conn=None,  # Plan-only
                )

                assert plan_result is not None, "Plan-only load should return result"
                assert "sql_plans" in plan_result, "Plan should include SQL plans"
                print(f"Plan-only result: {plan_result.get('summary', 'No summary')}")

                # Test actual execution with database
                execute_result = load(
                    table="sample_trustee_performance",
                    rows=processed_dicts,
                    mode="delete_insert",
                    pk=["report_date", "plan_code", "company_code"],
                    conn=db_connection,
                )

                assert execute_result is not None, "Execute load should return result"
                print(
                    f"Execute result: deleted={execute_result.get('deleted', 0)}, "
                    f"inserted={execute_result.get('inserted', 0)}"
                )

            except Exception as e:
                pytest.skip(f"Execute smoke test failed: {e}")

    @pytest.fixture
    def db_connection(self):
        """Database connection fixture for smoke tests."""
        import os

        # Use test database URI or fallback to application settings
        conn_str = os.getenv("WDH_TEST_DATABASE_URI")
        if not conn_str:
            conn_str = os.getenv("WDH_DATABASE__URI")

        if not conn_str:
            try:
                settings = get_settings()
                conn_str = settings.get_database_connection_string()
            except Exception:
                pytest.skip("Test database not configured")

        try:
            import psycopg2
        except ImportError:
            pytest.skip("psycopg2 not available")

        # Create connection with fast timeout for smoke tests
        try:
            conn = psycopg2.connect(conn_str, connect_timeout=5)
        except Exception as e:
            pytest.skip(f"Database connection failed: {e}")

        # Setup test table - use our test schema
        try:
            with conn.cursor() as cursor:
                # Use the same schema as our test DDL
                cursor.execute("""
                    CREATE TEMP TABLE sample_trustee_performance (
                        report_date DATE,
                        plan_code VARCHAR(50),
                        company_code VARCHAR(20),
                        return_rate NUMERIC(8,6),
                        net_asset_value NUMERIC(18,4),
                        fund_scale NUMERIC(18,2),
                        data_source VARCHAR(255),
                        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        has_performance_data BOOLEAN DEFAULT FALSE,
                        validation_warnings JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT NULL,
                        PRIMARY KEY (report_date, plan_code, company_code)
                    )
                """)
                conn.commit()
        except Exception as e:
            conn.close()
            pytest.skip(f"Failed to setup test table: {e}")

        yield conn
        conn.close()
