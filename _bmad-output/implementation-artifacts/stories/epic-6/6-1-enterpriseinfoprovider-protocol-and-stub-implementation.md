# Story 6.1: Enterprise Schema Creation

Status: Done

## Story

As a **data engineer**,
I want **the enterprise schema and core enrichment tables created via Alembic migration**,
so that **enrichment caching, mapping, and async queueing have a stable persistence layer without blocking pipelines**.

## Acceptance Criteria

1. **AC1**: Alembic migration `create_enterprise_schema` creates schema `enterprise` (idempotent if already exists).
2. **AC2**: Table `enterprise.company_master` with columns: `company_id` (PK, VARCHAR(100)), `official_name` (NOT NULL), `unified_credit_code` (UNIQUE, VARCHAR(50)), `aliases` (TEXT[]), `source` (default `internal`), `created_at`, `updated_at` (timestamp with time zone).
3. **AC3**: Table `enterprise.company_mapping` with columns: `id` (SERIAL PK), `alias_name` (NOT NULL), `canonical_id` (NOT NULL), `match_type` (`plan|account|hardcode|name|account_name`), `priority` CHECK 1-5, `source` default `internal`, timestamps; UNIQUE `(alias_name, match_type)` and index `idx_company_mapping_lookup` on `(alias_name, priority)`.
4. **AC4**: Table `enterprise.enrichment_requests` with columns: `id` (SERIAL PK), `raw_name`, `normalized_name`, `temp_id` (nullable), `status` (`pending|processing|done|failed` default `pending`), `attempts` default 0, `last_error`, `resolved_company_id`, timestamps; index `idx_enrichment_requests_status` on `(status, created_at)` and partial unique index `idx_enrichment_requests_normalized` on `normalized_name` when status in (`pending`,`processing`).
5. **AC5**: Migration is reversible: downgrade drops indexes, tables, and schema objects created by this migration only.
6. **AC6**: Smoke tests (or migration checks) verify tables and indexes exist after upgrade and are removed after downgrade.
7. **AC7**: No breaking changes to existing pipelines: enrichment remains optional; no runtime dependency on new tables unless explicitly used.

## Tasks / Subtasks

- [x] Task 1: Migration scaffolding (AC1, AC5)
  - [x] 1.1: Create Alembic migration file `io/schema/migrations/<timestamp>_create_enterprise_schema.py`
  - [x] 1.2: Ensure upgrade creates schema if not exists; downgrade removes created objects only

- [x] Task 2: `company_master` DDL (AC2)
  - [x] 2.1: Define columns and constraints per AC2
  - [x] 2.2: Add optional `aliases` TEXT[] column
  - [x] 2.3: Add timestamps with defaults (`now()`)

- [x] Task 3: `company_mapping` DDL (AC3)
  - [x] 3.1: Define columns and CHECK constraint on `priority` 1-5
  - [x] 3.2: Add UNIQUE(alias_name, match_type)
  - [x] 3.3: Add index `idx_company_mapping_lookup` on (alias_name, priority)

- [x] Task 4: `enrichment_requests` DDL (AC4)
  - [x] 4.1: Define status enum via CHECK or VARCHAR constraint with default `pending`
  - [x] 4.2: Add index `idx_enrichment_requests_status`
  - [x] 4.3: Add partial unique index `idx_enrichment_requests_normalized` on normalized_name for pending/processing

- [x] Task 5: Migration safety & reversibility (AC5, AC6)
  - [x] 5.1: Implement upgrade/downgrade with dependency-safe drop order
  - [x] 5.2: Guard against double-creation (IF NOT EXISTS)
  - [x] 5.3: Add simple verification helper in tests to check objects after upgrade/downgrade

- [x] Task 6: Tests & checks (AC6, AC7)
  - [x] 6.1: Add migration smoke tests (upgrade then reflect metadata; downgrade cleanup)
  - [x] 6.2: Document how to run migration locally (uv/alembic command)
  - [x] 6.3: Confirm pipelines remain optional: no code path requires the tables in this story

## Dev Notes

### Architecture Context

- Establishes the **persistence layer** for enrichment: master data, mapping cache, and async queue.
- Keeps pipelines non-blocking: enrichment tables are optional until higher-layer services consume them.
- Aligns with Tech Spec Phase 1 (enterprise schema + tables) before resolver/gateway stories.

### File Locations

| File | Purpose | Status |
|------|---------|--------|
| `io/schema/migrations/<timestamp>_create_enterprise_schema.py` | Alembic migration | NEW |
| `io/schema/env.py` | Alembic config hook (reuse) | Existing |
| `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` | Future reader of `company_mapping` | Existing/Future |
| `src/work_data_hub/domain/company_enrichment/service.py` | Future gateway | Existing/Future |
| `tests/integration/migrations/` | Migration smoke tests | NEW |
| `docs/sprint-artifacts/code-reviews/validation-report-20251206.md` | Story validation report | NEW |
| `docs/sprint-artifacts/code-reviews/validation-report-6-1-20251206-210644.md` | Story 6.1 code review report | NEW |
| `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` | Tech spec reference for Epic 6 | NEW |

### Design Details

**DDL specifics**
- `company_master(company_id PK, official_name NOT NULL, unified_credit_code UNIQUE, aliases TEXT[], source DEFAULT 'internal', created_at/updated_at DEFAULT now())`
- `company_mapping(id PK, alias_name NOT NULL, canonical_id NOT NULL, match_type VARCHAR(20) NOT NULL, priority INT CHECK 1-5, source DEFAULT 'internal', timestamps, UNIQUE(alias_name, match_type), INDEX idx_company_mapping_lookup(alias_name, priority))`
- `enrichment_requests(id PK, raw_name NOT NULL, normalized_name NOT NULL, temp_id NULL, status VARCHAR(20) DEFAULT 'pending', attempts INT DEFAULT 0, last_error TEXT, resolved_company_id VARCHAR(100), timestamps, INDEX idx_enrichment_requests_status(status, created_at), PARTIAL UNIQUE idx_enrichment_requests_normalized(normalized_name) WHERE status IN ('pending','processing'))`

**Reversibility**
- Upgrade creates schema then tables then indexes; downgrade drops indexes then tables then schema (if empty) to avoid dependency issues.
- Use IF EXISTS/IF NOT EXISTS guards where supported to keep idempotent.

**Safety & Compatibility**
- No existing pipeline depends on these tables in this story; enrichment remains optional.
- Regression guard: run any pipeline entrypoint without creating the schema to confirm it still succeeds (tables only used when explicitly invoked).
- Privilege model: migration runs as schema owner (DDL rights); app runtime may use a lower-privileged role with read/write on the new tables as needed.
- Avoid leaking secrets: no tokens or sensitive data in migration logs.

### Testing Strategy

- Migration upgrade/downgrade smoke tests:
  - Apply migration, reflect metadata, assert tables and indexes exist.
  - Downgrade and assert objects removed.
- Static checks: alembic lint (if available) to ensure heads aligned.
- Optional: run against local Postgres container to validate constraints and partial index.
- Run locally:
  1) `export DATABASE_URL=postgresql+psycopg2://<user>:<password>@localhost:5432/<db>` (or set in `.env`)
  2) `uv run alembic upgrade head`
  3) `uv run alembic downgrade -1`
  4) Verify indexes via `\\d enterprise.company_mapping` and `\\d enterprise.enrichment_requests` in psql.

### Dependencies

- Alembic migration framework (existing project setup).
- PostgreSQL (supports schema, partial index).

### Previous Epic Learnings

1. Keep migrations idempotent and reversible.
2. Prefer explicit constraints (CHECK, UNIQUE) to prevent data drift.
3. Keep enrichment optional; pipelines must not block when cache unavailable.
4. Document indexes to avoid accidental duplicates in future migrations.

### References

- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (Story 6.1)
- Epic: `docs/epics/epic-6-company-enrichment-service.md` (enrichment service goals)
- Legacy mappings analysis: `docs/supplement/01_company_id_analysis.md`
- Enrichment pipeline context: `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`
- Normalization/helpers to reuse (future resolver/gateway): `src/work_data_hub/infrastructure/enrichment/normalizer.py` (normalize_for_temp_id, generate_temp_company_id)

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Migration upgrade/downgrade tested successfully
- All 13 integration tests passed

### Completion Notes List

- Created Alembic migration `20251206_000001_create_enterprise_schema.py` with idempotent upgrade/downgrade
- Implemented `enterprise` schema with 3 tables: `company_master`, `company_mapping`, `enrichment_requests`
- All tables include proper constraints (PK, UNIQUE, CHECK) and indexes per AC requirements
- Migration uses helper functions `_table_exists()` and `_index_exists()` for idempotency
- Downgrade uses `DROP IF EXISTS` for safety
- Created comprehensive integration test suite with 13 tests covering all ACs
- Verified migration reversibility (downgrade + re-upgrade successful)
- Confirmed no breaking changes to existing pipelines (AC7)

### File List

- `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py` (NEW)
- `tests/integration/migrations/__init__.py` (NEW)
- `tests/integration/migrations/test_enterprise_schema_migration.py` (NEW)
- `docs/sprint-artifacts/stories/6-1-enterpriseinfoprovider-protocol-and-stub-implementation.md` (MODIFIED)
- `docs/sprint-artifacts/sprint-status.yaml` (MODIFIED)
- `docs/sprint-artifacts/code-reviews/validation-report-20251206.md` (NEW)
- `docs/sprint-artifacts/code-reviews/validation-report-6-1-20251206-210644.md` (NEW)
- `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md` (NEW)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story implementation complete - Enterprise schema and tables created via Alembic migration | Claude Opus 4.5 |
