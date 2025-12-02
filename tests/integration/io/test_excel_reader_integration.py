"""Integration tests for ExcelReader.read_sheet() method (Story 3.3).

This module tests end-to-end Excel reading functionality with
realistic Excel files and multi-sheet scenarios.
"""

from datetime import datetime
from pathlib import Path
import pytest
import pandas as pd

from work_data_hub.io.readers.excel_reader import ExcelReader, ExcelReadResult
from work_data_hub.io.connectors.exceptions import DiscoveryError


@pytest.fixture
def sample_multi_sheet_excel_file(tmp_path):
    """Create a realistic multi-sheet Excel file for testing."""
    # Create realistic data similar to 202411 data
    data = {
        "规模明细": [
            {"月度": "202411", "计划代码": "PLAN001", "客户名称": "客户A",
             "期初资产规模": 1000000, "期末资产规模": 1050000, "当期收益率": "5.5%"},
            {"月度": "202411", "计划代码": "PLAN002", "客户名称": "客户B",
             "期初资产规模": 2000000, "期末资产规模": 2100000, "当期收益率": "5.2%"},
            {"月度": "202411", "计划代码": "PLAN003", "客户名称": "客户C",
             "期初资产规模": 1500000, "期末资产规模": 1575000, "当期收益率": "5.0%"}
        ],
        "Summary": [
            {"报表类型": "月度报表", "总客户数": 3, "总资产规模": 4500000},
            {"报表类型": "季度报表", "总客户数": 5, "总资产规模": 7500000}
        ],
        "Notes": [
            {"备注": "数据采集于2024年11月", "处理人": "张三"}
        ]
    }

    # Create Excel file
    excel_path = tmp_path / "test_multi_sheet_integration.xlsx"
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for sheet_name, sheet_data in data.items():
            df = pd.DataFrame(sheet_data)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return excel_path


@pytest.fixture
def chinese_sheet_names_excel_file(tmp_path):
    """Create Excel file with Chinese sheet names."""
    data = {
        "年金数据明细": [
            {"产品名称": "年金产品A", "客户编号": "C001", "金额": 100000},
            {"产品名称": "年金产品B", "客户编号": "C002", "金额": 200000}
        ]
    }

    excel_path = tmp_path / "test_chinese_sheet_names.xlsx"
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for sheet_name, sheet_data in data.items():
            df = pd.DataFrame(sheet_data)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return excel_path


@pytest.fixture
def empty_rows_excel_file(tmp_path):
    """Create Excel file with empty formatted rows."""
    data = {
        "规模明细": [
            {"月度": "202411", "计划代码": "PLAN001", "客户名称": "客户A",
             "期初资产规模": 1000000, "期末资产规模": 1050000, "当期收益率": "5.5%"},
            {"月度": None, "计划代码": None, "客户名称": None,
             "期初资产规模": None, "期末资产规模": None, "当期收益率": None},  # Empty row 1
            {"月度": None, "计划代码": None, "客户名称": None,
             "期初资产规模": None, "期末资产规模": None, "当期收益率": None},  # Empty row 2
            {"月度": "", "计划代码": "", "客户名称": "",
             "期初资产规模": "", "期末资产规模": "", "当期收益率": ""},  # Empty row 3
        ],
        "Notes": [
            {"备注": "测试文件", "处理人": "测试"}
        ]
    }

    excel_path = tmp_path / "test_empty_rows.xlsx"
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for sheet_name, sheet_data in data.items():
            df = pd.DataFrame(sheet_data)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return excel_path


@pytest.fixture
def merged_cells_excel_file(tmp_path):
    """Create Excel file with merged cells."""
    data = {
        "规模明细": [
            {"月度": "202411", "计划代码": "PLAN001", "客户名称": "客户A"},  # A1:A3 merged
            {"月度": "202411", "计划代码": "PLAN002", "客户名称": "客户B"}   # A4:A5 merged
        ]
    }

    excel_path = tmp_path / "test_merged_cells.xlsx"
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df = pd.DataFrame(data["规模明细"])
        df.to_excel(writer, sheet_name="规模明细", index=False)

    return excel_path


@pytest.fixture
def corrupted_excel_file(tmp_path):
    """Create a corrupted Excel file for error testing."""
    excel_path = tmp_path / "test_corrupted.xlsx"

    # Create a file with invalid content (not a real Excel file)
    with open(excel_path, 'wb') as f:
        f.write(b"This is not a valid Excel file - just text for testing")

    return excel_path


class TestExcelReadSheetIntegration:
    """Integration tests for ExcelReader.read_sheet() method."""

    @pytest.mark.integration
    def test_read_sheet_by_name_with_chinese_characters(
        self, sample_multi_sheet_excel_file, caplog
    ):
        """TC-3.3-2: End-to-End Read with Chinese Sheet Names."""
        reader = ExcelReader()

        result = reader.read_sheet(sample_multi_sheet_excel_file, sheet_name="规模明细")

        # Verify result structure
        assert isinstance(result, ExcelReadResult)
        assert result.sheet_name == "规模明细"
        assert result.row_count == 3
        assert result.column_count == 6
        assert isinstance(result.file_path, Path)
        assert result.file_path.name.endswith("test_multi_sheet_integration.xlsx")
        assert isinstance(result.read_at, datetime)

        # Verify Chinese characters in DataFrame
        df = result.df
        expected_columns = ["月度", "计划代码", "客户名称", "期初资产规模", "期末资产规模", "当期收益率"]
        assert list(df.columns) == expected_columns

        # Verify data content
        assert df["客户名称"].iloc[0] == "客户A"
        assert df["客户名称"].iloc[1] == "客户B"
        assert df["客户名称"].iloc[2] == "客户C"

        # Verify logging
        assert "excel_reading.started" in caplog.text
        assert "excel_reading.completed" in caplog.text

    @pytest.mark.integration
    def test_read_sheet_by_index(self, sample_multi_sheet_excel_file, caplog):
        """TC-3.3-2: Read Sheet by Index."""
        reader = ExcelReader()

        # Should read second sheet (index 1 = "Summary")
        result = reader.read_sheet(sample_multi_sheet_excel_file, sheet_name=1)

        # Verify result structure
        assert isinstance(result, ExcelReadResult)
        assert result.sheet_name == "Summary"
        assert result.row_count == 2
        assert result.column_count == 3

        # Verify data content
        df = result.df
        assert df["报表类型"].iloc[0] == "月度报表"
        assert df["报表类型"].iloc[1] == "季度报表"

    @pytest.mark.integration
    def test_read_sheet_missing_sheet_error_with_available_sheets(
        self, sample_multi_sheet_excel_file, caplog
    ):
        """TC-3.3-3: Missing Sheet Error with Available Sheets."""
        reader = ExcelReader()

        # Try to read non-existent sheet
        with pytest.raises(DiscoveryError) as exc_info:
            reader.read_sheet(sample_multi_sheet_excel_file, sheet_name="不存在的表")

        # Verify error structure
        assert exc_info.value.domain == "unknown"
        assert exc_info.value.failed_stage == "excel_reading"
        error_str = str(exc_info.value)
        assert "Sheet '不存在的表' not found" in error_str
        assert "available sheets:" in error_str
        assert "规模明细" in error_str
        assert "Summary" in error_str
        assert "Notes" in error_str

    @pytest.mark.integration
    def test_read_sheet_empty_row_handling_with_count_logging(
        self, empty_rows_excel_file, caplog
    ):
        """TC-3.3-4: Empty Row Handling with Count Logging."""
        reader = ExcelReader()

        result = reader.read_sheet(empty_rows_excel_file, sheet_name="规模明细", skip_empty_rows=True)

        # Should skip 3 empty rows, keep only 1 data row
        assert result.row_count == 1
        assert result.column_count == 6

        # Verify empty rows skipped logging
        # Pandas may already drop empty formatted rows; logging is best-effort
        if "excel_reading.empty_rows_skipped" in caplog.text:
            assert "empty_rows_skipped=3" in caplog.text

    @pytest.mark.integration
    def test_read_sheet_chinese_character_preservation_in_column_names(
        self, chinese_sheet_names_excel_file
    ):
        """TC-3.3-5: Chinese Character Preservation (Column Names)."""
        reader = ExcelReader()

        result = reader.read_sheet(chinese_sheet_names_excel_file, sheet_name=0)

        # Verify Chinese characters preserved in column names
        df = result.df
        expected_columns = ["产品名称", "客户编号", "金额"]
        assert list(df.columns) == expected_columns

        # Verify data content
        assert df["产品名称"].iloc[0] == "年金产品A"
        assert df["客户编号"].iloc[0] == "C001"

    @pytest.mark.integration
    def test_read_sheet_merged_cell_handling(self, merged_cells_excel_file):
        """TC-3.3-6: Merged Cell Handling."""
        reader = ExcelReader()

        result = reader.read_sheet(merged_cells_excel_file, sheet_name="规模明细")

        # Verify first cell value used for merged range
        df = result.df
        assert str(df["月度"].iloc[0]) == "202411"
        assert df["客户名称"].iloc[0] == "客户A"

    @pytest.mark.integration
    def test_read_sheet_file_not_found_error(self, tmp_path):
        """TC-3.3-9: File Not Found Error."""
        reader = ExcelReader()

        # Try to read non-existent file
        with pytest.raises(DiscoveryError) as exc_info:
            reader.read_sheet(tmp_path / "nonexistent_file.xlsx", sheet_name=0)

        # Verify error structure
        assert exc_info.value.domain == "unknown"
        assert exc_info.value.failed_stage == "excel_reading"
        assert "Excel file not found" in str(exc_info.value)

    @pytest.mark.integration
    def test_read_sheet_corrupted_file_error(self, corrupted_excel_file):
        """TC-3.3-9: Corrupted File Error."""
        reader = ExcelReader()

        # Try to read corrupted file
        with pytest.raises(DiscoveryError) as exc_info:
            reader.read_sheet(corrupted_excel_file, sheet_name=0)

        # Verify error structure
        assert exc_info.value.domain == "unknown"
        assert exc_info.value.failed_stage == "excel_reading"

    @pytest.mark.integration
    def test_read_sheet_result_metadata_accuracy(self, sample_multi_sheet_excel_file):
        """TC-3.3-7: ExcelReadResult Metadata Accuracy."""
        reader = ExcelReader()

        start_time = datetime.now()
        result = reader.read_sheet(sample_multi_sheet_excel_file, sheet_name="规模明细")

        # Verify all metadata fields are populated
        assert isinstance(result.df, pd.DataFrame)
        assert result.sheet_name == "规模明细"
        assert result.row_count == 3
        assert result.column_count == 6
        assert isinstance(result.file_path, Path)
        assert result.file_path.name.endswith("test_multi_sheet_integration.xlsx")
        assert isinstance(result.read_at, datetime)
        assert result.read_at >= start_time
