# New Domain Addition Checklist

> **Document Status:** Technical Debt Analysis
> **Created:** 2025-12-28
> **Related Epic:** Multi-Domain ETL Architecture

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

### Current State: Hardcoded Dispatch

```
CLI (executors.py)
    └── if/elif chain → Jobs (jobs.py)
                            └── domain-specific ops → Domain Services
```

### Issues Identified

| Issue ID | Severity | Description |
|----------|----------|-------------|
| MD-001 | High | Job dispatch uses hardcoded if/elif chain (executors.py:200-232) |
| MD-002 | Medium | Backfill domain list hardcoded (config.py:157) |
| MD-003 | Medium | Each domain requires dedicated `process_{domain}_op` function |
| MD-004 | Low | Error message lists supported domains manually (executors.py:230-231) |
| MD-005 | Low | No validation that data_sources.yml domain has corresponding job |

### Recommended Improvements

1. **Job Registry Pattern:** Create `JOB_REGISTRY: Dict[str, JobDefinition]` mapping domain names to jobs
2. **Generic Process Op:** Create `process_generic_domain_op` that delegates to domain service dynamically
3. **Config-Driven Backfill:** Move backfill domain list to `data_sources.yml` as `requires_backfill: true`
4. **Domain Autodiscovery:** Scan `domain/*/` packages and auto-register jobs

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

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2025-12-28 | Barry (Quick Flow) | Initial analysis from `sandbox_trustee_performance_job` fix |
