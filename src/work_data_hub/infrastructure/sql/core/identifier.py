"""
SQL identifier handling utilities.

Provides functions for proper quoting and qualification of SQL identifiers
(table names, column names) to support Chinese characters and prevent
SQL injection.
"""

from typing import Optional


def quote_identifier(name: str, dialect: str = "postgresql") -> str:
    """
    Quote a SQL identifier (table or column name).

    Args:
        name: The identifier to quote
        dialect: Database dialect ("postgresql", "mysql")

    Returns:
        Properly quoted identifier

    Examples:
        >>> quote_identifier("年金计划号")
        '"年金计划号"'
        >>> quote_identifier("company_id")
        '"company_id"'
        >>> quote_identifier("table", dialect="mysql")
        '`table`'
    """
    if dialect == "mysql":
        # Escape backticks in MySQL
        escaped = name.replace("`", "``")
        return f"`{escaped}`"
    else:
        # PostgreSQL uses double quotes
        # Escape internal double quotes by doubling them
        escaped = name.replace('"', '""')
        return f'"{escaped}"'


def qualify_table(
    table: str, schema: Optional[str] = None, dialect: str = "postgresql"
) -> str:
    """
    Create a fully qualified table name with optional schema prefix.

    Args:
        table: Table name
        schema: Optional schema name
        dialect: Database dialect

    Returns:
        Qualified table name

    Examples:
        >>> qualify_table("年金计划", schema="mapping")
        'mapping."年金计划"'
        >>> qualify_table("users")
        '"users"'
        >>> qualify_table("users", schema="public")
        'public."users"'
    """
    quoted_table = quote_identifier(table, dialect)
    if schema:
        return f"{schema}.{quoted_table}"
    return quoted_table
