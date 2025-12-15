"""
Batch EQC Validation Script

Purpose: Validate enterprise data by querying EQC API with search_key_word
from archive_base_info records where for_check=true.

Usage:
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/batch_eqc_validation.py

Options:
    --limit N       Limit to first N records (default: all)
    --batch-size N  Batch size for processing (default: 10)
    --dry-run       Preview only, don't persist results
    --delay SECONDS Delay between API calls (default: 1.0)
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from work_data_hub.config.settings import get_settings
from work_data_hub.io.connectors.eqc_client import (
    EQCClient,
    EQCClientError,
    EQCAuthenticationError,
    EQCNotFoundError,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationRecord:
    """Record from archive_base_info for validation."""
    company_id: str
    search_key_word: str
    company_full_name: Optional[str]
    unite_code: Optional[str]


@dataclass
class ValidationResult:
    """Result of a single validation."""
    archive_company_id: str
    search_key_word: str
    archive_company_name: Optional[str]
    archive_unite_code: Optional[str]

    # API results
    api_success: bool = False
    api_company_id: Optional[str] = None
    api_company_name: Optional[str] = None
    api_unite_code: Optional[str] = None
    api_results_count: int = 0

    # Matching analysis
    company_id_match: bool = False
    company_name_match: bool = False
    unite_code_match: bool = False

    # Error info
    error_message: Optional[str] = None

    def analyze_match(self):
        """Analyze if API results match archive data."""
        if not self.api_success:
            return

        # Company ID match
        self.company_id_match = (
            self.api_company_id is not None and
            str(self.archive_company_id) == str(self.api_company_id)
        )

        # Company name match (partial match)
        if self.api_company_name and self.archive_company_name:
            self.company_name_match = (
                self.archive_company_name in self.api_company_name or
                self.api_company_name in self.archive_company_name or
                self.archive_company_name == self.api_company_name
            )

        # Unite code match (exact)
        if self.api_unite_code and self.archive_unite_code:
            self.unite_code_match = (
                self.archive_unite_code == self.api_unite_code
            )


@dataclass
class ValidationSummary:
    """Summary of batch validation."""
    total_records: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    company_id_matches: int = 0
    company_name_matches: int = 0
    unite_code_matches: int = 0
    no_results: int = 0
    errors: List[str] = field(default_factory=list)


def fetch_validation_records(
    connection: Connection,
    limit: Optional[int] = None
) -> List[ValidationRecord]:
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
        records.append(ValidationRecord(
            company_id=row[0],
            search_key_word=row[1],
            company_full_name=row[2],
            unite_code=row[3],
        ))

    return records


def validate_single_record(
    client: EQCClient,
    record: ValidationRecord,
) -> ValidationResult:
    """Validate a single record against EQC API."""

    result = ValidationResult(
        archive_company_id=record.company_id,
        search_key_word=record.search_key_word,
        archive_company_name=record.company_full_name,
        archive_unite_code=record.unite_code,
    )

    try:
        # Search using search_key_word
        search_results = client.search_company(record.search_key_word)

        result.api_results_count = len(search_results)

        if search_results:
            top_result = search_results[0]
            result.api_success = True
            result.api_company_id = top_result.company_id
            result.api_company_name = top_result.official_name
            result.api_unite_code = getattr(top_result, 'unite_code', None)

            # Analyze matches
            result.analyze_match()
        else:
            result.api_success = True  # API worked but no results
            result.error_message = "No results found"

    except EQCAuthenticationError as e:
        result.error_message = f"Auth error: {e}"
        raise  # Re-raise to stop batch processing

    except EQCNotFoundError:
        result.api_success = True
        result.error_message = "Not found (404)"

    except EQCClientError as e:
        result.error_message = f"API error: {e}"

    except Exception as e:
        result.error_message = f"Unexpected error: {type(e).__name__}: {e}"

    return result


def print_result(result: ValidationResult, index: int):
    """Print a single validation result."""
    status_icon = "✅" if result.api_success else "❌"

    print(f"\n[{index}] {status_icon} {result.search_key_word}")
    print(f"    Archive: company_id={result.archive_company_id}")
    print(f"    Archive: name={result.archive_company_name}")
    print(f"    Archive: unite_code={result.archive_unite_code}")

    if result.api_success and result.api_results_count > 0:
        print(f"    API Results: {result.api_results_count}")
        print(f"    API Top: company_id={result.api_company_id}")
        print(f"    API Top: name={result.api_company_name}")
        print(f"    API Top: unite_code={result.api_unite_code}")
        print(f"    Match: ID={result.company_id_match}, Name={result.company_name_match}, Code={result.unite_code_match}")
    elif result.error_message:
        print(f"    Error: {result.error_message}")


def print_summary(summary: ValidationSummary):
    """Print validation summary."""
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Records:        {summary.total_records}")
    print(f"Successful Queries:   {summary.successful_queries}")
    print(f"Failed Queries:       {summary.failed_queries}")
    print(f"No Results:           {summary.no_results}")
    print()
    print(f"Company ID Matches:   {summary.company_id_matches} / {summary.successful_queries}")
    print(f"Company Name Matches: {summary.company_name_matches} / {summary.successful_queries}")
    print(f"Unite Code Matches:   {summary.unite_code_matches} / {summary.successful_queries}")

    if summary.errors:
        print("\nErrors:")
        for err in summary.errors[:10]:
            print(f"  - {err}")
        if len(summary.errors) > 10:
            print(f"  ... and {len(summary.errors) - 10} more")

    print("=" * 70)


def save_results_to_db(
    connection: Connection,
    results: List[ValidationResult],
    dry_run: bool = False,
) -> int:
    """
    Save validation results to a new table for analysis.

    Returns number of records saved.
    """
    if dry_run:
        print("\n[DRY RUN] Would save results to database")
        return 0

    # Create results table if not exists
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS enterprise.validation_results (
            id SERIAL PRIMARY KEY,
            validated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            archive_company_id VARCHAR(255) NOT NULL,
            search_key_word VARCHAR(500),
            archive_company_name VARCHAR(500),
            archive_unite_code VARCHAR(50),
            api_success BOOLEAN,
            api_company_id VARCHAR(255),
            api_company_name VARCHAR(500),
            api_unite_code VARCHAR(50),
            api_results_count INTEGER,
            company_id_match BOOLEAN,
            company_name_match BOOLEAN,
            unite_code_match BOOLEAN,
            error_message TEXT
        )
    """))
    connection.commit()

    saved = 0
    for r in results:
        connection.execute(text("""
            INSERT INTO enterprise.validation_results (
                archive_company_id, search_key_word, archive_company_name, archive_unite_code,
                api_success, api_company_id, api_company_name, api_unite_code, api_results_count,
                company_id_match, company_name_match, unite_code_match, error_message
            ) VALUES (
                :archive_company_id, :search_key_word, :archive_company_name, :archive_unite_code,
                :api_success, :api_company_id, :api_company_name, :api_unite_code, :api_results_count,
                :company_id_match, :company_name_match, :unite_code_match, :error_message
            )
        """), {
            'archive_company_id': r.archive_company_id,
            'search_key_word': r.search_key_word,
            'archive_company_name': r.archive_company_name,
            'archive_unite_code': r.archive_unite_code,
            'api_success': r.api_success,
            'api_company_id': r.api_company_id,
            'api_company_name': r.api_company_name,
            'api_unite_code': r.api_unite_code,
            'api_results_count': r.api_results_count,
            'company_id_match': r.company_id_match,
            'company_name_match': r.company_name_match,
            'unite_code_match': r.unite_code_match,
            'error_message': r.error_message,
        })
        saved += 1

    connection.commit()
    return saved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch EQC validation for archive_base_info records"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit to first N records"
    )
    parser.add_argument(
        "--batch-size", type=int, default=10,
        help="Batch size for progress reporting"
    )
    parser.add_argument(
        "--delay", type=float, default=1.0,
        help="Delay between API calls in seconds"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview only, don't save results"
    )
    parser.add_argument(
        "--save-results", action="store_true",
        help="Save results to database table"
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
        print("  PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.io.auth --capture --save")
        return 1

    # Run validation
    try:
        with engine.connect() as connection:
            # Fetch records
            print("📋 Fetching validation records from archive_base_info...")
            records = fetch_validation_records(connection, limit=args.limit)

            if not records:
                print("⚠️ No records found with for_check=true")
                return 0

            print(f"   Found {len(records)} records to validate")

            if args.dry_run:
                print("\n[DRY RUN MODE] - Will not save results")

            # Initialize summary
            summary = ValidationSummary(total_records=len(records))
            results: List[ValidationResult] = []

            print("\n" + "=" * 70)
            print("STARTING BATCH VALIDATION")
            print("=" * 70)

            # Process each record
            for idx, record in enumerate(records, 1):
                try:
                    result = validate_single_record(client, record)
                    results.append(result)

                    # Update summary
                    if result.api_success:
                        summary.successful_queries += 1
                        if result.api_results_count == 0:
                            summary.no_results += 1
                        else:
                            if result.company_id_match:
                                summary.company_id_matches += 1
                            if result.company_name_match:
                                summary.company_name_matches += 1
                            if result.unite_code_match:
                                summary.unite_code_matches += 1
                    else:
                        summary.failed_queries += 1
                        if result.error_message:
                            summary.errors.append(f"{record.search_key_word}: {result.error_message}")

                    # Print result
                    print_result(result, idx)

                    # Rate limiting delay
                    if idx < len(records):
                        time.sleep(args.delay)

                    # Progress reporting
                    if idx % args.batch_size == 0:
                        print(f"\n📊 Progress: {idx}/{len(records)} processed")

                except EQCAuthenticationError:
                    print("\n❌ Token expired during validation!")
                    print("Please update your EQC token and resume.")
                    break

                except KeyboardInterrupt:
                    print("\n\n⚠️ Interrupted by user")
                    break

            # Print summary
            print_summary(summary)

            # Save results if requested
            if args.save_results:
                saved = save_results_to_db(connection, results, args.dry_run)
                print(f"\n💾 Saved {saved} results to enterprise.validation_results")

            return 0 if summary.failed_queries == 0 else 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.error("batch_validation.error", error=str(e), error_type=type(e).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
