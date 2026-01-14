# Phase 0: Multi-Source Data Loading - Implementation Plan

> **Status:** Ready for Implementation
> **Branch:** `feature/orchestration-layer-refactor`
> **Worktree:** `E:\Projects\WorkDataHub-orchestration-refactor`
> **Created:** 2026-01-13

---

## Executive Summary

This plan implements the missing multi-table data loading functionality identified in the orchestration layer refactor review. The configuration layer (`domain_sources.yaml`, `domain_sources.py`) is complete, but the actual loading logic (`MultiTableLoader`, `read_data_op`) was never implemented.

### Current State Analysis

| Component | Location | Status |
|-----------|----------|--------|
| `domain_sources.yaml` | `config/domain_sources.yaml` | ✅ Exists (single_file only) |
| `domain_sources.py` | `src/.../config/domain_sources.py` | ✅ Exists (basic dataclasses) |
| `MultiTableLoader` | `src/.../io/readers/` | ❌ **Not implemented** |
| `read_data_op` | `src/.../orchestration/ops/` | ❌ **Not implemented** |
| `annual_award` multi_table config | `config/domain_sources.yaml` | ❌ Still `single_file` |

---

## Implementation Tasks

### Task 1: Extend Configuration Models

**File:** `src/work_data_hub/config/domain_sources.py`

**Changes Required:**
1. Add `TableConfig` dataclass for individual table definitions
2. Add `JoinStrategy` dataclass for merge configuration
3. Extend `DomainSourceConfig` with `tables`, `join_strategy`, `output_format` fields
4. Update `_load_config()` to parse new fields

**Code Changes:**

```python
# NEW dataclasses to add:

@dataclass
class TableConfig:
    """Single table configuration for multi-table loading."""
    schema: str
    table: str
    role: str  # "primary" | "detail"

@dataclass
class JoinStrategy:
    """Table merge strategy configuration."""
    type: str  # "merge_on_key" | "left_join" | "union"
    key_columns: List[str] = field(default_factory=list)

# MODIFY DomainSourceConfig:
@dataclass
class DomainSourceConfig:
    """Domain data source configuration."""
    source_type: str  # "single_file" | "multi_table"
    discovery: Optional[DiscoveryConfig] = None
    tables: Optional[List[TableConfig]] = None
    join_strategy: Optional[JoinStrategy] = None
    output_format: str = "flattened"
```

**Acceptance Criteria:**
- [ ] `TableConfig` dataclass defined with schema, table, role fields
- [ ] `JoinStrategy` dataclass defined with type, key_columns fields
- [ ] `DomainSourceConfig` extended with new optional fields
- [ ] `_load_config()` correctly parses multi_table configurations

---

### Task 2: Implement MultiTableLoader

**File:** `src/work_data_hub/io/readers/multi_table_loader.py` (NEW)

**Purpose:** Load data from multiple database tables and merge according to configured strategy.

**Class Design:**

```python
class MultiTableLoader:
    """Multi-table data loader with configurable merge strategies."""

    @classmethod
    def load(cls, config: DomainSourceConfig) -> List[Dict[str, Any]]:
        """Load and merge data from multiple tables."""

    @classmethod
    def _load_table(cls, engine, table_config: TableConfig) -> pd.DataFrame:
        """Load single table from database."""

    @classmethod
    def _apply_join_strategy(
        cls,
        tables_data: Dict[str, pd.DataFrame],
        strategy: JoinStrategy,
    ) -> pd.DataFrame:
        """Apply configured join strategy to merge tables."""
```

**Supported Join Strategies:**
1. `merge_on_key` - Primary/detail merge on specified key columns (default)
2. `left_join` - Left join primary to detail tables
3. `union` - Concatenate all tables vertically

**Acceptance Criteria:**
- [ ] `MultiTableLoader.load()` returns `List[Dict[str, Any]]`
- [ ] Supports `merge_on_key` strategy with configurable key columns
- [ ] Supports `union` strategy for table concatenation
- [ ] Raises `ValueError` for missing primary table in merge scenarios
- [ ] Uses `get_settings().get_database_connection_string()` for DB connection

---

### Task 3: Create Unified read_data_op

**File:** `src/work_data_hub/orchestration/ops/file_processing.py`

**Changes Required:**
1. Add new `ReadDataOpConfig` class
2. Add new `read_data_op` function that dispatches based on source_type
3. Keep existing `read_excel_op` for backward compatibility

**Code Design:**

```python
class ReadDataOpConfig(Config):
    """Configuration for unified data reading operation."""
    domain: str
    sheet: Any = 0
    sheet_names: Optional[List[str]] = None
    sample: Optional[str] = None

@op
def read_data_op(
    context: OpExecutionContext,
    config: ReadDataOpConfig,
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    Unified data loading entry point.

    Dispatches to appropriate loader based on domain source configuration:
    - single_file: Uses Excel/CSV reader (existing logic)
    - multi_table: Uses MultiTableLoader for database tables
    """
```

**Dispatch Logic:**
1. Look up domain in `DOMAIN_SOURCE_REGISTRY`
2. If `source_type == "multi_table"`: call `MultiTableLoader.load()`
3. If `source_type == "single_file"` or not found: use existing Excel logic

**Acceptance Criteria:**
- [ ] `read_data_op` correctly dispatches to `MultiTableLoader` for multi_table domains
- [ ] `read_data_op` falls back to Excel loading for single_file domains
- [ ] Existing `read_excel_op` remains unchanged for backward compatibility
- [ ] Proper logging for source type detection

---

### Task 4: Update annual_award Configuration

**File:** `config/domain_sources.yaml`

**Changes Required:**
Update `annual_award` from `single_file` to `multi_table`:

```yaml
annual_award:
  source_type: multi_table
  tables:
    - schema: business
      table: 年度表彰_主表
      role: primary
    - schema: business
      table: 年度表彰_明细
      role: detail
  join_strategy:
    type: merge_on_key
    key_columns: ["客户号", "年度"]
  output_format: flattened
```

**Acceptance Criteria:**
- [ ] `annual_award` configured as `multi_table`
- [ ] Two tables defined with correct schema/table/role
- [ ] Join strategy specifies `merge_on_key` with appropriate key columns
- [ ] Configuration loads without errors

---

### Task 5: Update generic_domain_job

**File:** `src/work_data_hub/orchestration/jobs.py`

**Changes Required:**
1. Import `read_data_op` from ops
2. Update `generic_domain_job` to use `read_data_op` instead of `read_excel_op`
3. Update `build_run_config` to configure `read_data_op`

**Code Changes:**

```python
# In imports:
from .ops import (
    ...
    read_data_op,  # NEW
    read_excel_op,  # Keep for backward compatibility
)

# In generic_domain_job:
@job
def generic_domain_job() -> Any:
    """Generic ETL job with multi-source support."""
    discovered_paths = discover_files_op()

    # Use unified read_data_op instead of read_excel_op
    rows = read_data_op(discovered_paths)

    processed_data = process_domain_op_v2(rows, discovered_paths)
    backfill_result = generic_backfill_refs_op(processed_data)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)
```

**Acceptance Criteria:**
- [ ] `generic_domain_job` uses `read_data_op`
- [ ] `build_run_config` generates correct config for `read_data_op`
- [ ] Existing single_file domains continue to work

---

## Testing Strategy

### Unit Tests

#### Task 2 Tests: `tests/io/readers/test_multi_table_loader.py` (NEW)

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_load_single_table` | Load single table without merge | High |
| `test_merge_on_key_strategy` | Primary/detail merge on key columns | High |
| `test_union_strategy` | Vertical concatenation of tables | Medium |
| `test_missing_primary_table_error` | Error when primary role missing | High |
| `test_empty_tables_config_error` | Error when tables list is empty | Medium |
| `test_output_format_records` | Verify `List[Dict]` output format | High |

```bash
# Run unit tests
PYTHONPATH=src uv run pytest tests/io/readers/test_multi_table_loader.py -v
```

#### Task 1 Tests: `tests/config/test_domain_sources.py`

| Test Case | Description | Priority |
|-----------|-------------|----------|
| `test_load_multi_table_config` | Parse multi_table configuration | High |
| `test_table_config_dataclass` | TableConfig field validation | Medium |
| `test_join_strategy_dataclass` | JoinStrategy field validation | Medium |
| `test_backward_compat_single_file` | Existing single_file configs still work | High |

```bash
# Run config tests
PYTHONPATH=src uv run pytest tests/config/test_domain_sources.py -v
```

---

### Integration Tests

#### End-to-End: `tests/domain/annual_award/test_integration.py`

| Test Case | Description |
|-----------|-------------|
| `test_annual_award_multi_table_load` | Full pipeline with multi_table source |
| `test_annual_award_data_merge` | Verify primary/detail merge correctness |

```bash
# Run integration tests
PYTHONPATH=src uv run pytest tests/domain/annual_award/test_integration.py -v
```

---

### Regression Tests

Ensure existing `single_file` domains are unaffected:

```bash
# Run regression tests for existing domains
PYTHONPATH=src uv run pytest tests/orchestration/ -v -k "annuity"
PYTHONPATH=src uv run pytest tests/orchestration/ -v -k "sandbox_trustee"
```

---

### Manual Verification

#### Step 1: Verify Configuration Loading

```python
from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY

cfg = DOMAIN_SOURCE_REGISTRY.get("annual_award")
assert cfg.source_type == "multi_table"
assert len(cfg.tables) == 2
assert cfg.tables[0].role == "primary"
print(f"Config loaded: {cfg}")
```

#### Step 2: Verify Data Loading

```python
from work_data_hub.io.readers.multi_table_loader import MultiTableLoader
from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY

cfg = DOMAIN_SOURCE_REGISTRY.get("annual_award")
rows = MultiTableLoader.load(cfg)
print(f"Loaded {len(rows)} rows from multi-table source")
print(f"Sample row keys: {list(rows[0].keys()) if rows else 'N/A'}")
```

#### Step 3: Verify ETL Pipeline

```bash
# Plan-only mode (no database writes)
PYTHONPATH=src uv run python -m work_data_hub.cli etl --domains annual_award --plan-only
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Database connection failures | Medium | High | Use existing `get_settings()` pattern; add connection retry logic |
| Incorrect merge results | Medium | High | Comprehensive unit tests for join strategies; manual data verification |
| Breaking existing single_file domains | Low | High | Regression tests; keep `read_excel_op` unchanged |
| Performance issues with large tables | Medium | Medium | Add logging for row counts; consider pagination for large datasets |
| Configuration parsing errors | Low | Medium | Validate config at startup; fail-fast on invalid configs |

---

## Implementation Order

Tasks should be implemented in this order due to dependencies:

```
Task 1: Extend Configuration Models
    ↓
Task 2: Implement MultiTableLoader (depends on Task 1 dataclasses)
    ↓
Task 3: Create read_data_op (depends on Task 2 loader)
    ↓
Task 4: Update annual_award Configuration (can run in parallel with Task 3)
    ↓
Task 5: Update generic_domain_job (depends on Task 3)
    ↓
Testing & Verification
```

### Recommended Sequence

1. **Task 1** - Foundation: Config models must exist first
2. **Task 2** - Core: MultiTableLoader is the main new component
3. **Task 3 + Task 4** - Can be done in parallel
4. **Task 5** - Integration: Wire everything together
5. **Testing** - Verify all acceptance criteria

---

## Rollback Plan

If implementation fails or causes issues:

### Immediate Rollback (No Code Changes)

1. Revert `annual_award` config in `domain_sources.yaml` to `single_file`
2. The `read_data_op` will fall back to Excel loading automatically

### Full Rollback (Code Revert)

1. `MultiTableLoader` can be safely deleted (no other code depends on it)
2. Revert `read_data_op` changes in `file_processing.py`
3. Revert `generic_domain_job` to use `read_excel_op`
4. Revert `domain_sources.py` dataclass changes

### Rollback Commands

```bash
# Revert specific files
git checkout HEAD~1 -- config/domain_sources.yaml
git checkout HEAD~1 -- src/work_data_hub/config/domain_sources.py
git checkout HEAD~1 -- src/work_data_hub/orchestration/ops/file_processing.py
git checkout HEAD~1 -- src/work_data_hub/orchestration/jobs.py

# Or delete new file
rm src/work_data_hub/io/readers/multi_table_loader.py
```

---

## Dependencies

### Python Packages (Already in Project)

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | >=2.0 | DataFrame operations, merge/concat |
| `sqlalchemy` | >=2.0 | Database connection, SQL execution |
| `psycopg2-binary` | >=2.9 | PostgreSQL driver |
| `pyyaml` | >=6.0 | YAML configuration parsing |

### Internal Dependencies

| Module | Purpose |
|--------|---------|
| `work_data_hub.config.settings` | Database connection string |
| `work_data_hub.config.domain_sources` | Domain source registry |
| `work_data_hub.io.readers.excel_reader` | Existing Excel reading logic |

---

## Acceptance Criteria Summary

| # | Criterion | Verification Method |
|---|-----------|---------------------|
| AC1 | `MultiTableLoader.load()` returns `List[Dict]` | Unit test |
| AC2 | `annual_award` configured as `multi_table` | Config check |
| AC3 | `read_data_op` dispatches to correct loader | Integration test |
| AC4 | Existing `single_file` domains unchanged | Regression test |
| AC5 | Primary/detail merge uses configured key_columns | Unit test |
| AC6 | `generic_domain_job` uses `read_data_op` | Code review |

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2026-01-13 | Claude Code | Initial implementation plan |
