from typing import Optional


def quote_ident(name: str) -> str:
    """
    Quote PostgreSQL identifier with double quotes and escape internal quotes.

    Args:
        name: Identifier to quote (table, column name)

    Returns:
        Properly quoted identifier

    Raises:
        ValueError: If name is empty or contains invalid characters
    """
    if not name or not isinstance(name, str):
        raise ValueError("Identifier name must be non-empty string")

    # Basic validation - identifiers should be reasonable
    if len(name) > 63:  # PostgreSQL limit
        raise ValueError("Identifier too long (max 63 characters)")

    # Escape internal double quotes by doubling them
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def quote_qualified(schema: Optional[str], table: str) -> str:
    """
    Quote PostgreSQL identifier with optional schema qualification.

    Args:
        schema: Optional schema name
        table: Table name (required)

    Returns:
        Qualified identifier: "schema"."table" or "table"

    Raises:
        ValueError: If table is empty or invalid

    Examples:
        >>> quote_qualified("public", "年金计划")
        '"public"."年金计划"'
        >>> quote_qualified(None, "年金计划")
        '"年金计划"'
        >>> quote_qualified("", "年金计划")
        '"年金计划"'
    """
    # Validate required table name (reuse quote_ident validation logic)
    if not table or not isinstance(table, str):
        raise ValueError("Table name must be non-empty string")

    # Handle schema qualification
    if schema and str(schema).strip():
        # Both schema and table need individual quoting
        return f"{quote_ident(str(schema))}.{quote_ident(table)}"
    else:
        # Schema is None/empty - return table only
        return quote_ident(table)


def quote_table(table: str) -> str:
    """
    Quote a table identifier, supporting optional schema qualification.

    Accepts either:
    - "table"
    - "schema.table"

    Returns:
    - '"table"'
    - '"schema"."table"'
    """
    if not table or not isinstance(table, str):
        raise ValueError("Table name must be non-empty string")

    # If already contains quotes, assume pre-quoted by caller and return as-is.
    # (Callers can pass pre-quoted table names like '"schema"."table"' for advanced usage.)
    if '"' in table:
        return table

    if "." in table:
        schema, table_name = table.split(".", 1)
        if schema.strip() and table_name.strip():
            return quote_qualified(schema.strip(), table_name.strip())

    return quote_ident(table)
