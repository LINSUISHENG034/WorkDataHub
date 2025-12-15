#!/usr/bin/env python3
"""
EQC Iteration Diagnose Tool

Diagnostic tool to analyze the cleansing process for a specific company.
It fetches the raw JSON data from the database and applies the current cleansing rules,
showing a comparison of raw inputs vs cleansed outputs.

Usage:
    # Full diagnosis (raw data + cleansing simulation)
    python scripts/validation/EQC/eqc_iter_diagnose.py --company-id <ID>

    # Raw data only
    python scripts/validation/EQC/eqc_iter_diagnose.py --company-id <ID> --raw-only

    # Diagnose all for_check=true samples
    python scripts/validation/EQC/eqc_iter_diagnose.py --all-samples
"""
import argparse
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.cleansing.business_info_cleanser import BusinessInfoCleanser

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def inspect_raw_data(raw: Dict[str, Any], verbose: bool = False):
    """Inspect raw JSONB data structure and key fields."""
    print_section("RAW DATA INSPECTION")

    # 1. Top level structure
    print(f"Top-level keys: {list(raw.keys())}")

    # 2. Extract inner DTO if present (EQC structure usually has businessInfodto)
    data = raw.get("businessInfodto", raw)
    print(f"Data source keys: {list(data.keys())}")

    # 3. Dump key fields that often cause issues
    interesting_fields = [
        "company_name", "companyName",
        "registerCaptial", "registered_capital", "registerCapital",
        "registered_date", "est_date", "startDate", "start_date",
        "legal_person_name", "le_rep",
        "colleagues_num", "collegues_num", "staff_size",
        "credit_code", "unite_code",
        "actualCapi", "actual_capital"
    ]

    print("\n--- Key Field Values (Raw) ---")
    found_any = False
    for field in interesting_fields:
        if field in data:
            print(f"  {field:<20}: {data[field]}")
            found_any = True

    if not found_any:
        print("  (No common fields found in the expected data object)")

    # Verbose mode: print full JSON
    if verbose:
        print("\n--- Full Raw JSON ---")
        print(json.dumps(raw, indent=2, ensure_ascii=False, default=str))


def run_cleansing(raw: Dict[str, Any], company_id: str):
    """Run cleansing simulation and display results."""
    print_section("CLEANSING SIMULATION")

    cleanser = BusinessInfoCleanser()
    try:
        record = cleanser.transform(raw, company_id)

        print(f"{'Field':<25} | {'Status':<15} | {'Value'}")
        print("-" * 25 + "-+-" + "-" * 15 + "-+-" + "-" * 30)

        # Define fields to display (subset of important ones)
        display_fields = [
            "company_name",
            "legal_person_name",
            "registered_capital",
            "registered_date",
            "start_date",
            "end_date",
            "colleagues_num",
            "actual_capital",
            "credit_code",
            "industry_name"
        ]

        status_map = record.cleansing_status

        for field in display_fields:
            val = getattr(record, field)
            status = status_map.get(field, "N/A")

            # Colorize status if possible (simple indication)
            status_display = status
            if status == "cleansed":
                status_display = f"✅ {status}"
            elif status == "null_input":
                status_display = f"⚪ {status}"
            elif "failed" in status or "error" in status:
                status_display = f"❌ {status}"

            print(f"{field:<25} | {status_display:<15} | {val}")

    except Exception as e:
        logger.error(f"❌ Cleansing threw an exception: {e}")
        import traceback
        traceback.print_exc()


def get_sample_company_ids(conn) -> List[str]:
    """Get company IDs from for_check=true records."""
    result = conn.execute(text("""
        SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
    """)).fetchall()
    return [row[0] for row in result]


def diagnose_company(conn, company_id: str, raw_only: bool = False, verbose: bool = False):
    """Diagnose a single company."""
    print(f"\n{'#' * 60}")
    print(f"# Company ID: {company_id}")
    print(f"{'#' * 60}")

    # Fetch raw business info
    query = text("""
        SELECT raw_business_info 
        FROM enterprise.base_info
        WHERE company_id = :cid
    """)
    row = conn.execute(query, {'cid': company_id}).fetchone()

    if not row:
        logger.error(f"❌ No record found in 'enterprise.base_info' for company_id={company_id}")
        return

    raw_data = row[0]

    if not raw_data:
        logger.error(f"❌ Record found, but 'raw_business_info' is NULL.")
        return

    # 1. Inspect Raw
    inspect_raw_data(raw_data, verbose=verbose)

    # 2. Run Cleansing (unless raw-only mode)
    if not raw_only:
        run_cleansing(raw_data, company_id)


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose cleansing rules for a company.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Diagnose a specific company
  python scripts/validation/EQC/eqc_iter_diagnose.py --company-id 722929712

  # Show only raw data (skip cleansing simulation)
  python scripts/validation/EQC/eqc_iter_diagnose.py --company-id 722929712 --raw-only

  # Diagnose all for_check=true samples
  python scripts/validation/EQC/eqc_iter_diagnose.py --all-samples

  # Verbose mode (full JSON dump)
  python scripts/validation/EQC/eqc_iter_diagnose.py --company-id 722929712 --verbose
"""
    )
    parser.add_argument("--company-id", help="The company ID to diagnose")
    parser.add_argument("--all-samples", action="store_true",
                        help="Diagnose all for_check=true samples")
    parser.add_argument("--raw-only", action="store_true",
                        help="Only show raw data, skip cleansing simulation")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose mode: show full JSON")
    args = parser.parse_args()

    if not args.company_id and not args.all_samples:
        parser.error("Either --company-id or --all-samples is required")

    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())

    with engine.connect() as conn:
        if args.all_samples:
            company_ids = get_sample_company_ids(conn)
            if not company_ids:
                logger.error("❌ No records found with for_check=true")
                return
            print(f"Found {len(company_ids)} samples to diagnose")
            for cid in company_ids:
                diagnose_company(conn, cid, raw_only=args.raw_only, verbose=args.verbose)
        else:
            diagnose_company(conn, args.company_id, raw_only=args.raw_only, verbose=args.verbose)


if __name__ == "__main__":
    main()
