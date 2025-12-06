"""
Tests for Excel reader infrastructure.

This module tests the ExcelReader class and related functions with various
Excel file scenarios and error conditions.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from src.work_data_hub.io.readers.excel_reader import (
    ExcelReader,
    ExcelReadError,
    read_excel_rows,
)


@pytest.fixture
def sample_excel_data():
    """Sample Excel data for testing."""
    return pd.DataFrame(
        {
            "年": ["2024", "2024", "2023"],
            "月": ["11", "10", "12"],
            "计划代码": ["PLAN001", "PLAN002", "PLAN003"],
            "收益率": ["5.5%", "3.2%", "4.1%"],
            "净值": [1.055, 1.032, 1.041],
        }
    )


@pytest.fixture
def temp_excel_file(tmp_path, sample_excel_data):
    """Create a temporary Excel file for testing."""
    file_path = tmp_path / "test_file.xlsx"
    sample_excel_data.to_excel(file_path, index=False, engine="openpyxl")
    return str(file_path)


@pytest.fixture
def empty_excel_file(tmp_path):
    """Create an empty Excel file for testing."""
    file_path = tmp_path / "empty_file.xlsx"
    empty_df = pd.DataFrame()
    empty_df.to_excel(file_path, index=False, engine="openpyxl")
    return str(file_path)


@pytest.fixture
def multi_sheet_file(tmp_path, sample_excel_data):
    """Create Excel file with multiple sheets."""
    file_path = tmp_path / "multi_sheet.xlsx"

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        sample_excel_data.to_excel(writer, sheet_name="Sheet1", index=False)
        sample_excel_data.to_excel(writer, sheet_name="Data", index=False)

    return str(file_path)


class TestExcelReader:
    """Test ExcelReader class functionality."""

    def test_init_default(self):
        """Test ExcelReader initialization with defaults."""
        reader = ExcelReader()
        assert reader.max_rows is None

    def test_init_with_max_rows(self):
        """Test ExcelReader initialization with max_rows parameter."""
        reader = ExcelReader(max_rows=100)
        assert reader.max_rows == 100

    def test_read_rows_success(self, temp_excel_file):
        """Test successful reading of Excel rows."""
        reader = ExcelReader()
        rows = reader.read_rows(temp_excel_file)

        assert len(rows) == 3
        assert isinstance(rows, list)
        assert all(isinstance(row, dict) for row in rows)

        # Check first row content
        first_row = rows[0]
        assert first_row["年"] == "2024"
        assert first_row["月"] == "11"
        assert first_row["计划代码"] == "PLAN001"
        assert first_row["收益率"] == "5.5%"

    def test_read_rows_with_max_rows(self, temp_excel_file):
        """Test reading with max_rows limit."""
        reader = ExcelReader(max_rows=2)
        rows = reader.read_rows(temp_excel_file)

        assert len(rows) == 2  # Limited by max_rows

    def test_read_rows_specific_sheet_by_index(self, multi_sheet_file):
        """Test reading from specific sheet by index."""
        reader = ExcelReader()
        rows = reader.read_rows(multi_sheet_file, sheet=1)  # Second sheet

        assert len(rows) == 3
        assert isinstance(rows[0], dict)

    def test_read_rows_specific_sheet_by_name(self, multi_sheet_file):
        """Test reading from specific sheet by name."""
        reader = ExcelReader()
        rows = reader.read_rows(multi_sheet_file, sheet="Data")

        assert len(rows) == 3
        assert isinstance(rows[0], dict)

    def test_read_rows_nonexistent_file(self):
        """Test reading from non-existent file."""
        reader = ExcelReader()

        with pytest.raises(FileNotFoundError):
            reader.read_rows("/nonexistent/file.xlsx")

    def test_read_rows_empty_file(self, tmp_path):
        """Test reading completely empty file."""
        empty_file = tmp_path / "empty.xlsx"
        empty_file.write_text("")  # Completely empty

        reader = ExcelReader()

        with pytest.raises(ExcelReadError, match="Excel file is empty"):
            reader.read_rows(str(empty_file))

    def test_read_rows_invalid_sheet_name(self, temp_excel_file):
        """Test reading from non-existent sheet name."""
        reader = ExcelReader()

        with pytest.raises(ExcelReadError, match="Sheet.*not found"):
            reader.read_rows(temp_excel_file, sheet="NonExistentSheet")

    def test_read_rows_invalid_sheet_index(self, temp_excel_file):
        """Test reading from invalid sheet index."""
        reader = ExcelReader()

        with pytest.raises(ExcelReadError, match="Sheet.*not found"):
            reader.read_rows(temp_excel_file, sheet=99)  # Invalid index

    def test_read_rows_corrupted_file(self, tmp_path):
        """Test reading corrupted Excel file."""
        bad_file = tmp_path / "corrupted.xlsx"
        bad_file.write_text("This is not an Excel file")

        reader = ExcelReader()

        with pytest.raises(ExcelReadError, match="Failed to parse Excel file"):
            reader.read_rows(str(bad_file))

    def test_read_rows_empty_dataframe(self, empty_excel_file):
        """Test reading Excel file with empty dataframe."""
        reader = ExcelReader()
        rows = reader.read_rows(empty_excel_file)

        assert rows == []  # Should return empty list

    def test_read_rows_with_header_parameter(self, temp_excel_file):
        """Test reading with custom header parameter."""
        reader = ExcelReader()

        # Read without headers (header=None)
        rows = reader.read_rows(temp_excel_file, header=None)

        assert len(rows) == 4  # 3 data rows + 1 header row

        # First row should now contain the original headers as values
        first_row = rows[0]
        assert "0" in first_row  # Columns will be numbered when header=None

    def test_read_rows_with_skip_rows(self, temp_excel_file):
        """Test reading with skip_rows parameter."""
        reader = ExcelReader()
        rows = reader.read_rows(temp_excel_file, skip_rows=1)

        # Should skip first data row, so we get 2 rows instead of 3
        assert len(rows) == 2

    def test_get_sheet_names_success(self, multi_sheet_file):
        """Test getting sheet names from Excel file."""
        reader = ExcelReader()
        sheet_names = reader.get_sheet_names(multi_sheet_file)

        assert isinstance(sheet_names, list)
        assert "Sheet1" in sheet_names
        assert "Data" in sheet_names
        assert len(sheet_names) == 2

    def test_get_sheet_names_nonexistent_file(self):
        """Test getting sheet names from non-existent file."""
        reader = ExcelReader()

        with pytest.raises(FileNotFoundError):
            reader.get_sheet_names("/nonexistent/file.xlsx")

    def test_get_sheet_names_invalid_file(self, tmp_path):
        """Test getting sheet names from invalid file."""
        bad_file = tmp_path / "not_excel.xlsx"
        bad_file.write_text("not an excel file")

        reader = ExcelReader()

        with pytest.raises(ExcelReadError, match="Cannot read sheet names"):
            reader.get_sheet_names(str(bad_file))

    def test_validate_file_success(self, temp_excel_file):
        """Test file validation with valid file."""
        reader = ExcelReader()

        is_valid = reader.validate_file(temp_excel_file)

        assert is_valid is True

    def test_validate_file_nonexistent(self):
        """Test file validation with non-existent file."""
        reader = ExcelReader()

        is_valid = reader.validate_file("/nonexistent/file.xlsx")

        assert is_valid is False

    def test_validate_file_invalid(self, tmp_path):
        """Test file validation with invalid file."""
        bad_file = tmp_path / "invalid.xlsx"
        bad_file.write_text("not excel")

        reader = ExcelReader()

        is_valid = reader.validate_file(str(bad_file))

        assert is_valid is False

    def test_dataframe_to_rows_with_nan_values(self, tmp_path):
        """Test conversion of DataFrame with NaN values."""
        # Create DataFrame with NaN values
        df_with_nan = pd.DataFrame(
            {
                "col1": ["value1", None, "value3"],
                "col2": [1.5, float("nan"), 3.0],
                "col3": ["text", "", "more text"],
            }
        )

        # Save to Excel and read back
        file_path = tmp_path / "with_nan.xlsx"
        df_with_nan.to_excel(file_path, index=False, engine="openpyxl")

        reader = ExcelReader()
        rows = reader.read_rows(str(file_path))

        assert len(rows) == 3

        # Check that NaN values are converted to None
        assert rows[1]["col1"] is None  # Was None originally
        assert rows[1]["col2"] is None  # Was NaN originally

    def test_dataframe_to_rows_string_cleaning(self, tmp_path):
        """Test that string values are properly cleaned."""
        df_with_spaces = pd.DataFrame(
            {
                "field1": ["  value with spaces  ", "normal", "  leading"],
                "field2": [123, 456, 789],
            }
        )

        file_path = tmp_path / "with_spaces.xlsx"
        df_with_spaces.to_excel(file_path, index=False, engine="openpyxl")

        reader = ExcelReader()
        rows = reader.read_rows(str(file_path))

        # Check that string values are stripped
        assert rows[0]["field1"] == "value with spaces"  # Leading/trailing stripped
        assert rows[2]["field1"] == "leading"  # Leading space stripped

    def test_dataframe_to_rows_column_name_cleaning(self, tmp_path):
        """Test that column names are properly cleaned."""
        df_messy_columns = pd.DataFrame(
            {
                "  Column 1  ": ["value1"],
                None: ["value2"],  # None column name
                "": ["value3"],  # Empty column name
            }
        )

        file_path = tmp_path / "messy_columns.xlsx"
        df_messy_columns.to_excel(file_path, index=False, engine="openpyxl")

        reader = ExcelReader()
        rows = reader.read_rows(str(file_path))

        # Check that column names are cleaned
        row = rows[0]
        # New behavior: column normalizer removes all whitespace including internal spaces
        assert "Column1" in row  # All spaces removed from column name
        # Empty column names get placeholder names like "Unnamed_N"
        assert any(k.startswith("Unnamed_") for k in row.keys())

    def test_header_normalization_removes_newlines_and_tabs(self, tmp_path):
        """Test Excel header normalization for newlines and tabs."""
        import pandas as pd

        # Create DataFrame with problematic headers
        df_bad_headers = pd.DataFrame(
            {
                "正常列名": ["value1"],
                "包含\n换行符": ["value2"],
                "包含\t制表符": ["value3"],
                "包含\n\t两者": ["value4"],
                "多行\n\n\n标题": ["value5"],
                "\t\t前置制表符": ["value6"],
                "末尾换行\n": ["value7"],
            }
        )

        file_path = tmp_path / "bad_headers.xlsx"
        df_bad_headers.to_excel(file_path, index=False, engine="openpyxl")

        reader = ExcelReader()
        rows = reader.read_rows(str(file_path))

        # Verify headers are cleaned
        first_row = rows[0]
        assert "正常列名" in first_row, "正常列名应该保持不变"
        assert "包含换行符" in first_row, "\\n 应该被移除"
        assert "包含制表符" in first_row, "\\t 应该被移除"
        assert "包含两者" in first_row, "\\n\\t 都应该被移除"
        assert "多行标题" in first_row, "多个\\n应该被移除"
        assert "前置制表符" in first_row, "前置\\t应该被移除"
        assert "末尾换行" in first_row, "末尾\\n应该被移除"

        # Verify values are still accessible with cleaned headers
        assert first_row["正常列名"] == "value1"
        assert first_row["包含换行符"] == "value2"
        assert first_row["包含制表符"] == "value3"
        assert first_row["包含两者"] == "value4"
        assert first_row["多行标题"] == "value5"
        assert first_row["前置制表符"] == "value6"
        assert first_row["末尾换行"] == "value7"


class TestConvenienceFunction:
    """Test the convenience read_excel_rows function."""

    def test_read_excel_rows_default_parameters(self, temp_excel_file):
        """Test convenience function with default parameters."""
        rows = read_excel_rows(temp_excel_file)

        assert len(rows) == 3
        assert isinstance(rows[0], dict)

    def test_read_excel_rows_with_max_rows(self, temp_excel_file):
        """Test convenience function with max_rows parameter."""
        rows = read_excel_rows(temp_excel_file, max_rows=1)

        assert len(rows) == 1

    def test_read_excel_rows_with_sheet_name(self, multi_sheet_file):
        """Test convenience function with sheet name parameter."""
        rows = read_excel_rows(multi_sheet_file, sheet="Data")

        assert len(rows) == 3

    def test_read_excel_rows_error_handling(self):
        """Test convenience function error handling."""
        with pytest.raises(FileNotFoundError):
            read_excel_rows("/nonexistent/file.xlsx")


class TestErrorHandling:
    """Test various error scenarios and edge cases."""

    @patch("pandas.read_excel")
    def test_pandas_parser_error(self, mock_read_excel, tmp_path):
        """Test handling of pandas parser errors."""
        # Create a file that exists
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("dummy")

        # Mock pandas to raise a parser error
        mock_read_excel.side_effect = pd.errors.ParserError("Parsing failed")

        reader = ExcelReader()

        with pytest.raises(ExcelReadError, match="Failed to parse Excel file"):
            reader.read_rows(str(test_file))

    @patch("pandas.read_excel")
    def test_pandas_empty_data_error(self, mock_read_excel, tmp_path):
        """Test handling of empty data error."""
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("dummy")

        mock_read_excel.side_effect = pd.errors.EmptyDataError("No data")

        reader = ExcelReader()
        rows = reader.read_rows(str(test_file))

        assert rows == []  # Should return empty list for empty data

    @patch("pandas.read_excel")
    def test_generic_exception_handling(self, mock_read_excel, tmp_path):
        """Test handling of generic exceptions."""
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("dummy")

        mock_read_excel.side_effect = Exception("Unexpected error")

        reader = ExcelReader()

        with pytest.raises(ExcelReadError, match="Unexpected error reading Excel file"):
            reader.read_rows(str(test_file))
