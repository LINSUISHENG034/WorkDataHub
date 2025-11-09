"""
Excel file reading infrastructure for WorkDataHub.

This module provides robust, error-resilient Excel file reading capabilities
using pandas as the underlying engine. It handles common Excel reading issues
like missing sheets, corrupted files, and encoding problems.
"""

import logging
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from work_data_hub.utils.column_normalizer import normalize_columns

logger = logging.getLogger(__name__)


class ExcelReadError(Exception):
    """Raised when Excel file reading fails."""

    pass


class ExcelReader:
    """
    Robust Excel file reader with comprehensive error handling.

    This class wraps pandas Excel reading functionality with additional
    error handling, validation, and standardization features needed for
    reliable data processing pipelines.
    """

    def __init__(self, max_rows: Optional[int] = None):
        """
        Initialize Excel reader.

        Args:
            max_rows: Maximum number of rows to read (None = no limit)
        """
        self.max_rows = max_rows

    def read_rows(
        self,
        file_path: str,
        sheet: Union[str, int] = 0,
        header: Union[int, List[int], None] = 0,
        skip_rows: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read Excel file and return rows as list of dictionaries.

        This is the primary interface for reading Excel data. It handles
        common Excel file issues and returns clean, consistent data structures.

        Args:
            file_path: Path to the Excel file to read
            sheet: Sheet name (str) or index (int) to read from
            header: Row(s) to use as column headers (0-indexed)
            skip_rows: Number of rows to skip at the beginning

        Returns:
            List of dictionaries, where each dict represents a row with
            column names as keys and cell values as values

        Raises:
            ExcelReadError: If file cannot be read or processed
            FileNotFoundError: If file does not exist
        """
        file_path_obj = Path(file_path)

        # Validate file exists
        if not file_path_obj.exists():
            raise FileNotFoundError(f"Excel file not found: {file_path}")

        # Validate file is not empty
        if file_path_obj.stat().st_size == 0:
            raise ExcelReadError(f"Excel file is empty: {file_path}")

        try:
            logger.info(f"Reading Excel file: {file_path} (sheet: {sheet})")

            # Configure pandas read parameters
            read_kwargs: dict[str, Any] = {
                "sheet_name": sheet,
                "engine": "openpyxl",  # Explicitly use openpyxl for .xlsx files
                "header": header,
            }

            if skip_rows is not None:
                read_kwargs["skiprows"] = skip_rows

            if self.max_rows is not None:
                read_kwargs["nrows"] = self.max_rows

            # Read Excel file
            df = pd.read_excel(file_path, **read_kwargs)

            logger.info(f"Successfully read {len(df)} rows from {file_path}")

            # Convert to list of dictionaries
            rows = self._dataframe_to_rows(df)

            return rows

        except FileNotFoundError:
            raise
        except zipfile.BadZipFile:
            raise ExcelReadError(
                f"Failed to parse Excel file {file_path}: corrupted or invalid format"
            )
        except pd.errors.EmptyDataError:
            logger.warning(f"Excel file contains no data: {file_path}")
            return []
        except pd.errors.ParserError as e:
            raise ExcelReadError(f"Failed to parse Excel file {file_path}: {e}")
        except ValueError as e:
            # Handle sheet not found or invalid index/name consistently
            msg = str(e)
            sheet_err_signals = (
                "Worksheet",
                "does not exist",
                "is not a valid worksheet name",
                "is invalid",
                "worksheets less than",
                "out of range",
            )
            if any(s in msg for s in sheet_err_signals):
                raise ExcelReadError(f"Sheet '{sheet}' not found in {file_path}")
            raise ExcelReadError(
                f"Invalid Excel file or parameters for {file_path}: {e}"
            )
        except Exception as e:
            # Catch-all for other Excel reading issues, including openpyxl-related
            error_msg = str(e)
            if "openpyxl" in error_msg:
                raise ExcelReadError(f"Failed to parse Excel file {file_path}: {e}")
            raise ExcelReadError(
                f"Unexpected error reading Excel file {file_path}: {e}"
            )

    def get_sheet_names(self, file_path: str) -> List[Union[str, int]]:
        """
        Get list of sheet names from Excel file.

        Args:
            file_path: Path to the Excel file

        Returns:
            List of sheet names in the Excel file

        Raises:
            ExcelReadError: If file cannot be read
            FileNotFoundError: If file does not exist
        """
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise FileNotFoundError(f"Excel file not found: {file_path}")

        try:
            excel_file = pd.ExcelFile(file_path, engine="openpyxl")
            return excel_file.sheet_names
        except Exception as e:
            raise ExcelReadError(f"Cannot read sheet names from {file_path}: {e}")

    def validate_file(self, file_path: str, sheet: Union[str, int] = 0) -> bool:
        """
        Validate that an Excel file can be read successfully.

        Args:
            file_path: Path to the Excel file
            sheet: Sheet to validate

        Returns:
            True if file can be read, False otherwise
        """
        try:
            # Try to read just the header to validate
            reader = ExcelReader(max_rows=1)
            reader.read_rows(file_path, sheet=sheet)
            return True
        except (ExcelReadError, FileNotFoundError):
            return False

    def _dataframe_to_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Convert pandas DataFrame to list of dictionaries with data cleaning.

        Args:
            df: Pandas DataFrame to convert

        Returns:
            List of dictionaries representing the DataFrame rows
        """
        # Clean column names (remove leading/trailing whitespace and handle
        # unnamed columns)
        cleaned_columns = []
        for col in df.columns:
            col_str = str(col).strip() if col is not None else ""
            # Remove newlines and tabs from header names
            col_str = col_str.replace("\n", "").replace("\t", "")
            # Convert "Unnamed: n" columns to empty strings
            if re.match(r"^Unnamed:\s*\d+", col_str):
                cleaned_columns.append("")
            else:
                cleaned_columns.append(col_str)

        # Apply column name standardization
        column_mapping = normalize_columns(cleaned_columns)
        standardized_columns = [column_mapping.get(col, col) for col in cleaned_columns]

        df.columns = standardized_columns

        # Log column standardization if any changes were made
        changed_mappings = {k: v for k, v in column_mapping.items() if k != v}
        if changed_mappings:
            logger.info(
                "Applied column name standardization: %s columns normalized",
                len(changed_mappings),
            )
            for original, normalized in changed_mappings.items():
                logger.debug("  '%s' -> '%s'", original, normalized)

        # Ensure year/month columns remain as strings
        year_month_columns = ["年", "月", "year", "month"]
        for col in year_month_columns:
            if col in df.columns:
                df[col] = df[col].astype(str)

        # Convert to list of dictionaries
        rows = df.to_dict(orient="records")

        # Clean values in each row
        cleaned_rows = []
        for row in rows:
            cleaned_row: dict[str, Any] = {}
            for key, value in row.items():
                # Ensure key is a string
                str_key = str(key)
                # Handle pandas NaN values
                if pd.isna(value):
                    cleaned_row[str_key] = None
                # Convert numpy types to native Python types
                elif hasattr(value, "item"):
                    cleaned_row[str_key] = value.item()
                # Strip whitespace from string values
                elif isinstance(value, str):
                    cleaned_row[str_key] = value.strip()
                else:
                    cleaned_row[str_key] = value

            cleaned_rows.append(cleaned_row)

        return cleaned_rows


def read_excel_rows(
    file_path: str, sheet: Union[str, int] = 0, max_rows: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Convenience function for reading Excel rows with default settings.

    This is a simplified interface for the most common use case of reading
    all rows from an Excel sheet as a list of dictionaries.

    Args:
        file_path: Path to the Excel file
        sheet: Sheet name or index to read
        max_rows: Maximum number of rows to read (None = no limit)

    Returns:
        List of dictionaries representing Excel rows

    Raises:
        ExcelReadError: If file cannot be read
        FileNotFoundError: If file does not exist
    """
    reader = ExcelReader(max_rows=max_rows)
    return reader.read_rows(file_path, sheet=sheet)
