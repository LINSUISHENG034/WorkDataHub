"""
SQL parameter binding utilities.

Provides functions for creating indexed parameter names to avoid issues
with Chinese column names in psycopg2 parameter binding.
"""

from typing import Dict, List, Tuple, Any


def build_indexed_params(columns: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Build indexed parameter mapping for SQL queries.

    Creates a mapping from column names to indexed parameter names (col_0, col_1, etc.)
    to avoid issues with Chinese or special characters in psycopg2 parameter binding.

    Args:
        columns: List of column names

    Returns:
        Tuple of (column_to_param mapping, list of placeholder strings)

    Examples:
        >>> col_map, placeholders = build_indexed_params(["年金计划号", "计划全称"])
        >>> col_map
        {'年金计划号': 'col_0', '计划全称': 'col_1'}
        >>> placeholders
        [':col_0', ':col_1']
    """
    col_param_map = {col: f"col_{i}" for i, col in enumerate(columns)}
    placeholders = [f":{col_param_map[col]}" for col in columns]
    return col_param_map, placeholders


def remap_records(records: List[Dict[str, Any]], param_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Remap record keys to indexed parameter names.

    Args:
        records: List of record dictionaries with original column names as keys
        param_map: Mapping from column names to parameter names

    Returns:
        List of records with remapped keys

    Examples:
        >>> records = [{"年金计划号": "001", "计划全称": "Test"}]
        >>> param_map = {"年金计划号": "col_0", "计划全称": "col_1"}
        >>> remap_records(records, param_map)
        [{'col_0': '001', 'col_1': 'Test'}]
    """
    remapped = []
    for record in records:
        remapped_record = {
            param_map[k]: v for k, v in record.items() if k in param_map
        }
        remapped.append(remapped_record)
    return remapped
