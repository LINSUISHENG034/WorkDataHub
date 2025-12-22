"""
Batch EQC Data Acquisition Script

Purpose: Acquire complete enterprise data from EQC API and persist to database.
Uses search_key_word from archive_base_info (for_check=true) to fetch and store:
- base_info: Search results + raw_data + raw_business_info + raw_biz_label
- business_info: Cleansed business information (via cleansing step)
- biz_label: Parsed label hierarchy (via cleansing step)

Usage:
    # Acquire data for all for_check=true records
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/batch_eqc_acquisition.py

    # Limit to first N records
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/batch_eqc_acquisition.py --limit 5

    # With cleansing step
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/batch_eqc_acquisition.py --with-cleansing
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from work_data_hub.config.settings import get_settings
from work_data_hub.io.connectors.eqc_client import (
    EQCAuthenticationError,
    EQCClient,
    EQCClientError,
    EQCNotFoundError,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AcquisitionRecord:
    """Record from archive_base_info for acquisition."""

    company_id: str
    search_key_word: str
    company_full_name: Optional[str]
    unite_code: Optional[str]


@dataclass
class AcquisitionResult:
    """Result of a single acquisition."""

    search_key_word: str
    success: bool = False

    # API results
    api_company_id: Optional[str] = None
    api_company_name: Optional[str] = None
    api_unite_code: Optional[str] = None

    has_raw_data: bool = False
    has_raw_business_info: bool = False
    has_raw_biz_label: bool = False

    error_message: Optional[str] = None


@dataclass
class AcquisitionSummary:
    """Summary of batch acquisition."""

    total_records: int = 0
    successful: int = 0
    failed: int = 0
    with_business_info: int = 0
    with_biz_label: int = 0
    errors: List[str] = field(default_factory=list)


def fetch_acquisition_records(
    connection: Connection, limit: Optional[int] = None
) -> List[AcquisitionRecord]:
    """Fetch records from archive_base_info where for_check=true."""
    query = """
        SELECT company_id, search_key_word, "companyFullName", unite_code
        FROM enterprise.archive_base_info
        WHERE for_check = true
        ORDER BY search_key_word
    """
    if limit:
        query += f" LIMIT {limit}"

    result = connection.execute(text(query))
    records = []

    for row in result:
        records.append(
            AcquisitionRecord(
                company_id=row[0],
                search_key_word=row[1],
                company_full_name=row[2],
                unite_code=row[3],
            )
        )

    return records


def persist_to_base_info(
    connection: Connection,
    company_id: str,
    search_key_word: str,
    raw_search_data: dict,
    raw_business_info: Optional[dict],
    raw_biz_label: Optional[dict],
) -> None:
    """
    Persist acquired data to enterprise.base_info table.

    Extracts fields from raw_search_data and stores all raw responses.
    """
    import json

    # Extract fields from first search result
    search_list = raw_search_data.get("list", [])
    first_result = search_list[0] if search_list else {}

    # Build insert/update statement
    connection.execute(
        text("""
        INSERT INTO enterprise.base_info (
            company_id,
            search_key_word,
            name,
            name_display,
            symbol,
            rank_score,
            country,
            company_en_name,
            smdb_code,
            is_hk,
            coname,
            is_list,
            company_nature,
            _score,
            type,
            "registeredStatus",
            organization_code,
            le_rep,
            reg_cap,
            is_pa_relatedparty,
            province,
            "companyFullName",
            est_date,
            company_short_name,
            id,
            is_debt,
            unite_code,
            registered_status,
            cocode,
            default_score,
            company_former_name,
            is_rank_list,
            trade_register_code,
            "companyId",
            is_normal,
            company_full_name,
            raw_data,
            raw_business_info,
            raw_biz_label,
            api_fetched_at,
            updated_at
        ) VALUES (
            :company_id,
            :search_key_word,
            :name,
            :name_display,
            :symbol,
            :rank_score,
            :country,
            :company_en_name,
            :smdb_code,
            :is_hk,
            :coname,
            :is_list,
            :company_nature,
            :_score,
            :type,
            :registeredStatus,
            :organization_code,
            :le_rep,
            :reg_cap,
            :is_pa_relatedparty,
            :province,
            :companyFullName,
            :est_date,
            :company_short_name,
            :id,
            :is_debt,
            :unite_code,
            :registered_status,
            :cocode,
            :default_score,
            :company_former_name,
            :is_rank_list,
            :trade_register_code,
            :companyId,
            :is_normal,
            :company_full_name,
            :raw_data,
            :raw_business_info,
            :raw_biz_label,
            :api_fetched_at,
            NOW()
        )
        ON CONFLICT (company_id) DO UPDATE SET
            search_key_word = EXCLUDED.search_key_word,
            raw_data = EXCLUDED.raw_data,
            raw_business_info = EXCLUDED.raw_business_info,
            raw_biz_label = EXCLUDED.raw_biz_label,
            api_fetched_at = EXCLUDED.api_fetched_at,
            updated_at = NOW()
    """),
        {
            "company_id": company_id,
            "search_key_word": search_key_word,
            "name": first_result.get("name"),
            "name_display": first_result.get("name_display"),
            "symbol": first_result.get("symbol"),
            "rank_score": first_result.get("rank_score"),
            "country": first_result.get("country"),
            "company_en_name": first_result.get("company_en_name"),
            "smdb_code": first_result.get("smdb_code"),
            "is_hk": first_result.get("is_hk"),
            "coname": first_result.get("coname"),
            "is_list": first_result.get("is_list"),
            "company_nature": first_result.get("company_nature"),
            "_score": first_result.get("_score"),
            "type": first_result.get("type"),
            "registeredStatus": first_result.get("registeredStatus"),
            "organization_code": first_result.get("organization_code"),
            "le_rep": first_result.get("le_rep"),
            "reg_cap": first_result.get("reg_cap"),
            "is_pa_relatedparty": first_result.get("is_pa_relatedparty"),
            "province": first_result.get("province"),
            "companyFullName": first_result.get("companyFullName"),
            "est_date": first_result.get("est_date"),
            "company_short_name": first_result.get("company_short_name"),
            "id": first_result.get("id"),
            "is_debt": first_result.get("is_debt"),
            "unite_code": first_result.get("unite_code"),
            "registered_status": first_result.get("registered_status"),
            "cocode": first_result.get("cocode"),
            "default_score": first_result.get("default_score"),
            "company_former_name": first_result.get("company_former_name"),
            "is_rank_list": first_result.get("is_rank_list"),
            "trade_register_code": first_result.get("trade_register_code"),
            "companyId": first_result.get("companyId"),
            "is_normal": first_result.get("is_normal"),
            "company_full_name": first_result.get("company_full_name"),
            "raw_data": json.dumps(raw_search_data, ensure_ascii=False),
            "raw_business_info": json.dumps(raw_business_info, ensure_ascii=False)
            if raw_business_info
            else None,
            "raw_biz_label": json.dumps(raw_biz_label, ensure_ascii=False)
            if raw_biz_label
            else None,
            "api_fetched_at": datetime.now(timezone.utc),
        },
    )


def acquire_single_record(
    client: EQCClient,
    connection: Connection,
    record: AcquisitionRecord,
) -> AcquisitionResult:
    """Acquire complete data for a single record from EQC API."""

    result = AcquisitionResult(search_key_word=record.search_key_word)

    try:
        # Step 1: Search company
        search_results, raw_search = client.search_company_with_raw(
            record.search_key_word
        )

        if not search_results:
            result.error_message = "No search results"
            return result

        top = search_results[0]
        company_id = str(top.company_id)

        result.api_company_id = company_id
        result.api_company_name = top.official_name
        result.api_unite_code = getattr(top, "unite_code", None)
        result.has_raw_data = True

        # Step 2: Get business info (findDepart)
        raw_business_info = None
        try:
            _, raw_business_info = client.get_business_info_with_raw(company_id)
            result.has_raw_business_info = True
        except Exception as e:
            logger.warning(f"Failed to get business info for {company_id}: {e}")

        # Step 3: Get label info (findLabels)
        raw_biz_label = None
        try:
            _, raw_biz_label = client.get_label_info_with_raw(company_id)
            result.has_raw_biz_label = True
        except Exception as e:
            logger.warning(f"Failed to get label info for {company_id}: {e}")

        # Step 4: Persist to database
        persist_to_base_info(
            connection=connection,
            company_id=company_id,
            search_key_word=record.search_key_word,
            raw_search_data=raw_search,
            raw_business_info=raw_business_info,
            raw_biz_label=raw_biz_label,
        )
        connection.commit()

        result.success = True

    except EQCAuthenticationError as e:
        result.error_message = f"Auth error: {e}"
        raise  # Re-raise to stop batch processing

    except EQCNotFoundError:
        result.error_message = "Not found (404)"

    except EQCClientError as e:
        result.error_message = f"API error: {e}"

    except Exception as e:
        result.error_message = f"Unexpected error: {type(e).__name__}: {e}"
        logger.exception(f"Error acquiring {record.search_key_word}")

    return result


def print_result(result: AcquisitionResult, index: int):
    """Print a single acquisition result."""
    status_icon = "✅" if result.success else "❌"

    print(f"\n[{index}] {status_icon} {result.search_key_word}")

    if result.success:
        print(f"    company_id: {result.api_company_id}")
        print(f"    company_name: {result.api_company_name}")
        print(f"    unite_code: {result.api_unite_code}")
        print(
            f"    raw_data: ✓  business_info: {'✓' if result.has_raw_business_info else '✗'}  biz_label: {'✓' if result.has_raw_biz_label else '✗'}"
        )
    elif result.error_message:
        print(f"    Error: {result.error_message}")


def print_summary(summary: AcquisitionSummary):
    """Print acquisition summary."""
    print("\n" + "=" * 70)
    print("ACQUISITION SUMMARY")
    print("=" * 70)
    print(f"Total Records:        {summary.total_records}")
    print(f"Successful:           {summary.successful}")
    print(f"Failed:               {summary.failed}")
    print(f"With Business Info:   {summary.with_business_info}")
    print(f"With Biz Label:       {summary.with_biz_label}")

    if summary.errors:
        print("\nErrors:")
        for err in summary.errors[:10]:
            print(f"  - {err}")
        if len(summary.errors) > 10:
            print(f"  ... and {len(summary.errors) - 10} more")

    print("=" * 70)


def run_cleansing(connection: Connection) -> Dict[str, int]:
    """Run cleansing for business_info and biz_label."""
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

    stats = {
        "business_info_success": 0,
        "business_info_failed": 0,
        "biz_label_success": 0,
        "biz_label_records": 0,
    }

    # Cleanse business_info
    print("\n📊 Cleansing business_info...")
    cleanser = BusinessInfoCleanser()
    biz_repo = BusinessInfoRepository(connection)

    rows = connection.execute(
        text("""
        SELECT company_id, raw_business_info
        FROM enterprise.base_info
        WHERE raw_business_info IS NOT NULL
    """)
    ).fetchall()

    for row in rows:
        company_id, raw_biz = row
        try:
            record = cleanser.transform(raw_biz, company_id)
            biz_repo.upsert(record)
            stats["business_info_success"] += 1
        except Exception as e:
            logger.warning(f"Failed to cleanse business_info for {company_id}: {e}")
            stats["business_info_failed"] += 1

    connection.commit()
    print(f"   ✅ {stats['business_info_success']} records cleansed")

    # Parse biz_label
    print("\n🏷️ Parsing biz_label...")
    parser = BizLabelParser()
    label_repo = BizLabelRepository(connection)

    rows = connection.execute(
        text("""
        SELECT company_id, raw_biz_label
        FROM enterprise.base_info
        WHERE raw_biz_label IS NOT NULL
    """)
    ).fetchall()

    for row in rows:
        company_id, raw_label = row
        try:
            labels = parser.parse(raw_label, company_id)
            inserted = label_repo.upsert_batch(company_id, labels)
            stats["biz_label_success"] += 1
            stats["biz_label_records"] += inserted
        except Exception as e:
            logger.warning(f"Failed to parse biz_label for {company_id}: {e}")

    connection.commit()
    print(
        f"   ✅ {stats['biz_label_success']} companies, {stats['biz_label_records']} labels"
    )

    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch EQC data acquisition from archive_base_info"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit to first N records"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay between API calls in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--with-cleansing",
        action="store_true",
        help="Run cleansing step after acquisition",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview only, don't persist data"
    )

    args = parser.parse_args(argv)

    # Load settings
    try:
        settings = get_settings()
    except Exception as e:
        print(f"❌ Failed to load settings: {e}")
        return 1

    # Create database connection
    try:
        engine = create_engine(settings.get_database_connection_string())
    except Exception as e:
        print(f"❌ Failed to create database engine: {e}")
        return 1

    # Initialize EQC client
    try:
        client = EQCClient()
    except EQCAuthenticationError as e:
        print(f"❌ EQC Authentication Error: {e}")
        print("\nPlease update your EQC token:")
        print(
            "  PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.io.auth --capture --save"
        )
        return 1

    # Run acquisition
    try:
        with engine.connect() as connection:
            # Fetch records
            print("📋 Fetching records from archive_base_info (for_check=true)...")
            records = fetch_acquisition_records(connection, limit=args.limit)

            if not records:
                print("⚠️ No records found with for_check=true")
                return 0

            print(f"   Found {len(records)} records to acquire")

            if args.dry_run:
                print("\n[DRY RUN MODE] - Will not persist data")
                for i, rec in enumerate(records[:10], 1):
                    print(f"  [{i}] {rec.search_key_word}")
                if len(records) > 10:
                    print(f"  ... and {len(records) - 10} more")
                return 0

            # Initialize summary
            summary = AcquisitionSummary(total_records=len(records))

            print("\n" + "=" * 70)
            print("STARTING DATA ACQUISITION (3 APIs per company)")
            print("=" * 70)

            # Process each record
            for idx, record in enumerate(records, 1):
                try:
                    result = acquire_single_record(client, connection, record)

                    # Update summary
                    if result.success:
                        summary.successful += 1
                        if result.has_raw_business_info:
                            summary.with_business_info += 1
                        if result.has_raw_biz_label:
                            summary.with_biz_label += 1
                    else:
                        summary.failed += 1
                        if result.error_message:
                            summary.errors.append(
                                f"{record.search_key_word}: {result.error_message}"
                            )

                    # Print result
                    print_result(result, idx)

                    # Rate limiting delay (3 API calls per iteration)
                    if idx < len(records):
                        time.sleep(args.delay)

                    # Progress reporting
                    if idx % 10 == 0:
                        print(f"\n📊 Progress: {idx}/{len(records)} processed")

                except EQCAuthenticationError:
                    print("\n❌ Token expired during acquisition!")
                    print("Please update your EQC token and resume.")
                    break

                except KeyboardInterrupt:
                    print("\n\n⚠️ Interrupted by user")
                    break

            # Print summary
            print_summary(summary)

            # Run cleansing if requested
            if args.with_cleansing and summary.successful > 0:
                print("\n" + "=" * 70)
                print("RUNNING CLEANSING STEP")
                print("=" * 70)
                cleansing_stats = run_cleansing(connection)

            # Final database stats
            print("\n📊 Database Status:")
            for table in ["base_info", "business_info", "biz_label"]:
                count = connection.execute(
                    text(f"SELECT COUNT(*) FROM enterprise.{table}")
                ).scalar()
                print(f"   enterprise.{table}: {count} records")

            return 0 if summary.failed == 0 else 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.exception("batch_acquisition.error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
