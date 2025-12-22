"""
CLI for data cleansing operations.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 4.5: CLI entry point for data cleansing operations

Story 6.2-P9: Raw Data Cleansing & Transformation
Task 4.1: Extended with biz_label table support and --limit parameter

Usage:
    # Cleanse business_info table
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
        --table business_info --batch-size 100

    # Cleanse biz_label table
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
        --table biz_label --batch-size 100

    # Cleanse all tables
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
        --table all --batch-size 100 --limit 50

    # Dry run to preview
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
        --table all --batch-size 10 --limit 50 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from work_data_hub.infrastructure.cleansing.biz_label_parser import BizLabelParser
from work_data_hub.infrastructure.cleansing.business_info_cleanser import (
    BusinessInfoCleanser,
)
from work_data_hub.infrastructure.enrichment.biz_label_repository import (
    BizLabelRepository,
)
from work_data_hub.infrastructure.enrichment.business_info_repository import (
    BusinessInfoRepository,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


def fetch_raw_records(
    connection: Connection,
    batch_size: int,
    offset: int,
    table: str = "business_info",
    incremental: bool = True,
) -> List[Dict[str, Any]]:
    """
    Fetch raw records from base_info for cleansing.

    Args:
        connection: SQLAlchemy connection
        batch_size: Number of records per batch
        offset: Offset for pagination
        table: Target table (business_info or biz_label)
        incremental: If True, only fetch records not yet cleansed

    Returns:
        List of raw record dicts
    """
    if table == "business_info":
        if incremental:
            query = text("""
                SELECT b.company_id, b.raw_business_info
                FROM enterprise.base_info b
                LEFT JOIN enterprise.business_info bi ON b.company_id = bi.company_id
                WHERE b.raw_business_info IS NOT NULL
                  AND bi.company_id IS NULL
                ORDER BY b.company_id
                LIMIT :batch_size OFFSET :offset
            """)
        else:
            query = text("""
                SELECT company_id, raw_business_info
                FROM enterprise.base_info
                WHERE raw_business_info IS NOT NULL
                ORDER BY company_id
                LIMIT :batch_size OFFSET :offset
            """)
    elif incremental:
        query = text("""
                SELECT b.company_id, b.raw_biz_label
                FROM enterprise.base_info b
                WHERE b.raw_biz_label IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM enterprise.biz_label bl
                      WHERE bl.company_id = b.company_id
                  )
                ORDER BY b.company_id
                LIMIT :batch_size OFFSET :offset
            """)
    else:
        query = text("""
                SELECT company_id, raw_biz_label
                FROM enterprise.base_info
                WHERE raw_biz_label IS NOT NULL
                ORDER BY company_id
                LIMIT :batch_size OFFSET :offset
            """)

    rows = connection.execute(
        query, {"batch_size": batch_size, "offset": offset}
    ).fetchall()
    return [dict(row._mapping) for row in rows]


def cleanse_business_info_from_raw(
    connection: Connection,
    batch_size: int = 100,
    limit: Optional[int] = None,
    dry_run: bool = False,
    incremental: bool = True,
) -> Dict[str, int]:
    """
    Cleanse business_info records from raw JSONB in base_info.

    Story 6.2-P9: Transform raw_business_info to normalized business_info records.

    Args:
        connection: SQLAlchemy connection
        batch_size: Number of records per batch
        limit: Maximum total records to process (None = all)
        dry_run: If True, don't persist changes
        incremental: If True, only process un-cleansed records

    Returns:
        Stats dict with counts
    """
    cleanser = BusinessInfoCleanser()
    repository = BusinessInfoRepository(connection)

    total_processed = 0
    total_success = 0
    total_failed = 0
    offset = 0

    while True:
        if limit and total_processed >= limit:
            break

        effective_batch = (
            min(batch_size, limit - total_processed) if limit else batch_size
        )
        records = fetch_raw_records(
            connection, effective_batch, offset, "business_info", incremental
        )

        if not records:
            break

        for record in records:
            company_id = record["company_id"]
            raw_business_info = record.get("raw_business_info")

            if not raw_business_info:
                total_failed += 1
                continue

            try:
                business_record = cleanser.transform(raw_business_info, company_id)

                if not dry_run:
                    repository.upsert(business_record)
                    connection.commit()

                total_success += 1
            except Exception as e:
                logger.warning(
                    "cleanse_data.business_info_failed",
                    company_id=company_id,
                    error=str(e),
                )
                total_failed += 1

            total_processed += 1

            if limit and total_processed >= limit:
                break

        # Progress reporting
        print(
            f"  Processed {total_processed} records, {total_success} success, {total_failed} failed"
        )

        offset += effective_batch

    return {
        "total_records": total_processed,
        "records_success": total_success,
        "records_failed": total_failed,
    }


def cleanse_biz_label_from_raw(
    connection: Connection,
    batch_size: int = 100,
    limit: Optional[int] = None,
    dry_run: bool = False,
    incremental: bool = True,
) -> Dict[str, int]:
    """
    Cleanse biz_label records from raw JSONB in base_info.

    Story 6.2-P9: Parse and persist biz_label records.

    Args:
        connection: SQLAlchemy connection
        batch_size: Number of records per batch
        limit: Maximum total records to process (None = all)
        dry_run: If True, don't persist changes
        incremental: If True, only process un-cleansed records

    Returns:
        Stats dict with counts
    """
    parser = BizLabelParser()
    repository = BizLabelRepository(connection)

    total_processed = 0
    total_success = 0
    total_failed = 0
    total_labels = 0
    offset = 0

    while True:
        if limit and total_processed >= limit:
            break

        effective_batch = (
            min(batch_size, limit - total_processed) if limit else batch_size
        )
        records = fetch_raw_records(
            connection, effective_batch, offset, "biz_label", incremental
        )

        if not records:
            break

        for record in records:
            company_id = record["company_id"]
            raw_biz_label = record.get("raw_biz_label")

            if not raw_biz_label:
                total_failed += 1
                continue

            try:
                label_records = parser.parse(raw_biz_label, company_id)

                if not dry_run:
                    inserted = repository.upsert_batch(company_id, label_records)
                    connection.commit()
                    total_labels += inserted
                else:
                    total_labels += len(label_records)

                total_success += 1
            except Exception as e:
                logger.warning(
                    "cleanse_data.biz_label_failed",
                    company_id=company_id,
                    error=str(e),
                )
                total_failed += 1

            total_processed += 1

            if limit and total_processed >= limit:
                break

        # Progress reporting
        print(
            f"  Processed {total_processed} records, {total_success} success, {total_labels} labels"
        )

        offset += effective_batch

    return {
        "total_records": total_processed,
        "records_success": total_success,
        "records_failed": total_failed,
        "total_labels": total_labels,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Main CLI entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = argparse.ArgumentParser(
        description="Data cleansing operations for EQC raw data transformation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required arguments
    parser.add_argument(
        "--table",
        required=True,
        choices=["business_info", "biz_label", "all"],
        help="Table to cleanse (business_info, biz_label, or all)",
    )

    # Optional arguments
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing (default: 100)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode - show what would be cleansed without making changes",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Re-cleanse all records (default: incremental - only un-cleansed records)",
    )

    args = parser.parse_args(argv)

    # Load settings
    try:
        from work_data_hub.config.settings import get_settings

        settings = get_settings()
    except Exception as e:
        print(f"❌ Failed to load settings: {e}", file=sys.stderr)
        return 1

    # Create database engine
    try:
        engine = create_engine(settings.get_database_connection_string())
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}", file=sys.stderr)
        return 1

    incremental = not args.full_refresh

    # Use context manager for connection
    try:
        with engine.connect() as connection:
            mode_str = "[DRY RUN] " if args.dry_run else ""
            incr_str = "incremental" if incremental else "full refresh"

            print(f"\n{mode_str}🔄 Cleansing {args.table} table ({incr_str})...")
            print(f"   Batch size: {args.batch_size}, Limit: {args.limit or 'all'}")

            all_stats: Dict[str, Dict[str, int]] = {}

            # Cleanse business_info
            if args.table in ("business_info", "all"):
                print("\n📊 Processing business_info...")
                stats = cleanse_business_info_from_raw(
                    connection,
                    batch_size=args.batch_size,
                    limit=args.limit,
                    dry_run=args.dry_run,
                    incremental=incremental,
                )
                all_stats["business_info"] = stats

            # Cleanse biz_label
            if args.table in ("biz_label", "all"):
                print("\n🏷️ Processing biz_label...")
                stats = cleanse_biz_label_from_raw(
                    connection,
                    batch_size=args.batch_size,
                    limit=args.limit,
                    dry_run=args.dry_run,
                    incremental=incremental,
                )
                all_stats["biz_label"] = stats

            # Print results
            print("\n" + "=" * 60)
            print("Cleansing Results Summary")
            print("=" * 60)

            total_failed = 0
            for table_name, stats in all_stats.items():
                print(f"\n{table_name}:")
                print(f"  Total Records: {stats['total_records']}")
                print(f"  ✅ Success: {stats['records_success']}")
                print(f"  ❌ Failed: {stats['records_failed']}")
                if "total_labels" in stats:
                    print(f"  🏷️ Labels Inserted: {stats['total_labels']}")
                total_failed += stats["records_failed"]

            print("\n" + "=" * 60)

            return 0 if total_failed == 0 else 1

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        logger.error(
            "cleanse_data.unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
