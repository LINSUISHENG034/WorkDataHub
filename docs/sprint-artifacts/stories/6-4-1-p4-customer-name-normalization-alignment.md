# Story 6.4.1: P4 Customer Name Normalization Alignment

Status: done

## Context & Business Value

- Epic 6 builds a resilient company enrichment service with self-learning cache mechanism.
- Story 6.4 implemented multi-tier lookup (YAML → DB cache → existing column → EQC sync → temp ID) with backflow mechanism.
- **This story** fixes a critical inconsistency discovered during Epic 6 mid-sprint review: P4 (Customer Name) lookup and backflow use RAW values instead of normalized values, causing cache misses.
- Business value: Restores the self-learning feedback loop for P4 priority level, improving cache hit rates over time and reducing EQC API costs.

## Story

As a **data engineer**,
I want **CompanyIdResolver to use normalize_company_name for P4 (Customer Name) lookup and backflow**,
So that **the self-learning cache mechanism works correctly with legacy data format**.

## Acceptance Criteria

1. **AC1**: `_resolve_via_db_cache` applies `normalize_company_name` to customer_name column values before database lookup.
2. **AC2**: `_backflow_new_mappings` applies `normalize_company_name` to customer_name values before writing to database.
3. **AC3**: P1 (plan_code), P2 (account_number), P3 (hardcode), P5 (account_name) continue using RAW values (no normalization).
4. **AC4**: Unit tests verify normalization is applied correctly for P4 only.
5. **AC5**: Integration test confirms cache hit rate improvement with normalized P4 keys.
6. **AC6**: Backflow documentation updated with correction explaining P4-only normalization.

## Dependencies & Interfaces

- **Prerequisite**: Story 6.4 (Multi-tier Lookup) - DONE
- **Prerequisite**: Story 5.6.2 (normalize_company_name bracket fix) - DONE
- **Sprint Change Proposal**: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-07-p4-normalization-fix.md` (APPROVED)
- **Issue Report**: `docs/specific/backflow/critical-issue-resolver-inconsistency.md`
- **Integration Point**: Story 6.5 (Async Queue) - No changes needed, uses `normalize_for_temp_id` correctly

## Tasks / Subtasks

- [x] Task 1: Modify `_resolve_via_db_cache` for P4 normalization (AC1, AC3)
  - [x] 1.1: Import `normalize_company_name` from `work_data_hub.infrastructure.cleansing`
  - [x] 1.2: Add `needs_normalization` flag to lookup_columns tuple (P4=True, others=False)
  - [x] 1.3: Apply `normalize_company_name` to P4 values before adding to alias_names set
  - [x] 1.4: Maintain mapping from normalized → original values for result application

- [x] Task 2: Modify `_backflow_new_mappings` for P4 normalization (AC2, AC3)
  - [x] 2.1: Add `needs_normalization` flag to backflow_fields tuple (P4=True, others=False)
  - [x] 2.2: Apply `normalize_company_name` to P4 values before creating mapping entry
  - [x] 2.3: Skip backflow if normalization returns empty string

- [x] Task 3: Unit tests (AC4)
  - [x] 3.1: Test P4 lookup uses normalized value
  - [x] 3.2: Test P4 backflow writes normalized value
  - [x] 3.3: Test P1/P2/P5 continue using RAW values
  - [x] 3.4: Test normalization edge cases (empty result, special characters)
  - [x] 3.5: Test P3 (hardcode/plan_code) path remains RAW to guard AC3 regression

- [x] Task 4: Integration test (AC5)
  - [x] 4.1: Test cache hit with normalized P4 key after backflow
  - [x] 4.2: Verify round-trip: backflow → lookup → hit

- [x] Task 5: Documentation update (AC6)
  - [x] 5.1: Update `docs/specific/backflow/critical-issue-resolver-inconsistency.md` with correction section

## Dev Notes

### Architecture Context

- **Layer**: Infrastructure (enrichment subsystem)
- **Pattern**: Selective normalization based on priority level
- **Clean Architecture**: Import from `infrastructure.cleansing` (same layer)
- **Reference**: Sprint Change Proposal approved 2025-12-07

### Root Cause Analysis

The original backflow documentation suggested using normalized names for ALL priority levels. However, legacy system analysis revealed that **only P4 (Customer Name)** should use normalized values:

| Priority | Field | Lookup/Backflow Key | Rationale |
|----------|-------|---------------------|-----------|
| P1 (Plan) | 计划代码 | **RAW** | System-generated identifier |
| P2 (Account) | 年金账户号 | **RAW** | Structured identifier |
| P3 (Hardcode) | 硬编码 | **RAW** | Explicit business rules |
| P4 (Name) | 客户名称 | **NORMALIZED** | High variance, needs cleaning |
| P5 (Account Name) | 年金账户名 | **RAW** | Stored as-is in legacy DB |

### Non-Goals & Guardrails

- Do **not** modify async enqueue/dedupe behavior: `_enqueue_for_async_enrichment` and `normalize_for_temp_id` stay as-is (Story 6.5 scope).

### File Locations

| File | Purpose | Action |
|------|---------|--------|
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | Main resolver class | MODIFY |
| `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py` | `normalize_company_name` function | REFERENCE |
| `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | Resolver unit tests | MODIFY |
| `docs/specific/backflow/critical-issue-resolver-inconsistency.md` | Issue documentation | UPDATE |

**Additional Files Updated During Implementation**
- `scripts/validation/epic6/verify_resolver_flow.py` (validation harness aligned to normalization choice)
- `docs/specific/backflow/backflow-mechanism-intent.md`
- `docs/specific/backflow/epic-6-mid-sprint-review.md`
- `docs/specific/company-id/legacy-company-id-matching-logic.md`
- `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-07-p4-normalization-fix.md`
- `docs/sprint-artifacts/code-reviews/validation-report-20251207-114930.md`
- `docs/sprint-artifacts/sprint-status.yaml`

### Code Changes Required

**Change #1: `_resolve_via_db_cache` Method (Lines ~437-448)**

```python
# BEFORE
lookup_columns = [
    strategy.plan_code_column,
    strategy.account_number_column,
    strategy.customer_name_column,
    strategy.account_name_column,
]

alias_names: set[str] = set()
for col in lookup_columns:
    if col in df.columns:
        values = df.loc[mask_unresolved, col].dropna().astype(str).unique()
        alias_names.update(values)

# AFTER
from work_data_hub.infrastructure.cleansing import normalize_company_name

# P4 (customer_name) needs normalization, others use RAW values
lookup_columns = [
    (strategy.plan_code_column, False),      # P1: RAW
    (strategy.account_number_column, False), # P2: RAW
    (strategy.customer_name_column, True),   # P4: NORMALIZED
    (strategy.account_name_column, False),   # P5: RAW
]

alias_names: set[str] = set()
normalized_to_original: Dict[str, List[str]] = {}

for col, needs_normalization in lookup_columns:
    if col not in df.columns:
        continue
    values = df.loc[mask_unresolved, col].dropna().astype(str).unique()
    for v in values:
        if needs_normalization:
            normalized = normalize_company_name(v)
            if normalized:
                alias_names.add(normalized)
                if normalized not in normalized_to_original:
                    normalized_to_original[normalized] = []
                normalized_to_original[normalized].append(v)
        else:
            alias_names.add(v)
```

**Change #2: `_backflow_new_mappings` Method (Lines ~617-625)**

```python
# BEFORE
backflow_fields = [
    (strategy.account_number_column, "account", 2),
    (strategy.customer_name_column, "name", 4),
    (strategy.account_name_column, "account_name", 5),
]

for column, match_type, priority in backflow_fields:
    # ...
    new_mappings.append({
        "alias_name": str(alias_value).strip(),
        # ...
    })

# AFTER
from work_data_hub.infrastructure.cleansing import normalize_company_name

backflow_fields = [
    (strategy.account_number_column, "account", 2, False),    # P2: RAW
    (strategy.customer_name_column, "name", 4, True),         # P4: NORMALIZED
    (strategy.account_name_column, "account_name", 5, False), # P5: RAW
]

for column, match_type, priority, needs_normalization in backflow_fields:
    # ...
    if needs_normalization:
        alias_name = normalize_company_name(str(alias_value))
        if not alias_name:
            continue
    else:
        alias_name = str(alias_value).strip()

    new_mappings.append({
        "alias_name": alias_name,
        # ...
    })
```

### normalize_company_name Function Reference

Location: `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py:54-119`

Key behaviors:
- Collapses whitespace to single spaces
- Removes decorative characters
- Cleans leading/trailing bracket content (Story 5.6.2)
- Removes status markers (核心、非核心, etc.)
- Converts full-width ASCII to half-width
- Normalizes parentheses to full-width (Chinese standard)

**Important**: Use `normalize_company_name` (NOT `normalize_for_temp_id`) because:
1. `normalize_company_name` aligns with legacy `clean_company_name` behavior
2. `normalize_for_temp_id` includes lowercase conversion which is NOT in legacy

### Testing Strategy

**Unit Tests (add to existing test file):**
```python
def test_db_cache_lookup_normalizes_p4_customer_name():
    """P4 (customer_name) should be normalized before DB lookup."""
    # Setup: DB has normalized key "公司A"
    # Input: DataFrame has raw value "  公司A - 核心  "
    # Expected: Cache hit because normalized("  公司A - 核心  ") == "公司A"

def test_db_cache_lookup_raw_for_p1_p2_p5():
    """P1, P2, P5 should use RAW values for DB lookup."""
    # Setup: DB has raw key "PLAN001"
    # Input: DataFrame has "PLAN001"
    # Expected: Cache hit with exact match

def test_backflow_normalizes_p4_customer_name():
    """P4 backflow should write normalized value to DB."""
    # Input: Row with customer_name "  公司B - 非核心  "
    # Expected: Backflow writes "公司B" to DB

def test_backflow_raw_for_p2_p5():
    """P2, P5 backflow should write RAW values to DB."""
    # Input: Row with account_number "ACC001"
    # Expected: Backflow writes "ACC001" to DB

def test_p4_normalization_empty_result_skipped():
    """If normalization returns empty string, skip backflow."""
    # Input: customer_name that normalizes to empty
    # Expected: No backflow entry created
```

### Previous Story Learnings (Story 6.4)

1. Use dataclasses for result types (`MatchResult`, `InsertBatchResult`)
2. Use SQLAlchemy text() for raw SQL with parameterized queries
3. Repository: caller owns transaction; log counts only, never alias/company_id values
4. Keep enrichment optional; pipelines must not block when cache unavailable
5. Performance: 1000 rows < 100ms without EQC calls

### Git Intelligence (Recent Commits)

```
eeaa995 feat(story-6.5): implement async enrichment queue integration
4e317db feat(story-6.4): implement multi-tier company ID resolver lookup
85f48e3 feat(story-6.3): finalize mapping repository and yaml overrides
```

**Patterns to follow:**
- Import from `work_data_hub.infrastructure.cleansing` (same layer)
- Use structlog for logging with context binding
- Follow existing test patterns in `tests/unit/infrastructure/enrichment/`

### CRITICAL: Do NOT Reinvent

- **DO NOT** create new normalization functions - use existing `normalize_company_name`
- **DO NOT** modify `normalize_company_name` behavior - it's already correct
- **DO NOT** normalize P1, P2, P3, P5 - only P4 needs normalization
- **DO NOT** break backward compatibility - existing tests must pass

### Performance Requirements

| Operation | Target | Notes |
|-----------|--------|-------|
| `normalize_company_name` per value | <1ms | Already optimized |
| `_resolve_via_db_cache` with normalization | <60ms for 1000 rows | Slight overhead acceptable |
| `_backflow_new_mappings` with normalization | <60ms for 100 mappings | Slight overhead acceptable |

### Security & Logging Guardrails

- Logging: bind counts only; never log alias_name/company_id values
- Follow Decision #8 sanitization rules
- PII: treat alias_name/company_name as PII; mask or omit in logs

### Environment Variables

No new environment variables required. Uses existing:
- `DATABASE_URL` - PostgreSQL connection
- `WDH_MAPPINGS_DIR` - YAML overrides location
- `WDH_ALIAS_SALT` - Temporary ID generation

### Verification Script

After implementation, run: `scripts/validation/epic6/verify_resolver_flow.py`

Expected results:
1. Backflow writes Normalized Name for P4 only
2. Lookup queries with Normalized Name for P4 only
3. P1, P2, P5 continue using RAW values

### LLM Quick Brief (developer-ready)

1) **Scope**: Only P4 (customer_name) needs normalization; P1/P2/P3/P5 use RAW values.
2) **Function**: Use `normalize_company_name` from `infrastructure.cleansing.rules.string_rules`.
3) **Changes**: 2 methods in `company_id_resolver.py` - `_resolve_via_db_cache` and `_backflow_new_mappings`.
4) **Pattern**: Add `needs_normalization` flag to lookup_columns/backflow_fields tuples.
5) **Tests**: Add 5 unit tests verifying P4 normalization and P1/P2/P5 RAW behavior.
6) **Guardrails**: No PII in logs; maintain backward compatibility; no new deps.

## References

- Sprint Change Proposal: `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-07-p4-normalization-fix.md`
- Issue Report: `docs/specific/backflow/critical-issue-resolver-inconsistency.md`
- Story 6.4: `docs/sprint-artifacts/stories/6-4-internal-mapping-resolver-multi-tier-lookup.md`
- normalize_company_name: `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py:54-119`
- CompanyIdResolver: `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`

### Quick Start (Dev Agent Checklist)

1. **Files to modify**: `company_id_resolver.py`, `test_company_id_resolver.py`
2. **Files to reference**: `string_rules.py` (normalize_company_name)
3. **Import**: `from work_data_hub.infrastructure.cleansing import normalize_company_name`
4. **Methods**: `_resolve_via_db_cache` (lines 413-481), `_backflow_new_mappings` (lines 576-663)
5. **Tests**: Add 5 new tests for P4 normalization behavior
6. **Commands**: `uv run pytest tests/unit/infrastructure/enrichment/test_company_id_resolver.py -v`; `uv run ruff check`; `uv run mypy src/`
7. **Verification**: `uv run python scripts/validation/epic6/verify_resolver_flow.py`

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 60 unit tests pass (including 12 new P4 normalization tests)
- No regressions detected

### Completion Notes List

- ✅ Task 1: Modified `_resolve_via_db_cache` to apply `normalize_company_name` for P4 (customer_name) lookup while keeping P1/P2/P5 RAW
- ✅ Task 2: Modified `_backflow_new_mappings` to apply `normalize_company_name` for P4 backflow while keeping P2/P5 RAW
- ✅ Task 3: Added 12 unit tests covering P4 normalization, RAW value preservation for other priorities, and edge cases
- ✅ Task 4: Added integration test verifying round-trip cache hit improvement with normalized P4 keys
- ✅ Task 5: Updated `critical-issue-resolver-inconsistency.md` with Section 6 documenting the resolution

### File List

| File | Action |
|------|--------|
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | MODIFIED |
| `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | MODIFIED |
| `docs/specific/backflow/critical-issue-resolver-inconsistency.md` | MODIFIED |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-07 | Story drafted from Sprint Change Proposal with comprehensive context | Claude Opus 4.5 |
| 2025-12-07 | Implementation complete - P4 normalization for lookup and backflow | Claude Opus 4.5 |
