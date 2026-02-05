"""SQL templates for customer MDM operations.

This package contains SQL files for contract sync and related operations.
SQL files are loaded at runtime using pathlib.
"""

from pathlib import Path

SQL_DIR = Path(__file__).parent


def load_sql(filename: str) -> str:
    """Load SQL content from a file in this directory.

    Args:
        filename: Name of the SQL file (e.g., 'close_old_records.sql')

    Returns:
        SQL content as string

    Raises:
        FileNotFoundError: If the SQL file doesn't exist
    """
    sql_path = SQL_DIR / filename
    return sql_path.read_text(encoding="utf-8")
