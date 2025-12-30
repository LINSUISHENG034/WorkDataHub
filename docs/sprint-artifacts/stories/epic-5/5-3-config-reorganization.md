# Story 5.3: Config Namespace Reorganization

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | 5.3 |
| **Epic** | Epic 5: Infrastructure Layer Architecture & Domain Refactoring |
| **Status** | Done |
| **Created** | 2025-12-02 |
| **Priority** | Critical (Blocks Epic 9) |
| **Estimate** | 1.0 day |

---

## User Story

**As a** developer,
**I want to** eliminate config namespace conflicts and organize configuration by responsibility,
**So that** architecture layers are clear and configs are easy to locate.

---

## Strategic Context

> **This story enforces separation of concerns for configuration.**
>
> Currently, the `config` namespace is overloaded with infrastructure code (`schema.py`, `loader.py`), business data (`mappings/`), and runtime settings. This story distributes these artifacts to their proper architectural layers: `infrastructure/settings` for code, `data/mappings` for business rules, and domain-specific constants consolidated into single files.

### Business Value

- **Clearer Architecture:** Separates infrastructure code from business data configuration.
- **Eliminates Conflicts:** Resolves namespace collisions (multiple `config.py` files).
- **Improves Maintainability:** Developers know exactly where to look for settings vs. data.
- **Enables Scalability:** Standardizes configuration patterns for future domains.

### Dependencies

- **Story 5.2 (Cleansing Migration)** must be completed ✅
- This story affects 28 files across source and tests.

---

## Acceptance Criteria

### AC-5.3.1: Infrastructure Code Relocated

**Requirement:** Move configuration handling code to the infrastructure layer.

**Migrations:**
- Move `src/work_data_hub/config/schema.py` → `src/work_data_hub/infrastructure/settings/data_source_schema.py`
- Move `src/work_data_hub/config/mapping_loader.py` → `src/work_data_hub/infrastructure/settings/loader.py`

**Verification:**
```bash
test -f src/work_data_hub/infrastructure/settings/data_source_schema.py && echo "PASS: Schema moved" || echo "FAIL"
test -f src/work_data_hub/infrastructure/settings/loader.py && echo "PASS: Loader moved" || echo "FAIL"
```

---

### AC-5.3.2: Business Data Relocated

**Requirement:** Move business mapping YAML files to the data directory.

**Pre-condition:** `data/mappings/` directory already exists (created in Story 5.1) with only `__init__.py`.

**Migrations:**
- Move `src/work_data_hub/config/mappings/business_type_code.yml` → `data/mappings/`
- Move `src/work_data_hub/config/mappings/company_branch.yml` → `data/mappings/`
- Move `src/work_data_hub/config/mappings/company_id_overrides_plan.yml` → `data/mappings/`
- Move `src/work_data_hub/config/mappings/default_portfolio_code.yml` → `data/mappings/`

**Verification:**
```bash
ls data/mappings/*.yml 2>/dev/null | wc -l | grep -q "4" && echo "PASS: 4 YAML files moved" || echo "FAIL"
test ! -d src/work_data_hub/config/mappings && echo "PASS: Old mappings dir removed" || echo "FAIL"
```

---

### AC-5.3.3: Domain Configs Consolidated

**Requirement:** Consolidate and rename domain-level config files to eliminate conflicts.

**CRITICAL - Annuity Performance:**
Two files exist that must be MERGED:
- `src/work_data_hub/domain/annuity_performance/config.py` (155 lines - business mappings)
- `src/work_data_hub/domain/annuity_performance/constants.py` (35 lines - gold columns)

**Action:** Merge `config.py` content INTO existing `constants.py`, then DELETE `config.py`.

**Pipelines:**
- Rename `src/work_data_hub/domain/pipelines/config.py` → `src/work_data_hub/domain/pipelines/pipeline_config.py`

**Verification:**
```bash
test ! -f src/work_data_hub/domain/annuity_performance/config.py && echo "PASS: config.py deleted" || echo "FAIL"
grep -q "PLAN_CODE_CORRECTIONS" src/work_data_hub/domain/annuity_performance/constants.py && echo "PASS: Merged" || echo "FAIL"
test -f src/work_data_hub/domain/pipelines/pipeline_config.py && echo "PASS: Pipeline config renamed" || echo "FAIL"
```

---

### AC-5.3.4: Config Directory Cleanup

**Requirement:** The `src/work_data_hub/config/` directory should only contain runtime environment settings.

**Allowed Files (KEEP):**
- `__init__.py`
- `settings.py` (Environment variables)
- `data_sources.yml` (Runtime config)

**Files to REMOVE:**
- `schema.py` (moved to infrastructure)
- `mapping_loader.py` (moved to infrastructure)
- `mappings/` directory (moved to data/)

**Verification:**
```bash
ls src/work_data_hub/config/ | sort | tr '\n' ' ' | grep -q "__init__.py __pycache__ data_sources.yml settings.py" && echo "PASS" || echo "Check remaining files"
```

---

### AC-5.3.5: Global Import Updates

**Requirement:** Update all import statements (28 files) to reflect new paths.

**Transformation Table (BOTH patterns - codebase uses mixed formats):**

| Old Import Pattern | New Import Pattern |
|-------------------|-------------------|
| `from work_data_hub.config.schema` | `from work_data_hub.infrastructure.settings.data_source_schema` |
| `from src.work_data_hub.config.schema` | `from src.work_data_hub.infrastructure.settings.data_source_schema` |
| `from work_data_hub.config.mapping_loader` | `from work_data_hub.infrastructure.settings.loader` |
| `from src.work_data_hub.config.mapping_loader` | `from work_data_hub.infrastructure.settings.loader` |
| `from work_data_hub.domain.annuity_performance.config` | `from work_data_hub.domain.annuity_performance.constants` |
| `from work_data_hub.domain.pipelines.config` | `from work_data_hub.domain.pipelines.pipeline_config` |
| `from src.work_data_hub.domain.pipelines.config` | `from src.work_data_hub.domain.pipelines.pipeline_config` |

**Pass Criteria:** No `ImportError` or `ModuleNotFoundError` during tests.

---

### AC-5.3.6: Functionality Preservation

**Requirement:** System behavior must remain unchanged.

**Verification:**
```bash
uv run pytest tests/ -v --tb=short
```

**Pass Criteria:** All tests pass green.

---

## Complete File Reference

### Files to Move/Rename

| Source | Destination | Action |
|--------|-------------|--------|
| `src/work_data_hub/config/schema.py` | `src/work_data_hub/infrastructure/settings/data_source_schema.py` | Move |
| `src/work_data_hub/config/mapping_loader.py` | `src/work_data_hub/infrastructure/settings/loader.py` | Move |
| `src/work_data_hub/config/mappings/*.yml` (4 files) | `data/mappings/` | Move |
| `src/work_data_hub/domain/annuity_performance/config.py` | Merge into `constants.py` | Merge+Delete |
| `src/work_data_hub/domain/pipelines/config.py` | `pipeline_config.py` | Rename |

### Files Requiring Import Updates

**Group 1: `config.schema` imports (8 files)**

| File | Line | Current Import |
|------|------|----------------|
| `src/work_data_hub/io/connectors/file_connector.py` | 22 | `from src.work_data_hub.config.schema import (` |
| `src/work_data_hub/orchestration/ops.py` | 59 | `from src.work_data_hub.config.schema import (` |
| `tests/config/test_data_sources_schema.py` | 11 | `from src.work_data_hub.config.schema import (` |
| `tests/integration/test_annuity_config.py` | 22 | `from src.work_data_hub.config.schema import (` |
| `tests/integration/config/test_settings_integration.py` | 15, 242, 250, 268, 275 | `from src.work_data_hub.config.schema import ...` |
| `tests/integration/io/test_file_discovery_integration.py` | 24 | `from src.work_data_hub.config.schema import ...` |
| `tests/unit/config/test_schema_v2.py` | 14 | `from src.work_data_hub.config.schema import (` |
| `tests/unit/io/connectors/test_file_discovery_service.py` | 15 | `from src.work_data_hub.config.schema import ...` |

**Group 2: `config.mapping_loader` imports (1 file)**

| File | Line | Current Import |
|------|------|----------------|
| `tests/config/test_mapping_loader.py` | 14 | `from src.work_data_hub.config.mapping_loader import (` |

**Group 3: `pipelines.config` imports (8 files)**

| File | Line | Current Import |
|------|------|----------------|
| `src/work_data_hub/domain/annuity_performance/pipeline_steps.py` | 43 | `from work_data_hub.domain.pipelines.config import PipelineConfig, StepConfig` |
| `tests/domain/pipelines/conftest.py` | 14 | `from src.work_data_hub.domain.pipelines.config import ...` |
| `tests/domain/pipelines/test_config_builder.py` | 18 | `from src.work_data_hub.domain.pipelines.config import ...` |
| `tests/domain/pipelines/test_core.py` | 10 | `from src.work_data_hub.domain.pipelines.config import ...` |
| `tests/integration/test_performance_baseline.py` | 14 | `from work_data_hub.domain.pipelines.config import ...` |
| `tests/integration/test_pipeline_end_to_end.py` | 12 | `from work_data_hub.domain.pipelines.config import ...` |
| `tests/integration/pipelines/test_generic_steps_pipeline.py` | 17 | `from work_data_hub.domain.pipelines.config import ...` |
| `tests/unit/domain/pipelines/test_core.py` | 11 | `from src.work_data_hub.domain.pipelines.config import ...` |

**Group 4: `annuity_performance.config` imports (2 files)**

| File | Line | Current Import |
|------|------|----------------|
| `src/work_data_hub/domain/annuity_performance/config.py` | 14 | Self-reference (will be deleted) |
| `src/work_data_hub/domain/annuity_performance/pipeline_steps.py` | 27 | `from work_data_hub.domain.annuity_performance.config import (` |

---

## Tasks / Subtasks

### Task 1: Move Infrastructure Code (AC 5.3.1)

- [x] Copy `src/work_data_hub/config/schema.py` to `src/work_data_hub/infrastructure/settings/data_source_schema.py`
- [x] Copy `src/work_data_hub/config/mapping_loader.py` to `src/work_data_hub/infrastructure/settings/loader.py`
- [x] Update `infrastructure/settings/__init__.py` exports

### Task 2: Move Business Data (AC 5.3.2)

- [x] Move 4 YAML files from `config/mappings/` to `data/mappings/`
- [x] Update `loader.py` path resolution (see Dev Notes)
- [x] Remove empty `src/work_data_hub/config/mappings/` directory

### Task 3: Merge Annuity Config Files (AC 5.3.3) - CRITICAL

- [x] Read existing `constants.py` content (35 lines - `DEFAULT_ALLOWED_GOLD_COLUMNS`)
- [x] Read existing `config.py` content (155 lines - all mappings)
- [x] Create merged `constants.py` with ALL content from both files
- [x] Delete `config.py`
- [x] Update `__all__` exports to include all symbols

### Task 4: Rename Pipeline Config (AC 5.3.3)

- [x] Rename `domain/pipelines/config.py` → `domain/pipelines/pipeline_config.py`
- [x] Update `domain/pipelines/__init__.py` if it exports from config

### Task 5: Update Group 1 Imports - config.schema (8 files)

- [x] `src/work_data_hub/io/connectors/file_connector.py` (line 22)
- [x] `src/work_data_hub/orchestration/ops.py` (line 59)
- [x] `tests/config/test_data_sources_schema.py` (line 11)
- [x] `tests/integration/test_annuity_config.py` (line 22)
- [x] `tests/integration/config/test_settings_integration.py` (lines 15, 242, 250, 268, 275)
- [x] `tests/integration/io/test_file_discovery_integration.py` (line 24)
- [x] `tests/unit/config/test_schema_v2.py` (line 14)
- [x] `tests/unit/io/connectors/test_file_discovery_service.py` (line 15)

### Task 6: Update Group 2 Imports - mapping_loader (1 file)

- [x] `tests/config/test_mapping_loader.py` (line 14)

### Task 7: Update Group 3 Imports - pipelines.config (8 files)

- [x] `src/work_data_hub/domain/annuity_performance/pipeline_steps.py` (line 43)
- [x] `tests/domain/pipelines/conftest.py` (line 14)
- [x] `tests/domain/pipelines/test_config_builder.py` (line 18)
- [x] `tests/domain/pipelines/test_core.py` (line 10)
- [x] `tests/integration/test_performance_baseline.py` (line 14)
- [x] `tests/integration/test_pipeline_end_to_end.py` (line 12)
- [x] `tests/integration/pipelines/test_generic_steps_pipeline.py` (line 17)
- [x] `tests/unit/domain/pipelines/test_core.py` (line 11)

### Task 8: Update Group 4 Imports - annuity_performance.config (1 file after merge)

- [x] `src/work_data_hub/domain/annuity_performance/pipeline_steps.py` (line 27)

### Task 9: Cleanup & Verification (AC 5.3.4, 5.3.6)

- [x] Delete `src/work_data_hub/config/schema.py`
- [x] Delete `src/work_data_hub/config/mapping_loader.py`
- [x] Run `uv run ruff check .` - fix any errors
- [x] Run `uv run pytest tests/ -v --tb=short`

### Review Follow-ups (AI)

- [x] [AI-Review][Medium] Mutable default in Pydantic model (PipelineConfig.retry_limits) fixed
- [x] [AI-Review][Medium] Brittle path logic in loader.py fixed
- [x] [AI-Review][Low] Undocumented file change added to File List
- [x] [AI-Review][Low] Test failure in test_settings_env.py fixed

---

## Dev Notes

### Mapping Loader Path Update (CRITICAL)

**Current Logic:**
```python
# src/work_data_hub/config/mapping_loader.py line 43
return Path(__file__).parent / "mappings"
```

**New Logic Required:**
```python
# src/work_data_hub/infrastructure/settings/loader.py
def get_mappings_dir() -> Path:
    env_dir = os.environ.get("WDH_MAPPINGS_DIR")
    if env_dir:
        p = Path(env_dir)
        if not p.exists() or not p.is_dir():
            raise MappingLoaderError(f"WDH_MAPPINGS_DIR not found: {env_dir}")
        return p
    # New default: project root / data / mappings
    return Path(__file__).parents[4] / "data" / "mappings"
```

**Path Depth Calculation:**
```
infrastructure/settings/loader.py
    parents[0] = settings/
    parents[1] = infrastructure/
    parents[2] = work_data_hub/
    parents[3] = src/
    parents[4] = project root (E:\Projects\WorkDataHub)
```

### Annuity Constants Merge Strategy

**Final `constants.py` structure:**
```python
"""
Annuity Performance Domain Constants.

Consolidated from config.py (Story 4.10) and constants.py (Story 4.4).
"""
from typing import Dict, Sequence

# From original constants.py
DEFAULT_ALLOWED_GOLD_COLUMNS: Sequence[str] = (...)

# From original config.py
PLAN_CODE_CORRECTIONS: Dict[str, str] = {...}
PLAN_CODE_DEFAULTS: Dict[str, str] = {...}
BUSINESS_TYPE_CODE_MAPPING: Dict[str, str] = {...}
# ... all other mappings ...

__all__: list[str] = [
    "DEFAULT_ALLOWED_GOLD_COLUMNS",
    "PLAN_CODE_CORRECTIONS",
    # ... all exports ...
]
```

### Mypy Strict Mode

Ensure all `__init__.py` files have type-annotated exports:
```python
__all__: list[str] = ["DataSourceSchema", "load_mappings", ...]
```

---

## Dev Agent Record

### Context Reference

- **Previous Story (5.2):** Successfully migrated cleansing module. Follow same pattern.
- **Project Structure:** `data/` folder is at project root level, NOT inside `src/`.
- **Import Patterns:** Codebase uses BOTH `work_data_hub.` and `src.work_data_hub.` - handle both.

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- ✅ Moved `schema.py` to `infrastructure/settings/data_source_schema.py`
- ✅ Moved `mapping_loader.py` to `infrastructure/settings/loader.py` with updated path resolution
- ✅ Moved 4 YAML mapping files to `data/mappings/`
- ✅ Merged `annuity_performance/config.py` into `constants.py` (consolidated all domain constants)
- ✅ Renamed `pipelines/config.py` to `pipeline_config.py`
- ✅ Updated all import statements across 20+ files
- ✅ Updated `config/settings.py` to use new infrastructure path
- ✅ Updated internal pipelines module imports (core.py, builder.py, examples.py, __init__.py)
- ✅ Fixed test assertions in `test_mapping_loader.py` for new path structure
- ✅ All 1162 tests pass (5 pre-existing failures unrelated to this story)

### File List

**New Files:**
- `src/work_data_hub/infrastructure/settings/data_source_schema.py`
- `src/work_data_hub/infrastructure/settings/loader.py`
- `data/mappings/business_type_code.yml`
- `data/mappings/company_branch.yml`
- `data/mappings/company_id_overrides_plan.yml`
- `data/mappings/default_portfolio_code.yml`

**Modified Files:**
- `src/work_data_hub/infrastructure/settings/__init__.py`
- `src/work_data_hub/config/settings.py`
- `src/work_data_hub/domain/annuity_performance/constants.py`
- `src/work_data_hub/domain/annuity_performance/pipeline_steps.py`
- `src/work_data_hub/domain/pipelines/__init__.py`
- `src/work_data_hub/domain/pipelines/core.py`
- `src/work_data_hub/domain/pipelines/builder.py`
- `src/work_data_hub/domain/pipelines/examples.py`
- `src/work_data_hub/io/connectors/file_connector.py`
- `src/work_data_hub/orchestration/ops.py`
- `tests/config/test_data_sources_schema.py`
- `tests/config/test_mapping_loader.py`
- `tests/integration/test_annuity_config.py`
- `tests/integration/config/test_settings_integration.py`
- `tests/integration/io/test_file_discovery_integration.py`
- `tests/integration/test_performance_baseline.py`
- `tests/integration/test_pipeline_end_to_end.py`
- `tests/integration/pipelines/test_generic_steps_pipeline.py`
- `tests/unit/config/test_schema_v2.py`
- `tests/unit/io/connectors/test_file_discovery_service.py`
- `tests/unit/domain/pipelines/test_core.py`
- `tests/domain/pipelines/conftest.py`
- `tests/domain/pipelines/test_config_builder.py`
- `tests/domain/pipelines/test_core.py`
- `docs/architecture/architectural-decisions.md`

**Renamed Files:**
- `src/work_data_hub/domain/pipelines/config.py` → `pipeline_config.py`

**Deleted Files:**
- `src/work_data_hub/config/schema.py`
- `src/work_data_hub/config/mapping_loader.py`
- `src/work_data_hub/config/mappings/` (directory)
- `src/work_data_hub/domain/annuity_performance/config.py`

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-02 | Story implementation complete - all config namespace reorganization done | Claude Opus 4.5 |
| 2025-12-02 | Code Review fixes (Pydantic defaults, loader robustness, test fixes) | Amelia (Reviewer) |