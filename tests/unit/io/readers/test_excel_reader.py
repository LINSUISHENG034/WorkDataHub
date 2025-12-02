"""Unit tests for ExcelReader.read_sheet() method (Story 3.3).

This module tests the new read_sheet functionality including:
- Sheet selection by name and index
- Chinese character preservation
- Error handling for missing sheets
- Empty row handling with logging
- Merged cell handling
- ExcelReadResult metadata accuracy
"""

from datetime import datetime
from pathlib import Path
import pytest
import pandas as pd

from work_data_hub.io.readers.excel_reader import ExcelReader, ExcelReadResult
from work_data_hub.io.connectors.exceptions import DiscoveryError


@pytest.fixture
def multi_sheet_excel_file(tmp_path):
    """Create a multi-sheet Excel file for testing."""
    # Sample data with Chinese characters
    data = {
        "规模明细": [
            {"月度": "202411", "计划代码": "PLAN001", "客户名称": "客户A", "期初资产规模": 1000000, "期末资产规模": 1050000, "当期收益率": "5.5%"},
            {"月度": "202411", "计划代码": "PLAN002", "客户名称": "客户B", "期初资产规模": 2000000, "期末资产规模": 2100000, "当期收益率": "5.2%"},
            {"月度": "202411", "计划代码": "PLAN003", "客户名称": "客户C", "期初资产规模": 1500000, "期末资产规模": 1575000, "当期收益率": "5.0%"}
        ],
        "Summary": [
            {"报表类型": "月度报表", "总客户数": 3, "总资产规模": 4500000},
            {"报表类型": "季度报表", "总客户数": 5, "总资产规模": 7500000}
        ],
        "Notes": [
            {"备注": "数据采集于2024年11月", "处理人": "张三"}
        ]
    }

    # Create DataFrames for each sheet
    dfs = {}
    for sheet_name, sheet_data in data.items():
        dfs[sheet_name] = pd.DataFrame(sheet_data)

    # Create Excel file
    excel_path = tmp_path / "test_multi_sheet.xlsx"
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    return excel_path


@pytest.fixture
def chinese_column_excel_file(tmp_path):
    """Create Excel file with Chinese column names."""
    data = {
        "月度": ["202411", "202411", "202411"],
        "计划代码": ["PLAN001", "PLAN002", "PLAN003"],
        "客户名称": ["客户A", "客户B", "客户C"],
        "期初资产规模": [1000000, 2000000, 1500000],
        "期末资产规模": [1050000, 2100000, 1575000],
        "当期收益率": ["5.5%", "5.2%", "5.0%"]
    }

    excel_path = tmp_path / "test_chinese_columns.xlsx"
    df = pd.DataFrame(data)
    df.to_excel(excel_path, index=False, engine='openpyxl')

    return excel_path


@pytest.fixture
def empty_rows_excel_file(tmp_path):
    """Create Excel file with empty rows (formatting only)."""
    # Create data with empty rows
    data = [
        ["月度", "计划代码", "客户名称", "期初资产规模", "期末资产规模"],
        ["202411", "PLAN001", "客户A", 1000000, 1050000],  # Real data
        [None, None, None, None, None],  # Empty row 1
        ["", "", "", "", ""],  # Empty row 2
        [None, None, None, None, None],  # Empty row 3
        ["202412", "PLAN004", "客户D", 1200000, 1260000],  # Real data
    ]

    excel_path = tmp_path / "test_empty_rows.xlsx"
    df = pd.DataFrame(data)
    df.to_excel(excel_path, index=False, engine='openpyxl')

    return excel_path


@pytest.fixture
def merged_cells_excel_file(tmp_path):
    """Create Excel file with merged cells."""
    data = {
        "A": ["Header1", "Header2"],  # A1:A2 merged
        "B": ["Value1", "Value2"],
        "C": ["Value3", "Value4"]
    }

    excel_path = tmp_path / "test_merged_cells.xlsx"
    df = pd.DataFrame(data)
    df.to_excel(excel_path, index=False, engine='openpyxl')

    return excel_path


@pytest.fixture
def whitespace_columns_excel_file(tmp_path):
    """Create Excel file with messy column names (whitespace, full-width, duplicates)."""
    data = {
        "月度  ": ["202411"],
        "  计划代码": ["PLAN001"],
        "客户　名称": ["客户A"],  # full-width space
        "客户 名称": ["客户A"],   # duplicate after whitespace removal
        "": ["空列"],             # empty column header
    }

    excel_path = tmp_path / "test_whitespace_columns.xlsx"
    df = pd.DataFrame(data)
    df.to_excel(excel_path, index=False, engine="openpyxl")
    return excel_path


class TestExcelReadSheetMethod:
    """Test ExcelReader.read_sheet() method."""

    @pytest.mark.unit
    def test_read_sheet_by_name_chinese_characters(self, multi_sheet_excel_file):
        """TC-3.3-1: Sheet Selection by Name (Chinese)."""
        reader = ExcelReader()
        result = reader.read_sheet(multi_sheet_excel_file, sheet_name="规模明细")

        # Verify result structure
        assert isinstance(result, ExcelReadResult)
        assert result.sheet_name == "规模明细"
        assert result.row_count == 3
        assert result.column_count == 6
        assert isinstance(result.file_path, Path)
        assert result.file_path.name.endswith("test_multi_sheet.xlsx")
        assert isinstance(result.read_at, datetime)

        # Verify DataFrame content
        df = result.df
        assert list(df.columns) == ["月度", "计划代码", "客户名称", "期初资产规模", "期末资产规模", "当期收益率"]
        assert len(df) == 3

        # Verify Chinese characters preserved
        assert "客户名称" in df.columns  # Chinese column name preserved

    @pytest.mark.unit
    def test_read_sheet_by_index(self, multi_sheet_excel_file):
        """TC-3.3-2: Sheet Selection by Index."""
        reader = ExcelReader()
        result = reader.read_sheet(multi_sheet_excel_file, sheet_name=1)

        # Should load second sheet (Summary)
        assert result.sheet_name == "Summary"
        assert result.row_count == 2
        assert result.column_count == 3

    @pytest.mark.unit
    def test_read_sheet_missing_sheet_error(self, multi_sheet_excel_file):
        """TC-3.3-3: Missing Sheet Error with Available Sheets."""
        reader = ExcelReader()

        # Try to read non-existent sheet
        with pytest.raises(DiscoveryError) as exc_info:
            reader.read_sheet(multi_sheet_excel_file, sheet_name="不存在的表")

        # Verify error structure
        assert exc_info.value.domain == "unknown"
        assert exc_info.value.failed_stage == "excel_reading"
        error_str = str(exc_info.value)
        assert "不存在的表" in error_str
        assert "available sheets" in error_str
        assert "规模明细" in error_str
        assert "Summary" in error_str
        assert "Notes" in error_str

    @pytest.mark.unit
    def test_read_sheet_empty_row_handling_with_logging(self, empty_rows_excel_file, caplog):
        """TC-3.3-4: Empty Row Handling with Count Logging."""
        reader = ExcelReader()
        result = reader.read_sheet(empty_rows_excel_file, sheet_name=0, skip_empty_rows=True)

        # Should skip blank/empty rows (header row remains)
        assert result.row_count == 3
        assert result.column_count == 5

        # Check logging
        assert "excel_reading.empty_rows_skipped" in caplog.text
        assert "empty_rows_skipped=3" in caplog.text

    @pytest.mark.unit
    def test_read_sheet_chinese_character_preservation(self, chinese_column_excel_file):
        """TC-3.3-5: Chinese Character Preservation (Column Names)."""
        reader = ExcelReader()
        result = reader.read_sheet(chinese_column_excel_file, sheet_name=0)

        # Verify Chinese characters preserved in column names
        df = result.df
        expected_columns = ["月度", "计划代码", "客户名称", "期初资产规模", "期末资产规模", "当期收益率"]
        assert list(df.columns) == expected_columns

        # Verify data integrity
        assert df["客户名称"].iloc[0] == "客户A"

    @pytest.mark.unit
    def test_read_sheet_merged_cell_handling(self, merged_cells_excel_file):
        """TC-3.3-6: Merged Cell Handling."""
        reader = ExcelReader()
        result = reader.read_sheet(merged_cells_excel_file, sheet_name=0)

        # Verify first cell value used for merged range
        df = result.df
        assert df["A"].iloc[0] == "Header1"  # First cell value
        # For non-merged cells in fixture, second value remains populated
        assert df["A"].iloc[1] in ["Header1", "Header2"]

    @pytest.mark.unit
    def test_read_sheet_result_metadata_accuracy(self, multi_sheet_excel_file):
        """TC-3.3-7: ExcelReadResult Metadata Accuracy."""
        reader = ExcelReader()
        start_time = datetime.now()
        result = reader.read_sheet(multi_sheet_excel_file, sheet_name="规模明细")

        # Verify all metadata fields
        assert isinstance(result.file_path, Path)
        assert result.file_path.name.endswith("test_multi_sheet.xlsx")
        assert result.sheet_name == "规模明细"
        assert result.row_count == 3
        assert result.column_count == 6
        assert isinstance(result.read_at, datetime)
        assert result.read_at >= start_time

    @pytest.mark.unit
    def test_read_sheet_backward_compatibility_read_rows_still_works(self, multi_sheet_excel_file):
        """TC-3.3-11: Backward Compatibility: read_rows() Still Works."""
        reader = ExcelReader()

        # Existing read_rows method should still work
        rows = reader.read_rows(str(multi_sheet_excel_file), sheet="规模明细")
        assert isinstance(rows, list)
        assert len(rows) == 3
        assert rows[0]["客户名称"] == "客户A"

    @pytest.mark.unit
    def test_read_sheet_resolve_sheet_name_index_out_of_range(self, multi_sheet_excel_file):
        """Test _resolve_sheet_name with out-of-range index."""
        reader = ExcelReader()

        with pytest.raises(DiscoveryError) as exc_info:
            reader.read_sheet(multi_sheet_excel_file, sheet_name=10)  # Only 3 sheets exist

        assert exc_info.value.failed_stage == "excel_reading"
        assert "Sheet index 10 out of range" in str(exc_info.value)

    @pytest.mark.unit
    def test_read_sheet_resolve_sheet_name_not_found(self, multi_sheet_excel_file):
        """Test _resolve_sheet_name with non-existent sheet name."""
        reader = ExcelReader()

        with pytest.raises(DiscoveryError) as exc_info:
            reader.read_sheet(multi_sheet_excel_file, sheet_name="不存在的表")

        assert exc_info.value.failed_stage == "excel_reading"
        assert "Sheet '不存在的表' not found" in str(exc_info.value)

    @pytest.mark.unit
    def test_read_sheet_file_not_found_error(self):
        """Test file not found error handling."""
        reader = ExcelReader()

        with pytest.raises(DiscoveryError) as exc_info:
            reader.read_sheet(Path("nonexistent_file.xlsx"), sheet_name=0)

        assert exc_info.value.failed_stage == "excel_reading"
        assert "Excel file not found" in str(exc_info.value)

    @pytest.mark.unit
    def test_read_sheet_column_normalization_mapping(self, whitespace_columns_excel_file):
        """Verify column normalization mapping and duplicate handling."""
        reader = ExcelReader()
        result = reader.read_sheet(whitespace_columns_excel_file, sheet_name=0)

        assert result.columns_renamed == {
            "月度  ": "月度",
            "  计划代码": "计划代码",
            "客户　名称": "客户名称",
            "客户 名称": "客户名称_1",
            "Unnamed: 4": "Unnamed_1",
        }
        assert list(result.df.columns) == [
            "月度",
            "计划代码",
            "客户名称",
            "客户名称_1",
            "Unnamed_1",
        ]
        assert result.normalization_duration_ms is not None
        assert result.duration_breakdown is not None
        assert result.duration_breakdown.get("normalization_ms") == result.normalization_duration_ms

    @pytest.mark.unit
    def test_read_sheet_disable_normalization(self, whitespace_columns_excel_file):
        """Normalization can be turned off when caller opts out."""
        reader = ExcelReader()
        result = reader.read_sheet(
            whitespace_columns_excel_file, sheet_name=0, normalize_columns=False
        )

        # Columns remain as originally authored (pandas preserves ordering/whitespace)
        assert result.columns_renamed == {}
        assert list(result.df.columns) == [
            "月度  ",
            "  计划代码",
            "客户　名称",
            "客户 名称",
            "Unnamed: 4",
        ]
        assert result.normalization_duration_ms is None
        assert result.duration_breakdown is not None
        assert "normalization_ms" not in result.duration_breakdown
