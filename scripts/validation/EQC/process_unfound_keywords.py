#!/usr/bin/env python
"""
Process un-found keywords in search_key_word table using EQC queries.

This script:
1. Reads keywords where search_result=false from enterprise.search_key_word
2. Executes EQC queries for each keyword
3. Persists results to enterprise.base_info table
4. Writes enrichment data to enterprise.enrichment_index (customer_name + former_name)
5. Updates search_key_word.search_result and search_key_word.type fields

Usage:
    # Process all un-found keywords
    uv run python scripts/validation/EQC/process_unfound_keywords.py

    # Process with limit
    uv run python scripts/validation/EQC/process_unfound_keywords.py --limit 10

    # Filter by source
    uv run python scripts/validation/EQC/process_unfound_keywords.py --source name

    # Dry run (show what would be done)
    uv run python scripts/validation/EQC/process_unfound_keywords.py --dry-run

    # Batch processing
    uv run python scripts/validation/EQC/process_unfound_keywords.py --batch-size 50
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

# Ensure correct import path
sys.path.insert(0, "src")


def configure_logging(verbose: bool = False) -> None:
    """Configure logging to suppress JSON noise in CLI output."""
    # Suppress noisy loggers
    # In non-verbose mode, set to ERROR to hide IntegrityError savepoint rollback warnings
    # These are expected during normal operation (e.g., duplicate former_name conflicts)
    noisy_loggers = [
        "work_data_hub.infrastructure.enrichment",
        "work_data_hub.infrastructure.enrichment.eqc_provider",
        "work_data_hub.infrastructure.enrichment.repository",
        "work_data_hub.io.connectors.eqc",
        "httpx",
        "httpcore",
    ]
    level = logging.DEBUG if verbose else logging.ERROR
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(level)


@dataclass
class ProcessResult:
    """Result of processing a single keyword."""

    keyword: str
    success: bool
    source: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    match_type: Optional[str] = None
    former_names_count: int = 0
    error_message: Optional[str] = None


@dataclass
class ProcessReport:
    """Summary report of all processing."""

    total_keywords: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    base_info_writes: int = 0
    customer_name_writes: int = 0
    former_name_writes: int = 0
    search_key_word_updates: int = 0
    results: List[ProcessResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


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
        print("⚠️  No EQC token configured.")
        return _refresh_token()

    print("🔑 Validating EQC token...")
    if validate_eqc_token(token, base_url):
        print("✅ Token is valid.")
        return True

    print("⚠️  Token is expired or invalid.")
    return _refresh_token()


def _refresh_token() -> bool:
    """
    Trigger auto EQC authentication to refresh token.

    Returns:
        True if token refreshed successfully, False otherwise.
    """
    import os

    print("🔄 Starting automatic token refresh...")
    print("📱 Please scan the QR code when the window appears.\n")

    try:
        from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr

        new_token = run_get_token_auto_qr(save_to_env=True)

        if new_token:
            print("\n✅ Token refreshed successfully.")
            # Update environment variable so get_settings() picks up new token
            os.environ["WDH_EQC_TOKEN"] = new_token
            # Clear settings cache to force reload with new token
            from work_data_hub.config.settings import get_settings

            get_settings.cache_clear()
            return True
        else:
            print("\n❌ Token refresh failed.")
            return False
    except Exception as e:
        print(f"\n❌ Token refresh error: {e}")
        return False


def load_unfound_keywords(
    limit: Optional[int] = None, source: Optional[str] = None
) -> List[Tuple[str, str]]:
    """
    Load keywords where search_result=false from enterprise.search_key_word table.

    Args:
        limit: Maximum number of keywords to load.
        source: Filter by source column (optional).

    Returns:
        List of (key_word, source) tuples.
    """
    from sqlalchemy import create_engine, text

    from work_data_hub.config.settings import get_settings

    settings = get_settings()
    engine = create_engine(settings.get_database_connection_string())

    with engine.connect() as conn:
        query_str = """
            SELECT key_word, COALESCE(source, 'unknown') as source
            FROM enterprise.search_key_word
            WHERE search_result = false
        """

        params = {}
        if source:
            query_str += " AND source = :source"
            params["source"] = source
        if limit:
            query_str += " LIMIT :limit"
            params["limit"] = limit

        result = conn.execute(text(query_str), params)
        keywords = [(row[0], row[1]) for row in result.fetchall()]

    print(f"📦 Loaded {len(keywords)} un-found keywords from search_key_word")
    return keywords


def update_search_key_word_found(
    connection, key_word: str, search_result: bool, match_type: Optional[str]
) -> bool:
    """
    Update found and type fields in search_key_word table.

    Args:
        connection: Database connection.
        key_word: The keyword to update.
        found: Whether match was found.
        match_type: Type of match (from base_info.type).

    Returns:
        True if update successful, False otherwise.
    """
    from sqlalchemy import text

    try:
        connection.execute(
            text("""
                UPDATE enterprise.search_key_word
                SET search_result = :search_result, type = :type
                WHERE key_word = :key_word
            """),
            {"search_result": search_result, "type": match_type, "key_word": key_word},
        )
        return True
    except Exception as e:
        print(f"    ⚠️  Failed to update search_key_word: {e}")
        return False


def verify_base_info(connection, company_id: str) -> dict:
    """
    Check if base_info record exists for company_id.

    Args:
        connection: Database connection.
        company_id: Company ID to check.

    Returns:
        Dictionary with base_info record details.
    """
    from sqlalchemy import text

    result = connection.execute(
        text("""
            SELECT company_id, search_key_word, company_full_name,
                   company_former_name, type, raw_data IS NOT NULL as has_raw_data,
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
            "type": row[4],
            "has_raw_data": row[5],
            "has_raw_business_info": row[6],
        }
    return {"exists": False}


def verify_enrichment_index(connection, company_id: str) -> dict:
    """
    Check enrichment_index records for company_id.

    Args:
        connection: Database connection.
        company_id: Company ID to check.

    Returns:
        Dictionary with enrichment_index record counts.
    """
    from sqlalchemy import text

    # Check customer_name record
    customer_name_result = connection.execute(
        text("""
            SELECT COUNT(*) as count
            FROM enterprise.enrichment_index
            WHERE company_id = :company_id AND lookup_type = 'customer_name'
        """),
        {"company_id": company_id},
    )
    customer_name_count = customer_name_result.fetchone()[0]

    # Check former_name records
    former_name_result = connection.execute(
        text("""
            SELECT COUNT(*) as count
            FROM enterprise.enrichment_index
            WHERE company_id = :company_id AND lookup_type = 'former_name'
        """),
        {"company_id": company_id},
    )
    former_name_count = former_name_result.fetchone()[0]

    return {
        "customer_name_count": customer_name_count,
        "former_name_count": former_name_count,
    }


def process_keywords(
    keywords: List[Tuple[str, str]],
    dry_run: bool = False,
    batch_size: Optional[int] = None,
    quiet: bool = False,
) -> ProcessReport:
    """
    Process un-found keywords with EQC queries.

    Args:
        keywords: List of (key_word, source) tuples.
        dry_run: If True, only print what would be done.
        batch_size: Process in batches of this size.
        quiet: If True, minimal output.

    Returns:
        ProcessReport with all results.
    """
    from sqlalchemy import create_engine

    from work_data_hub.config.settings import get_settings
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

    settings = get_settings()
    report = ProcessReport(total_keywords=len(keywords), start_time=datetime.now())

    if dry_run:
        print("\n🔍 DRY-RUN MODE - Would process the following keywords:")
        for i, (kw, src) in enumerate(keywords, 1):
            print(f"  {i}. [{src}] {kw}")
        print("\n⚠️  No actual queries will be made.")
        return report

    # Initialize database connection
    engine = create_engine(settings.get_database_connection_string())
    connection = engine.connect()
    repository = CompanyMappingRepository(connection)

    # Initialize EQC provider
    # Budget = keyword count + 5 (use --limit to control indirectly)
    effective_budget = len(keywords) + 5
    provider = EqcProvider(
        mapping_repository=repository,
        budget=effective_budget,
    )

    if not provider.is_available:
        print("❌ EQC provider is not available. Check token configuration.")
        connection.close()
        return report

    if not quiet:
        print(f"\n🚀 EQC Provider initialized (budget: {effective_budget})")
        print(f"📊 Processing {len(keywords)} keywords...\n")

    # Process in batches if specified
    if batch_size and batch_size < len(keywords):
        batches = [
            keywords[i : i + batch_size] for i in range(0, len(keywords), batch_size)
        ]
        if not quiet:
            print(f"🔄 Processing in {len(batches)} batches of {batch_size}\n")
    else:
        batches = [keywords]

    for batch_idx, batch in enumerate(batches, 1):
        if len(batches) > 1 and not quiet:
            print(f"📍 Batch {batch_idx}/{len(batches)}:")

        for i, (keyword, source) in enumerate(batch, 1):
            global_idx = sum(len(b) for b in batches[: batch_idx - 1]) + i
            if not quiet:
                print(f"[{global_idx}/{len(keywords)}] [{source}] {keyword}")

            result = ProcessResult(keyword=keyword, source=source, success=False)

            try:
                # Execute EQC lookup
                company_info = provider.lookup(keyword)

                if company_info is None:
                    result.error_message = "Not found in EQC"
                    report.failed_queries += 1
                    if not quiet:
                        print("  ❌ Not found")
                else:
                    result.success = True
                    result.company_id = company_info.company_id
                    result.company_name = company_info.official_name
                    report.successful_queries += 1
                    if not quiet:
                        print(
                            f"  ✅ Found: {company_info.company_id} - {company_info.official_name}"
                        )

                    # Commit to persist cached data
                    connection.commit()

                    # Verify base_info persistence
                    base_info = verify_base_info(connection, company_info.company_id)
                    if base_info["exists"]:
                        result.match_type = base_info.get("type")
                        report.base_info_writes += 1
                        if base_info.get("company_former_name"):
                            result.former_names_count = len(
                                base_info["company_former_name"].split(",")
                            )
                            report.former_name_writes += result.former_names_count
                        if not quiet:
                            print(
                                f"     📝 base_info: {result.match_type} (former_names: {result.former_names_count})"
                            )
                    elif not quiet:
                        print("     ⚠️  base_info: NOT FOUND")

                    # Verify enrichment_index
                    enrichment = verify_enrichment_index(
                        connection, company_info.company_id
                    )

                    if enrichment["customer_name_count"] > 0:
                        report.customer_name_writes += 1
                        if not quiet:
                            print(
                                f"     🔗 enrichment_index (customer_name): {enrichment['customer_name_count']} records"
                            )

                    if enrichment["former_name_count"] > 0 and not quiet:
                        print(
                            f"     🔗 enrichment_index (former_name): {enrichment['former_name_count']} records"
                        )

                    # Update search_key_word table
                    if update_search_key_word_found(
                        connection,
                        keyword,
                        search_result=True,
                        match_type=result.match_type,
                    ):
                        report.search_key_word_updates += 1
                        if not quiet:
                            print("     ✅ Updated search_key_word: found=true")

            except Exception as e:
                result.error_message = str(e)
                report.failed_queries += 1
                print(f"  ❌ Error: {e}")  # Always show errors

            report.results.append(result)
            if not quiet:
                print()

        # Commit after each batch
        connection.commit()

    # Cleanup
    connection.close()
    report.end_time = datetime.now()

    return report


def print_progress_bar(current: int, total: int, width: int = 40) -> None:
    """Print a progress bar."""
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    percent = 100.0 * current / total
    print(f"\r[{bar}] {percent:.1f}% ({current}/{total})", end="", flush=True)


def print_summary(report: ProcessReport) -> None:
    """Print processing summary with rich formatting."""
    print("\n" + "=" * 70)
    print("📊 PROCESSING SUMMARY")
    print("=" * 70)

    # Time stats
    if report.start_time and report.end_time:
        duration = (report.end_time - report.start_time).total_seconds()
        print(f"⏱️  Duration: {duration:.2f} seconds")

    print("\n📈 Statistics:")
    print(f"  Total keywords:      {report.total_keywords:,}")
    print(
        f"  ✅ Successful:       {report.successful_queries:,} ({100 * report.successful_queries / report.total_keywords:.1f}%)"
    )
    print(
        f"  ❌ Failed:           {report.failed_queries:,} ({100 * report.failed_queries / report.total_keywords:.1f}%)"
    )

    print("\n📝 Data Writes:")
    print(f"  base_info writes:           {report.base_info_writes:,}")
    print(f"  customer_name writes:       {report.customer_name_writes:,}")
    print(f"  former_name writes:         {report.former_name_writes:,}")
    print(f"  search_key_word updates:    {report.search_key_word_updates:,}")

    # Success criteria
    success = (
        report.successful_queries > 0
        and report.base_info_writes == report.successful_queries
        and report.search_key_word_updates == report.successful_queries
    )

    print("\n" + "=" * 70)
    if success:
        print("✅ PROCESSING COMPLETED SUCCESSFULLY")
        if report.former_name_writes > 0:
            print(
                f"   🎉 former_name feature working ({report.former_name_writes} records)"
            )
        remaining = report.total_keywords - report.search_key_word_updates
        if remaining > 0:
            print(f"   📌 {remaining:,} keywords still need processing")
    else:
        print("❌ PROCESSING HAD ISSUES")
        if report.base_info_writes < report.successful_queries:
            print("   ⚠️  Some base_info writes failed")
        if report.search_key_word_updates < report.successful_queries:
            print("   ⚠️  Some search_key_word updates failed")
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process un-found keywords in search_key_word table using EQC queries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of keywords to process (default: all)",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["name", "search_key_word", "规模明细"],
        default=None,
        help="Filter by source (default: all sources)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Process in batches of this size (default: no batching)",
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
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed logging output (JSON logs)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (only errors and final summary)",
    )

    args = parser.parse_args()

    # Configure logging based on verbosity
    configure_logging(verbose=args.verbose)

    if not args.quiet:
        print("=" * 70)
        print("🔍 EQC Keyword Processing - Un-found Keywords")
        print("=" * 70)

    # Validate and refresh token if needed
    if not args.dry_run and not args.skip_token_check:
        if not validate_and_refresh_token():
            print("\n❌ Cannot proceed without valid EQC token.")
            sys.exit(1)
        if not args.quiet:
            print()  # Add spacing

    # Load keywords
    keywords = load_unfound_keywords(limit=args.limit, source=args.source)

    if not keywords:
        print("\n✅ No un-found keywords to process!")
        print("🎉 All keywords have been processed.")
        sys.exit(0)

    # Show breakdown by source
    if not args.quiet:
        from collections import Counter

        source_counts = Counter(source for _, source in keywords)
        print("\n📊 Keywords by source:")
        for source, count in sorted(source_counts.items()):
            print(f"  {source}: {count:,}")

    # Run processing
    report = process_keywords(
        keywords, dry_run=args.dry_run, batch_size=args.batch_size, quiet=args.quiet
    )

    if not args.dry_run:
        print_summary(report)


if __name__ == "__main__":
    main()
