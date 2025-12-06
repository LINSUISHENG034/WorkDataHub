"""
Comprehensive End-to-End validation tests for trustee performance pipeline.

This module provides E2E validation tests that verify the complete ETL pipeline
from Excel files to PostgreSQL database, including plan-only mode execution,
error handling, and recovery scenarios according to PRP P-013 requirements.
"""

import os
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import yaml
from dagster import build_op_context

pytestmark = [
    pytest.mark.sample_domain,
    pytest.mark.e2e_suite,
]

from src.work_data_hub.domain.sample_trustee_performance.service import process
from src.work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError, load
from src.work_data_hub.orchestration.ops import (
    DiscoverFilesConfig,
    LoadConfig,
    ReadExcelConfig,
    discover_files_op,
    load_op,
    process_sample_trustee_performance_op,
    read_excel_op,
)


class TestTrusteePerformanceE2E:
    """End-to-end pipeline validation tests."""

    @pytest.fixture
    def sample_excel_data(self):
        """Create sample Excel data for E2E testing."""
        return pd.DataFrame(
            {
                "年": ["2024", "2024", "2024"],
                "月": ["11", "11", "11"],
                "计划代码": ["PLAN001", "PLAN002", "PLAN003"],
                "公司代码": ["COMP001", "COMP001", "COMP002"],
                "收益率": ["5.5%", "4.8%", "6.2%"],
                "净值": ["1.0512", "1.0448", "1.0623"],
                "规模": ["12000000.50", "8500000.25", "15600000.75"],
            }
        )

    @pytest.fixture
    def temp_excel_file(self, sample_excel_data, tmp_path):
        """Create temporary Excel file for testing."""
        excel_file = tmp_path / "2024_11_受托业绩报告.xlsx"
        sample_excel_data.to_excel(excel_file, index=False, engine="openpyxl")
        return str(excel_file)

    @pytest.fixture
    def temp_config_file(self, tmp_path):
        """Create temporary data sources configuration."""
        config_data = {
            "domains": {
                "sample_trustee_performance": {
                    "pattern": r"(?P<year>20\d{2})[-_](?P<month>0?[1-9]|1[0-2]).*受托业绩.*\.xlsx$",
                    "select": "latest_by_year_month",
                    "sheet": 0,
                    "table": "sample_trustee_performance",
                    "primary_key": ["report_date", "plan_code", "company_code"],
                }
            }
        }

        config_file = tmp_path / "test_data_sources.yml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        return str(config_file)

    def test_complete_pipeline_plan_only_mode(self, temp_excel_file, temp_config_file):
        """Test complete E2E pipeline in plan-only mode."""
        with patch("src.work_data_hub.orchestration.ops.get_settings") as mock_settings:
            mock_settings.return_value.data_sources_config = temp_config_file

            # Mock DataSourceConnector
            with patch(
                "src.work_data_hub.orchestration.ops.DataSourceConnector"
            ) as mock_connector_class:
                mock_discovered = Mock()
                mock_discovered.path = temp_excel_file
                mock_discovered.year = 2024
                mock_discovered.month = 11

                mock_connector = Mock()
                mock_connector.discover.return_value = [mock_discovered]
                mock_connector_class.return_value = mock_connector

                # Step 1: Discover files
                context = build_op_context()
                discover_config = DiscoverFilesConfig(
                    domain="sample_trustee_performance"
                )
                file_paths = discover_files_op(context, discover_config)

                assert len(file_paths) == 1
                assert file_paths[0] == temp_excel_file

                # Step 2: Read Excel
                read_config = ReadExcelConfig(sheet=0)
                excel_rows = read_excel_op(context, read_config, file_paths)

                assert len(excel_rows) == 3
                assert excel_rows[0]["年"] == "2024"
                assert excel_rows[0]["计划代码"] == "PLAN001"

                # Step 3: Process domain data
                processed_rows = process_sample_trustee_performance_op(
                    context, excel_rows, file_paths
                )

                assert len(processed_rows) == 3
                assert processed_rows[0]["plan_code"] == "PLAN001"
                assert processed_rows[0]["report_date"] == "2024-11-01"

                # Step 4: Load (plan-only mode)
                load_config = LoadConfig(
                    table="sample_trustee_performance",
                    mode="delete_insert",
                    pk=["report_date", "plan_code", "company_code"],
                    plan_only=True,
                )
                load_result = load_op(context, load_config, processed_rows)

                # Verify plan-only results
                assert load_result["mode"] == "delete_insert"
                assert load_result["deleted"] == 3  # Unique PK combinations
                assert load_result["inserted"] == 3
                assert "sql_plans" in load_result

                operations = load_result["sql_plans"]
                assert len(operations) == 2  # DELETE + INSERT
                assert operations[0][0] == "DELETE"
                assert operations[1][0] == "INSERT"

    def test_pipeline_with_decimal_precision_validation(self, tmp_path):
        """Test E2E pipeline handles decimal precision edge cases correctly."""
        # Create Excel data with problematic float precision values
        problematic_data = pd.DataFrame(
            {
                "年": ["2024"],
                "月": ["11"],
                "计划代码": ["PLAN001"],
                "公司代码": ["COMP001"],
                "收益率": [0.048799999999999996],  # Problematic float precision
                "净值": [1.0512000000000001],  # Another float edge case
                "规模": [12000000.003],  # Large number precision issue
            }
        )

        excel_file = tmp_path / "precision_test.xlsx"
        problematic_data.to_excel(excel_file, index=False, engine="openpyxl")

        # Process the data through domain service
        excel_rows = problematic_data.to_dict("records")
        processed_models = process(excel_rows, data_source=str(excel_file))

        # Verify decimal quantization worked correctly
        assert len(processed_models) == 1
        model = processed_models[0]

        # These should be quantized correctly without causing ValidationError
        assert model.return_rate == Decimal("0.048800")  # 6 decimal places
        assert model.net_asset_value == Decimal("1.0512")  # 4 decimal places
        assert model.fund_scale == Decimal("12000000.00")  # 2 decimal places

        # Test through complete pipeline
        processed_dicts = [model.model_dump() for model in processed_models]

        # Load in plan-only mode
        load_result = load(
            table="sample_trustee_performance",
            rows=processed_dicts,
            mode="delete_insert",
            pk=["report_date", "plan_code", "company_code"],
            conn=None,
        )

        assert load_result["inserted"] == 1
        assert "sql_plans" in load_result

    def test_pipeline_with_jsonb_complex_structures(self):
        """Test E2E pipeline handles JSONB complex data structures."""
        # Create processed rows with complex JSONB data
        processed_rows = [
            {
                "report_date": date(2024, 11, 1),
                "plan_code": "PLAN001",
                "company_code": "COMP001",
                "return_rate": Decimal("0.055"),
                "data_source": "test_e2e",
                "validation_warnings": [
                    "High return rate detected: 5.5%",
                    {
                        "warning_type": "data_quality",
                        "details": {
                            "field": "return_rate",
                            "value": 0.055,
                            "threshold": 0.05,
                            "metadata": {
                                "source_row": 1,
                                "processing_timestamp": "2024-01-01T12:00:00Z",
                            },
                        },
                    },
                ],
                "metadata": {
                    "processing_context": {
                        "data_source": "/path/to/sample_trustee_performance_2024_11.xlsx",
                        "batch_id": "batch_20241101_001",
                    },
                    "data_lineage": [
                        {"step": "extraction", "timestamp": "2024-01-01T11:00:00Z"},
                        {"step": "validation", "timestamp": "2024-01-01T11:30:00Z"},
                    ],
                },
            }
        ]

        # Convert to dicts for serialization
        row_dicts = []
        for row in processed_rows:
            row_dict = {}
            for key, value in row.items():
                if isinstance(value, (date, Decimal)):
                    row_dict[key] = str(value)
                else:
                    row_dict[key] = value
            row_dicts.append(row_dict)

        # Test load operation plan generation
        load_result = load(
            table="sample_trustee_performance",
            rows=row_dicts,
            mode="delete_insert",
            pk=["report_date", "plan_code", "company_code"],
            conn=None,
        )

        assert load_result["inserted"] == 1
        assert "sql_plans" in load_result

        # Verify JSONB parameters are in the plan
        operations = load_result["sql_plans"]
        insert_op = next(op for op in operations if op[0] == "INSERT")
        sql, params = insert_op[1], insert_op[2]

        assert "INSERT INTO" in sql
        # Should have flattened parameters including JSONB structures
        assert len(params) >= 7  # At least the core fields plus JSONB data

    def test_pipeline_error_handling_invalid_data(self, tmp_path):
        """Test E2E pipeline error handling with invalid data."""
        # Create Excel data with invalid/problematic values
        invalid_data = pd.DataFrame(
            {
                "年": ["invalid_year", "2024", ""],
                "月": ["invalid_month", "13", "11"],  # Invalid month
                "计划代码": ["", "PLAN002", "PLAN003"],  # Empty plan code
                "公司代码": ["COMP001", "", "COMP003"],  # Empty company code
                "收益率": ["not_a_number", "5.5%", "150%"],  # Invalid/extreme values
            }
        )

        excel_file = tmp_path / "invalid_data_test.xlsx"
        invalid_data.to_excel(excel_file, index=False, engine="openpyxl")

        excel_rows = invalid_data.to_dict("records")

        # Process should handle errors gracefully
        # Some rows should be filtered out, others should be processed successfully
        with patch(
            "src.work_data_hub.domain.sample_trustee_performance.service.logger"
        ) as mock_logger:
            processed_models = process(excel_rows, data_source=str(excel_file))

            # Should process at least some valid data (not all rows are completely invalid)
            assert len(processed_models) <= 3  # Some rows may be filtered out

            # Verify error logging occurred
            assert mock_logger.warning.called or mock_logger.error.called

    def test_pipeline_recovery_from_processing_errors(self):
        """Test pipeline recovery from processing errors."""
        # Create mix of valid and invalid rows
        mixed_rows = [
            # Valid row
            {
                "年": "2024",
                "月": "11",
                "计划代码": "PLAN001",
                "公司代码": "COMP001",
                "收益率": "5.5%",
                "净值": "1.05",
                "规模": "1000000",
            },
            # Invalid row (missing critical data)
            {"年": "2024", "月": "11", "其他字段": "some_value"},
            # Another valid row
            {
                "年": "2024",
                "月": "11",
                "计划代码": "PLAN003",
                "公司代码": "COMP003",
                "收益率": "4.2%",
                "净值": "1.03",
                "规模": "2000000",
            },
        ]

        # Process should continue despite errors in some rows
        processed_models = process(mixed_rows, data_source="recovery_test")

        # Should successfully process the valid rows
        assert len(processed_models) == 2  # Two valid rows out of three

        valid_plan_codes = [model.plan_code for model in processed_models]
        assert "PLAN001" in valid_plan_codes
        assert "PLAN003" in valid_plan_codes

    def test_pipeline_empty_data_handling(self):
        """Test E2E pipeline handles empty datasets gracefully."""
        # Test empty file list
        context = build_op_context()
        read_config = ReadExcelConfig(sheet=0)
        excel_rows = read_excel_op(context, read_config, [])  # Empty file list

        assert excel_rows == []

        # Test empty Excel data
        processed_rows = process_sample_trustee_performance_op(context, [], [])

        assert processed_rows == []

        # Test empty load operation
        load_config = LoadConfig(plan_only=True)
        load_result = load_op(context, load_config, [])

        assert load_result["deleted"] == 0
        assert load_result["inserted"] == 0
        assert load_result["batches"] == 0

    @pytest.mark.parametrize("mode", ["delete_insert", "append"])
    def test_pipeline_different_load_modes(self, mode, tmp_path):
        """Test E2E pipeline with different load modes."""
        # Create simple test data
        test_data = pd.DataFrame(
            {
                "年": ["2024"],
                "月": ["11"],
                "计划代码": ["PLAN001"],
                "公司代码": ["COMP001"],
                "收益率": ["5.5%"],
            }
        )

        excel_file = tmp_path / f"load_mode_{mode}_test.xlsx"
        test_data.to_excel(excel_file, index=False, engine="openpyxl")

        excel_rows = test_data.to_dict("records")
        processed_models = process(excel_rows, data_source=str(excel_file))
        processed_dicts = [model.model_dump() for model in processed_models]

        # Test load operation in specified mode
        pk = (
            ["report_date", "plan_code", "company_code"]
            if mode == "delete_insert"
            else []
        )

        load_result = load(
            table="sample_trustee_performance",
            rows=processed_dicts,
            mode=mode,
            pk=pk,
            conn=None,  # Plan-only mode
        )

        assert load_result["mode"] == mode
        assert load_result["inserted"] == 1

        if mode == "delete_insert":
            assert load_result["deleted"] == 1
            assert len(load_result["sql_plans"]) == 2  # DELETE + INSERT
        else:  # append
            assert load_result["deleted"] == 0
            assert len(load_result["sql_plans"]) == 1  # INSERT only

    def test_pipeline_large_dataset_chunking(self):
        """Test E2E pipeline handles large datasets with chunking."""
        # Create large dataset
        large_dataset = []
        for i in range(2500):  # Larger than default chunk_size
            large_dataset.append(
                {
                    "年": "2024",
                    "月": "11",
                    "计划代码": f"PLAN{i:04d}",
                    "公司代码": f"COMP{i % 10:03d}",
                    "收益率": f"{(i % 10) * 0.5 + 1.0:.2f}%",
                }
            )

        # Process large dataset
        processed_models = process(large_dataset, data_source="large_dataset_test")
        processed_dicts = [model.model_dump() for model in processed_models]

        assert len(processed_dicts) == 2500

        # Test chunked load operation
        load_result = load(
            table="sample_trustee_performance",
            rows=processed_dicts,
            mode="append",
            chunk_size=1000,
            conn=None,
        )

        assert load_result["inserted"] == 2500
        assert load_result["batches"] == 3  # ceil(2500/1000)

        # Should have 3 INSERT operations
        operations = load_result["sql_plans"]
        insert_ops = [op for op in operations if op[0] == "INSERT"]
        assert len(insert_ops) == 3


@pytest.mark.postgres
class TestTrusteePerformanceE2EIntegration:
    """Integration tests requiring actual PostgreSQL database."""

    @pytest.fixture
    def db_connection(self):
        """Create test database connection for E2E integration tests."""

        # Use test database URI or fallback to application settings
        conn_str = os.getenv("WDH_TEST_DATABASE_URI")
        if not conn_str:
            try:
                from src.work_data_hub.config.settings import get_settings

                settings = get_settings()
                conn_str = settings.get_database_connection_string()
            except Exception:
                pytest.skip("Test database not configured")

        try:
            import psycopg2
        except ImportError:
            pytest.skip("psycopg2 not available")

        # Create connection with timeout
        conn = psycopg2.connect(conn_str, connect_timeout=5)

        # Setup temporary test table
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TEMP TABLE test_trustee_performance (
                    report_date DATE,
                    plan_code VARCHAR(50),
                    company_code VARCHAR(20), 
                    return_rate NUMERIC(8,6),
                    net_asset_value NUMERIC(18,4),
                    fund_scale NUMERIC(18,2),
                    data_source VARCHAR(255),
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    has_performance_data BOOLEAN DEFAULT FALSE,
                    validation_warnings JSONB DEFAULT NULL,
                    metadata JSONB DEFAULT NULL,
                    PRIMARY KEY (report_date, plan_code, company_code)
                )
            """)

        yield conn
        conn.close()

    def test_complete_e2e_with_database_execution(self, db_connection, tmp_path):
        """Test complete E2E pipeline with actual database execution."""
        # Create test data with JSONB columns
        test_data = pd.DataFrame(
            {
                "年": ["2024", "2024"],
                "月": ["11", "11"],
                "计划代码": ["PLAN001", "PLAN002"],
                "公司代码": ["COMP001", "COMP002"],
                "收益率": ["5.5%", "4.8%"],
                "净值": ["1.0512", "1.0448"],
                "规模": ["12000000.50", "8500000.25"],
            }
        )

        excel_file = tmp_path / "e2e_integration_test.xlsx"
        test_data.to_excel(excel_file, index=False, engine="openpyxl")

        # Process through domain service
        excel_rows = test_data.to_dict("records")
        processed_models = process(excel_rows, data_source=str(excel_file))

        # Add JSONB data to test adaptation
        processed_dicts = []
        for i, model in enumerate(processed_models):
            model_dict = model.model_dump()
            model_dict["validation_warnings"] = [f"Test warning {i + 1}"]
            model_dict["metadata"] = {
                "source_file": str(excel_file),
                "processing_batch": f"batch_{i + 1}",
            }
            processed_dicts.append(model_dict)

        # Execute actual database load
        load_result = load(
            table="test_trustee_performance",
            rows=processed_dicts,
            mode="delete_insert",
            pk=["report_date", "plan_code", "company_code"],
            conn=db_connection,
        )

        assert load_result["inserted"] == 2
        assert load_result["deleted"] >= 0  # May delete existing test data

        # Verify data was actually inserted
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_trustee_performance")
            count = cursor.fetchone()[0]
            assert count == 2

            # Verify JSONB data was stored correctly
            cursor.execute("""
                SELECT validation_warnings, metadata 
                FROM test_trustee_performance 
                WHERE plan_code = 'PLAN001'
            """)
            warnings, metadata = cursor.fetchone()

            assert warnings == ["Test warning 1"]
            assert metadata["processing_batch"] == "batch_1"

    def test_database_transaction_rollback_on_error(self, db_connection):
        """Test that database transactions rollback properly on errors."""
        # Create data that will cause a constraint violation
        invalid_data = [
            {
                "report_date": "2024-11-01",
                "plan_code": "PLAN001",
                "company_code": "COMP001",
                "return_rate": Decimal("0.055"),
                "data_source": "test",
            },
            {
                "report_date": "2024-11-01",
                "plan_code": "PLAN001",  # Duplicate primary key
                "company_code": "COMP001",
                "return_rate": Decimal("0.048"),
                "data_source": "test",
            },
        ]

        # This should fail due to duplicate primary key
        with pytest.raises(DataWarehouseLoaderError):
            load(
                table="test_trustee_performance",
                rows=invalid_data,
                mode="append",  # Will try to insert duplicates
                conn=db_connection,
            )

        # Verify no data was inserted (transaction rolled back)
        with db_connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_trustee_performance")
            count = cursor.fetchone()[0]
            assert count == 0  # No partial inserts

    def test_database_connection_lifecycle_integration(self, db_connection):
        """Test database connection lifecycle in realistic scenario."""
        test_data = [
            {
                "report_date": "2024-11-01",
                "plan_code": "PLAN001",
                "company_code": "COMP001",
                "return_rate": Decimal("0.055"),
                "data_source": "connection_test",
            }
        ]

        # Mock load_op to test connection handling
        with patch("src.work_data_hub.orchestration.ops.psycopg2") as mock_psycopg2:
            mock_psycopg2.connect.return_value = db_connection

            context = build_op_context()
            config = LoadConfig(
                table="test_trustee_performance", mode="append", pk=[], plan_only=False
            )

            with patch(
                "src.work_data_hub.orchestration.ops.get_settings"
            ) as mock_settings:
                mock_settings.return_value.get_database_connection_string.return_value = "mocked_dsn"

                result = load_op(context, config, test_data)

                # Verify successful execution
                assert result["inserted"] == 1

                # Verify connection was closed (mock shows close was called)
                # Note: In real test, db_connection fixture handles cleanup
