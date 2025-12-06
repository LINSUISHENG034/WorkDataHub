"""
Simple CLI to apply SQL to PostgreSQL using project .env, with domain support.

Usage (PowerShell / Bash):
  # Apply specific SQL file
  uv run python -m scripts.create_table.apply_sql --sql scripts/create_table/ddl/annuity_performance.sql

  # Or apply by domain (per manifest)
  uv run python -m scripts.create_table.apply_sql --domain annuity_performance

  # List supported domains
  uv run python -m scripts.create_table.apply_sql --list

Notes:
- Loads database configuration from the project .env via Settings (get_settings).
  You can override with --dsn if needed.
- Output avoids printing secrets; only sanitized connection info is shown.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply a SQL file to PostgreSQL using project .env settings.",
    )
    parser.add_argument(
        "--sql",
        required=False,
        help="Path to the SQL file to execute (UTF-8)",
    )
    parser.add_argument(
        "--domain",
        required=False,
        help="Domain name defined in manifest.yml (e.g., annuity_performance)",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help="Optional DSN to override .env settings (e.g., postgresql://user:pass@host:5432/db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show connection info and a preview of the SQL, do not execute.",
    )
    return parser.parse_args()


def load_dsn(override_dsn: str | None) -> str:
    if override_dsn:
        return override_dsn
    # Fallback to project settings (.env)
    from src.work_data_hub.config.settings import get_settings

    settings = get_settings()
    return settings.get_database_connection_string()


def resolve_sql_path(sql: Optional[str], domain: Optional[str]) -> Path:
    if sql:
        return Path(sql)
    if domain:
        manifest_path = Path("scripts/create_table/manifest.yml")
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        dom = data.get("domains", {}).get(domain)
        if not dom:
            raise ValueError(f"Domain not found in manifest: {domain}")
        ddl = dom.get("ddl")
        if not ddl:
            raise ValueError(f"Domain '{domain}' missing 'ddl' in manifest")
        return Path(ddl)
    raise ValueError("Either --sql or --domain must be provided")


def sanitize_dsn(dsn: str) -> str:
    p = urlparse(dsn)
    # Rebuild without password
    user = p.username or ""
    host = p.hostname or ""
    port = f":{p.port}" if p.port else ""
    db = p.path.lstrip("/") if p.path else ""
    return f"postgresql://{user}:***@{host}{port}/{db}"


def main() -> int:
    args = parse_args()
    if getattr(args, "list", False):
        try:
            m = (
                yaml.safe_load(
                    Path("scripts/create_table/manifest.yml").read_text(
                        encoding="utf-8"
                    )
                )
                or {}
            )
            domains = sorted((m.get("domains") or {}).keys())
            print("Available domains:")
            for d in domains:
                print(f" - {d}")
            return 0
        except Exception as e:
            print(f"Failed to read manifest: {e}")
            return 2

    try:
        sql_path = resolve_sql_path(args.sql, args.domain)
    except Exception as e:
        print(str(e))
        return 2

    if not sql_path.exists() or not sql_path.is_file():
        print(f"SQL file not found: {sql_path}")
        return 2

    try:
        sql_text = sql_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Failed to read SQL file: {e}")
        return 2

    dsn = load_dsn(args.dsn)
    print("Applying SQL with DSN:")
    print(f"  {sanitize_dsn(dsn)}")
    print(f"  SQL file: {sql_path}")

    if args.dry_run:
        preview = sql_text.strip().splitlines()[:10]
        print("--- SQL preview (first 10 lines) ---")
        for line in preview:
            print(line)
        print("--- end preview ---")
        return 0

    try:
        import psycopg2  # type: ignore
    except Exception as e:
        print(f"psycopg2 not available: {e}")
        return 3

    try:
        conn = psycopg2.connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql_text)
        conn.close()
        print("SQL applied successfully.")
        return 0
    except Exception as e:
        print(f"Failed to apply SQL: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
