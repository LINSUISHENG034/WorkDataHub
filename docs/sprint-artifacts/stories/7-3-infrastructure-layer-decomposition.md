# Story 7.3: Infrastructure Layer Decomposition
---
epic: 7
epic-title: Code Quality - File Length Refactoring
story-id: 7.3
title: Infrastructure Layer Decomposition
priority: P0-CRITICAL
status: done  # Code Review passed 2025-12-22
source: sprint-change-proposal-2025-12-21-file-length-refactoring.md §4.1, Item 7.3
---
Scope & Dependencies:
- Story 7.2 (IO Layer Modularization) should be complete or in parallel
- This story focuses on 2 infrastructure enrichment layer files > 800 lines
- All existing consumers must not be impacted by the refactoring

## Story

As a **developer maintaining WorkDataHub**,
I want **the oversized infrastructure enrichment files decomposed into focused sub-modules**,
so that **code is more navigable, testable, and maintainable**.

## Acceptance Criteria

1. **AC-1: company_id_resolver.py Decomposition**
   - Create `infrastructure/enrichment/resolver/` package with `__init__.py`
   - Split `company_id_resolver.py` (1343 lines) into modules < 500 lines each
   - **CRITICAL:** Retain original `company_id_resolver.py` as a facade module re-exporting from new package
   - All existing `from work_data_hub.infrastructure.enrichment.company_id_resolver import X` imports continue to work

2. **AC-2: mapping_repository.py Decomposition**
   - Create `infrastructure/enrichment/repository/` package with `__init__.py`
   - Split `mapping_repository.py` (1069 lines) into modules < 500 lines each
   - **CRITICAL:** Retain original `mapping_repository.py` as a facade module re-exporting from new package
   - All existing `from work_data_hub.infrastructure.enrichment.mapping_repository import X` imports continue to work

3. **AC-3: Module Size Compliance**
   - Each new module MUST be < 500 lines (target: 200-400 lines)
   - Total line count should remain approximately the same (no omissions)

4. **AC-4: Test Preservation**
   - All existing tests pass without modification
   - `uv run pytest -v -m "not postgres and not monthly_data"` → 100% pass

5. **AC-5: No Circular Imports**
   - No new circular import issues introduced
   - Verify with:
     ```bash
     uv run python -c "from work_data_hub.infrastructure.enrichment.company_id_resolver import CompanyIdResolver; print('OK')"
     uv run python -c "from work_data_hub.infrastructure.enrichment.mapping_repository import CompanyMappingRepository; print('OK')"
     ```

6. **AC-6: No Functional Changes**
   - This is a pure refactoring story - no behavioral changes
   - ETL command operates identically

## Tasks / Subtasks

### company_id_resolver.py Decomposition (1343 → ~6 modules)

- [x] Task 1: Analyze `company_id_resolver.py` structure (AC: 1)
  - [x] Identify logical groupings by resolution strategy
  - [x] Map dependencies between methods
  - [x] Plan split strategy following patterns from Story 7-2

- [x] Task 2: Create `infrastructure/enrichment/resolver/` package structure (AC: 1, 3)
  - [x] Create `resolver/__init__.py` with re-exports (28 lines)
  - [x] Create `resolver/core.py` - CompanyIdResolver class + resolve_batch (467 lines)
  - [x] ~~Create `resolver/batch_resolver.py`~~ - merged into core.py for simplicity
  - [x] Create `resolver/yaml_strategy.py` - `_resolve_via_yaml_overrides` (78 lines)
  - [x] Create `resolver/db_strategy.py` - DB cache/enrichment_index strategies (370 lines)
    - `_resolve_via_db_cache`
    - `_resolve_via_enrichment_index`
    - `_resolve_via_company_mapping`
  - [x] Create `resolver/eqc_strategy.py` - EQC sync/provider strategies (267 lines)
    - `_resolve_via_eqc_sync`
    - `_resolve_via_eqc_provider`
  - [x] Create `resolver/backflow.py` - Backflow and async enrichment (223 lines)
    - `_backflow_new_mappings`
    - `_enqueue_for_async_enrichment`
    - `_generate_temp_id`

- [x] Task 3: Update facade module (AC: 1)
  - [x] Convert original `company_id_resolver.py` to facade (53 lines)
  - [x] Re-export `CompanyIdResolver` and all public symbols
  - [x] Preserve `__all__` for explicit exports

### mapping_repository.py Decomposition (1069 → ~5 modules)

- [x] Task 4: Analyze `mapping_repository.py` structure (AC: 2)
  - [x] Identify logical groupings by table/operation
  - [x] Map dependencies between methods
  - [x] Plan split strategy

- [x] Task 5: Create `infrastructure/enrichment/repository/` package structure (AC: 2, 3)
  - [x] Create `repository/__init__.py` with re-exports (29 lines)
  - [x] Create `repository/models.py` - Result dataclasses (58 lines)
    - `MatchResult`
    - `InsertBatchResult`
    - `EnqueueResult`
  - [x] Create `repository/core.py` - CompanyMappingRepository base with mixins (84 lines)
    - `__init__`
    - `_normalize_lookup_key`
  - [x] Create `repository/company_mapping_ops.py` - company_mapping table operations (358 lines)
    - `lookup_batch`
    - `insert_batch`
    - `insert_batch_with_conflict_check`
    - `get_all_mappings`
    - `delete_by_source`
  - [x] Create `repository/enrichment_index_ops.py` - enrichment_index table operations (366 lines)
    - `lookup_enrichment_index`
    - `lookup_enrichment_index_batch`
    - `insert_enrichment_index_batch`
    - `update_hit_count`
  - [x] Create `repository/other_ops.py` - Other table operations (266 lines)
    - `insert_company_name_index_batch`
    - `enqueue_for_enrichment`
    - `upsert_base_info`

- [x] Task 6: Update facade module (AC: 2)
  - [x] Convert original `mapping_repository.py` to facade (34 lines)
  - [x] Re-export `CompanyMappingRepository`, `MatchResult`, `InsertBatchResult`, `EnqueueResult`
  - [x] Preserve `__all__` for explicit exports

### Verification

- [x] Task 7: Verify backward compatibility (AC: 1, 2, 5)
  - [x] Run AC-5 import verification commands
  - [x] Verify no circular imports

- [x] Task 8: Run test suite (AC: 4, 6)
  - [x] Run `uv run pytest -v -m "not postgres and not monthly_data"` → 1983 passed
  - [x] Verify ETL command works (plan-only mode)

---

## Dev Notes

### Decomposition Strategy (from Story 7-2)

**Pattern Established in Story 7-2:**
1. Create new package directory (e.g., `resolver/`)
2. Move logical groups of methods to focused modules
3. Use mixin or partial class pattern if needed for method splitting
4. Convert original file to facade with re-exports
5. Test backward compatibility with import verification

### CompanyIdResolver Analysis

| Method Group | Target Module | Est. Lines |
|--------------|---------------|------------|
| Core init, constants | `resolver/core.py` | ~180 |
| resolve_batch main flow | `resolver/batch_resolver.py` | ~200 |
| YAML override logic | `resolver/yaml_strategy.py` | ~60 |
| DB cache strategies | `resolver/db_strategy.py` | ~250 |
| EQC provider strategies | `resolver/eqc_strategy.py` | ~200 |
| Backflow + temp ID | `resolver/backflow.py` | ~200 |
| **Facade** | `company_id_resolver.py` | ~30 |
| **Total** | | ~1120 |

### MappingRepository Analysis

| Method Group | Target Module | Est. Lines |
|--------------|---------------|------------|
| Result dataclasses | `repository/models.py` | ~50 |
| Core init, helpers | `repository/core.py` | ~150 |
| company_mapping ops | `repository/company_mapping_ops.py` | ~270 |
| enrichment_index ops | `repository/enrichment_index_ops.py` | ~350 |
| Other table ops | `repository/other_ops.py` | ~200 |
| **Facade** | `mapping_repository.py` | ~30 |
| **Total** | | ~1050 |

### Class Splitting Approach

**Option A: Mixin Pattern (Recommended)**
```python
# repository/company_mapping_ops.py
class CompanyMappingOpsMixin:
    def lookup_batch(self, ...): ...
    def insert_batch(self, ...): ...

# repository/core.py
from .company_mapping_ops import CompanyMappingOpsMixin
from .enrichment_index_ops import EnrichmentIndexOpsMixin

class CompanyMappingRepository(CompanyMappingOpsMixin, EnrichmentIndexOpsMixin, ...):
    def __init__(self, connection: Connection):
        self._conn = connection
```

**Option B: Composition Pattern**
```python
# Keep single class, import helper functions
from .company_mapping_ops import lookup_batch_impl

class CompanyMappingRepository:
    def lookup_batch(self, ...):
        return lookup_batch_impl(self._conn, ...)
```

> [!TIP]
> **Prefer Mixin Pattern** as it preserves method signatures and allows IDE autocomplete.

### Zero Legacy Policy Reminder

From [project-context.md](file:///e:/Projects/WorkDataHub/docs/project-context.md):
- ❌ NEVER keep commented-out code or "v1" backups
- ❌ NEVER create wrappers for backward compatibility beyond simple re-exports
- ✅ ALWAYS refactor atomically

### Deprecated Methods to Consider

`company_id_resolver.py` contains deprecated methods:
- `_resolve_via_enrichment` (line 1254) - marked DEPRECATED
- `_resolve_via_enrichment_batch` (line 1293) - marked DEPRECATED

**Decision:** Keep deprecated methods in `resolver/backflow.py` or `resolver/eqc_strategy.py` for now since they may still have call sites. Document for future removal.

### References

- [Sprint Change Proposal §4.1](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-21-file-length-refactoring.md#4-detailed-change-proposals)
- [Story 7-2 IO Layer Modularization](file:///e:/Projects/WorkDataHub/docs/sprint-artifacts/stories/7-2-io-layer-modularization.md) - Pattern reference
- [project-context.md](file:///e:/Projects/WorkDataHub/docs/project-context.md) - Code structure limits

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - Pure refactoring story, no debugging required.

### Completion Notes List

1. **Design Decision:** Merged `batch_resolver.py` into `core.py` to avoid excessive module fragmentation. The `resolve_batch` method is tightly coupled with `CompanyIdResolver` class initialization.

2. **Mixin Pattern Adopted:** `CompanyMappingRepository` uses mixin pattern (`CompanyMappingOpsMixin`, `EnrichmentIndexOpsMixin`, `OtherOpsMixin`) for clean separation while preserving single class interface.

3. **Test Compatibility:** Added re-exports in facade for `_stdlib_logger`, `normalize_for_temp_id`, `normalize_company_name` to maintain test monkeypatching compatibility.

4. **Line Count Summary:**
   - Resolver package: 1433 lines (6 modules)
   - Repository package: 1161 lines (6 modules)
   - Facades: 87 lines (2 files)
   - Total: 2681 lines (vs original 2412 lines, +11% overhead from module structure)

5. **All ACs Verified:** AC-1 through AC-6 passed during code review 2025-12-22.

### File List

**New Files Created:**
- `src/work_data_hub/infrastructure/enrichment/resolver/__init__.py` (28 lines)
- `src/work_data_hub/infrastructure/enrichment/resolver/core.py` (467 lines)
- `src/work_data_hub/infrastructure/enrichment/resolver/yaml_strategy.py` (78 lines)
- `src/work_data_hub/infrastructure/enrichment/resolver/db_strategy.py` (370 lines)
- `src/work_data_hub/infrastructure/enrichment/resolver/eqc_strategy.py` (267 lines)
- `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py` (223 lines)
- `src/work_data_hub/infrastructure/enrichment/repository/__init__.py` (29 lines)
- `src/work_data_hub/infrastructure/enrichment/repository/models.py` (58 lines)
- `src/work_data_hub/infrastructure/enrichment/repository/core.py` (84 lines)
- `src/work_data_hub/infrastructure/enrichment/repository/company_mapping_ops.py` (358 lines)
- `src/work_data_hub/infrastructure/enrichment/repository/enrichment_index_ops.py` (366 lines)
- `src/work_data_hub/infrastructure/enrichment/repository/other_ops.py` (266 lines)

**Modified Files (Converted to Facades):**
- `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` (1343 → 53 lines)
- `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` (1069 → 34 lines)
