# Story 6.8: Enrichment Observability and Export

Status: done

## Context & Business Value

- Epic 6 builds a resilient company enrichment service: internal mappings → EQC sync (budgeted, cached) → async queue → temporary IDs as safety net.
- Stories 6.1-6.7 implemented the complete enrichment pipeline with multi-tier resolution, temporary ID generation, async queue processing, and Dagster scheduling.
- **This story** completes Epic 6 by adding comprehensive observability metrics and CSV export of unknown companies for manual backfill.
- Business value: Data engineers can monitor enrichment effectiveness, identify trends (cache hit rate improving, queue depth stable), and manually prioritize high-frequency unknown companies for resolution.

## Architecture Audit Findings

### Existing Implementation (Stories 6.1-6.7)

| Component | Location | Status |
|-----------|----------|--------|
| `CompanyEnrichmentService` | `domain/company_enrichment/service.py` | ✅ Complete |
| `LookupQueue.get_queue_stats()` | `domain/company_enrichment/lookup_queue.py` | ✅ Complete |
| `process_company_lookup_queue_op` | `orchestration/ops.py` | ✅ Complete (logs queue stats) |
| Structured logging | `utils/logging.py` | ✅ Complete |
| Enrichment stats collection | N/A | ❌ **MISSING** |
| Unknown companies CSV export | N/A | ❌ **MISSING** |
| Observability module | N/A | ❌ **MISSING** |

### What This Story Adds

1. **EnrichmentStats dataclass** - Comprehensive metrics collection during pipeline runs
2. **EnrichmentObserver class** - Tracks lookups, cache hits, temp IDs, API calls, queue depth
3. **ResolutionStatistics alignment** - Metrics shape compatible with existing resolution stats (yaml/db/cache/backflow/async) to avoid duplicate frameworks
4. **CSV Export (orchestration-owned I/O)** - Domain returns export rows; orchestration/infra writes `logs/unknown_companies_YYYYMMDD_HHMMSS.csv` with configurable dir
5. **Integration with CompanyEnrichmentService** - Inject observer for metrics collection
6. **Structured logging + persistence** - JSON-formatted enrichment stats and trend-ready emission
7. **Disabled-mode coverage** - Enrichment-off path still emits 100% temp-ID rate evidence

## Story

As a **data engineer**,
I want **comprehensive metrics and CSV export of unknown companies**,
so that **I can monitor enrichment effectiveness and manually backfill critical unknowns**.

## Acceptance Criteria

1. **AC1**: Pipeline completion logs enrichment stats in JSON format (ResolutionStatistics-compatible, includes distribution for yaml/db/cache/backflow/async and queue depth):
   ```json
   {
     "enrichment_stats": {
       "total_lookups": 1000,
       "cache_hits": 850,
       "cache_hit_rate": 0.85,
       "temp_ids_generated": 100,
       "api_calls": 5,
       "sync_budget_used": 5,
       "async_queued": 45,
       "queue_depth_after": 120
     }
   }
   ```

2. **AC2**: When temporary IDs are generated, export CSV to `logs/unknown_companies_YYYYMMDD_HHMMSS.csv` with columns:
   - `company_name`: Original company name
   - `temporary_id`: Generated temporary ID (IN_* format)
   - `first_seen`: Timestamp of first occurrence
   - `occurrence_count`: Number of times this company appeared

3. **AC3**: CSV is sorted by `occurrence_count DESC` (most frequent unknowns first).

4. **AC4**: Manual mappings can be added to `enterprise.company_name_index` from CSV review.

5. **AC5**: Enrichment stats are persisted (structured log/metrics sink) so trends over time are observable: cache hit rate improving, queue depth stable, temp ID rate decreasing.

6. **AC6**: When enrichment disabled via `WDH_ENRICH_ENABLED=False`, all companies get temporary IDs, stats explicitly log 100% temp ID rate and skip API/queue paths.

7. **AC7**: All new code has >85% unit test coverage.

8. **AC8**: CSV export location is configurable via `WDH_OBSERVABILITY_LOG_DIR` (default: `logs/`).

9. **AC9**: Observer is optional - pipelines work without it (graceful degradation).

## Dependencies & Interfaces

- **Prerequisite**: Story 6.5 (EnrichmentGateway with metrics tracking) - DONE
- **Prerequisite**: Story 6.2 (Temporary ID generation) - DONE
- **Prerequisite**: Story 6.7 (Async queue with stats) - DONE
- **Epic 6 roster**: 6.1-6.7 complete, **6.8 observability/export (this story)** - final story
- **Database**: PostgreSQL `enterprise.enrichment_requests` table (for queue depth)
- **Integration Point**: `CompanyEnrichmentService.resolve_company_id()` - inject observer

## Tasks / Subtasks

### Phase 1: EnrichmentStats and Observer Implementation

- [x] Task 1: Create `EnrichmentStats` dataclass (AC1)
  - [x] 1.1: Define dataclass with all metric fields
  - [x] 1.2: Add `cache_hit_rate` computed property
  - [x] 1.3: Add `to_dict()` method for JSON serialization
  - [x] 1.4: Add `merge()` method for combining stats from multiple runs
  - [x] 1.5: Ensure shape aligns with existing `ResolutionStatistics` (yaml/db/cache/backflow/async distributions) to avoid duplicate frameworks

- [x] Task 2: Create `EnrichmentObserver` class (AC1, AC5)
  - [x] 2.1: Implement `record_lookup()` method for tracking each lookup
  - [x] 2.2: Implement `record_cache_hit()` method
  - [x] 2.3: Implement `record_temp_id()` method with company name tracking
  - [x] 2.4: Implement `record_api_call()` method
  - [x] 2.5: Implement `record_async_queued()` method
  - [x] 2.6: Implement `get_stats()` method returning `EnrichmentStats`
  - [x] 2.7: Implement `reset()` method for clearing stats between runs

### Phase 2: Unknown Companies CSV Export

- [x] Task 3: Implement CSV export flow with domain/orchestration split (AC2, AC3, AC8)
  - [x] 3.1: In domain observer, expose sorted unknown company rows (data only, no file I/O)
  - [x] 3.2: In orchestration/infra, write CSV to `unknown_companies_YYYYMMDD_HHMMSS.csv`
  - [x] 3.3: Sort by occurrence_count DESC before export
  - [x] 3.4: Make output directory configurable via `WDH_OBSERVABILITY_LOG_DIR`
  - [x] 3.5: Create output directory if it doesn't exist; handle write errors gracefully

- [x] Task 4: Add `UnknownCompanyRecord` dataclass
  - [x] 4.1: Define fields: company_name, temporary_id, first_seen, occurrence_count
  - [x] 4.2: Provide row/header helpers for orchestration writer

### Phase 3: Service Integration

- [x] Task 5: Integrate observer with `CompanyEnrichmentService` (AC9)
  - [x] 5.1: Add optional `observer` parameter to `resolve_company_id()`
  - [x] 5.2: Call observer methods at appropriate points in resolution flow
  - [x] 5.3: Ensure observer is optional (graceful degradation)
  - [x] 5.4: Add `get_enrichment_stats()` method to service

- [x] Task 6: Add settings for observability (AC6, AC8)
  - [x] 6.1: Add `WDH_ENRICH_ENABLED` setting (default: True)
  - [x] 6.2: Add `WDH_OBSERVABILITY_LOG_DIR` setting (default: "logs/")
  - [x] 6.3: Add `WDH_OBSERVABILITY_EXPORT_ENABLED` setting (default: True)

### Phase 4: Orchestration Integration

- [x] Task 7: Enhance pipeline ops with observability (AC1, AC5)
  - [x] 7.1: Create observer instance in pipeline ops
  - [x] 7.2: Pass observer to enrichment service
  - [x] 7.3: Log enrichment stats at pipeline completion
  - [x] 7.4: Export CSV when temp IDs generated
  - [x] 7.5: Include queue depth in final stats
  - [x] 7.6: Persist stats to structured log/metrics sink for trend analysis (AC5)
  - [x] 7.7: In disabled mode, skip API/queue, force temp-ID counting, and emit 100% temp-ID rate evidence (AC6)

### Phase 5: Testing & Documentation

- [x] Task 8: Unit tests (AC7)
  - [x] 8.1: Test `EnrichmentStats` dataclass and computed properties
  - [x] 8.2: Test `EnrichmentObserver` recording methods
  - [x] 8.3: Test CSV export with various data scenarios
  - [x] 8.4: Test observer integration with service
  - [x] 8.5: Test graceful degradation without observer
  - [x] 8.6: Test enrichment disabled mode (100% temp IDs)

- [x] Task 9: Integration tests
  - [x] 9.1: Test full pipeline with observer
  - [x] 9.2: Test CSV file creation and content
  - [x] 9.3: Test stats logging format

- [x] Task 10: Documentation
  - [x] 10.1: Code documentation with docstrings
  - [x] 10.2: Document configuration options
  - [x] 10.3: Add operational runbook section

## Dev Notes

### Architecture Context

- **Layer**: Domain (observability module) + Orchestration (integration)
- **Pattern**: Observer pattern for non-intrusive metrics collection
- **Clean Architecture**: Observer + export data shaping in domain layer (logic only); orchestration/infra performs all file I/O
- **Reference**: Epic 6 Story 6.8 in `docs/epics/epic-6-company-enrichment-service.md`

### Existing Code Analysis

#### 1. `CompanyEnrichmentService` (`domain/company_enrichment/service.py`) - **ENHANCE**

Current methods:
- `resolve_company_id()` - Main resolution flow (needs observer integration)
- `process_lookup_queue()` - Async queue processing
- `get_queue_status()` - Returns queue stats

**Enhancement needed**: Add optional `observer` parameter to `resolve_company_id()` and call observer methods at appropriate points.

#### 2. `LookupQueue` (`domain/company_enrichment/lookup_queue.py`) - **USE AS-IS**

Current methods:
- `get_queue_stats()` - Returns pending/processing/done/failed counts
- `get_queue_depth()` - Returns count for specific status

**No changes needed**: Use existing methods for queue depth in stats.

#### 3. `process_company_lookup_queue_op` (`orchestration/ops.py`) - **ENHANCE**

Current implementation:
- Logs queue statistics after processing (Story 6.7)
- Returns processing statistics

**Enhancement needed**: Create observer, pass to service, log enrichment stats, export CSV.

### EnrichmentStats Design

```python
# domain/company_enrichment/observability.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
import csv
from pathlib import Path

@dataclass
class EnrichmentStats:
    """
    Comprehensive enrichment metrics for pipeline observability.

    Tracks all enrichment operations during a pipeline run for
    monitoring effectiveness and identifying optimization opportunities.
    """
    total_lookups: int = 0
    cache_hits: int = 0
    temp_ids_generated: int = 0
    api_calls: int = 0
    sync_budget_used: int = 0
    async_queued: int = 0
    queue_depth_after: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as decimal (0.0-1.0)."""
        if self.total_lookups == 0:
            return 0.0
        return self.cache_hits / self.total_lookups

    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for JSON logging."""
        return {
            "total_lookups": self.total_lookups,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "temp_ids_generated": self.temp_ids_generated,
            "api_calls": self.api_calls,
            "sync_budget_used": self.sync_budget_used,
            "async_queued": self.async_queued,
            "queue_depth_after": self.queue_depth_after,
        }

    def merge(self, other: "EnrichmentStats") -> "EnrichmentStats":
        """Merge stats from another run (for aggregation)."""
        return EnrichmentStats(
            total_lookups=self.total_lookups + other.total_lookups,
            cache_hits=self.cache_hits + other.cache_hits,
            temp_ids_generated=self.temp_ids_generated + other.temp_ids_generated,
            api_calls=self.api_calls + other.api_calls,
            sync_budget_used=self.sync_budget_used + other.sync_budget_used,
            async_queued=self.async_queued + other.async_queued,
            queue_depth_after=other.queue_depth_after,  # Take latest
        )
```

### EnrichmentObserver Design

```python
@dataclass
class UnknownCompanyRecord:
    """Record of an unknown company for CSV export."""
    company_name: str
    temporary_id: str
    first_seen: datetime
    occurrence_count: int = 1


class EnrichmentObserver:
    """
    Observer for tracking enrichment metrics during pipeline execution.

    Thread-safe metrics collection with support for unknown company
    tracking and CSV export.

    Examples:
        >>> observer = EnrichmentObserver()
        >>> observer.record_lookup()
        >>> observer.record_cache_hit()
        >>> observer.record_temp_id("Unknown Corp", "IN_ABC123")
        >>> stats = observer.get_stats()
        >>> observer.export_unknown_companies("logs/")
    """

    def __init__(self):
        self._stats = EnrichmentStats()
        self._unknown_companies: Dict[str, UnknownCompanyRecord] = {}
        self._lock = threading.Lock()  # Thread safety for concurrent pipelines

    def record_lookup(self) -> None:
        """Record a lookup attempt."""
        with self._lock:
            self._stats.total_lookups += 1

    def record_cache_hit(self) -> None:
        """Record a successful cache hit (internal mapping)."""
        with self._lock:
            self._stats.cache_hits += 1

    def record_temp_id(self, company_name: str, temp_id: str) -> None:
        """Record temporary ID generation for unknown company."""
        with self._lock:
            self._stats.temp_ids_generated += 1

            # Track unknown company with occurrence count
            if company_name in self._unknown_companies:
                self._unknown_companies[company_name].occurrence_count += 1
            else:
                self._unknown_companies[company_name] = UnknownCompanyRecord(
                    company_name=company_name,
                    temporary_id=temp_id,
                    first_seen=datetime.utcnow(),
                    occurrence_count=1,
                )

    def record_api_call(self) -> None:
        """Record an EQC API call."""
        with self._lock:
            self._stats.api_calls += 1
            self._stats.sync_budget_used += 1

    def record_async_queued(self) -> None:
        """Record a request queued for async processing."""
        with self._lock:
            self._stats.async_queued += 1

    def set_queue_depth(self, depth: int) -> None:
        """Set final queue depth after processing."""
        with self._lock:
            self._stats.queue_depth_after = depth

    def get_stats(self) -> EnrichmentStats:
        """Get current enrichment statistics."""
        with self._lock:
            return EnrichmentStats(
                total_lookups=self._stats.total_lookups,
                cache_hits=self._stats.cache_hits,
                temp_ids_generated=self._stats.temp_ids_generated,
                api_calls=self._stats.api_calls,
                sync_budget_used=self._stats.sync_budget_used,
                async_queued=self._stats.async_queued,
                queue_depth_after=self._stats.queue_depth_after,
            )

    def get_unknown_companies(self) -> List[UnknownCompanyRecord]:
        """Get unknown companies sorted by occurrence count DESC."""
        with self._lock:
            return sorted(
                self._unknown_companies.values(),
                key=lambda x: x.occurrence_count,
                reverse=True,
            )

    def reset(self) -> None:
        """Reset all statistics for new run."""
        with self._lock:
            self._stats = EnrichmentStats()
            self._unknown_companies.clear()
```

### CSV Export Design

```python
def build_unknown_company_rows(observer: EnrichmentObserver) -> List[List[str]]:
    """
    Domain-side: produce sorted rows for CSV export (no file I/O).
    """
    rows: List[List[str]] = []
    for record in observer.get_unknown_companies():
        rows.append([
            record.company_name,
            record.temporary_id,
            record.first_seen.isoformat(),
            record.occurrence_count,
        ])
    return rows
```

```python
# In orchestration/infra
def write_unknown_companies_csv(
    rows: List[List[str]],
    output_dir: str = "logs/",
) -> Optional[Path]:
    """
    Persist unknown companies CSV. Handles directory creation and logging.
    """
    if not rows:
        logger.info("No unknown companies to export")
        return None

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filepath = output_path / f"unknown_companies_{timestamp}.csv"

    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company_name", "temporary_id", "first_seen", "occurrence_count"])
        writer.writerows(rows)

    logger.info(
        "Exported unknown companies to CSV",
        extra={"filepath": str(filepath), "count": len(rows)},
    )
    return filepath
```

### Service Integration Design

```python
# In CompanyEnrichmentService.resolve_company_id()

def resolve_company_id(
    self,
    *,
    plan_code: Optional[str] = None,
    customer_name: Optional[str] = None,
    account_name: Optional[str] = None,
    sync_lookup_budget: Optional[int] = None,
    observer: Optional["EnrichmentObserver"] = None,  # NEW: Optional observer
) -> CompanyIdResult:
    """
    Resolve company ID with optional observability tracking.

    Args:
        ...existing args...
        observer: Optional EnrichmentObserver for metrics collection
    """
    # Record lookup attempt
    if observer:
        observer.record_lookup()

    # Step 1: Try internal mappings
    internal_result = resolve_company_id(mappings, query)
    if internal_result.company_id:
        if observer:
            observer.record_cache_hit()
        return CompanyIdResult(...)

    # Step 2: Try EQC lookup
    if budget > 0 and customer_name:
        if observer:
            observer.record_api_call()
        # ... EQC lookup logic ...

    # Step 3: Queue for async
    if customer_name:
        if observer:
            observer.record_async_queued()
        # ... queue logic ...

    # Step 4: Generate temp ID
    temp_id = self.queue.get_next_temp_id()
    if observer:
        observer.record_temp_id(customer_name or "", temp_id)
    return CompanyIdResult(...)
```

### Runtime Dependencies & Versions

- structlog 25.4.0 — structured logging
- pytest 8.4.2 — testing framework
- Python 3.11+ — dataclasses, pathlib, csv (stdlib)

### File Locations

| File | Purpose | Action |
|------|---------|--------|
| `src/work_data_hub/domain/company_enrichment/observability.py` | Observability module | ADD |
| `src/work_data_hub/domain/company_enrichment/service.py` | Enrichment service | MODIFY |
| `src/work_data_hub/config/settings.py` | Configuration | MODIFY |
| `src/work_data_hub/orchestration/ops.py` | Pipeline ops | MODIFY |
| `tests/domain/company_enrichment/test_observability.py` | Observability tests | ADD |

### Environment Variables

```bash
# Observability configuration
WDH_ENRICH_ENABLED=true  # Enable/disable enrichment (default: true)
WDH_OBSERVABILITY_LOG_DIR=logs/  # CSV export directory (default: logs/)
WDH_OBSERVABILITY_EXPORT_ENABLED=true  # Enable/disable CSV export (default: true)

# Existing variables (unchanged)
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/workdatahub
WDH_EQC_TOKEN=<eqc_api_token>
```

### Operational Runbook

1. **View Enrichment Stats**: Check pipeline logs for `enrichment_stats` JSON block
2. **Find Unknown Companies**: Look in `logs/unknown_companies_*.csv`
3. **Manual Backfill**: Add high-priority mappings to `enterprise.company_name_index`:
   ```sql
   INSERT INTO enterprise.company_name_index (normalized_name, company_id, match_type, confidence)
   VALUES ('unknown corp', 'COMP123', 'manual', 1.00);
   ```
4. **Monitor Trends**: Track cache_hit_rate over time (should increase as mappings grow)
5. **Disable Export**: Set `WDH_OBSERVABILITY_EXPORT_ENABLED=false`
6. **Change Export Dir**: Set `WDH_OBSERVABILITY_LOG_DIR=/custom/path/`

### Previous Story Learnings (Stories 6.1-6.7)

1. Keep migrations idempotent and reversible (Story 6.1).
2. Use `normalize_for_temp_id()` for consistent normalization (Story 6.2).
3. Never log sensitive data (salt, tokens, alias values) (Story 6.2, 6.3).
4. Use dataclasses for result types (Story 6.3).
5. Repository: caller owns transaction; log counts only (Story 6.3).
6. Graceful degradation is critical: failures don't block pipeline (Story 6.4).
7. Story 6.5: Async enqueue uses `normalize_for_temp_id()` for dedup parity.
8. Story 6.6: EqcProvider budget enforcement and session disable on 401.
9. Story 6.7: Exponential backoff with bounded schedule [1, 5, 15] minutes.

### Git Intelligence (Recent Commits)

```
7442c9c feat(story-6.7): finalize async enrichment queue
b6d5747 feat(story-6.6): implement EQC API provider with budget management
152ff8b Complete Story 6-4-1 P4 normalization alignment
eeaa995 feat(story-6.5): implement async enrichment queue integration
830eaba chore(tests): refactor story-based test files to domain-centric names
```

**Patterns to follow:**
- Use dataclasses for data structures (EnrichmentStats, UnknownCompanyRecord)
- Use structlog for logging with context binding
- Observer pattern for non-intrusive metrics collection
- Graceful degradation: observer is optional
- Commit message format: `feat(story-6.8): <description>`

### CRITICAL: Do NOT Reinvent

- **DO NOT** create new database tables - use existing `enterprise.enrichment_requests` for queue depth
- **DO NOT** duplicate logging logic - use existing structlog patterns
- **DO NOT** break backward compatibility - observer must be optional
- **DO NOT** log sensitive data - only log counts and rates
- **DO NOT** block pipeline on export failures - graceful degradation

### Performance Requirements

| Operation | Target | Measurement |
|-----------|--------|-------------|
| Stats collection | <1ms per lookup | Unit test with mock |
| CSV export (1000 records) | <100ms | Integration test |
| Observer overhead | <5% pipeline time | Benchmark test |

### Testing Strategy

**Unit Tests:**
- `test_enrichment_stats_cache_hit_rate`: Verify rate calculation
- `test_enrichment_stats_to_dict`: Verify JSON serialization
- `test_observer_record_methods`: Verify all recording methods
- `test_observer_thread_safety`: Verify concurrent access
- `test_csv_export_sorted`: Verify occurrence_count DESC sorting
- `test_csv_export_creates_directory`: Verify directory creation
- `test_service_with_observer`: Verify observer integration
- `test_service_without_observer`: Verify graceful degradation

**Integration Tests:**
- `test_full_pipeline_with_observability`: End-to-end with observer
- `test_csv_file_content`: Verify CSV format and content
- `test_stats_logging_format`: Verify JSON log format

### Quick Start (Dev Agent Checklist)

1. **Files to add**: `observability.py`, `test_observability.py`
2. **Files to modify**: `service.py`, `settings.py`, `ops.py`
3. **Env**: `WDH_ENRICH_ENABLED`, `WDH_OBSERVABILITY_LOG_DIR`, `WDH_OBSERVABILITY_EXPORT_ENABLED`
4. **Performance gates**: Stats collection <1ms; CSV export <100ms
5. **Commands**: `uv run pytest tests/domain/company_enrichment/ -v`; `uv run ruff check`; `uv run mypy --strict src/`
6. **Logging**: Use structlog; log counts only; never log company names in stats
7. **Graceful degradation**: Observer failures must not affect pipeline

### Implementation Plan (Condensed)

1) Create `observability.py` with `EnrichmentStats`, `UnknownCompanyRecord`, `EnrichmentObserver` classes.
2) Add `export_unknown_companies()` function for CSV export.
3) Add settings: `WDH_ENRICH_ENABLED`, `WDH_OBSERVABILITY_LOG_DIR`, `WDH_OBSERVABILITY_EXPORT_ENABLED`.
4) Modify `CompanyEnrichmentService.resolve_company_id()` to accept optional observer.
5) Enhance pipeline ops to create observer, pass to service, log stats, export CSV.
6) Add unit tests for all new functionality.
7) Add integration tests for full pipeline with observability.

## References

- Epic: `docs/epics/epic-6-company-enrichment-service.md` (Story 6.8)
- Architecture: `docs/architecture-boundaries.md` (Clean Architecture)
- PRD: §849-855 (Enrichment observability)
- Previous Story: `docs/sprint-artifacts/stories/6-7-async-enrichment-queue-deferred-resolution.md`
- Service: `src/work_data_hub/domain/company_enrichment/service.py`
- LookupQueue: `src/work_data_hub/domain/company_enrichment/lookup_queue.py`
- Ops: `src/work_data_hub/orchestration/ops.py`

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List
- Implemented `EnrichmentStats` to track hit_type_counts for better granularity.
- Modified `EnrichmentObserver.record_cache_hit` to accept match_type.
- Downgraded per-row `logger.info` calls to `logger.debug` in `service.py` to prevent log flooding.
- Removed `observer.record_lookup()` from `process_lookup_queue` in `service.py` to prevent metric double-counting.
- Added UUID suffix to CSV export filenames in `csv_exporter.py` to mitigate collision risk.

### File List
- src/work_data_hub/config/settings.py
- src/work_data_hub/domain/company_enrichment/observability.py
- src/work_data_hub/domain/company_enrichment/service.py
- src/work_data_hub/infrastructure/enrichment/csv_exporter.py
- src/work_data_hub/orchestration/ops.py
- tests/domain/company_enrichment/test_enrichment_service.py
- tests/domain/company_enrichment/test_observability.py
- tests/infrastructure/enrichment/test_csv_exporter.py
- docs/sprint-artifacts/code-reviews/validation-report-6-8-enrichment-observability-and-export.md

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-07 | Story drafted with comprehensive context for dev readiness | Claude Opus 4.5 |
| 2025-12-07 | Code review and automatic fixes applied based on findings (logging, metric clarity, CSV filename, stat granularity) | Amelia |
