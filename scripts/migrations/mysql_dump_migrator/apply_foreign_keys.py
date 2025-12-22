#!/usr/bin/env python
"""
Apply foreign keys after data-only migration.

Reads MySQL dump, extracts FOREIGN KEY definitions for selected databases,
and applies them to PostgreSQL tables created by the main migrator.

Notes:
- Uses NOT VALID to create constraints without blocking, then VALIDATE to catch bad data.
- Logs failures per constraint for follow-up fixes.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import List, Optional

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Local imports
from scripts.migrations.mysql_dump_migrator.migrator import MigrationConfig
from scripts.migrations.mysql_dump_migrator.parser import MySQLDumpParser

logger = structlog.get_logger(__name__)


FK_PATTERN_NAMED = re.compile(
    r"CONSTRAINT\s+`?([^`\s]+)`?\s+FOREIGN KEY\s*\(([^)]+)\)\s+REFERENCES\s+`?([^`\s]+)`?\s*\(([^)]+)\)(?:\s+ON\s+DELETE\s+(\w+))?(?:\s+ON\s+UPDATE\s+(\w+))?",
    re.IGNORECASE,
)

FK_PATTERN_ANON = re.compile(
    r"FOREIGN KEY\s*\(([^)]+)\)\s+REFERENCES\s+`?([^`\s]+)`?\s*\(([^)]+)\)(?:\s+ON\s+DELETE\s+(\w+))?(?:\s+ON\s+UPDATE\s+(\w+))?",
    re.IGNORECASE,
)


@dataclass
class ForeignKeyDef:
    constraint_name: str
    table: str
    columns: List[str]
    ref_table: str
    ref_columns: List[str]
    on_delete: Optional[str] = None
    on_update: Optional[str] = None


def _clean_cols(raw: str) -> List[str]:
    cols = []
    for part in raw.split(","):
        col = part.strip().strip("`").strip('"')
        if col:
            cols.append(col)
    return cols


def extract_foreign_keys(create_sql: str, table: str) -> List[ForeignKeyDef]:
    """Extract FK definitions from a CREATE TABLE statement."""
    fks: List[ForeignKeyDef] = []
    seen = 0

    for match in FK_PATTERN_NAMED.finditer(create_sql):
        name = match.group(1)
        cols = _clean_cols(match.group(2))
        ref_table = match.group(3)
        ref_cols = _clean_cols(match.group(4))
        on_delete = match.group(5)
        on_update = match.group(6)
        fks.append(
            ForeignKeyDef(
                constraint_name=name,
                table=table,
                columns=cols,
                ref_table=ref_table,
                ref_columns=ref_cols,
                on_delete=on_delete,
                on_update=on_update,
            )
        )
        seen += 1

    # Anonymous foreign keys: generate a name
    for match in FK_PATTERN_ANON.finditer(create_sql):
        cols = _clean_cols(match.group(1))
        ref_table = match.group(2)
        ref_cols = _clean_cols(match.group(3))
        on_delete = match.group(4)
        on_update = match.group(5)
        seen += 1
        name = f"fk_{table}_{seen}"
        fks.append(
            ForeignKeyDef(
                constraint_name=name,
                table=table,
                columns=cols,
                ref_table=ref_table,
                ref_columns=ref_cols,
                on_delete=on_delete,
                on_update=on_update,
            )
        )

    return fks


def fk_exists(engine: Engine, schema: str, table: str, constraint: str) -> bool:
    query = text(
        """
        select 1
        from pg_constraint c
        join pg_class t on t.oid = c.conrelid
        join pg_namespace n on n.oid = c.connamespace
        where n.nspname = :schema and t.relname = :table and c.conname = :constraint
        """
    )
    with engine.connect() as conn:
        res = conn.execute(
            query, {"schema": schema, "table": table, "constraint": constraint}
        ).first()
    return res is not None


def apply_fk(engine: Engine, schema: str, fk: ForeignKeyDef, validate: bool) -> None:
    cols = ", ".join(f'"{c}"' for c in fk.columns)
    ref_cols = ", ".join(f'"{c}"' for c in fk.ref_columns)
    clauses = []
    if fk.on_delete:
        clauses.append(f"ON DELETE {fk.on_delete.upper()}")
    if fk.on_update:
        clauses.append(f"ON UPDATE {fk.on_update.upper()}")
    clause_sql = " ".join(clauses)

    add_sql = f'ALTER TABLE "{schema}"."{fk.table}" ADD CONSTRAINT "{fk.constraint_name}" FOREIGN KEY ({cols}) REFERENCES "{schema}"."{fk.ref_table}" ({ref_cols})'
    if clause_sql:
        add_sql += f" {clause_sql}"
    add_sql += " NOT VALID"

    validate_sql = f'ALTER TABLE "{schema}"."{fk.table}" VALIDATE CONSTRAINT "{fk.constraint_name}"'

    with engine.begin() as conn:
        conn.execute(text(add_sql))
        if validate:
            conn.execute(text(validate_sql))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply foreign keys after MySQL→PostgreSQL data migration"
    )
    parser.add_argument(
        "--dump-file",
        default="tests/fixtures/legacy_db/alldb_backup_20251208.sql",
        help="Path to MySQL dump file",
    )
    parser.add_argument(
        "--databases",
        "-d",
        nargs="+",
        default=["mapping", "business", "customer", "finance"],
        help="Databases to process (schema names in Postgres)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate constraints after adding (may fail if data violates FKs)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    log_level = "DEBUG" if args.verbose else "INFO"
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(log_level))

    config = MigrationConfig.from_env(
        dump_file_path=args.dump_file,
        target_databases=args.databases,
        # target_schema is used only for logging here; FKs use per-db schema.
        target_schema="legacy",
        dry_run=False,
        save_converted_sql=False,
    )

    engine = create_engine(config.get_database_url())

    summary_success = 0
    summary_fail = 0
    failed: List[str] = []

    parser_obj = MySQLDumpParser(args.dump_file)

    for db_name in args.databases:
        logger.info("fk.apply.start_db", database=db_name)
        db_content = parser_obj.extract_database(db_name)
        for table_name, table_content in db_content.tables.items():
            fks = extract_foreign_keys(table_content.create_statement, table_name)
            if not fks:
                continue
            for fk in fks:
                if fk_exists(engine, db_name, fk.table, fk.constraint_name):
                    logger.info(
                        "fk.exists",
                        database=db_name,
                        table=fk.table,
                        constraint=fk.constraint_name,
                    )
                    continue
                try:
                    apply_fk(engine, db_name, fk, validate=args.validate)
                    summary_success += 1
                    logger.info(
                        "fk.applied",
                        database=db_name,
                        table=fk.table,
                        constraint=fk.constraint_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    summary_fail += 1
                    failed.append(f"{db_name}.{fk.table}.{fk.constraint_name}: {exc}")
                    logger.error(
                        "fk.failed",
                        database=db_name,
                        table=fk.table,
                        constraint=fk.constraint_name,
                        error=str(exc),
                    )

    print("\nForeign Key Application Summary")
    print("-" * 40)
    print(f"Applied: {summary_success}")
    print(f"Failed: {summary_fail}")
    if failed:
        print("\nFailures:")
        for item in failed:
            print(f" - {item}")
    else:
        print("No failures.")
    print()

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
