"""
PostgreSQL-specific SQL dialect implementation.

Provides PostgreSQL-specific SQL syntax for INSERT statements,
conflict handling, and identifier quoting.
"""

from typing import List, Optional

from ..core.identifier import qualify_table, quote_identifier


class PostgreSQLDialect:
    """PostgreSQL SQL dialect implementation."""

    name = "postgresql"

    def quote(self, identifier: str) -> str:
        """Quote an identifier using PostgreSQL syntax (double quotes)."""
        return quote_identifier(identifier, dialect=self.name)

    def qualify(self, table: str, schema: Optional[str] = None) -> str:
        """Create a fully qualified table reference."""
        return qualify_table(table, schema, dialect=self.name)

    def build_insert(
        self,
        table: str,
        columns: List[str],
        placeholders: List[str],
        schema: Optional[str] = None,
    ) -> str:
        """
        Build a simple INSERT statement.

        Args:
            table: Table name
            columns: List of column names
            placeholders: List of parameter placeholders
            schema: Optional schema name

        Returns:
            INSERT SQL statement
        """
        qualified_table = self.qualify(table, schema)
        quoted_cols = ", ".join(self.quote(c) for c in columns)
        values = ", ".join(placeholders)
        return f"INSERT INTO {qualified_table} ({quoted_cols}) VALUES ({values})"

    def build_insert_on_conflict_do_nothing(
        self,
        table: str,
        columns: List[str],
        placeholders: List[str],
        conflict_columns: List[str],
        schema: Optional[str] = None,
    ) -> str:
        """
        Build INSERT ... ON CONFLICT DO NOTHING statement.

        Args:
            table: Table name
            columns: List of column names
            placeholders: List of parameter placeholders
            conflict_columns: Columns for conflict detection (usually primary key)
            schema: Optional schema name

        Returns:
            INSERT ... ON CONFLICT DO NOTHING SQL statement
        """
        base_insert = self.build_insert(table, columns, placeholders, schema)
        conflict_cols = ", ".join(self.quote(c) for c in conflict_columns)
        return f"{base_insert} ON CONFLICT ({conflict_cols}) DO NOTHING"

    def build_insert_on_conflict_do_update(
        self,
        table: str,
        columns: List[str],
        placeholders: List[str],
        conflict_columns: List[str],
        update_columns: List[str],
        null_guard: bool = True,
        schema: Optional[str] = None,
        jsonb_merge_columns: Optional[List[str]] = None,
    ) -> str:
        """
        Build INSERT ... ON CONFLICT DO UPDATE statement.

        Args:
            table: Table name
            columns: List of column names to insert
            placeholders: List of parameter placeholders
            conflict_columns: Columns for conflict detection
            update_columns: Columns to update on conflict
            null_guard: If True, only update if existing value is NULL
            schema: Optional schema name
            jsonb_merge_columns: Columns that should use JSONB array merge

        Returns:
            INSERT ... ON CONFLICT DO UPDATE SQL statement
        """
        qualified_table = self.qualify(table, schema)
        base_insert = self.build_insert(table, columns, placeholders, schema)
        conflict_cols = ", ".join(self.quote(c) for c in conflict_columns)
        jsonb_merge_set = set(jsonb_merge_columns or [])

        update_parts = []
        for col in update_columns:
            quoted_col = self.quote(col)
            if col in jsonb_merge_set:
                # JSONB array merge: append new values, deduplicate
                update_parts.append(
                    f"{quoted_col} = ("
                    f"SELECT jsonb_agg(DISTINCT elem) "
                    f"FROM jsonb_array_elements("
                    f"COALESCE({qualified_table}.{quoted_col}, '[]'::jsonb) || "
                    f"COALESCE(EXCLUDED.{quoted_col}, '[]'::jsonb)"
                    f") AS elem"
                    f")"
                )
            elif null_guard:
                update_parts.append(
                    f"{quoted_col} = CASE WHEN "
                    f"{qualified_table}.{quoted_col} IS NULL "
                    f"THEN EXCLUDED.{quoted_col} "
                    f"ELSE {qualified_table}.{quoted_col} END"
                )
            else:
                update_parts.append(f"{quoted_col} = EXCLUDED.{quoted_col}")

        update_set = ", ".join(update_parts)
        return f"{base_insert} ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}"
