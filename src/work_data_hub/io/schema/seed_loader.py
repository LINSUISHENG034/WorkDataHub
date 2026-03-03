"""Seed data loader for loading CSV seed data into the database.

This module provides a unified interface for loading seed data from
CSV files into the database.

Usage in migration scripts:
    from work_data_hub.io.schema.seed_loader import load_seed_data

    # Automatically detects format and loads data
    count = load_seed_data(conn, "base_info", "enterprise", seeds_base_dir)
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa

from .seed_resolver import resolve_seed_file

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection


def _normalize_value(value: str) -> str | None:
    """Normalize CSV value by stripping whitespace and newlines."""
    if value is None:
        return None
    cleaned = value.strip().replace("\r\n", "").replace("\n", "").replace("\r", "")
    return cleaned if cleaned else None


def _load_csv_seed_data(
    conn: Connection,
    csv_path: Path,
    table_name: str,
    schema: str,
    exclude_columns: Optional[list[str]] = None,
) -> int:
    """Load seed data from CSV file into table.

    Args:
        conn: SQLAlchemy connection
        csv_path: Path to CSV file
        table_name: Target table name
        schema: Target schema name
        exclude_columns: Columns to exclude (e.g., ['id', 'created_at'])

    Returns:
        Number of rows inserted
    """
    exclude_columns = exclude_columns or []

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return 0

    # Filter columns
    columns = [c for c in rows[0].keys() if c not in exclude_columns]
    columns_str = ", ".join(f'"{col}"' for col in columns)
    placeholders_str = ", ".join(f":param_{i}" for i in range(len(columns)))

    insert_sql = f"""
        INSERT INTO {schema}."{table_name}" ({columns_str})
        VALUES ({placeholders_str})
        ON CONFLICT DO NOTHING
    """

    inserted = 0
    for row in rows:
        params = {
            f"param_{i}": _normalize_value(row[col]) for i, col in enumerate(columns)
        }
        if all(v is None for v in params.values()):
            continue
        conn.execute(sa.text(insert_sql), params)
        inserted += 1

    return inserted


def load_seed_data(  # noqa: PLR0913
    conn: Connection,
    table_name: str,
    schema: str,
    seeds_base_dir: Path,
    exclude_columns: Optional[list[str]] = None,
    version: Optional[str] = None,
) -> int:
    """Load seed data for a table from CSV.

    Args:
        conn: SQLAlchemy connection
        table_name: Target table name
        schema: Target schema name
        seeds_base_dir: Path to seeds base directory
        exclude_columns: Columns to exclude
        version: Optional explicit version override

    Returns:
        Number of rows loaded

    Raises:
        FileNotFoundError: If no seed CSV found
    """
    seed_info = resolve_seed_file(table_name, seeds_base_dir, version)

    if seed_info is None or not seed_info.exists:
        raise FileNotFoundError(f"No seed CSV found for {table_name}")

    return _load_csv_seed_data(
        conn, seed_info.path, table_name, schema, exclude_columns
    )
