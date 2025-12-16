#!/usr/bin/env python
"""
Legacy Data Migration to Enrichment Index (Story 6.1.4).

Migrates data from legacy tables to enterprise.enrichment_index:
- legacy.company_id_mapping (~19,141 rows) -> customer_name lookups
- legacy.eqc_search_result (~11,820 rows) -> customer_name lookups

Usage:
    # Dry run (no actual inserts)
    PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --dry-run

    # Full migration with verbose logging
    PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --verbose

    # Custom batch size
    PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --batch-size 500

    # Rollback (delete all legacy_migration records)
    PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --rollback

    # Force rollback without confirmation
    PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --rollback --force

Architecture Reference:
- Story 6.1.4: Legacy Data Migration to Enrichment Index
- Uses existing insert_enrichment_index_batch() from Story 6.1.1
- Uses normalize_for_temp_id() for consistent cache hits
"""

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Generator, List, Optional

import structlog
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.engine import Connection

from sqlalchemy import create_engine

from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
)
from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
from work_data_hub.infrastructure.enrichment.types import (
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)

logger = structlog.get_logger(__name__)


def create_engine_from_env():
    """Create SQLAlchemy engine for TARGET database from .wdh_env.
    
    Uses WDH_DATABASE__URI (canonical) from .wdh_env file.
    All database configuration is centralized in .wdh_env.
    """
    import os

    database_url = os.environ.get("WDH_DATABASE__URI")
    if not database_url:
        raise ValueError(
            "WDH_DATABASE__URI environment variable is required (from .wdh_env). "
            "Example: postgres://user:pass@localhost:5432/postgres"
        )
    # Fix for SQLAlchemy compatibility (postgres:// is deprecated)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return create_engine(database_url)


def create_legacy_engine_from_env():
    """Create SQLAlchemy engine for LEGACY database from .wdh_env.
    
    Uses LEGACY_DATABASE__URI (canonical) from .wdh_env file.
    Falls back to target database if not set (single-DB mode).
    """
    import os

    legacy_url = os.environ.get("LEGACY_DATABASE__URI")
    if legacy_url:
        # Fix for SQLAlchemy compatibility
        if legacy_url.startswith("postgres://"):
            legacy_url = legacy_url.replace("postgres://", "postgresql://", 1)
        return create_engine(legacy_url)
    
    # Fall back to target database if legacy URL is not set (single-DB mode)
    return create_engine_from_env()


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class LegacyMigrationConfig:
    """Configuration for legacy data migration."""

    batch_size: int = 1000
    progress_interval: int = 5000
    dry_run: bool = False
    verbose: bool = False
    perform_preflight: bool = True
    report_path: Optional[Path] = None

    # Source tables (updated for PostgreSQL migration: legacy tables now in 'enterprise' schema)
    company_id_mapping_table: str = "enterprise.company_id_mapping"
    eqc_search_result_table: str = "enterprise.eqc_search_result"

    # Confidence mapping
    confidence_current: Decimal = field(default_factory=lambda: Decimal("1.00"))
    confidence_former: Decimal = field(default_factory=lambda: Decimal("0.90"))
    confidence_eqc_success: Decimal = field(default_factory=lambda: Decimal("1.00"))


# =============================================================================
# Migration Report
# =============================================================================


@dataclass
class MigrationReport:
    """Report for a single source table migration."""

    source_table: str
    total_read: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    skipped_reasons: Dict[str, int] = field(default_factory=dict)
    errors: int = 0
    sample_records: List[Dict] = field(default_factory=list)

    def add_skipped(self, reason: str) -> None:
        """Track skipped record with reason."""
        self.skipped += 1
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            "source_table": self.source_table,
            "total_read": self.total_read,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "skipped_reasons": self.skipped_reasons,
            "errors": self.errors,
        }


@dataclass
class FullMigrationReport:
    """Aggregated report for full migration."""

    reports: List[MigrationReport] = field(default_factory=list)
    dry_run: bool = False
    runtime_seconds: float = 0.0
    preflight_summary: Optional[Dict[str, str]] = None

    @property
    def total_read(self) -> int:
        return sum(r.total_read for r in self.reports)

    @property
    def total_inserted(self) -> int:
        return sum(r.inserted for r in self.reports)

    @property
    def total_updated(self) -> int:
        return sum(r.updated for r in self.reports)

    @property
    def total_skipped(self) -> int:
        return sum(r.skipped for r in self.reports)

    @property
    def total_errors(self) -> int:
        return sum(r.errors for r in self.reports)

    def add_report(self, report: MigrationReport) -> None:
        """Add a source table report."""
        self.reports.append(report)

    def print_summary(self) -> None:
        """Print human-readable summary."""
        print("\n" + "=" * 70)
        print("LEGACY DATA MIGRATION REPORT")
        if self.dry_run:
            print(">>> DRY RUN MODE - No data was actually inserted <<<")
        print("=" * 70)

        for report in self.reports:
            print(f"\nSource: {report.source_table}")
            print(f"  Total Read:  {report.total_read:,}")
            print(f"  Inserted:    {report.inserted:,}")
            print(f"  Updated:     {report.updated:,}")
            print(f"  Skipped:     {report.skipped:,}")
            if report.skipped_reasons:
                for reason, count in report.skipped_reasons.items():
                    print(f"    - {reason}: {count:,}")
            print(f"  Errors:      {report.errors:,}")

            if report.sample_records:
                print(f"\n  Sample Records (first 5):")
                for i, rec in enumerate(report.sample_records[:5], 1):
                    print(f"    {i}. {rec['lookup_key'][:40]}... -> {rec['company_id']}")

        print("\n" + "-" * 70)
        print("TOTALS:")
        print(f"  Total Read:     {self.total_read:,}")
        print(f"  Total Inserted: {self.total_inserted:,}")
        print(f"  Total Updated:  {self.total_updated:,}")
        print(f"  Total Skipped:  {self.total_skipped:,}")
        print(f"  Total Errors:   {self.total_errors:,}")
        print("=" * 70 + "\n")


# =============================================================================
# Migration Functions
# =============================================================================


def _fetch_company_id_mapping(
    connection: Connection,
    table: str,
    batch_size: int,
) -> Generator[Dict, None, None]:
    """
    Fetch records from legacy.company_id_mapping with pagination.

    Orders by type='current' first to ensure higher confidence records
    are processed first (for deduplication).
    """
    query = text(f"""
        SELECT company_name, company_id, type
        FROM {table}
        WHERE company_id IS NOT NULL
          AND company_name IS NOT NULL
          AND TRIM(company_name) != ''
          AND TRIM(company_id) != ''
        ORDER BY CASE WHEN type = 'current' THEN 0 ELSE 1 END, id
    """)

    result = connection.execute(query)
    for row in result:
        yield {
            "company_name": row[0],
            "company_id": row[1],
            "type": row[2],
        }


def _fetch_eqc_search_result(
    connection: Connection,
    table: str,
    batch_size: int,
) -> Generator[Dict, None, None]:
    """
    Fetch successful records from legacy.eqc_search_result.

    Only migrates records where result='Success' and company_id is not null.
    """
    query = text(f"""
        SELECT key_word, company_id
        FROM {table}
        WHERE result = 'Success'
          AND company_id IS NOT NULL
          AND key_word IS NOT NULL
          AND TRIM(key_word) != ''
          AND TRIM(company_id) != ''
    """)

    result = connection.execute(query)
    for row in result:
        yield {
            "key_word": row[0],
            "company_id": row[1],
        }


def _estimate_conflicts(
    connection: Connection, records: List[EnrichmentIndexRecord]
) -> int:
    """
    Estimate how many records will hit ON CONFLICT based on existing rows.
    """
    if not records:
        return 0

    lookup_keys = [r.lookup_key for r in records]
    lookup_types = [r.lookup_type.value for r in records]

    conflict_query = text(
        """
        SELECT COUNT(*) AS conflict_count
        FROM enterprise.enrichment_index ei
        JOIN unnest(:lookup_keys, :lookup_types) AS t(lookup_key, lookup_type)
          ON ei.lookup_key = t.lookup_key
         AND ei.lookup_type = t.lookup_type
        """
    ).bindparams(
        bindparam("lookup_keys", type_=ARRAY(TEXT())),
        bindparam("lookup_types", type_=ARRAY(TEXT())),
    )
    result = connection.execute(conflict_query, {"lookup_keys": lookup_keys, "lookup_types": lookup_types})
    return int(result.scalar() or 0)


def _run_preflight_checks(connection: Connection) -> Dict[str, str]:
    """
    Run compatibility checks before migration (AC11).
    """
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10+ is required for this migration.")

    summary: Dict[str, str] = {}

    pg_version_query = text("SHOW server_version_num;")
    pg_version_num = int(connection.execute(pg_version_query).scalar() or 0)
    if pg_version_num < 140000:
        raise RuntimeError("PostgreSQL 14+ is required for this migration.")
    summary["postgres_version_num"] = str(pg_version_num)

    table_exists_query = text(
        "SELECT to_regclass('enterprise.enrichment_index') IS NOT NULL;"
    )
    if not connection.execute(table_exists_query).scalar():
        raise RuntimeError("Table enterprise.enrichment_index does not exist.")
    summary["table"] = "enterprise.enrichment_index"

    columns_query = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'enterprise'
          AND table_name = 'enrichment_index'
          AND column_name IN ('lookup_key', 'lookup_type', 'company_id', 'confidence', 'hit_count');
        """
    )
    columns = {row[0] for row in connection.execute(columns_query)}
    required_columns = {
        "lookup_key",
        "lookup_type",
        "company_id",
        "confidence",
        "hit_count",
    }
    if not required_columns.issubset(columns):
        missing = required_columns - columns
        raise RuntimeError(
            f"Missing required columns in enterprise.enrichment_index: {missing}"
        )

    index_query = text(
        """
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'enterprise'
          AND tablename = 'enrichment_index'
          AND indexdef ILIKE '%(lookup_key, lookup_type)%'
        LIMIT 1;
        """
    )
    if not connection.execute(index_query).scalar():
        raise RuntimeError(
            "Unique index on (lookup_key, lookup_type) is required for ON CONFLICT."
        )
    summary["unique_index"] = "(lookup_key, lookup_type)"
    summary["python_version"] = sys.version.split()[0]
    return summary


def _default_report_path() -> Path:
    """Compute default validation report path under sprint artifacts."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path("docs/sprint-artifacts/stories") / f"validation-report-{timestamp}.md"


def _deduplicate_records(
    records: List[EnrichmentIndexRecord],
) -> tuple[List[EnrichmentIndexRecord], Dict[tuple, int]]:
    """
    Deduplicate records within a batch to avoid ON CONFLICT multiple hits in one insert.

    Keeps highest confidence per (lookup_key, lookup_type); if tie, keeps first.
    Returns extra_hits mapping for duplicates (count minus one) to optionally
    increment hit_count after insert.
    """
    deduped: Dict[tuple, EnrichmentIndexRecord] = {}
    extra_hits: Dict[tuple, int] = {}
    for r in records:
        key = (r.lookup_type, r.lookup_key)
        existing = deduped.get(key)
        if not existing or float(r.confidence) > float(existing.confidence):
            deduped[key] = r
            extra_hits[key] = extra_hits.get(key, 0)
        else:
            extra_hits[key] = extra_hits.get(key, 0) + 1
    return list(deduped.values()), extra_hits


def _write_validation_report(
    full_report: FullMigrationReport,
    report_path: Path,
    runtime_seconds: float,
    preflight_summary: Optional[Dict[str, str]] = None,
) -> None:
    """Write validation report summarizing migration results (AC6)."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def _format_samples(report: MigrationReport) -> str:
        if not report.sample_records:
            return "None"
        lines = []
        for rec in report.sample_records[:5]:
            lines.append(
                f"- `{rec['lookup_key']}` -> `{rec['company_id']}` (confidence={rec.get('confidence', '')})"
            )
        return "\n".join(lines)

    throughput = full_report.total_read / runtime_seconds if runtime_seconds else 0

    lines = [
        "# Validation Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Dry Run:** {full_report.dry_run}",
        f"**Runtime (s):** {runtime_seconds:.2f}",
        f"**Throughput (rows/s):** {throughput:.2f}",
        "",
        "## Preflight",
    ]
    if preflight_summary:
        for k, v in preflight_summary.items():
            lines.append(f"- **{k}**: {v}")
    else:
        lines.append("- (skipped)")

    lines.extend(
        [
            "",
            "## Totals",
            f"- Total Read: {full_report.total_read}",
            f"- Inserted: {full_report.total_inserted}",
            f"- Updated: {full_report.total_updated}",
            f"- Skipped: {full_report.total_skipped}",
            f"- Errors: {full_report.total_errors}",
            "",
            "## Sources",
        ]
    )

    for report in full_report.reports:
        lines.extend(
            [
                f"### {report.source_table}",
                f"- Read: {report.total_read}",
                f"- Inserted: {report.inserted}",
                f"- Updated: {report.updated}",
                f"- Skipped: {report.skipped}",
                f"- Errors: {report.errors}",
                f"- Sample:\n{_format_samples(report)}",
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(
        "migration.validation_report.saved",
        report_path=str(report_path),
    )


def migrate_company_id_mapping(
    connection: Connection,
    repo: CompanyMappingRepository,
    config: LegacyMigrationConfig,
) -> MigrationReport:
    """
    Migrate legacy.company_id_mapping to enrichment_index.

    Transformation:
    - company_name -> normalized lookup_key
    - lookup_type = customer_name (DB-P4)
    - type='current' -> confidence=1.00
    - type='former' -> confidence=0.90
    - source = legacy_migration
    """
    report = MigrationReport(source_table=config.company_id_mapping_table)
    records: List[EnrichmentIndexRecord] = []

    logger.info(
        "migration.company_id_mapping.starting",
        table=config.company_id_mapping_table,
        batch_size=config.batch_size,
        dry_run=config.dry_run,
    )

    for row in _fetch_company_id_mapping(
        connection, config.company_id_mapping_table, config.batch_size
    ):
        report.total_read += 1

        # Normalize lookup key
        normalized = normalize_for_temp_id(row["company_name"])
        if not normalized:
            report.add_skipped("empty_after_normalization")
            continue

        # Map confidence based on type
        row_type = (row.get("type") or "").lower()
        confidence = (
            config.confidence_current
            if row_type == "current"
            else config.confidence_former
        )

        record = EnrichmentIndexRecord(
            lookup_key=normalized,
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id=row["company_id"].strip(),
            confidence=confidence,
            source=SourceType.LEGACY_MIGRATION,
            source_table=config.company_id_mapping_table,
        )
        records.append(record)

        # Collect sample records
        if len(report.sample_records) < 10:
            report.sample_records.append(
                {
                    "lookup_key": normalized,
                    "company_id": row["company_id"],
                    "confidence": str(confidence),
                }
            )

        # Batch insert
        if len(records) >= config.batch_size:
            unique_records, extra_hits = _deduplicate_records(records)
            if not config.dry_run:
                result = repo.insert_enrichment_index_batch(unique_records)
                report.inserted += result.inserted_count
                # Increment hit_count for intra-batch duplicates we collapsed
                for key, count in extra_hits.items():
                    for _ in range(count):
                        repo.update_hit_count(key[1], key[0])
            else:
                report.inserted += len(unique_records)
            records = []

            # Progress logging
            if report.total_read % config.progress_interval == 0:
                logger.info(
                    "migration.company_id_mapping.progress",
                    processed=report.total_read,
                    inserted=report.inserted,
                    skipped=report.skipped,
                )

    # Final batch
    if records:
        unique_records, extra_hits = _deduplicate_records(records)
        if not config.dry_run:
            result = repo.insert_enrichment_index_batch(unique_records)
            report.inserted += result.inserted_count
            for key, count in extra_hits.items():
                for _ in range(count):
                    repo.update_hit_count(key[1], key[0])
        else:
            report.inserted += len(unique_records)

    logger.info(
        "migration.company_id_mapping.completed",
        **report.to_dict(),
    )

    return report


def migrate_eqc_search_result(
    connection: Connection,
    repo: CompanyMappingRepository,
    config: LegacyMigrationConfig,
) -> MigrationReport:
    """
    Migrate legacy.eqc_search_result to enrichment_index.

    Transformation:
    - key_word -> normalized lookup_key
    - lookup_type = customer_name (DB-P4)
    - confidence = 1.00 (all successful EQC results)
    - source = legacy_migration
    """
    report = MigrationReport(source_table=config.eqc_search_result_table)
    records: List[EnrichmentIndexRecord] = []

    logger.info(
        "migration.eqc_search_result.starting",
        table=config.eqc_search_result_table,
        batch_size=config.batch_size,
        dry_run=config.dry_run,
    )

    for row in _fetch_eqc_search_result(
        connection, config.eqc_search_result_table, config.batch_size
    ):
        report.total_read += 1

        # Normalize lookup key
        normalized = normalize_for_temp_id(row["key_word"])
        if not normalized:
            report.add_skipped("empty_after_normalization")
            continue

        record = EnrichmentIndexRecord(
            lookup_key=normalized,
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id=row["company_id"].strip(),
            confidence=config.confidence_eqc_success,
            source=SourceType.LEGACY_MIGRATION,
            source_table=config.eqc_search_result_table,
        )
        records.append(record)

        # Collect sample records
        if len(report.sample_records) < 10:
            report.sample_records.append(
                {
                    "lookup_key": normalized,
                    "company_id": row["company_id"],
                    "confidence": str(config.confidence_eqc_success),
                }
            )

        # Batch insert
        if len(records) >= config.batch_size:
            unique_records, extra_hits = _deduplicate_records(records)
            if not config.dry_run:
                result = repo.insert_enrichment_index_batch(unique_records)
                report.inserted += result.inserted_count
                for key, count in extra_hits.items():
                    for _ in range(count):
                        repo.update_hit_count(key[1], key[0])
            else:
                report.inserted += len(unique_records)
            records = []

            # Progress logging
            if report.total_read % config.progress_interval == 0:
                logger.info(
                    "migration.eqc_search_result.progress",
                    processed=report.total_read,
                    inserted=report.inserted,
                    skipped=report.skipped,
                )

    # Final batch
    if records:
        unique_records, extra_hits = _deduplicate_records(records)
        if not config.dry_run:
            result = repo.insert_enrichment_index_batch(unique_records)
            report.inserted += result.inserted_count
            for key, count in extra_hits.items():
                for _ in range(count):
                    repo.update_hit_count(key[1], key[0])
        else:
            report.inserted += len(unique_records)

    logger.info(
        "migration.eqc_search_result.completed",
        **report.to_dict(),
    )

    return report


def rollback_migration(
    connection: Connection,
    force: bool = False,
) -> int:
    """
    Rollback legacy migration by deleting all legacy_migration records.

    Args:
        connection: Database connection.
        force: Skip confirmation prompt.

    Returns:
        Number of records deleted.
    """
    # Count records to delete
    count_query = text("""
        SELECT COUNT(*)
        FROM enterprise.enrichment_index
        WHERE source = 'legacy_migration'
    """)
    count_result = connection.execute(count_query)
    count = count_result.scalar() or 0

    if count == 0:
        print("No legacy_migration records found. Nothing to rollback.")
        return 0

    print(f"\nFound {count:,} records with source='legacy_migration'")

    if not force:
        confirm = input("Are you sure you want to delete these records? [y/N]: ")
        if confirm.lower() != "y":
            print("Rollback cancelled.")
            return 0

    # Delete records
    delete_query = text("""
        DELETE FROM enterprise.enrichment_index
        WHERE source = 'legacy_migration'
    """)
    result = connection.execute(delete_query)
    connection.commit()

    deleted = result.rowcount
    print(f"Deleted {deleted:,} records.")

    logger.info(
        "migration.rollback.completed",
        deleted_count=deleted,
    )

    return deleted


def run_migration(config: LegacyMigrationConfig) -> FullMigrationReport:
    """
    Run the full legacy data migration.

    Supports dual-database mode: reads from Legacy database (LEGACY_DATABASE_URL)
    and writes to target database (DATABASE_URL).

    Args:
        config: Migration configuration.

    Returns:
        Full migration report with all source table reports.
    """
    full_report = FullMigrationReport(dry_run=config.dry_run)

    # Create separate engines for source and target databases
    target_engine = create_engine_from_env()
    legacy_engine = create_legacy_engine_from_env()

    with target_engine.connect() as target_conn, legacy_engine.connect() as legacy_conn:
        preflight_summary: Optional[Dict[str, str]] = None
        if config.perform_preflight:
            preflight_summary = _run_preflight_checks(target_conn)

        start_time = time.perf_counter()
        repo = CompanyMappingRepository(target_conn)

        # Migrate company_id_mapping first (process 'current' before 'former')
        # Read from legacy_conn, write via repo (to target_conn)
        report1 = migrate_company_id_mapping(legacy_conn, repo, config)
        full_report.add_report(report1)

        # Migrate eqc_search_result
        report2 = migrate_eqc_search_result(legacy_conn, repo, config)
        full_report.add_report(report2)

        # Commit if not dry run
        if not config.dry_run:
            target_conn.commit()

        full_report.runtime_seconds = time.perf_counter() - start_time
        full_report.preflight_summary = preflight_summary
        logger.info(
            "migration.completed",
            runtime_seconds=full_report.runtime_seconds,
            total_read=full_report.total_read,
        )

    return full_report



# =============================================================================
# CLI Interface
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy data to enrichment_index table.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (no actual inserts)
  PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --dry-run

  # Full migration with verbose logging
  PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --verbose

  # Custom batch size
  PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --batch-size 500

  # Rollback (delete all legacy_migration records)
  PYTHONPATH=src uv run python scripts/migrations/migrate_legacy_to_enrichment_index.py --rollback
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually inserting data",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of records per batch insert (default: 1000)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Delete all legacy_migration records (rollback)",
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompts (use with --rollback)",
    )

    parser.add_argument(
        "--report-path",
        type=str,
        default=None,
        help=(
            "Path to write validation report "
            "(default: docs/sprint-artifacts/stories/validation-report-<timestamp>.md)"
        ),
    )

    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip preflight validation (not recommended)",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Configure logging
    import logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    if args.rollback:
        # Rollback mode
        engine = create_engine_from_env()
        with engine.connect() as connection:
            rollback_migration(connection, force=args.force)
        return 0

    # Migration mode
    config = LegacyMigrationConfig(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        verbose=args.verbose,
        perform_preflight=not args.skip_preflight,
        report_path=Path(args.report_path)
        if args.report_path
        else _default_report_path(),
    )

    logger.info(
        "migration.starting",
        dry_run=config.dry_run,
        batch_size=config.batch_size,
    )

    try:
        report = run_migration(config)
        report.print_summary()

        if config.report_path:
            _write_validation_report(
                report,
                config.report_path,
                runtime_seconds=report.runtime_seconds,
                preflight_summary=report.preflight_summary,
            )

        if report.total_errors > 0:
            return 1
        return 0

    except Exception as e:
        logger.exception("migration.failed", error=str(e))
        print(f"\nMigration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
