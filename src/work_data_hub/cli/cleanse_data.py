"""
CLI for data cleansing operations.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 4.5: CLI entry point for data cleansing operations

Usage:
    # Cleanse specific table
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli cleanse --table business_info --domain eqc_business_info

    # Cleanse with dry run
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli cleanse --table business_info --domain eqc_business_info --dry-run

    # Cleanse specific company IDs
    PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli cleanse --table business_info --domain eqc_business_info --company-ids 123,456
"""

import argparse
import json
import sys
from typing import List, Optional, Sequence

from sqlalchemy import create_engine, text

from work_data_hub.infrastructure.cleansing.rule_engine import CleansingRuleEngine
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


def cleanse_business_info_table(
    connection,
    domain: str,
    company_ids: Optional[Sequence[str]] = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """
    Cleanse records in enterprise.business_info table.

    Args:
        connection: SQLAlchemy connection.
        domain: Domain name for cleansing rules (e.g., "eqc_business_info").
        company_ids: Optional list of company IDs to cleanse. If None, cleanses all.
        dry_run: If True, don't commit changes.
        batch_size: Number of records to process per batch.

    Returns:
        Dict with cleansing statistics.
    """
    engine = CleansingRuleEngine()

    select_columns = """
        company_id,
        registered_date,
        "registerCaptial",
        registered_status,
        legal_person_name,
        address,
        company_name,
        credit_code,
        company_type,
        industry_name,
        business_scope
    """

    update_query = text("""
        UPDATE enterprise.business_info
        SET _cleansing_status = CAST(:cleansing_status AS jsonb),
            registered_date = :registered_date,
            "registerCaptial" = :registerCaptial,
            registered_status = :registered_status,
            legal_person_name = :legal_person_name,
            address = :address,
            company_name = :company_name,
            credit_code = :credit_code,
            company_type = :company_type,
            industry_name = :industry_name,
            business_scope = :business_scope
        WHERE company_id = :company_id
    """)

    total_records = 0
    total_fields_cleansed = 0
    total_fields_failed = 0

    def _apply_batch(rows) -> None:
        nonlocal total_records, total_fields_cleansed, total_fields_failed

        records = [dict(row._mapping) for row in rows]
        results = engine.cleanse_batch(domain, records)

        total_records += len(records)
        total_fields_cleansed += sum(r.fields_cleansed for r in results)
        total_fields_failed += sum(r.fields_failed for r in results)

        if dry_run:
            return

        for record, result in zip(records, results, strict=False):
            connection.execute(
                update_query,
                {
                    "company_id": record["company_id"],
                    "cleansing_status": json.dumps(
                        result.cleansing_status, ensure_ascii=False
                    ),
                    "registered_date": record.get("registered_date"),
                    "registerCaptial": record.get("registerCaptial"),
                    "registered_status": record.get("registered_status"),
                    "legal_person_name": record.get("legal_person_name"),
                    "address": record.get("address"),
                    "company_name": record.get("company_name"),
                    "credit_code": record.get("credit_code"),
                    "company_type": record.get("company_type"),
                    "industry_name": record.get("industry_name"),
                    "business_scope": record.get("business_scope"),
                },
            )

        connection.commit()

    # If company_ids specified, process in manageable chunks
    if company_ids:
        ids = [str(cid).strip() for cid in company_ids if str(cid).strip()]
        for start in range(0, len(ids), batch_size):
            chunk = ids[start : start + batch_size]
            placeholders = ",".join([f":id{i}" for i in range(len(chunk))])
            query = text(f"""
                SELECT {select_columns}
                FROM enterprise.business_info
                WHERE company_id IN ({placeholders})
                ORDER BY company_id
            """)
            params = {f"id{i}": cid for i, cid in enumerate(chunk)}
            rows = connection.execute(query, params).fetchall()
            if rows:
                _apply_batch(rows)
        return {
            "total_records": total_records,
            "records_cleansed": total_records,
            "fields_cleansed": total_fields_cleansed,
            "fields_failed": total_fields_failed,
        }

    # Otherwise: scan the whole table with keyset pagination
    last_company_id: Optional[str] = None
    while True:
        if last_company_id is None:
            query = text(f"""
                SELECT {select_columns}
                FROM enterprise.business_info
                ORDER BY company_id
                LIMIT :limit
            """)
            params = {"limit": batch_size}
        else:
            query = text(f"""
                SELECT {select_columns}
                FROM enterprise.business_info
                WHERE company_id > :last_company_id
                ORDER BY company_id
                LIMIT :limit
            """)
            params = {"last_company_id": last_company_id, "limit": batch_size}

        rows = connection.execute(query, params).fetchall()
        if not rows:
            break

        _apply_batch(rows)
        last_company_id = str(rows[-1]._mapping["company_id"])

    return {
        "total_records": total_records,
        "records_cleansed": total_records,
        "fields_cleansed": total_fields_cleansed,
        "fields_failed": total_fields_failed,
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
        description="Data cleansing operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Required arguments
    parser.add_argument(
        "--table",
        required=True,
        choices=["business_info"],
        help="Table to cleanse",
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Domain name for cleansing rules (e.g., eqc_business_info)",
    )

    # Optional arguments
    parser.add_argument(
        "--company-ids",
        type=str,
        help="Comma-separated list of company IDs to cleanse",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for processing (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode - show what would be cleansed without making changes",
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

    # Parse company IDs if provided
    company_ids = None
    if args.company_ids:
        company_ids = [cid.strip() for cid in args.company_ids.split(",")]

    # Use context manager for connection
    try:
        with engine.connect() as connection:
            if args.dry_run:
                print(f"\n[DRY RUN] Would cleanse {args.table} table with domain {args.domain}")
                if company_ids:
                    print(f"Company IDs: {', '.join(company_ids)}")
                else:
                    print(f"Batch size: {args.batch_size}")
                return 0

            print(f"\n🔄 Cleansing {args.table} table with domain {args.domain}...")

            # Cleanse table
            if args.table == "business_info":
                stats = cleanse_business_info_table(
                    connection,
                    args.domain,
                    company_ids=company_ids,
                    dry_run=args.dry_run,
                    batch_size=args.batch_size,
                )
            else:
                print(f"❌ Unsupported table: {args.table}", file=sys.stderr)
                return 1

            # Print results
            print("\n" + "=" * 60)
            print("Cleansing Results")
            print("=" * 60)
            print(f"Total Records: {stats['total_records']}")
            print(f"Records Cleansed: {stats['records_cleansed']}")
            print(f"✅ Fields Cleansed: {stats['fields_cleansed']}")
            print(f"❌ Fields Failed: {stats['fields_failed']}")
            print("=" * 60)

            return 0 if stats['fields_failed'] == 0 else 1

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
