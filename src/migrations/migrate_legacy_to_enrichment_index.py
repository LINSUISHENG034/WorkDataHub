from __future__ import annotations

# Re-export the implementation used by tests.
#
# Tests import `migrations.migrate_legacy_to_enrichment_index` and may or may not
# manipulate `sys.path` to include `scripts/`. Providing this module under `src/`
# keeps imports deterministic when running with `PYTHONPATH=src`.
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, Iterator, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
from work_data_hub.infrastructure.enrichment.types import (
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)


@dataclass
class LegacyMigrationConfig:
    batch_size: int = 1000
    progress_interval: int = 5000
    dry_run: bool = False

    company_id_mapping_table: str = "legacy.company_id_mapping"
    eqc_search_result_table: str = "legacy.eqc_search_result"

    confidence_current: Decimal = field(default_factory=lambda: Decimal("1.00"))
    confidence_former: Decimal = field(default_factory=lambda: Decimal("0.90"))
    confidence_eqc_success: Decimal = field(default_factory=lambda: Decimal("1.00"))


@dataclass
class MigrationReport:
    source_table: str
    total_read: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    skipped_reasons: Dict[str, int] = field(default_factory=dict)
    errors: int = 0
    sample_records: List[Dict[str, Any]] = field(default_factory=list)

    def add_skipped(self, reason: str) -> None:
        self.skipped += 1
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_table": self.source_table,
            "total_read": self.total_read,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "skipped_reasons": dict(self.skipped_reasons),
            "errors": self.errors,
            "sample_records": list(self.sample_records),
        }


@dataclass
class FullMigrationReport:
    dry_run: bool = False
    reports: List[MigrationReport] = field(default_factory=list)

    total_read: int = 0
    total_inserted: int = 0
    total_skipped: int = 0

    def add_report(self, report: MigrationReport) -> None:
        self.reports.append(report)
        self.total_read += report.total_read
        self.total_inserted += report.inserted
        self.total_skipped += report.skipped


def _estimate_conflicts(_connection: Any, _report: MigrationReport) -> int:
    return 0


def _fetch_company_id_mapping(
    connection: Connection, table: str
) -> Iterator[Dict[str, Any]]:
    result = connection.execute(
        text(
            f"""
            SELECT company_name, company_id, unite_code, type
            FROM {table}
            """
        )
    )
    for row in result.mappings():
        yield dict(row)


def _fetch_eqc_search_result(
    connection: Connection, table: str
) -> Iterator[Dict[str, Any]]:
    result = connection.execute(
        text(
            f"""
            SELECT key_word, company_id, company_name, unite_code, result
            FROM {table}
            """
        )
    )
    for row in result.mappings():
        yield dict(row)


def _iter_batches(
    items: Iterable[EnrichmentIndexRecord], batch_size: int
) -> Iterator[List[EnrichmentIndexRecord]]:
    batch: List[EnrichmentIndexRecord] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def migrate_company_id_mapping(
    connection: Any, repo: Any, config: LegacyMigrationConfig
) -> MigrationReport:
    report = MigrationReport(source_table=config.company_id_mapping_table)

    def to_record(row: Dict[str, Any]) -> Optional[EnrichmentIndexRecord]:
        normalized = normalize_for_temp_id(row.get("company_name"))
        if not normalized:
            report.add_skipped("empty_after_normalization")
            return None
        company_id = row.get("company_id")
        if not company_id:
            report.add_skipped("null_company_id")
            return None

        record_type = str(row.get("type") or "former").lower()
        confidence = (
            config.confidence_current
            if record_type == "current"
            else config.confidence_former
        )

        return EnrichmentIndexRecord(
            lookup_key=normalized,
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id=str(company_id),
            confidence=confidence,
            source=SourceType.LEGACY_MIGRATION,
            source_table=config.company_id_mapping_table,
        )

    records: List[EnrichmentIndexRecord] = []
    for row in _fetch_company_id_mapping(connection, config.company_id_mapping_table):  # type: ignore[arg-type]
        report.total_read += 1
        rec = to_record(row)
        if rec is None:
            continue
        if len(report.sample_records) < 10:
            report.sample_records.append(
                {"lookup_key": rec.lookup_key, "company_id": rec.company_id}
            )
        records.append(rec)

    if config.dry_run:
        report.inserted = len(records)
        return report

    for batch in _iter_batches(records, config.batch_size):
        result = repo.insert_enrichment_index_batch(batch)
        inserted_count = int(getattr(result, "inserted_count", 0))
        conflicts = int(_estimate_conflicts(connection, report))
        report.updated += max(conflicts, 0)
        report.inserted += max(inserted_count - conflicts, 0)

    return report


def migrate_eqc_search_result(
    connection: Any, repo: Any, config: LegacyMigrationConfig
) -> MigrationReport:
    report = MigrationReport(source_table=config.eqc_search_result_table)

    def to_record(row: Dict[str, Any]) -> Optional[EnrichmentIndexRecord]:
        normalized = normalize_for_temp_id(row.get("key_word"))
        if not normalized:
            report.add_skipped("empty_after_normalization")
            return None
        company_id = row.get("company_id")
        if not company_id:
            report.add_skipped("null_company_id")
            return None

        return EnrichmentIndexRecord(
            lookup_key=normalized,
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id=str(company_id),
            confidence=config.confidence_eqc_success,
            source=SourceType.LEGACY_MIGRATION,
            source_table=config.eqc_search_result_table,
        )

    records: List[EnrichmentIndexRecord] = []
    for row in _fetch_eqc_search_result(connection, config.eqc_search_result_table):  # type: ignore[arg-type]
        report.total_read += 1
        rec = to_record(row)
        if rec is None:
            continue
        if len(report.sample_records) < 10:
            report.sample_records.append(
                {"lookup_key": rec.lookup_key, "company_id": rec.company_id}
            )
        records.append(rec)

    if config.dry_run:
        report.inserted = len(records)
        return report

    for batch in _iter_batches(records, config.batch_size):
        result = repo.insert_enrichment_index_batch(batch)
        inserted_count = int(getattr(result, "inserted_count", 0))
        conflicts = int(_estimate_conflicts(connection, report))
        report.updated += max(conflicts, 0)
        report.inserted += max(inserted_count - conflicts, 0)

    return report


def rollback_migration(connection: Connection, *, force: bool = False) -> int:
    if not force:
        raise ValueError(
            "rollback_migration requires force=True in non-interactive mode"
        )
    result = connection.execute(
        text(
            "DELETE FROM enterprise.enrichment_index WHERE source = 'legacy_migration'"
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)
