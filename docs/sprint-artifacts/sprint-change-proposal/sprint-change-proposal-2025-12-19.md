# Sprint Change Proposal: Configuration File Modularization (Zero Legacy)

**Date:** 2025-12-19
**Author:** Link (via Correct-Course Workflow)
**Status:** Approved
**Epic:** 6.2 (Generic Reference Data Management)
**Scope:** Breaking Change - Direct Refactor

---

## 1. Issue Summary

### Problem Statement

The `config/data_sources.yml` file violates the **Single Responsibility Principle** by mixing three distinct concerns:

| Concern | Lines | Purpose |
|---------|-------|---------|
| Domain Discovery | ~180 | `domains.*` - File paths, patterns, version_strategy |
| Reference Backfill | ~90 | `domains.*.foreign_keys` - FK rules for backfill |
| Reference Sync | ~80 | `reference_sync.*` - Legacy system synchronization |

This coupling complicates domain management, validation, and onboarding.

### Policy Alignment: Zero Legacy (Pre-Production)

Per the "Zero Legacy Policy," we will **not** implement backward compatibility layers. We will perform a clean, atomic refactor to separate these concerns into dedicated configuration files and immediately update all consuming code.

**Justification:** WorkDataHub is still pre-production (Epic 7 Testing in backlog), no external consumers, no need for migration layers.

---

## 2. Impact Analysis

### 2.1 Artifacts Affected

| Artifact | Action | Lines Changed |
|----------|--------|---------------|
| `config/data_sources.yml` | **Prune** | Remove `foreign_keys` (from domains) and `reference_sync` sections |
| `config/foreign_keys.yml` | **Create** | New home for FK backfill rules |
| `config/reference_sync.yml` | **Create** | New home for Reference Sync rules |
| `config_loader.py` | **Modify** | Change default path to `config/foreign_keys.yml` |
| `sync_config_loader.py` | **Modify** | Change default path to `config/reference_sync.yml` |
| `observability.py` | **Modify** | Update config loading logic |

### 2.2 Code Change Summary

**Minimal changes required** - Both loaders already support custom `config_path` parameter:

```python
# config_loader.py (Line 21) - Already supports Path parameter
def load_foreign_keys_config(config_path: Path, domain: str) -> List[ForeignKeyConfig]:

# sync_config_loader.py (Line 26, 89) - Already supports path parameter
def __init__(self, config_path: str = "config/data_sources.yml"):
def load_reference_sync_config(config_path: str = "config/data_sources.yml"):
```

### 2.3 All Call Sites (15 total)

| File | Function | Change Required |
|------|----------|-----------------|
| `ops.py:1258` | `load_foreign_keys_config()` | Update default path |
| `ops.py:1861` | `load_foreign_keys_config()` | Update default path |
| `ops.py:1910` | `load_reference_sync_config()` | Update default path |
| `reference_sync_ops.py:75` | `load_reference_sync_config()` | Update default path |
| `observability.py:130` | Direct YAML read | Refactor to use loader |

### 2.4 Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Breaking existing configs | **Low** | Atomic commit updates all files |
| Test failures | **Low** | Update fixtures in same PR |
| Runtime errors | **Low** | Pydantic validation catches misconfigs |

---

## 3. Recommended Approach: Clean Split + Defaults Inheritance

### 3.1 New File Structure

```
config/
├── data_sources.yml      # Domain discovery with defaults + overrides
├── foreign_keys.yml      # Foreign Key definitions ONLY
└── reference_sync.yml    # Reference Sync definitions ONLY
```

### 3.2 Defaults/Overrides Mechanism

**Design Pattern:** Global `defaults` section + per-domain overrides (similar to Ansible defaults)

**Merge Rules:**
| Type | Behavior | Example |
|------|----------|---------|
| Scalar | Domain value wins | `version_strategy: "manual"` overrides default |
| List (replace) | Domain value replaces default | `file_patterns` fully replaces |
| List (extend) | Use `+` prefix to extend | `exclude_patterns: ["+*回复*"]` adds to defaults |
| Object | Deep merge | `output.table` can be set without losing `output.schema_name` |

**Benefits:**
- **DRY:** Common patterns defined once
- **Explicit:** Overrides are visible at domain level
- **Flexible:** Extend or replace as needed
- **Onboarding:** New domains inherit sensible defaults

**Implementation:** Add `_merge_with_defaults()` function in `data_source_schema.py`

---

## 4. Detailed Changes

### 4.1 [NEW] `config/foreign_keys.yml`

```yaml
# Foreign Key Backfill Configuration
# Separated from data_sources.yml per SRP (Story 6.2-P14)
schema_version: "1.0"

domains:
  annuity_performance:
    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        target_schema: "mapping"
        mode: "insert_missing"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
          - source: "计划名称"
            target: "计划全称"
            optional: true
          - source: "计划类型"
            target: "计划类型"
            optional: true
          - source: "客户名称"
            target: "客户名称"
            optional: true
          - source: "主拓代码"
            target: "主拓代码"
            optional: true
          - source: "主拓机构"
            target: "主拓机构"
            optional: true
          - source: "资格"
            target: "管理资格"
            optional: true

      - name: "fk_portfolio"
        source_column: "组合代码"
        target_table: "组合计划"
        target_key: "组合代码"
        target_schema: "mapping"
        mode: "insert_missing"
        depends_on: ["fk_plan"]
        backfill_columns:
          - source: "组合代码"
            target: "组合代码"
          - source: "计划代码"
            target: "年金计划号"
          - source: "组合名称"
            target: "组合名称"
            optional: true
          - source: "组合类型"
            target: "组合类型"
            optional: true

      - name: "fk_product_line"
        source_column: "产品线代码"
        target_table: "产品线"
        target_key: "产品线代码"
        target_schema: "mapping"
        mode: "insert_missing"
        backfill_columns:
          - source: "产品线代码"
            target: "产品线代码"
          - source: "业务类型"
            target: "产品线"
            optional: true

      - name: "fk_organization"
        source_column: "机构代码"
        target_table: "组织架构"
        target_key: "机构代码"
        target_schema: "mapping"
        mode: "insert_missing"
        skip_blank_values: true
        backfill_columns:
          - source: "机构代码"
            target: "机构代码"
          - source: "机构"
            target: "机构"
            optional: true

  annuity_income:
    foreign_keys: []
```

---

### 4.2 [NEW] `config/reference_sync.yml`

```yaml
# Reference Data Sync Configuration
# Separated from data_sources.yml per SRP (Story 6.2-P14)
schema_version: "1.0"

reference_sync:
  enabled: true
  schedule: "0 1 * * *"  # Daily at 01:00 AM (Asia/Shanghai)
  concurrency: 1
  batch_size: 5000

  tables:
    - name: "年金计划"
      target_table: "年金计划"
      target_schema: "business"
      source_type: "postgres"
      source_config:
        connection_env_prefix: "WDH_LEGACY"
        schema: "enterprise"
        table: "annuity_plan"
        columns:
          - source: "plan_code"
            target: "年金计划号"
          - source: "plan_name"
            target: "计划名称"
          - source: "plan_type"
            target: "计划类型"
          - source: "customer_name"
            target: "客户名称"
      sync_mode: "upsert"
      primary_key: "年金计划号"

    - name: "组合计划"
      target_table: "组合计划"
      target_schema: "business"
      source_type: "postgres"
      source_config:
        connection_env_prefix: "WDH_LEGACY"
        schema: "enterprise"
        table: "portfolio_plan"
        columns:
          - source: "portfolio_code"
            target: "组合代码"
          - source: "plan_code"
            target: "年金计划号"
          - source: "portfolio_name"
            target: "组合名称"
          - source: "portfolio_type"
            target: "组合类型"
      sync_mode: "upsert"
      primary_key: "组合代码"

    - name: "组织架构"
      target_table: "组织架构"
      target_schema: "business"
      source_type: "postgres"
      source_config:
        connection_env_prefix: "WDH_LEGACY"
        schema: "enterprise"
        table: "organization"
        columns:
          - source: "org_code"
            target: "组织代码"
          - source: "org_name"
            target: "组织名称"
        incremental:
          where: "updated_at >= :last_synced_at"
          updated_at_column: "updated_at"
      sync_mode: "upsert"
      primary_key: "组织代码"

    - name: "产品线"
      target_table: "产品线"
      target_schema: "business"
      source_type: "config_file"
      source_config:
        file_path: "config/reference_data/product_lines.yml"
        schema_version: "1.0"
      sync_mode: "delete_insert"
      primary_key: "产品线代码"
```

---

### 4.3 [MODIFY] `config/data_sources.yml` (With Defaults)

Remove `foreign_keys` and `reference_sync`. Add `defaults` section for common settings:

```yaml
# WorkDataHub Data Source Configuration
# Uses: defaults + per-domain overrides pattern
# FK Backfill: See config/foreign_keys.yml
# Reference Sync: See config/reference_sync.yml
schema_version: "1.1"  # Version bump for defaults support

# ============================================================================
# DEFAULTS - Applied to all domains unless overridden
# ============================================================================
defaults:
  # Common exclusion patterns for all domains
  exclude_patterns:
    - "~$*"         # Excel temp files
    - "*.eml"       # Email files

  # Default version selection strategy
  version_strategy: "highest_number"
  fallback: "error"

  # Default output schema
  output:
    schema_name: "business"

# ============================================================================
# DOMAINS - Only specify what differs from defaults
# ============================================================================
domains:
  # Sandbox domain - overrides output.schema_name
  sandbox_trustee_performance:
    base_path: "tests/fixtures/real_data/202411/收集数据/业务收集"
    file_patterns:
      - "**/*受托业绩*.xlsx"
    sheet_name: 0
    output:
      table: "sandbox_trustee_performance"
      schema_name: "sandbox"  # Override: sandbox instead of business

  # Annuity Performance - extends exclude_patterns
  annuity_performance:
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
    file_patterns:
      - "*规模收入数据*.xlsx"
    exclude_patterns:
      - "+*回复*"    # Extend: add to default exclusions (+ prefix)
    sheet_name: "规模明细"
    output:
      table: "annuity_performance"
      pk:
        - "月度"
        - "业务类型"
        - "计划类型"

  # Annuity Income - minimal config, inherits most from defaults
  annuity_income:
    base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
    file_patterns:
      - "*规模收入数据*.xlsx"
    exclude_patterns:
      - "+*回复*"    # Extend defaults
    sheet_name: "收入明细"
    output:
      table: "annuity_income"
      pk:
        - "月度"
        - "计划号"
        - "组合代码"
        - "company_id"
```

**Comparison: Before vs After**

| Metric | Before (No Defaults) | After (With Defaults) |
|--------|----------------------|-----------------------|
| Total Lines | ~80 lines | ~50 lines |
| Repeated `exclude_patterns` | 3x | 0x (inherited) |
| Repeated `version_strategy` | 3x | 0x (inherited) |
| Adding new domain | ~25 lines | ~10 lines |

---

### 4.4 [MODIFY] Code Changes

#### `config_loader.py` (2 changes)

```diff
- def load_foreign_keys_config(config_path: Path, domain: str) -> List[ForeignKeyConfig]:
+ def load_foreign_keys_config(
+     domain: str,
+     config_path: Path = Path("config/foreign_keys.yml")
+ ) -> List[ForeignKeyConfig]:
      """
-     Load foreign key configurations from data_sources.yml for a specific domain.
+     Load foreign key configurations from foreign_keys.yml for a specific domain.
      ...
      """
```

#### `sync_config_loader.py` (2 changes)

```diff
- def __init__(self, config_path: str = "config/data_sources.yml"):
+ def __init__(self, config_path: str = "config/reference_sync.yml"):

- def load_reference_sync_config(config_path: str = "config/data_sources.yml"):
+ def load_reference_sync_config(config_path: str = "config/reference_sync.yml"):
```

#### `observability.py` (1 change)

```diff
  def _load_reference_tables(self, config_path: str = None):
-     # Load from config/data_sources.yml
+     # Load from config/foreign_keys.yml
      if config_path is None:
-         config_path = os.path.join(project_root, "config", "data_sources.yml")
+         config_path = os.path.join(project_root, "config", "foreign_keys.yml")
```

#### `data_source_schema.py` (NEW: Defaults Merge)

```python
import copy
from typing import Any, Dict

def _merge_with_defaults(
    domain_config: Dict[str, Any],
    defaults: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge domain config with defaults using inheritance rules:
    - Scalars: domain value wins
    - Lists: replace by default, extend if item starts with "+"
    - Dicts: deep merge
    """
    result = copy.deepcopy(defaults)
    
    for key, value in domain_config.items():
        if key not in result:
            result[key] = value
        elif isinstance(value, dict) and isinstance(result[key], dict):
            # Deep merge for dicts
            result[key] = _merge_with_defaults(value, result[key])
        elif isinstance(value, list):
            # Check for extend pattern (+ prefix)
            extend_items = [v[1:] for v in value if isinstance(v, str) and v.startswith("+")]
            replace_items = [v for v in value if not (isinstance(v, str) and v.startswith("+"))]
            
            if extend_items and not replace_items:
                # Extend: add to defaults
                result[key] = result.get(key, []) + extend_items
            else:
                # Replace: use domain value
                result[key] = replace_items + extend_items
        else:
            # Scalar: domain wins
            result[key] = value
    
    return result


def get_domain_config_with_defaults(
    domain_name: str, config_path: str = "config/data_sources.yml"
) -> DomainConfigV2:
    """Load domain config with defaults applied."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    defaults = data.get("defaults", {})
    domain_raw = data["domains"].get(domain_name, {})
    
    # Merge with defaults
    merged = _merge_with_defaults(domain_raw, defaults)
    
    return DomainConfigV2(**merged)
```

---

## 5. Implementation Checklist

### Step 1: Create New Config Files (15 min)

```bash
# 1. Create foreign_keys.yml
cp config/data_sources.yml config/foreign_keys.yml
# Edit: Keep only domains.*.foreign_keys, add schema_version

# 2. Create reference_sync.yml
cp config/data_sources.yml config/reference_sync.yml
# Edit: Keep only reference_sync section, add schema_version

# 3. Clean data_sources.yml
# Edit: Remove foreign_keys from domains, remove reference_sync
```

### Step 2: Update Loaders (20 min)

```bash
# Files to modify:
# 1. src/work_data_hub/domain/reference_backfill/config_loader.py
#    - Change default path to config/foreign_keys.yml
#    - Swap parameter order (domain first, path second with default)

# 2. src/work_data_hub/domain/reference_backfill/sync_config_loader.py
#    - Change default path to config/reference_sync.yml

# 3. src/work_data_hub/domain/reference_backfill/observability.py
#    - Update config path logic (Line 111, 501)
```

### Step 3: Update Call Sites (10 min)

```bash
# ops.py - Update 3 call sites:
# Line 1258: Update load_foreign_keys_config() call
# Line 1861: Update load_foreign_keys_config() call
# Line 1910: Update load_reference_sync_config() call

# reference_sync_ops.py - Update 1 call site:
# Line 75: Update load_reference_sync_config() call
```

### Step 4: Verify (15 min)

```bash
# Run unit tests
uv run pytest tests/unit/domain/reference_backfill -v

# Run integration tests
uv run pytest tests/integration/test_reference_sync_integration.py -v

# Quick smoke test
uv run python -c "from work_data_hub.domain.reference_backfill import load_foreign_keys_config; print('FK loader OK')"
uv run python -c "from work_data_hub.domain.reference_backfill import load_reference_sync_config; print('Sync loader OK')"
```

---

## 6. Implementation Strategy (Team Recommendations)

### 6.1 Atomic Commit Strategy

To ensure rollback capability at each step, implement changes in 5 atomic commits:

| Commit | Scope | Verification |
|--------|-------|--------------|
| **1** | `[Config]` Add `foreign_keys.yml` and `reference_sync.yml` | Files exist, valid YAML |
| **2** | `[Loader]` Update `config_loader.py` default path | Unit tests pass |
| **3** | `[Loader]` Update `sync_config_loader.py` default path | Unit tests pass |
| **4** | `[Refactor]` Add `_merge_with_defaults()` to `data_source_schema.py` | New tests pass |
| **5** | `[Cleanup]` Remove FK/sync sections from `data_sources.yml` | All tests pass |

### 6.2 Pre-Implementation Verification

Run these checks before starting implementation:

```bash
# 1. Verify FK config locations (should only be in data_sources.yml)
git grep "foreign_keys:" config/

# 2. Verify sync config locations
git grep "reference_sync:" config/

# 3. Verify all call sites (confirm 15 locations)
git grep "load_foreign_keys_config\|load_reference_sync_config" --files-with-matches

# 4. Record baseline test count
uv run pytest tests/unit/domain/reference_backfill --collect-only | tail -n 1
```

### 6.3 Enhanced Testing Requirements

**Critical Edge Cases for `_merge_with_defaults()`:**

```python
def test_extend_pattern_with_plus_prefix():
    """AC: '+pattern' should append to defaults, non '+' should replace"""

def test_deep_merge_nested_dicts():
    """AC: output.table override should not lose output.schema_name"""

def test_missing_domain_raises_clear_error():
    """AC: Unknown domain should raise DomainNotFoundError, not KeyError"""

def test_non_string_in_list_handled_gracefully():
    """AC: Non-string items in list should not cause silent failures"""
```

**Migration Completeness Test:**

```python
def test_all_legacy_fk_configs_migrated():
    """Compare FK config count before/after migration to prevent omissions"""
```

### 6.4 Documentation Guidelines

Add header comments to new configuration files:

```yaml
# foreign_keys.yml
# ================
# Purpose: Foreign Key backfill rules for reference data management
# History: Extracted from data_sources.yml (2025-12-19, Story 6.2-P14)
# Related: config/reference_sync.yml, config/data_sources.yml
#
# Inheritance Rules (for data_sources.yml):
# - Scalars: domain value overrides default
# - Lists: replace by default. Use "+" prefix to extend (e.g., "+*pattern*")
# - Dicts: deep merge
```

---

## 7. Effort Estimate (Calibrated)

| Task | Original | Calibrated | Notes |
|------|----------|------------|-------|
| Create new config files | 15 min | 20 min | Verify no omissions |
| Implement defaults merge | 25 min | 30 min | Edge case testing |
| Update loaders | 15 min | 15 min | Straightforward |
| Update call sites | 10 min | 10 min | Straightforward |
| Update tests | 15 min | 25 min | Additional fixtures |
| Verification | 15 min | 20 min | Regression testing |
| **Total** | **~2h** | **~2.5h** | +25% buffer |

---

## 8. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| **AC-1** | Three separate config files exist with valid schema |
| **AC-2** | All 15 call sites updated and functioning |
| **AC-3** | All existing unit tests pass (100%) |
| **AC-4** | New `_merge_with_defaults()` edge case tests added and passing |
| **AC-5** | Configuration files include header documentation |
| **AC-6** | New domain addition demo using defaults inheritance |

### Done Definition

> ✅ **Done** when:
> - All existing tests pass
> - New merge logic tests added and passing
> - Config files have complete header comments
> - ETL CLI can successfully run `annuity_performance` domain
> - `git diff --stat` shows no unexpected changes

---

## 9. Approval

- [ ] **User Approval:** Pending
- [ ] **Story Created:** After approval → `6.2-p14-config-file-modularization.md`

---

*Generated by Correct-Course Workflow on 2025-12-19*
*Enhanced with BMAD Party Mode team review on 2025-12-19*
