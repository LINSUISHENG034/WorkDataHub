"""Database bootstrap script for Story 1.7.

Provides a cross-platform helper that:
1. Runs Alembic migrations against the target database URL.
2. Optionally loads seed data for local testing.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text

from work_data_hub.config import get_settings
from work_data_hub.io.schema import migration_runner
from work_data_hub.utils.logging import get_logger

logger = get_logger("work_data_hub.scripts.db_setup")

DEFAULT_SEED_FILE = Path("io/schema/fixtures/test_data.sql")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Setup or teardown the WorkDataHub schema via Alembic."
    )
    parser.add_argument(
        "--database-url",
        dest="database_url",
        help="Override database URL (defaults to Settings.get_database_connection_string()).",
    )
    parser.add_argument(
        "--revision",
        default="head",
        help="Revision to upgrade/downgrade to (default: head).",
    )
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Run downgrade instead of upgrade (use with caution).",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load seed data after migrations succeed.",
    )
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=DEFAULT_SEED_FILE,
        help=f"Path to SQL seed file (default: {DEFAULT_SEED_FILE}).",
    )
    return parser.parse_args()


def resolve_database_url(cli_value: Optional[str]) -> str:
    if cli_value:
        return cli_value

    settings = get_settings()
    return settings.get_database_connection_string()


def load_seed_data(database_url: str, seed_path: Path) -> None:
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")

    sql = seed_path.read_text(encoding="utf-8")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(sql))
    logger.info("db_setup.seed_loaded", seed_file=str(seed_path))


def main() -> None:
    args = parse_args()
    database_url = resolve_database_url(args.database_url)

    if args.downgrade:
        migration_runner.downgrade(database_url, args.revision)
        logger.info("db_setup.downgraded", revision=args.revision, url=database_url)
    else:
        migration_runner.upgrade(database_url, args.revision)
        logger.info("db_setup.upgraded", revision=args.revision, url=database_url)

    if args.seed:
        load_seed_data(database_url, args.seed_file)


if __name__ == "__main__":
    main()
