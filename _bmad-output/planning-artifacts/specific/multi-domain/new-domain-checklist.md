# New Domain Addition Checklist

> **Document Status:** ✅ **RESOLVED** - Epic 7.4 (Domain Registry Architecture) has addressed all issues identified in this document.
> **Resolution Date:** 2025-12-30
> **Created:** 2025-12-28
> **Related Epic:** Epic 7.4 - Domain Registry Architecture

> **📌 RESOLUTION SUMMARY**
>
> All issues (MD-001 through MD-005) identified in this document have been **resolved** through Epic 7.4's Registry Pattern architecture.
>
> - **Adding new domain**: Reduced from 5-7 files → 2-3 files
> - **Documentation**: See [Domain Registry Architecture](../../architecture/domain-registry.md) for the new pattern
> - **Related Stories**: [7.4-1](../../sprint-artifacts/stories/7.4-1-job-registry-pattern.md), [7.4-2](../../sprint-artifacts/stories/7.4-2-config-driven-backfill-list.md), [7.4-3](../../sprint-artifacts/stories/7.4-3-generic-process-domain-op.md), [7.4-4](../../sprint-artifacts/stories/7.4-4-domain-autodiscovery-validation.md)
>
> **See "Resolution Summary" section below for detailed mapping.**

---

## Overview

This document identifies all code locations that require modification when adding a new domain to the WorkDataHub ETL system. The current architecture uses **hardcoded conditional logic** rather than a configuration-driven registry pattern.

---

## Required Code Changes

### 1. Domain Layer (Required)

**Location:** `src/work_data_hub/domain/{new_domain}/`

Create new domain package with:

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `models.py` | Domain-specific data models, validation schemas |
| `service.py` | Domain service with `process()` or `process_with_enrichment()` |
| `pipeline_builder.py` | Pipeline step configuration (if using Pipeline framework) |
| `schemas.py` | Column mappings, composite keys (optional) |

**Example Structure:**
```
src/work_data_hub/domain/
├── annuity_performance/
│   ├── __init__.py
│   ├── models.py
│   ├── schemas.py
│   ├── service.py
│   └── pipeline_builder.py
└── {new_domain}/
    ├── __init__.py
    ├── models.py
    ├── service.py
    └── ...
```

---

### 2. Orchestration Ops (Required)

**Location:** `src/work_data_hub/orchestration/ops/pipeline_ops.py`

**Action:** Add new `process_{domain}_op` function.

**Current Pattern (L55, L99, L362):**
```python
@op
def process_sandbox_trustee_performance_op(...)

@op
def process_annuity_performance_op(...)

@op
def process_annuity_income_op(...)
```

**Issue:** Each domain requires a dedicated op function. No generic `process_domain_op` exists.

---

### 3. Orchestration Jobs (Required)

**Location:** `src/work_data_hub/orchestration/jobs.py`

**Action:** Add new `{domain}_job()` function.

**Current Pattern (L42-71, L83-110, L113-134):**
```python
@job
def sandbox_trustee_performance_job() -> Any:
    discovered_paths = discover_files_op()
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_sandbox_trustee_performance_op(excel_rows, discovered_paths)
    backfill_result = generic_backfill_refs_op(processed_data)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)

@job
def annuity_performance_job() -> Any:
    # Similar structure...

@job
def annuity_income_job() -> Any:
    # Simpler structure (no backfill)...
```

**Issue:**
- Jobs are manually wired with domain-specific ops
- Backfill ops must be explicitly added if domain needs FK backfill
- No factory pattern to generate jobs from configuration

---

### 4. CLI Executor Dispatch (Required)

**Location:** `src/work_data_hub/cli/etl/executors.py`

**Action:** Add new branch to `_execute_single_domain()` function (L200-232).

**Current Pattern:**
```python
def _execute_single_domain(args: argparse.Namespace, domain: str) -> int:
    # ...
    if domain_key == "annuity_performance":
        from work_data_hub.orchestration.jobs import annuity_performance_job
        selected_job = annuity_performance_job
    elif domain_key == "annuity_income":
        from work_data_hub.orchestration.jobs import annuity_income_job
        selected_job = annuity_income_job
    elif domain_key == "sandbox_trustee_performance":
        from work_data_hub.orchestration.jobs import (
            sandbox_trustee_performance_job,
            sandbox_trustee_performance_multi_file_job,
        )
        selected_job = (
            sandbox_trustee_performance_multi_file_job
            if max_files > 1
            else sandbox_trustee_performance_job
        )
    elif domain_key == "company_lookup_queue":
        return _execute_queue_processing_job(args)
    elif domain_key == "reference_sync":
        return _execute_reference_sync_job(args)
    else:
        raise ValueError(
            f"Unsupported domain: {domain}. "
            f"Supported: sandbox_trustee_performance, annuity_performance, annuity_income, "
            f"company_lookup_queue, reference_sync"
        )
```

**Issues:**
- Hardcoded if/elif chain
- Error message lists supported domains manually
- No registry pattern for job lookup

---

### 5. CLI Config Builder (Conditional)

**Location:** `src/work_data_hub/cli/etl/config.py`

**Action:** Update `build_run_config()` if domain needs special handling.

**Current Hardcoded Lists:**

1. **Backfill Configuration (L157):**
   ```python
   if domain in ["annuity_performance", "sandbox_trustee_performance"]:
       run_config["ops"]["generic_backfill_refs_op"] = {...}
   ```

2. **Enrichment Configuration (L167):**
   ```python
   if domain == "annuity_performance":
       # Add EQC lookup config
   ```

3. **Multi-file Op (L144):**
   ```python
   run_config["ops"]["read_and_process_sandbox_trustee_files_op"] = {...}
   ```

**Issues:**
- Domain-specific behavior scattered in conditional blocks
- Adding backfill support requires code change
- No way to declare domain capabilities in config

---

### 6. Configuration Files (Required)

#### 6.1 Data Sources Configuration

**Location:** `config/data_sources.yml`

**Action:** Add domain entry under `domains:` section.

**Required Fields:**
```yaml
domains:
  {new_domain}:
    base_path: "path/to/{YYYYMM}/data"  # Template with {YYYYMM}
    file_patterns:
      - "*pattern*.xlsx"
    sheet_name: "Sheet1"  # or integer index
    output:
      table: "target_table_name"
      schema_name: "business"  # Optional, inherits from defaults
      pk:  # For delete_insert mode
        - "column1"
        - "column2"
```

#### 6.2 Foreign Keys Configuration (If backfill needed)

**Location:** `config/foreign_keys.yml`

**Action:** Add FK rules if domain needs reference table backfill.

```yaml
domains:
  {new_domain}:
    foreign_keys:
      fk_reference:
        table: "reference_table"
        schema_name: "business"
        source_columns:
          column_a: "target_column_a"
        lookup_column: "id"
```

---

## Dependency Matrix

| Step | File | Depends On | Blocking? |
|------|------|------------|-----------|
| 1 | `domain/{new_domain}/` | None | Yes |
| 2 | `orchestration/ops/pipeline_ops.py` | Step 1 | Yes |
| 3 | `orchestration/jobs.py` | Step 2 | Yes |
| 4 | `cli/etl/executors.py` | Step 3 | Yes |
| 5 | `cli/etl/config.py` | Step 3 | Conditional |
| 6.1 | `config/data_sources.yml` | None | Yes |
| 6.2 | `config/foreign_keys.yml` | None | Conditional |

---

## Architectural Debt Summary

### Current State: Hardcoded Dispatch (BEFORE Epic 7.4)

```
CLI (executors.py)
    └── if/elif chain → Jobs (jobs.py)
                            └── domain-specific ops → Domain Services
```

### New State: Registry Pattern (AFTER Epic 7.4) ✅

```
CLI (executors.py)
    └── JOB_REGISTRY.get() → Jobs (jobs.py)
                            └── DOMAIN_SERVICE_REGISTRY → Domain Services
```

### Issues Identified & Resolved

| Issue ID | Severity | Description | Resolution Status | Resolved By |
|----------|----------|-------------|-------------------|------------|
| MD-001 | **High** | Job dispatch uses hardcoded if/elif chain (executors.py:200-232) | ✅ **RESOLVED** | Story 7.4-1: JOB_REGISTRY pattern |
| MD-002 | Medium | Backfill domain list hardcoded (config.py:157) | ✅ **RESOLVED** | Story 7.4-2: Config-driven backfill |
| MD-003 | Medium | Each domain requires dedicated `process_{domain}_op` function | ✅ **RESOLVED** | Story 7.4-3: Generic process_domain_op |
| MD-004 | Low | Error message lists supported domains manually (executors.py:230-231) | ✅ **RESOLVED** | Story 7.4-1: Dynamic error from registry |
| MD-005 | Low | No validation that data_sources.yml domain has corresponding job | ✅ **RESOLVED** | Story 7.4-4: validate_domain_registry() |

### Recommended Improvements → Implementation Status

| Recommendation | Status | Implementation |
|----------------|--------|----------------|
| 1. **Job Registry Pattern** | ✅ **COMPLETE** | `JOB_REGISTRY: Dict[str, JobEntry]` in `orchestration/jobs.py` |
| 2. **Generic Process Op** | ✅ **COMPLETE** | `process_domain_op` delegates via `DOMAIN_SERVICE_REGISTRY` |
| 3. **Config-Driven Backfill** | ✅ **COMPLETE** | `requires_backfill: true/false` in `data_sources.yml` |
| 4. **Domain Autodiscovery** | ✅ **COMPLETE** | `validate_domain_registry()` validates config completeness |

---

## Quick Reference: Minimum Changes for New Domain

For a **simple domain** (no backfill, no enrichment):

| # | File | Change Type |
|---|------|-------------|
| 1 | `domain/{new_domain}/` | Create package |
| 2 | `ops/pipeline_ops.py` | Add `process_{domain}_op` |
| 3 | `jobs.py` | Add `{domain}_job` |
| 4 | `executors.py` | Add elif branch |
| 5 | `data_sources.yml` | Add domain config |

**Total: 5 files minimum**

For a **complex domain** (with backfill + enrichment):

**Total: 7 files** (add config.py conditional + foreign_keys.yml)

---

## Related Documentation

- [Project Context](../../../project-context.md) - Architecture overview
- [Infrastructure Layer](../../architecture/infrastructure-layer.md) - Orchestration patterns
- [Implementation Patterns](../../architecture/implementation-patterns.md) - Story patterns

---

## Resolution Summary

### Epic 7.4: Domain Registry Architecture (2025-12-30)

**Problem:** Adding a new domain required modifications to 5-7 files due to hardcoded dispatch logic.

**Solution:** Introduced configuration-driven Registry Pattern with two central registries:

1. **`JOB_REGISTRY`** (`orchestration/jobs.py`): Maps domain names to Dagster Job definitions
2. **`DOMAIN_SERVICE_REGISTRY`** (`orchestration/ops/pipeline_ops.py`): Maps domain names to processing services

**Results:**
- ✅ Adding new domain reduced to **2-3 files** (domain package + config)
- ✅ Eliminated all if/elif dispatch chains
- ✅ Config-driven domain capabilities (`requires_backfill`, `supports_enrichment`)
- ✅ Startup validation (`validate_domain_registry()`)
- ✅ Self-documenting supported domains

### Story Mapping

| Story | Issue Resolved | Description |
|-------|----------------|-------------|
| **[7.4-1](../../sprint-artifacts/stories/7.4-1-job-registry-pattern.md)** | MD-001, MD-004 | JOB_REGISTRY pattern eliminates if/elif dispatch |
| **[7.4-2](../../sprint-artifacts/stories/7.4-2-config-driven-backfill-list.md)** | MD-002 | Config-driven backfill via `requires_backfill` |
| **[7.4-3](../../sprint-artifacts/stories/7.4-3-generic-process-domain-op.md)** | MD-003 | Generic `process_domain_op` delegates via registry |
| **[7.4-4](../../sprint-artifacts/stories/7.4-4-domain-autodiscovery-validation.md)** | MD-005 | Startup validation for config completeness |
| **[7.4-5](../../sprint-artifacts/stories/7.4-5-documentation-update.md)** | - | Architecture documentation and checklist resolution |

### New Documentation

- **[Domain Registry Architecture](../../architecture/domain-registry.md)**: Comprehensive technical documentation
- **[Project Context - Section 6](../../project-context.md#6--domain-registry-architecture)**: Overview and quick reference
- **[Sprint Change Proposal (Epic 7.4)](../../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-30-domain-registry-architecture.md)**: Architecture evolution plan

### Before vs After Epic 7.4

| Aspect | Before | After |
|--------|--------|-------|
| **Files to Modify** | 5-7 files | 2-3 files |
| **Dispatch Logic** | if/elif chains | Registry lookup |
| **Backfill Config** | Hardcoded list | `requires_backfill` in YAML |
| **Domain Ops** | Per-domain functions | Generic `process_domain_op` |
| **Validation** | None | Startup validation |
| **Error Messages** | Hardcoded domain list | Dynamic from registry |

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2025-12-28 | Barry (Quick Flow) | Initial analysis from `sandbox_trustee_performance_job` fix |
| 2025-12-30 | Epic 7.4 Team | ✅ RESOLVED - All issues addressed via Registry Pattern architecture |
