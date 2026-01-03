#!/usr/bin/env python
"""
Verification script for EQC Query data writeback to enrichment_index table.

This script verifies the former_name enrichment feature by:
1. Reading the first 10 keywords from enterprise.search_key_word table
2. Simulating EQC queries using EqcProvider
3. Verifying base_info table persistence
4. Verifying enrichment_index table writes (customer_name + former_name lookup_types)

Usage:
    uv run python scripts/validation/EQC/verify_eqc_enrichment_writeback.py
    uv run python scripts/validation/EQC/verify_eqc_enrichment_writeback.py --limit 5
    uv run python scripts/validation/EQC/verify_eqc_enrichment_writeback.py --dry-run
"""

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Ensure correct import path
sys.path.insert(0, "src")


@dataclass
class VerificationResult:
    """Result of a single EQC query verification."""

    keyword: str
    success: bool
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    has_former_names: bool = False
    former_names_count: int = 0
    base_info_written: bool = False
    enrichment_customer_name_written: bool = False
    enrichment_former_names_written: int = 0
    error_message: Optional[str] = None


@dataclass
class VerificationReport:
    """Summary report of all verifications."""

    total_keywords: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    base_info_writes: int = 0
    customer_name_writes: int = 0
    former_name_writes: int = 0
    results: List[VerificationResult] = field(default_factory=list)


def validate_and_refresh_token() -> bool:
    """
    Validate EQC token and auto-refresh if expired.

    Returns:
        True if token is valid (or successfully refreshed), False otherwise.
    """
    from work_data_hub.config.settings import get_settings
    from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token

    settings = get_settings()
    token = getattr(settings, "eqc_token", None)
    base_url = settings.eqc_base_url

    if not token:
        print("[WARN] No EQC token configured.")
        return _refresh_token()

    print("[INFO] Validating EQC token...")
    if validate_eqc_token(token, base_url):
        print("[INFO] ✓ Token is valid.")
        return True

    print("[WARN] ✗ Token is expired or invalid.")
    return _refresh_token()


def _refresh_token() -> bool:
    """
    Trigger auto EQC authentication to refresh token.

    Returns:
        True if token refreshed successfully, False otherwise.
    """
    import os

    print("[INFO] Starting automatic token refresh...")
    print("[INFO] Please scan the QR code when the window appears.\n")

    try:
        from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr

        new_token = run_get_token_auto_qr(save_to_env=True)

        if new_token:
            print("\n[INFO] ✓ Token refreshed successfully.")
            # Update environment variable so get_settings() picks up new token
            os.environ["WDH_EQC_TOKEN"] = new_token
            # Clear settings cache to force reload with new token
            from work_data_hub.config.settings import get_settings

            get_settings.cache_clear()
            return True
        else:
            print("\n[ERROR] ✗ Token refresh failed.")
            return False
    except Exception as e:
        print(f"\n[ERROR] ✗ Token refresh error: {e}")
        return False


def load_keywords_from_db(limit: Optional[int] = None) -> List[str]:
    """Load keywords from enterprise.search_key_word table."""
    from sqlalchemy import create_engine, text

    from work_data_hub.config.settings import get_settings

    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())

    with engine.connect() as conn:
        if limit is None:
            result = conn.execute(
                text("SELECT key_word FROM enterprise.search_key_word")
            )
        else:
            result = conn.execute(
                text("SELECT key_word FROM enterprise.search_key_word LIMIT :limit"),
                {"limit": limit},
            )
        keywords = [row[0] for row in result.fetchall()]

    print(f"[INFO] Loaded {len(keywords)} keywords from enterprise.search_key_word")
    return keywords


def verify_base_info(conn, company_id: str) -> Dict[str, Any]:
    """Check if base_info record exists for company_id."""
    from sqlalchemy import text

    result = conn.execute(
        text("""
            SELECT company_id, search_key_word, company_full_name,
                   company_former_name, raw_data IS NOT NULL as has_raw_data,
                   raw_business_info IS NOT NULL as has_raw_business_info
            FROM enterprise.base_info
            WHERE company_id = :company_id
        """),
        {"company_id": company_id},
    )
    row = result.fetchone()

    if row:
        return {
            "exists": True,
            "company_id": row[0],
            "search_key_word": row[1],
            "company_full_name": row[2],
            "company_former_name": row[3],
            "has_raw_data": row[4],
            "has_raw_business_info": row[5],
        }
    return {"exists": False}


def verify_enrichment_index(conn, company_id: str, lookup_key: str) -> Dict[str, Any]:
    """Check enrichment_index records for company_id."""
    from sqlalchemy import text

    # Check customer_name record
    customer_name_result = conn.execute(
        text("""
            SELECT lookup_key, lookup_type, company_id, confidence, source_domain
            FROM enterprise.enrichment_index
            WHERE company_id = :company_id AND lookup_type = 'customer_name'
            LIMIT 5
        """),
        {"company_id": company_id},
    )
    customer_name_records = customer_name_result.fetchall()

    # Check former_name records
    former_name_result = conn.execute(
        text("""
            SELECT lookup_key, lookup_type, company_id, confidence, source_domain
            FROM enterprise.enrichment_index
            WHERE company_id = :company_id AND lookup_type = 'former_name'
        """),
        {"company_id": company_id},
    )
    former_name_records = former_name_result.fetchall()

    return {
        "customer_name_count": len(customer_name_records),
        "customer_name_records": [
            {
                "lookup_key": r[0],
                "lookup_type": r[1],
                "company_id": r[2],
                "confidence": float(r[3]) if r[3] else None,
                "source_domain": r[4],
            }
            for r in customer_name_records
        ],
        "former_name_count": len(former_name_records),
        "former_name_records": [
            {
                "lookup_key": r[0],
                "lookup_type": r[1],
                "company_id": r[2],
                "confidence": float(r[3]) if r[3] else None,
                "source_domain": r[4],
            }
            for r in former_name_records
        ],
    }


def run_verification(
    keywords: List[str],
    dry_run: bool = False,
) -> VerificationReport:
    """
    Run EQC queries and verify data writeback.

    Args:
        keywords: List of company names to query.
        dry_run: If True, only print what would be done without executing.

    Returns:
        VerificationReport with all results.
    """
    from sqlalchemy import create_engine

    from work_data_hub.config.settings import get_settings
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

    settings = get_settings()
    report = VerificationReport(total_keywords=len(keywords))

    if dry_run:
        print("\n[DRY-RUN MODE] Would query the following keywords:")
        for i, kw in enumerate(keywords, 1):
            print(f"  {i}. {kw}")
        print("\n[DRY-RUN MODE] No actual queries will be made.")
        return report

    # Initialize database connection
    engine = create_engine(settings.get_database_connection_string())
    connection = engine.connect()
    repository = CompanyMappingRepository(connection)

    # Initialize EQC provider with repository for auto-caching
    provider = EqcProvider(
        mapping_repository=repository,
        budget=len(keywords) + 5,  # Extra budget for safety
    )

    if not provider.is_available:
        print("[ERROR] EQC provider is not available. Check token configuration.")
        return report

    print(f"\n[INFO] EQC Provider initialized with budget: {provider.budget}")
    print(f"[INFO] Starting verification of {len(keywords)} keywords...\n")

    for i, keyword in enumerate(keywords, 1):
        print(f"[{i}/{len(keywords)}] Querying: {keyword}")
        result = VerificationResult(keyword=keyword, success=False)

        try:
            # Execute EQC lookup (this will auto-cache via _cache_result)
            company_info = provider.lookup(keyword)

            if company_info is None:
                result.error_message = "EQC lookup returned None"
                report.failed_queries += 1
                print("  ❌ Not found or error")
            else:
                result.success = True
                result.company_id = company_info.company_id
                result.company_name = company_info.official_name
                report.successful_queries += 1
                print(
                    f"  ✓ Found: {company_info.company_id} - {company_info.official_name}"
                )

                # Commit to persist the cached data
                connection.commit()

                # Verify base_info
                base_info = verify_base_info(connection, company_info.company_id)
                if base_info["exists"]:
                    result.base_info_written = True
                    report.base_info_writes += 1
                    if base_info.get("company_former_name"):
                        result.has_former_names = True
                        result.former_names_count = len(
                            base_info["company_former_name"].split(",")
                        )
                    print(
                        f"    → base_info: ✓ (former_names: {result.former_names_count})"
                    )
                else:
                    print("    → base_info: ❌ NOT FOUND")

                # Verify enrichment_index
                from work_data_hub.infrastructure.enrichment.normalizer import (
                    normalize_for_temp_id,
                )

                normalized_key = normalize_for_temp_id(keyword) or keyword
                enrichment = verify_enrichment_index(
                    connection, company_info.company_id, normalized_key
                )

                if enrichment["customer_name_count"] > 0:
                    result.enrichment_customer_name_written = True
                    report.customer_name_writes += 1
                    print(
                        f"    → enrichment_index (customer_name): ✓ ({enrichment['customer_name_count']} records)"
                    )
                else:
                    print("    → enrichment_index (customer_name): ❌ NOT FOUND")

                if enrichment["former_name_count"] > 0:
                    result.enrichment_former_names_written = enrichment[
                        "former_name_count"
                    ]
                    report.former_name_writes += enrichment["former_name_count"]
                    print(
                        f"    → enrichment_index (former_name): ✓ ({enrichment['former_name_count']} records)"
                    )
                elif result.has_former_names:
                    print(
                        "    → enrichment_index (former_name): ⚠ Expected but NOT FOUND"
                    )
                else:
                    print(
                        "    → enrichment_index (former_name): - (no former names in source)"
                    )

        except Exception as e:
            result.error_message = str(e)
            report.failed_queries += 1
            print(f"  ❌ Error: {e}")

        report.results.append(result)
        print()

    # Cleanup
    connection.close()

    return report


def print_summary(report: VerificationReport) -> None:
    """Print verification summary."""
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Total keywords:           {report.total_keywords}")
    print(f"Successful queries:       {report.successful_queries}")
    print(f"Failed queries:           {report.failed_queries}")
    print("-" * 60)
    print(f"base_info writes:         {report.base_info_writes}")
    print(f"customer_name writes:     {report.customer_name_writes}")
    print(f"former_name writes:       {report.former_name_writes}")
    print("=" * 60)

    # Check success criteria
    success = (
        report.successful_queries > 0
        and report.base_info_writes == report.successful_queries
        and report.customer_name_writes == report.successful_queries
    )

    if success:
        print("\n✅ VERIFICATION PASSED")
        if report.former_name_writes > 0:
            print(
                f"   → former_name feature working ({report.former_name_writes} records written)"
            )
        else:
            print("   → Note: No former names found in queried companies")
    else:
        print("\n❌ VERIFICATION FAILED")
        print("   → Check the detailed output above for errors")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify EQC query data writeback to enrichment_index table."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of keywords to query (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be done, don't execute queries",
    )
    parser.add_argument(
        "--skip-token-check",
        action="store_true",
        help="Skip token validation (use existing token as-is)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("EQC Enrichment Writeback Verification")
    print("=" * 60)

    # Validate and refresh token if needed (unless dry-run or skipped)
    if not args.dry_run and not args.skip_token_check:
        if not validate_and_refresh_token():
            print("[ERROR] Cannot proceed without valid EQC token.")
            sys.exit(1)
        print()  # Add spacing after token validation

    # Load keywords
    keywords = load_keywords_from_db(limit=args.limit)

    if not keywords:
        print("[ERROR] No keywords found in enterprise.search_key_word table")
        sys.exit(1)

    # Run verification
    report = run_verification(keywords, dry_run=args.dry_run)

    if not args.dry_run:
        print_summary(report)


if __name__ == "__main__":
    main()
