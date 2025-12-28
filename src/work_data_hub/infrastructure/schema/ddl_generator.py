"""DDL SQL generation for domain schemas.

Story 7.5: Domain Registry Pre-modularization
Extracted from domain_registry.py for clean separation of SQL generation logic.
"""

from __future__ import annotations

from typing import List

from work_data_hub.infrastructure.sql.core.identifier import (
    qualify_table,
    quote_identifier,
)

from .core import ColumnDef, ColumnType
from .registry import get_domain


def _column_type_to_sql(col: ColumnDef) -> str:
    """Convert a ColumnDef to SQL type definition."""
    if col.column_type == ColumnType.STRING:
        length = col.max_length or 255
        return f"VARCHAR({length})"
    if col.column_type == ColumnType.DATE:
        return "DATE"
    if col.column_type == ColumnType.DATETIME:
        return "TIMESTAMP WITH TIME ZONE"
    if col.column_type == ColumnType.DECIMAL:
        precision = col.precision or 18
        scale = col.scale or 4
        return f"DECIMAL({precision}, {scale})"
    if col.column_type == ColumnType.INTEGER:
        return "INTEGER"
    if col.column_type == ColumnType.BOOLEAN:
        return "BOOLEAN"
    if col.column_type == ColumnType.TEXT:
        return "TEXT"
    return "VARCHAR(255)"


def generate_create_table_ddl(domain_name: str, if_not_exists: bool = False) -> str:
    """Generate just the CREATE TABLE statement."""
    schema = get_domain(domain_name)
    qualified_table = qualify_table(schema.pg_table, schema.pg_schema)
    quoted_pk = quote_identifier(schema.primary_key)

    lines: List[str] = []
    lines.append(f"-- Table: {qualified_table}")

    exists_clause = "IF NOT EXISTS " if if_not_exists else ""
    lines.append(f"CREATE TABLE {exists_clause}{qualified_table} (")
    lines.append(f"  {quoted_pk} INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,")
    lines.append("")
    lines.append("  -- Business columns")
    for col in schema.columns:
        quoted_name = quote_identifier(col.name)
        sql_type = _column_type_to_sql(col)
        nullable_str = "" if col.nullable else " NOT NULL"
        lines.append(f"  {quoted_name} {sql_type}{nullable_str},")
    lines.append("")
    lines.append("  -- Audit columns")
    lines.append('  "created_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,')
    lines.append('  "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP')
    lines.append(");")

    return "\n".join(lines)


def generate_indexes_ddl(domain_name: str) -> List[str]:
    """Generate INDEX creation statements."""
    schema = get_domain(domain_name)
    qualified_table = qualify_table(schema.pg_table, schema.pg_schema)

    sqls: List[str] = []
    if schema.indexes:
        # Note: Do not append standalone comments as they cause "empty query" errors
        # when executed individually
        for idx in schema.indexes:
            cols_str = ", ".join(quote_identifier(c) for c in idx.columns)
            idx_name = idx.name or f"idx_{schema.pg_table}_{'_'.join(idx.columns)}"
            quoted_idx_name = quote_identifier(idx_name)
            unique_str = "UNIQUE " if idx.unique else ""
            method_str = f" USING {idx.method}" if idx.method else ""
            where_str = f" WHERE {idx.where}" if idx.where else ""
            sqls.append(
                f"CREATE {unique_str}INDEX IF NOT EXISTS {quoted_idx_name} "
                f"ON {qualified_table}{method_str} ({cols_str}){where_str};"
            )
    return sqls


def generate_triggers_ddl(domain_name: str) -> List[str]:
    """Generate FUNCTION and TRIGGER statements."""
    schema = get_domain(domain_name)
    qualified_table = qualify_table(schema.pg_table, schema.pg_schema)

    sqls: List[str] = []
    func_name = f"update_{domain_name}_updated_at"

    # Function
    lines = []
    lines.append(f"CREATE OR REPLACE FUNCTION {func_name}()")
    lines.append("RETURNS TRIGGER AS $$")
    lines.append("BEGIN")
    lines.append("    NEW.updated_at = CURRENT_TIMESTAMP;")
    lines.append("    RETURN NEW;")
    lines.append("END;")
    lines.append("$$ LANGUAGE plpgsql;")
    sqls.append("\n".join(lines))

    # Trigger
    trigger_name = f"trigger_{func_name}"
    lines = []
    lines.append(f"CREATE TRIGGER {trigger_name}")
    lines.append(f"    BEFORE UPDATE ON {qualified_table}")
    lines.append("    FOR EACH ROW")
    lines.append(f"    EXECUTE FUNCTION {func_name}();")
    sqls.append("\n".join(lines))

    return sqls


def generate_create_table_sql(domain_name: str) -> str:
    """Generate complete DDL SQL for a domain (backwards compatible)."""
    schema = get_domain(domain_name)
    qualified_table = qualify_table(schema.pg_table, schema.pg_schema)

    parts: List[str] = []
    parts.append(f"-- DDL for domain: {domain_name}")
    parts.append("")
    parts.append(f"DROP TABLE IF EXISTS {qualified_table} CASCADE;")
    parts.append("")
    parts.append(generate_create_table_ddl(domain_name, if_not_exists=False))
    parts.append("")

    indexes = generate_indexes_ddl(domain_name)
    if indexes:
        parts.extend(indexes)
        parts.append("")

    triggers = generate_triggers_ddl(domain_name)
    if triggers:
        parts.append("-- Trigger for updated_at")
        parts.extend(triggers)

    return "\n".join(parts)


__all__ = [
    "generate_create_table_sql",
    "generate_create_table_ddl",
    "generate_indexes_ddl",
    "generate_triggers_ddl",
]
