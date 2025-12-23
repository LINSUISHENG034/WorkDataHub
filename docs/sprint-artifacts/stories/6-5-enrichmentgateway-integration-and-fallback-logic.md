# Story 6.5: EnrichmentGateway Integration and Fallback Logic

Status: Done

## Context & Business Value

- Epic 6 builds a resilient company enrichment service: internal mappings → EQC sync (budgeted, cached) → async queue → temporary IDs as safety net.
- Story 6.1 created the `enterprise` schema with 3 tables (`company_master`, `company_mapping`, `enrichment_requests`).
- Story 6.2 implemented deterministic temporary ID generation (HMAC-SHA1).
- Story 6.3 created `CompanyMappingRepository` for database access and `load_company_id_overrides()` for multi-file YAML loading.
- Story 6.4 enhanced `CompanyIdResolver` with multi-tier lookup (YAML → DB cache → existing column → EQC sync → temp ID) and backflow mechanism.
- **This story** adds async queue enqueue logic: when temporary IDs are generated, automatically queue unresolved company names for async enrichment via the `enterprise.enrichment_requests` table, and aligns with Epic 6 gateway flow (internal cache → EQC sync budget → temp ID → async queue by confidence).
- Business value: Enables gradual cache hit rate improvement through async backfill. Unresolved companies are queued for later EQC resolution, and once resolved, future pipeline runs will hit the cache directly.

## Story

As a **data engineer**,
I want **CompanyIdResolver to automatically enqueue unresolved company names for async enrichment when generating temporary IDs**,
so that **temporary IDs can be resolved to real company IDs in background processing, improving cache hit rates over time**.

## Acceptance Criteria

1. **AC1**: When `CompanyIdResolver.resolve_batch()` generates temporary IDs, it automatically enqueues unresolved company names to `enterprise.enrichment_requests` table.
2. **AC2**: Enqueue logic respects deduplication: same `normalized_name` is not enqueued if already `pending` or `processing` (partial unique index enforced) and reuse the shared `normalize_for_temp_id` helper for parity with temp-ID generation.
3. **AC3**: Each enqueued request includes: `raw_name`, `normalized_name`, `temp_id`, `status='pending'`, `created_at`.
4. **AC4**: `ResolutionStrategy` extended with `enable_async_queue: bool = True` to control enqueue behavior.
5. **AC5**: `ResolutionStatistics` extended with `async_queued: int` field tracking number of newly enqueued requests.
6. **AC6**: Enqueue operation is non-blocking: failures logged but do not interrupt pipeline execution.
7. **AC7**: `CompanyMappingRepository` extended with `enqueue_for_enrichment()` method for batch insert with conflict handling.
8. **AC8**: Backward compatible: all new parameters optional; legacy callers unchanged.
9. **AC9**: Enqueue performance <50ms for 100 requests (single batch insert statement with ON CONFLICT).
10. **AC10**: All new code has >85% unit test coverage.

## Dependencies & Interfaces

- **Prerequisite**: Story 6.1 (enterprise schema with `enrichment_requests` table) - DONE
- **Prerequisite**: Story 6.2 (temporary ID generation) - DONE
- **Prerequisite**: Story 6.3 (mapping repository) - DONE
- **Prerequisite**: Story 6.4 (multi-tier lookup) - DONE
- **Epic 6 roster (for alignment)**: 6.1 schema, 6.2 temp IDs, 6.3 DB cache, 6.4 multi-tier lookup, **6.5 async queue enqueue (this story)**, 6.6 EQC API provider, 6.7 async Dagster job, 6.8 observability/export.
- **Tech Spec**: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (Story 6.5 section)
- **Integration Point**: Story 6.7 will consume the queue via Dagster job
- **Database**: PostgreSQL `enterprise.enrichment_requests` table

## Tasks / Subtasks

- [x] Task 1: Extend ResolutionStrategy (AC4)
  - [x] 1.1: Add `enable_async_queue: bool = True` field to `ResolutionStrategy` dataclass
  - [x] 1.2: Update docstring with new field description

- [x] Task 2: Extend ResolutionStatistics (AC5)
  - [x] 2.1: Add `async_queued: int = 0` field to `ResolutionStatistics` dataclass
  - [x] 2.2: Update `to_dict()` method to include `async_queued`
  - [x] 2.3: Update docstring with new field description

- [x] Task 3: Implement enqueue method in CompanyMappingRepository (AC7)
  - [x] 3.1: Create `enqueue_for_enrichment()` method with single-statement batch insert (no per-row execute)
  - [x] 3.2: Handle ON CONFLICT DO NOTHING for partial unique index
  - [x] 3.3: Return count of actually inserted records (vs skipped duplicates)
  - [x] 3.4: Use parameterized queries via `text()` for security

- [x] Task 4: Integrate enqueue into CompanyIdResolver (AC1, AC2, AC3, AC6)
  - [x] 4.1: Create `_enqueue_for_async_enrichment()` private method
  - [x] 4.2: Call enqueue after temp ID generation in `resolve_batch()`
  - [x] 4.3: Wrap enqueue in try/except for graceful degradation
  - [x] 4.4: Log enqueue results (count only, no PII)
  - [x] 4.5: Use `normalize_for_temp_id()` for deduplication parity

- [x] Task 5: Unit tests (AC9, AC10)
  - [x] 5.1: Test enqueue method with mocked repository
  - [x] 5.2: Test deduplication (same normalized_name not re-enqueued via `normalize_for_temp_id`)
  - [x] 5.3: Test graceful degradation (enqueue failure doesn't block pipeline)
  - [x] 5.4: Test statistics accuracy (async_queued count)
  - [x] 5.5: Test backward compatibility (enable_async_queue=False skips enqueue)
  - [x] 5.6: Test performance guard (100 requests < 50ms) using single batch insert
  - [x] 5.7: Test queue metrics logging (queued vs skipped) to prove AC2+AC9

- [x] Task 6: Documentation (AC8)
  - [x] 6.1: Update docstrings for modified classes/methods
  - [x] 6.2: Document enqueue API contract in Dev Notes

## Dev Notes

### Architecture Context

- **Layer**: Infrastructure (enrichment subsystem)
- **Pattern**: Queue pattern for deferred processing
- **Clean Architecture**: No domain imports; only stdlib + pandas + SQLAlchemy; repository consumes caller-owned DB connection (no implicit commits)
- **Reference**: AD-010 in `docs/architecture/architectural-decisions.md`; see `docs/architecture/index.md` for boundaries

### Resolution Flow with Async Queue (Updated)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Company ID Resolution Priority                │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: YAML Configuration (5 priority levels)                 │
│                              ↓ Not found                         │
│  Layer 2: Database Cache (enterprise.company_mapping)            │
│                              ↓ Not found                         │
│  Layer 3: Existing company_id Column (passthrough + backflow)    │
│                              ↓ Not found                         │
│  Layer 4: EQC Sync Lookup (budget-limited, cached)               │
│                              ↓ Not found                         │
│  Layer 5: Temporary ID Generation (IN<16-char-Base32>)          │
│           + ENQUEUE for async enrichment (Story 6.5) ← NEW       │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema (enrichment_requests)

Defined in Story 6.1 migration `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py` (partial unique index on normalized_name for pending/processing).

### Runtime Dependencies & Versions

- SQLAlchemy 2.0.43 — use 2.x APIs (`text()`, `Connection.execute` returns `Result`)
- pandas 2.2.3 — vectorized operations for batch processing
- structlog 25.4.0 — reuse `utils/logging.get_logger`, follow Decision #8 sanitization
- pytest 8.4.2 — prefer fixtures/marks over ad-hoc setup

### File Locations

| File | Purpose | Status |
|------|---------|--------|
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | Main resolver class | MODIFY |
| `src/work_data_hub/infrastructure/enrichment/types.py` | ResolutionStrategy, ResolutionStatistics | MODIFY |
| `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` | Database repository | MODIFY |
| `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | Resolver unit tests | MODIFY |
| `tests/unit/infrastructure/enrichment/test_mapping_repository.py` | Repository unit tests | MODIFY |
| `docs/sprint-artifacts/code-reviews/validation-report-6-5.md` | Review/report doc | ADD |
| `docs/sprint-artifacts/code-reviews/validation-report-20251207-091848.md` | Validation report | ADD |
| `docs/sprint-artifacts/sprint-status.yaml` | Sprint status updates | MODIFY |
| `docs/specific/backflow/` | Backflow mechanism notes | ADD |

### Design Details

Gateway alignment: follow Epic 6 flow (internal cache → EQC sync within budget → temp ID) and enqueue when confidence is unknown/temporary; Story 6.7 consumes the queue.

**Extended ResolutionStrategy:**
```python
# src/work_data_hub/infrastructure/enrichment/types.py
@dataclass
class ResolutionStrategy:
    plan_code_column: str = "计划代码"
    customer_name_column: str = "客户名称"
    account_name_column: str = "年金账户名"
    account_number_column: str = "年金账户号"
    company_id_column: str = "公司代码"
    output_column: str = "company_id"
    use_enrichment_service: bool = False
    sync_lookup_budget: int = 0
    generate_temp_ids: bool = True
    enable_backflow: bool = True
    enable_async_queue: bool = True  # NEW: Story 6.5
```

**Extended ResolutionStatistics:**
```python
# src/work_data_hub/infrastructure/enrichment/types.py
@dataclass
class ResolutionStatistics:
    total_rows: int = 0
    plan_override_hits: int = 0
    existing_column_hits: int = 0
    enrichment_service_hits: int = 0
    temp_ids_generated: int = 0
    unresolved: int = 0

    # Story 6.4 fields
    yaml_hits: Dict[str, int] = field(default_factory=dict)
    db_cache_hits: int = 0
    eqc_sync_hits: int = 0
    budget_consumed: int = 0
    budget_remaining: int = 0
    backflow_stats: Dict[str, int] = field(default_factory=dict)

    # Story 6.5: Async queue statistics
    async_queued: int = 0  # NEW

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary for logging."""
        return {
            # ... existing fields ...
            "async_queued": self.async_queued,  # NEW
        }
```

**Enqueue Method in CompanyMappingRepository (batch, single statement):**
Use one `INSERT ... ON CONFLICT DO NOTHING` with parameter array (executemany) to avoid per-row latency; return queued vs skipped counts. Log counts only.

**Enqueue Integration in CompanyIdResolver:**
Normalize with `normalize_for_temp_id` to align dedup and temp-ID generation; call `_enqueue_for_async_enrichment` after temp IDs; keep try/except for graceful degradation; log counts only.

### API Contracts

- `CompanyMappingRepository.enqueue_for_enrichment(requests: List[Dict]) -> EnqueueResult`
  - Input: List of `{raw_name: str, normalized_name: str, temp_id: str}`
  - Output: `EnqueueResult(queued_count: int, skipped_count: int)`
  - Behavior: Single batch insert with ON CONFLICT DO NOTHING; duplicates silently skipped
  - Error handling: Raises on connection errors; caller handles gracefully

- `ResolutionStrategy.enable_async_queue: bool`
  - Default: `True`
  - When `False`: Skip enqueue even if temp IDs generated

- `ResolutionStatistics.async_queued: int`
  - Count of requests actually enqueued (excludes duplicates)
  - Included in `to_dict()` output

### Security & Performance Guardrails

- Logging: bind counts only; never log raw_name/normalized_name/temp_id; follow Decision #8 sanitization; reuse `normalize_for_temp_id`
- Secrets: No new secrets required for this story
- Performance: Batch insert for efficiency; target <50ms for 100 requests
- Graceful degradation: Enqueue failures logged but don't block pipeline
- PII: treat raw_name/normalized_name as PII; mask or omit in logs/metrics

### Testing Strategy

**Unit Tests (mocked database):**
- `test_enqueue_for_enrichment_batch`: Batch insert works correctly
- `test_enqueue_deduplication`: Duplicates skipped via partial unique index using `normalize_for_temp_id`
- `test_enqueue_empty_list`: Empty list returns zero counts
- `test_resolve_batch_enqueues_temp_ids`: Temp IDs trigger enqueue
- `test_resolve_batch_enqueue_disabled`: `enable_async_queue=False` skips enqueue
- `test_resolve_batch_enqueue_graceful_degradation`: Enqueue failure doesn't block
- `test_statistics_async_queued`: Statistics include async_queued count
- `test_enqueue_performance`: 100 requests < 50ms (single batch insert timing)
- `test_enqueue_logging_counts_only`: Logs only counts, no PII

**Integration Tests (deferred to Story 6.7):**
- Full pipeline with database connection
- Queue consumption by Dagster job

### Previous Story Learnings (Stories 6.1-6.4)

1. Keep migrations idempotent and reversible (Story 6.1).
2. Prefer explicit constraints (CHECK, UNIQUE) to prevent data drift (Story 6.1).
3. Keep enrichment optional; pipelines must not block when cache unavailable (Story 6.1).
4. Use `normalize_for_temp_id()` for consistent normalization (Story 6.2) — enforced for enqueue dedup.
5. Never log sensitive data (salt, tokens, alias values) (Story 6.2, 6.3).
6. Use dataclasses for result types (`MatchResult`, `InsertBatchResult`, `EnqueueResult`) (Story 6.3).
7. Use SQLAlchemy text() for raw SQL with parameterized queries (Story 6.3).
8. Repository: caller owns transaction; log counts only, never alias/company_id values (Story 6.3).
9. CI regressions surfaced on mypy/ruff (Story 6.3) — keep signatures precise and imports minimal.
10. Graceful degradation is critical: EQC failures don't block pipeline (Story 6.4).
11. Backflow mechanism pattern: collect candidates, batch insert, handle conflicts (Story 6.4).

### Git Intelligence (Recent Commits)

```
7edf98b feat(story-6.4): implement multi-tier company ID resolver lookup
85f48e3 feat(story-6.3): finalize mapping repository and yaml overrides
78e4d11 fix(ci): resolve mypy, ruff-lint and ruff-format failures
8b01df7 docs(story-6.2): finalize temporary company ID story
8467f08 fix(story-6.1): harden enterprise schema migration and finalize review
```

**Patterns to follow:**
- Use dataclasses for new types (`EnqueueResult`)
- Use structlog for logging with context binding
- Follow existing test patterns in `tests/unit/infrastructure/enrichment/`
- Use `field(default_factory=dict)` for mutable default values
- Commit impact summary:
  - `7edf98b`: Multi-tier lookup pattern; reuse graceful degradation approach
  - `85f48e3`: Repository API shape; follow `insert_batch_with_conflict_check` pattern
  - `78e4d11`: lint/format/mypy rules tightened—ensure compliance

### CRITICAL: Do NOT Reinvent

- **DO NOT** create new tables - use existing `enterprise.enrichment_requests`
- **DO NOT** create alternative queue mechanisms - use database queue pattern
- **DO NOT** add external dependencies - use stdlib + pandas + SQLAlchemy only
- **DO NOT** break backward compatibility - all new parameters must be optional
- **DO NOT** log PII - only log counts, never raw_name/normalized_name

### Performance Requirements

| Operation | Target | Measurement |
|-----------|--------|-------------|
| `enqueue_for_enrichment(100 requests)` | <50ms | Unit test with mock |
| `resolve_batch(1000 rows)` with enqueue | <150ms | Unit test with mock |

### Environment Variables

```bash
# Required for database operations
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/workdatahub

# Required for temporary ID generation
WDH_ALIAS_SALT=<production_salt>

# Optional - defaults to data/mappings
WDH_MAPPINGS_DIR=data/mappings
```

### Database Access & Transactions

- Repository accepts upstream `Connection`; caller owns commit/rollback
- No implicit autocommit; wrap inserts in explicit transaction
- Always parameterize via `text()`; no f-strings
- Bind logger context with counts only; never log raw_name/normalized_name values

## References

- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (Story 6.5)
- Epic: `docs/epics/epic-6-company-enrichment-service.md` (Story 5.5 in epic index)
- Architecture Decision: `docs/architecture/architectural-decisions.md` (AD-010)
- Database Schema: `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py`
- Mapping Repository: `src/work_data_hub/infrastructure/enrichment/mapping_repository.py`
- CompanyIdResolver: `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
- Previous Story: `docs/sprint-artifacts/stories/6-4-internal-mapping-resolver-multi-tier-lookup.md`

### Quick Start (Dev Agent Checklist)

1. **Files to modify**: `types.py` (ResolutionStrategy, ResolutionStatistics), `mapping_repository.py` (enqueue method), `company_id_resolver.py` (enqueue integration), test files
2. **Files to reference**: Story 6.4 implementation for patterns
3. **Env**: `DATABASE_URL`, `WDH_ALIAS_SALT`
4. **Performance gates**: `enqueue(100)` <50ms; `resolve_batch(1000)` <150ms with enqueue
5. **Commands**: `uv run pytest tests/unit/infrastructure/enrichment/ -v`; `uv run ruff check`; `uv run mypy --strict src/`
6. **Logging**: `utils.logging.get_logger(__name__)`; bind counts only; never log raw_name/normalized_name
7. **Graceful degradation**: Enqueue failures must not block pipeline
8. **Backward compatibility**: All existing tests must pass without modification

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 139 unit tests pass (125 existing + 14 new Story 6.5 tests)
- Ruff check passes with no errors
- mypy --strict passes for modified files (no new type errors introduced)

### Completion Notes List

- **Task 1**: Added `enable_async_queue: bool = True` to `ResolutionStrategy` dataclass with docstring
- **Task 2**: Added `async_queued: int = 0` to `ResolutionStatistics` dataclass, updated `to_dict()` method
- **Task 3**: Implemented `EnqueueResult` dataclass and `enqueue_for_enrichment()` method in `CompanyMappingRepository` with batch INSERT and ON CONFLICT DO NOTHING
- **Task 4**: Implemented `_enqueue_for_async_enrichment()` in `CompanyIdResolver`, integrated after temp ID generation with graceful degradation and `normalize_for_temp_id()` for dedup parity
- **Task 5**: Added 14 new unit tests covering all ACs (6 repository tests, 8 resolver integration tests)
- **Task 6**: All docstrings updated, API contracts documented

### File List

| File | Action |
|------|--------|
| `src/work_data_hub/infrastructure/enrichment/types.py` | MODIFIED - Added `enable_async_queue` to ResolutionStrategy, `async_queued` to ResolutionStatistics |
| `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` | MODIFIED - Added `EnqueueResult` dataclass and `enqueue_for_enrichment()` method |
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | MODIFIED - Added `_enqueue_for_async_enrichment()` method, integrated into `resolve_batch()` |
| `tests/unit/infrastructure/enrichment/test_mapping_repository.py` | MODIFIED - Added `TestEnqueueResult` and `TestEnqueueForEnrichment` test classes |
| `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | MODIFIED - Added `TestAsyncQueueIntegration` test class |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-07 | Story drafted with comprehensive context for dev readiness | Claude Opus 4.5 |
| 2025-12-07 | Implementation complete - all tasks done, 139 tests pass | Claude Opus 4.5 |
| 2025-12-07 | Code review: Fixed ruff E501 line too long in mapping_repository.py:492 | Claude Opus 4.5 |
