"""
SQL INSERT statement builders.

Provides high-level builders for constructing INSERT statements
with upsert (INSERT ... ON CONFLICT) support.
"""

from typing import List, Literal, Optional, Protocol


class Dialect(Protocol):
    """Protocol for SQL dialects."""

    name: str

    def quote(self, identifier: str) -> str: ...
    def qualify(self, table: str, schema: Optional[str] = None) -> str: ...
    def build_insert(
        self, table: str, columns: List[str], placeholders: List[str], schema: Optional[str] = None
    ) -> str: ...
    def build_insert_on_conflict_do_nothing(
        self, table: str, columns: List[str], placeholders: List[str], conflict_columns: List[str], schema: Optional[str] = None
    ) -> str: ...
    def build_insert_on_conflict_do_update(
        self, table: str, columns: List[str], placeholders: List[str], conflict_columns: List[str], update_columns: List[str], null_guard: bool = True, schema: Optional[str] = None
    ) -> str: ...


class InsertBuilder:
    """
    High-level builder for INSERT statements.

    Example:
        >>> from work_data_hub.infrastructure.sql import InsertBuilder, PostgreSQLDialect
        >>> builder = InsertBuilder(PostgreSQLDialect())
        >>> sql = builder.insert("mapping", "年金计划", ["年金计划号", "计划全称"], [":col_0", ":col_1"])
        >>> print(sql)
        INSERT INTO mapping."年金计划" ("年金计划号", "计划全称") VALUES (:col_0, :col_1)
    """

    def __init__(self, dialect: Dialect):
        """
        Initialize the InsertBuilder.

        Args:
            dialect: SQL dialect to use for statement generation
        """
        self.dialect = dialect

    def insert(
        self,
        schema: Optional[str],
        table: str,
        columns: List[str],
        placeholders: List[str],
    ) -> str:
        """
        Build a simple INSERT statement.

        Args:
            schema: Schema name (optional)
            table: Table name
            columns: List of column names
            placeholders: List of parameter placeholders

        Returns:
            INSERT SQL statement
        """
        return self.dialect.build_insert(table, columns, placeholders, schema)

    def upsert(
        self,
        schema: Optional[str],
        table: str,
        columns: List[str],
        placeholders: List[str],
        conflict_columns: List[str],
        mode: Literal["do_nothing", "do_update"] = "do_nothing",
        update_columns: Optional[List[str]] = None,
        null_guard: bool = True,
    ) -> str:
        """
        Build an INSERT ... ON CONFLICT (upsert) statement.

        Args:
            schema: Schema name (optional)
            table: Table name
            columns: List of column names to insert
            placeholders: List of parameter placeholders
            conflict_columns: Columns for conflict detection
            mode: "do_nothing" or "do_update"
            update_columns: Columns to update on conflict (required if mode="do_update")
            null_guard: If True, only update if existing value is NULL

        Returns:
            INSERT ... ON CONFLICT SQL statement
        """
        if mode == "do_nothing":
            return self.dialect.build_insert_on_conflict_do_nothing(
                table, columns, placeholders, conflict_columns, schema
            )
        else:
            if not update_columns:
                # Default: update all non-conflict columns
                update_columns = [c for c in columns if c not in conflict_columns]
            return self.dialect.build_insert_on_conflict_do_update(
                table, columns, placeholders, conflict_columns, update_columns, null_guard, schema
            )
