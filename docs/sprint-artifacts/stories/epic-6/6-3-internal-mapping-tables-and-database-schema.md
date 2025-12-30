# Story 6.3: Internal Mapping Tables and Database Schema

Status: done

## Context & Business Value

- Epic 6 builds a resilient company enrichment service: internal mappings → EQC sync (budgeted) → async backfill → temporary IDs as safety net.
- Story 6.1 created the `enterprise` schema with 3 tables (`company_master`, `company_mapping`, `enrichment_requests`).
- Story 6.2 implemented deterministic temporary ID generation (HMAC-SHA1).
- **This story** creates the data access layer (`CompanyMappingRepository`) and multi-file YAML loading to enable `CompanyIdResolver` to query the database cache.
- Business value: 90%+ of lookups resolved locally with zero API cost and sub-millisecond latency once mappings are populated.

## Story

As a **data engineer**,
I want **a data access layer for company mappings with multi-file YAML configuration support**,
so that **CompanyIdResolver can query the database cache and YAML overrides using a unified interface**.

## Acceptance Criteria

1. **AC1**: Multi-file YAML loader `load_company_id_overrides()` loads all 5 priority levels from `data/mappings/company_id_overrides_*.yml` files.
2. **AC2**: `CompanyMappingRepository` class provides batch lookup from `enterprise.company_mapping` table.
3. **AC3**: `CompanyMappingRepository.lookup_batch()` returns highest-priority match per alias_name (sorted by priority ASC).
4. **AC4**: `CompanyMappingRepository.insert_batch()` supports ON CONFLICT DO NOTHING for idempotent inserts.
5. **AC5**: Batch lookup performance <100ms for 1,000 alias_names.
6. **AC6**: All new code has >85% unit test coverage.
7. **AC7**: Backward compatible: `CompanyIdResolver` continues to work without database connection (YAML-only mode).

## Dependencies & Interfaces

- **Prerequisite**: Story 6.1 (enterprise schema created) - DONE
- **Prerequisite**: Story 6.2 (temporary ID generation) - DONE
- **Tech Spec**: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (Story 6.3 section)
- **Integration Point**: `CompanyIdResolver` will consume `CompanyMappingRepository` in Story 6.4
- **Database**: PostgreSQL `enterprise.company_mapping` table (created in Story 6.1)

## Tasks / Subtasks

- [x] Task 1: Create multi-file YAML loader (AC1)
  - [x] 1.1: Create `src/work_data_hub/config/mapping_loader.py` with `load_company_id_overrides()`
  - [x] 1.2: Create placeholder YAML files for missing priority levels (account, hardcode, name, account_name)
  - [x] 1.3: Add unit tests for YAML loading (missing files, empty files, valid files)

- [x] Task 2: Create CompanyMappingRepository (AC2, AC3, AC4)
  - [x] 2.1: Create `src/work_data_hub/infrastructure/enrichment/mapping_repository.py`
  - [x] 2.2: Implement `MatchResult` dataclass with company_id, match_type, priority, source
  - [x] 2.3: Implement `lookup_batch()` with priority-sorted results
  - [x] 2.4: Implement `insert_batch()` with ON CONFLICT DO NOTHING
  - [x] 2.5: Implement `insert_batch_with_conflict_check()` for backflow with conflict detection

- [x] Task 3: Unit tests for CompanyMappingRepository (AC5, AC6)
  - [x] 3.1: Create `tests/unit/infrastructure/enrichment/test_mapping_repository.py`
  - [x] 3.2: Test lookup_batch with various scenarios (exact match, multiple matches, no match)
  - [x] 3.3: Test insert_batch idempotency
  - [x] 3.4: Test conflict detection in insert_batch_with_conflict_check
  - [x] 3.5: Add performance test guard (1000 lookups < 100ms with mock)

- [x] Task 4: Integration preparation (AC7)
  - [x] 4.1: Verify CompanyIdResolver works without mapping_repository (YAML-only mode)
  - [x] 4.2: Document integration pattern for Story 6.4

## Dev Notes

### Architecture Context

- **Layer**: Infrastructure (data access layer)
- **Pattern**: Repository pattern for database access
- **Clean Architecture**: No domain imports; only stdlib + SQLAlchemy
- **Reference**: AD-010 in `docs/architecture/architectural-decisions.md`

### Runtime Dependencies & Versions

- SQLAlchemy 2.0.43 (pyproject/uv.lock) — use 2.x APIs (`text()`, no implicit autocommit; `Connection.execute` returns `Result`).
- structlog 25.4.0 — reuse `utils/logging.get_logger`, keep Decision #8 sanitization, do not reconfigure globally.
- pytest 8.4.2 (+pytest-asyncio, pytest-postgresql) — prefer fixtures/marks over ad-hoc DB setup.

### Schema Contract (enterprise.company_mapping)

- Columns: `id SERIAL PK`, `alias_name VARCHAR(255) NOT NULL`, `canonical_id VARCHAR(100) NOT NULL`, `match_type VARCHAR(20) NOT NULL`, `priority INT CHECK (1-5)`, `source VARCHAR(50) NOT NULL DEFAULT 'internal'`, `created_at/updated_at TIMESTAMPTZ DEFAULT NOW()`.
- Constraints/Indexes: `UNIQUE(alias_name, match_type)`; index `idx_company_mapping_lookup (alias_name, priority)` for priority ordering. Expect UTF-8 input; no nullable alias/match_type.
- Sources: `internal/eqc/pipeline_backflow`; conflict semantics defined in repository contract below.

### File Locations

| File | Purpose | Status |
|------|---------|--------|
| `src/work_data_hub/config/mapping_loader.py` | Multi-file YAML loader | NEW |
| `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` | Database repository | NEW |
| `data/mappings/company_id_overrides_plan.yml` | Priority 1: Plan code mappings | EXISTING |
| `data/mappings/company_id_overrides_account.yml` | Priority 2: Account number mappings | NEW (placeholder) |
| `data/mappings/company_id_overrides_hardcode.yml` | Priority 3: Hardcoded special cases | NEW (placeholder) |
| `data/mappings/company_id_overrides_name.yml` | Priority 4: Customer name mappings | NEW (placeholder) |
| `data/mappings/company_id_overrides_account_name.yml` | Priority 5: Account name mappings | NEW (placeholder) |
| `tests/unit/infrastructure/enrichment/test_mapping_repository.py` | Repository unit tests | NEW |
| `tests/unit/config/test_mapping_loader.py` | YAML loader unit tests | NEW |
| `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | YAML-only compatibility coverage | MODIFIED |

### Design Details

**Multi-file YAML Loader:**
```python
# src/work_data_hub/config/mapping_loader.py
def load_company_id_overrides(
    mappings_dir: Optional[Path] = None
) -> Dict[str, Dict[str, str]]:
    """
    Load all company_id mapping configurations (5 priority levels).

    Returns:
        {
            "plan": {"FP0001": "614810477", ...},         # Priority 1
            "account": {"12345678": "601234567", ...},    # Priority 2
            "hardcode": {"FP0001": "614810477", ...},     # Priority 3
            "name": {"中国平安": "600866980", ...},        # Priority 4
            "account_name": {"平安年金账户": "600866980", ...},  # Priority 5
        }
    """
```

**YAML Loader Behavior (must implement):**
- Missing file → return empty dict and debug-log filename (no exception).
- Empty file → empty dict.
- Invalid YAML → raise ValueError with filename; do not silently ignore.
- Validate shape: mapping of string→string; strip whitespace in keys/values.

**CompanyMappingRepository:**
```python
# src/work_data_hub/infrastructure/enrichment/mapping_repository.py
@dataclass
class MatchResult:
    company_id: str
    match_type: str  # plan/account/hardcode/name/account_name
    priority: int    # 1-5
    source: str      # internal/eqc/pipeline_backflow

@dataclass
class InsertBatchResult:
    inserted_count: int
    skipped_count: int
    conflicts: List[Dict[str, Any]]  # alias_name exists but company_id differs

class CompanyMappingRepository:
    """Database access layer for enterprise.company_mapping table."""

    def __init__(self, connection):
        self.connection = connection

    def lookup_batch(
        self,
        alias_names: List[str],
        match_types: Optional[List[str]] = None
    ) -> Dict[str, MatchResult]:
        """
        Batch lookup mappings, return {alias_name: MatchResult}.
        Returns highest priority match per alias_name.
        """
        ...

    def insert_batch(
        self,
        mappings: List[Dict[str, Any]]
    ) -> int:
        """
        Batch insert mappings with ON CONFLICT DO NOTHING.
        Returns number of rows inserted.
        """
        ...

    def insert_batch_with_conflict_check(
        self,
        mappings: List[Dict[str, Any]]
    ) -> InsertBatchResult:
        """
        Batch insert with conflict detection for backflow.
        Conflicts: alias_name+match_type exists but canonical_id differs.
        """
        ...
```

**Repository Contracts (add to implementation notes):**
- `lookup_batch`: single SQL round-trip using DISTINCT ON + ORDER BY priority ASC; filters by `match_types` if provided; missing alias returns None/absent key (no exception); log counts only (never alias values).
- `insert_batch`: uses ON CONFLICT DO NOTHING; caller owns transaction; log inserted/skipped counts only.
- `insert_batch_with_conflict_check`: prefetch existing rows once; return conflicts list (`existing_id` vs `new_id`); propagate IntegrityError after logging counts; bulk insert via parameterized `text`/executemany.

**SQL Query for lookup_batch:**
```sql
SELECT DISTINCT ON (alias_name)
    alias_name, canonical_id, match_type, priority, source
FROM enterprise.company_mapping
WHERE alias_name = ANY(:alias_names)
ORDER BY alias_name, priority ASC
```

### Testing Strategy

**Unit Tests (mocked database):**
- `test_lookup_batch_exact_match`: Single alias returns correct MatchResult
- `test_lookup_batch_priority_ordering`: Multiple matches return highest priority
- `test_lookup_batch_no_match`: Missing alias returns None
- `test_lookup_batch_filter_by_match_type`: Filter works correctly
- `test_insert_batch_idempotent`: Duplicate inserts don't fail
- `test_insert_batch_with_conflict_check_detects_conflicts`: Conflict detection works

**Integration Tests (real database):**
- Deferred to Story 6.4 when integrating with CompanyIdResolver

### Previous Story Learnings (Stories 6.1, 6.2)

1. Keep migrations idempotent and reversible (Story 6.1).
2. Prefer explicit constraints (CHECK, UNIQUE) to prevent data drift (Story 6.1).
3. Keep enrichment optional; pipelines must not block when cache unavailable (Story 6.1).
4. Document indexes to avoid accidental duplicates in future migrations (Story 6.1).
5. Use `normalize_for_temp_id()` for consistent normalization (Story 6.2).
6. Never log sensitive data (salt, tokens) (Story 6.2).

### Git Intelligence (Recent Commits)

```
2239fee docs(story-6.2): finalize temporary company ID story
8467f08 fix(story-6.1): harden enterprise schema migration and finalize review
cdc4c1c feat(epic-5.6): post-MVP optimizations and data loading redesign
```

**Patterns to follow:**
- Use dataclasses for result types (`MatchResult`, `InsertBatchResult`)
- Use SQLAlchemy text() for raw SQL with parameterized queries
- Use structlog for logging with context binding
- Follow existing test patterns in `tests/unit/infrastructure/enrichment/`

### CRITICAL: Do NOT Reinvent

- **DO NOT** create alternative mapping loaders - extend `load_company_id_overrides()`
- **DO NOT** create alternative repository patterns - follow existing infrastructure patterns
- **DO NOT** add external dependencies - use stdlib + SQLAlchemy only
- **DO NOT** modify `CompanyIdResolver` in this story - that's Story 6.4

### Performance Requirements

| Operation | Target | Measurement |
|-----------|--------|-------------|
| `lookup_batch(1000 names)` | <100ms | Unit test with mock |
| `insert_batch(100 mappings)` | <50ms | Unit test with mock |
| YAML loading (5 files) | <10ms | Unit test |

### Environment Variables

```bash
# Optional - defaults to data/mappings
WDH_MAPPINGS_DIR=data/mappings
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/workdatahub   # required when exercising DB-backed repo
TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/workdatahub_test  # optional override; otherwise use pytest-postgresql fixture
```

### Database Access & Transactions

- Use SQLAlchemy 2.x `create_engine` with default pooling; obtain URL from `work_data_hub.config.get_settings()` when wiring repo.
- Repo accepts upstream `Connection`/`Session`; caller owns commit/rollback. No implicit autocommit; wrap inserts in explicit transaction.
- Always parameterize via `text()`; no f-strings. Bind logger context with counts only; never log alias/company_id values.

## References

- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (Story 6.3)
- Epic: `docs/epics/epic-6-company-enrichment-service.md` (Story 5.3 in epic index)
- Architecture Decision: `docs/architecture/architectural-decisions.md` (AD-010)
- Database Schema: `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py`
- Existing YAML: `data/mappings/company_id_overrides_plan.yml`
- CompanyIdResolver: `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`

### Quick Start (Dev Agent Checklist)

1. Files: `src/work_data_hub/config/mapping_loader.py`, `src/work_data_hub/infrastructure/enrichment/mapping_repository.py`, YAMLs under `data/mappings/*.yml`, tests in `tests/unit/config/` and `tests/unit/infrastructure/enrichment/`.
2. Env: set `WDH_MAPPINGS_DIR` if custom path; `DATABASE_URL` for manual DB runs; `TEST_DATABASE_URL` if overriding pytest-postgresql fixture.
3. Performance gates: YAML load (5 files) <10ms; `lookup_batch(1000)` <100ms; `insert_batch(100)` <50ms.
4. Commands: `uv run pytest tests/unit/config/test_mapping_loader.py tests/unit/infrastructure/enrichment/test_mapping_repository.py`; `uv run ruff check`; `uv run mypy --strict src/`.
5. Logging: `utils.logging.get_logger(__name__)`; bind counts only; never log alias/company_id; follow Decision #8 sanitization.
6. Error handling: propagate IntegrityError after logging counts; record conflicts list; YAML loader raises on invalid syntax, returns empty on missing file.

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 681 unit tests passing (no regressions)
- 17 new tests for mapping_loader.py
- 22 new tests for mapping_repository.py
- Ruff linting: All checks passed
- mypy: No errors in new files

### Completion Notes List

- **AC1 ✅**: Created `load_company_id_overrides()` in `mapping_loader.py` that loads all 5 priority levels from YAML files
- **AC2 ✅**: Created `CompanyMappingRepository` class with batch lookup from `enterprise.company_mapping` table
- **AC3 ✅**: `lookup_batch()` uses DISTINCT ON + ORDER BY priority ASC to return highest-priority match per alias_name
- **AC4 ✅**: `insert_batch()` uses ON CONFLICT DO NOTHING for idempotent inserts
- **AC5 ✅**: Performance test confirms 1000 lookups < 100ms with mock (actual: ~5ms)
- **AC6 ✅**: 39 new unit tests added (17 for YAML loader, 22 for repository)
- **AC7 ✅**: CompanyIdResolver continues to work without database connection (27 existing tests pass)
- Added type enforcement for YAML entries (string→string) and ordinality-based conflict lookup pairing to prevent false positives; refreshed compatibility test for YAML-only mode.

**Integration Pattern for Story 6.4:**
```python
# In CompanyIdResolver, add optional mapping_repository parameter:
from work_data_hub.infrastructure.enrichment import CompanyMappingRepository

# Usage with database:
with engine.connect() as conn:
    repo = CompanyMappingRepository(conn)
    results = repo.lookup_batch(alias_names)
    conn.commit()

# YAML-only mode (existing behavior):
from work_data_hub.config import load_company_id_overrides
overrides = load_company_id_overrides()
```

### File List

**New Files:**
- `src/work_data_hub/config/mapping_loader.py` - Multi-file YAML loader
- `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` - Database repository
- `data/mappings/company_id_overrides_account.yml` - Priority 2 placeholder
- `data/mappings/company_id_overrides_hardcode.yml` - Priority 3 placeholder
- `data/mappings/company_id_overrides_name.yml` - Priority 4 placeholder
- `data/mappings/company_id_overrides_account_name.yml` - Priority 5 placeholder
- `tests/unit/config/test_mapping_loader.py` - YAML loader unit tests
- `tests/unit/infrastructure/enrichment/test_mapping_repository.py` - Repository unit tests

**Modified Files:**
- `src/work_data_hub/config/__init__.py` - Added exports for mapping_loader
- `src/work_data_hub/infrastructure/enrichment/__init__.py` - Added exports for mapping_repository
- `docs/sprint-artifacts/sprint-status.yaml` - Updated story status

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story drafted with comprehensive context for dev readiness | Claude Opus 4.5 |
| 2025-12-06 | Implementation complete: YAML loader, repository, 39 unit tests | Claude Opus 4.5 |
