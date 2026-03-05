---
title: 'ETL Enrichment Budget Parameter Propagation Fix'
slug: 'etl-enrichment-budget-fix'
created: '2026-03-05'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python', 'Dagster', 'argparse', 'pytest']
files_to_modify:
  - 'src/work_data_hub/orchestration/ops/generic_ops.py'
  - 'src/work_data_hub/cli/etl/config.py'
  - 'tests/unit/orchestration/test_generic_ops.py'
  - 'tests/unit/orchestration/test_jobs_run_config.py'
code_patterns:
  - 'Dagster Config class with typed fields and Optional/default values'
  - 'getattr(args, field, default) pattern for safe CLI arg access'
  - 'EnrichmentServiceFactory.create() classmethod with keyword args'
test_patterns:
  - 'pytest classes with SimpleNamespace for CLI args mocking'
  - 'Direct dict-key assertions on run_config structure'
---

# Tech-Spec: ETL Enrichment Budget Parameter Propagation Fix

**Created:** 2026-03-05

## Overview

### Problem Statement

CLI `--enrichment-sync-budget` (default: 500) is parsed correctly by argparse in `main.py` but is silently dropped in `build_run_config()`. The resulting Dagster run_config never includes this value, so `GenericDomainOpConfig` has no field to receive it, and `process_domain_op_v2` calls `EnrichmentServiceFactory.create()` without `sync_lookup_budget`. The factory defaults to `sync_lookup_budget=0`, causing `CompanyEnrichmentService` to skip all EQC API lookups. Every processed company receives a temporary `IN-{hash}` company_id instead of a real EQC id.

**Root cause chain (confirmed by code inspection):**
```
CLI: enrichment_sync_budget=500 (default)
  → build_run_config() [config.py:201-207]: NOT included in process_domain_op_v2 config
  → GenericDomainOpConfig [generic_ops.py:14-19]: field does not exist
  → EnrichmentServiceFactory.create(plan_only=...) [generic_ops.py:59-61]: sync_lookup_budget omitted
  → factory.py:43: sync_lookup_budget=0 (default) → no EQC queries
```

This affects ALL environments (not only intranet) and ALL enrichment-capable domains: `annuity_performance`, `annual_award`.

### Solution

Minimum-touch parameter propagation (Plan A from bug analysis): thread `enrichment_sync_budget` through the 3-layer call chain without introducing new abstractions. Only `generic_ops.py` and `config.py` need changes; `factory.py` requires no modification.

### Scope

**In Scope:**
- Add `enrichment_sync_budget: int = 0` field to `GenericDomainOpConfig`
- Pass `enrichment_sync_budget` in `build_run_config()` → `process_domain_op_v2` config block
- Use `config.enrichment_sync_budget` when calling `EnrichmentServiceFactory.create()`
- Add/update unit tests for both modified files

**Out of Scope:**
- Passing `enrich_enabled` CLI flag through Dagster config (factory already reads `settings.enrich_enabled` from `.wdh_env`)
- Refactoring to use `EqcLookupConfig` / `ProcessingConfig` serialization (Plan B)
- Changes to `factory.py` — signature is compatible as-is
- Changes to `CompanyEnrichmentService` or EQC client layer

## Context for Development

### Codebase Patterns

- **Dagster Config**: Uses `class Foo(Config): field: type = default` pattern. `Optional[str]` used for nullable fields. Defaults must be JSON-serializable.
- **CLI arg access**: `getattr(args, "field_name", default_value)` is the established safe-access pattern (see `config.py:113` for `session_id`).
- **Factory call**: `EnrichmentServiceFactory.create(plan_only=..., sync_lookup_budget=...)` — keyword-arg only, no positional.
- **Test args**: `SimpleNamespace(field=value, ...)` is used across `test_jobs_run_config.py` to simulate `argparse.Namespace`.
- **Test structure**: `class TestFoo:` grouping with `def test_*` methods, using `from types import SimpleNamespace`.

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `src/work_data_hub/orchestration/ops/generic_ops.py` | **MODIFY** — `GenericDomainOpConfig` + op call site |
| `src/work_data_hub/cli/etl/config.py` | **MODIFY** — `build_run_config()` process_domain_op_v2 block |
| `src/work_data_hub/infrastructure/enrichment/factory.py` | **READ ONLY** — `EnrichmentServiceFactory.create()` signature (already accepts `sync_lookup_budget`) |
| `tests/unit/orchestration/test_generic_ops.py` | **MODIFY** — add config field assertion |
| `tests/unit/orchestration/test_jobs_run_config.py` | **MODIFY** — add enrichment budget propagation test |

### Technical Decisions

- **Default value in `GenericDomainOpConfig`**: Use `0` (not `500`) so that Dagster's default matches the factory's existing default. The `500` default lives at the CLI boundary (`main.py`) and is propagated explicitly when the user provides no override.
- **No `enrich_enabled` field**: `factory.py` reads `settings.enrich_enabled` from environment, which is the correct authority for feature-flag-level control. CLI `--no-enrichment` is handled by the pipeline not being invoked at all (the `--no-enrichment` guard is already in `main.py:332-341`).
- **No changes to `factory.py`**: Its `create(plan_only, sync_lookup_budget=0)` signature already supports the fix without modification.

## Implementation Plan

### Tasks

Tasks ordered dependency-first (lowest level first):

**Task 1: Add `enrichment_sync_budget` field to `GenericDomainOpConfig`**

- File: `src/work_data_hub/orchestration/ops/generic_ops.py`
- Location: `GenericDomainOpConfig` class (line 14-19)
- Action: Add field after `session_id`:
  ```python
  enrichment_sync_budget: int = 0
  ```
- Then update `process_domain_op_v2` factory call (line 59-61):
  ```python
  enrichment_ctx = EnrichmentServiceFactory.create(
      plan_only=config.plan_only,
      sync_lookup_budget=config.enrichment_sync_budget,
  )
  ```

**Task 2: Pass `enrichment_sync_budget` in `build_run_config()`**

- File: `src/work_data_hub/cli/etl/config.py`
- Location: `process_domain_op_v2` config dict (line 201-207)
- Action: Add key to the config dict:
  ```python
  run_config["ops"]["process_domain_op_v2"] = {
      "config": {
          "domain": domain,
          "plan_only": effective_plan_only,
          "session_id": session_id,
          "enrichment_sync_budget": getattr(args, "enrichment_sync_budget", 0),
      }
  }
  ```

**Task 3: Update test for `GenericDomainOpConfig`**

- File: `tests/unit/orchestration/test_generic_ops.py`
- Location: `TestGenericOpExists` or a new test method
- Action: Add test asserting `GenericDomainOpConfig` has `enrichment_sync_budget` field with default `0`:
  ```python
  def test_config_has_enrichment_sync_budget(self):
      from work_data_hub.orchestration.ops.generic_ops import GenericDomainOpConfig
      cfg = GenericDomainOpConfig(domain="annuity_performance")
      assert cfg.enrichment_sync_budget == 0
  ```

**Task 4: Update `test_jobs_run_config.py` with enrichment budget propagation test**

- File: `tests/unit/orchestration/test_jobs_run_config.py`
- Action: Add new test function:
  ```python
  def test_build_run_config_enrichment_sync_budget():
      """Test that enrichment_sync_budget is passed to process_domain_op_v2."""
      args = SimpleNamespace(
          mode="delete_insert",
          execute=True,
          sheet=0,
          max_files=1,
          pk=None,
          backfill_refs=None,
          backfill_mode="insert_missing",
          enrichment_sync_budget=300,
      )
      run_config = build_run_config(args, domain="annuity_performance")
      op_cfg = run_config["ops"]["process_domain_op_v2"]["config"]
      assert op_cfg["enrichment_sync_budget"] == 300

  def test_build_run_config_enrichment_sync_budget_defaults_zero():
      """Test that enrichment_sync_budget defaults to 0 when not in args."""
      args = SimpleNamespace(
          mode="delete_insert",
          execute=False,
          sheet=0,
          max_files=1,
          pk=None,
          backfill_refs=None,
          backfill_mode="insert_missing",
          # no enrichment_sync_budget attribute
      )
      run_config = build_run_config(args, domain="annuity_performance")
      op_cfg = run_config["ops"]["process_domain_op_v2"]["config"]
      assert op_cfg["enrichment_sync_budget"] == 0
  ```

### Acceptance Criteria

**AC-1: Budget propagated from CLI to factory**
- Given: User runs `uv run wdh etl run annuity_performance --enrichment-sync-budget 300 --execute`
- When: `process_domain_op_v2` executes
- Then: `EnrichmentServiceFactory.create()` is called with `sync_lookup_budget=300`

**AC-2: Default budget value is preserved**
- Given: User runs `uv run wdh etl run annuity_performance --execute` (no `--enrichment-sync-budget` flag)
- When: `build_run_config()` is called
- Then: `run_config["ops"]["process_domain_op_v2"]["config"]["enrichment_sync_budget"]` equals `0` (the Dagster config default; actual CLI default of 500 is stored in `args.enrichment_sync_budget` by argparse)

**AC-3: Zero budget disables EQC lookups**
- Given: `enrichment_sync_budget=0`
- When: `CompanyEnrichmentService` processes rows
- Then: No EQC API calls are made (existing behavior, verified by factory default test)

**AC-4: `GenericDomainOpConfig` accepts new field**
- Given: Dagster serializes config with `enrichment_sync_budget: 300`
- When: Op config is instantiated
- Then: `config.enrichment_sync_budget == 300` (no Dagster config validation errors)

**AC-5: Existing tests pass unchanged**
- Given: All pre-existing unit tests in `test_generic_ops.py`, `test_jobs_run_config.py`, `test_enrichment_factory.py`
- When: Test suite is run
- Then: All existing tests continue to pass

## Additional Context

### Dependencies

- No new package dependencies
- Dagster Config system supports `int` field type natively
- `EnrichmentServiceFactory.create()` already has `sync_lookup_budget` parameter — no factory changes needed

### Testing Strategy

Run affected test files to verify fix:
```bash
PYTHONPATH=src uv run pytest tests/unit/orchestration/test_generic_ops.py tests/unit/orchestration/test_jobs_run_config.py tests/unit/infrastructure/test_enrichment_factory.py -v
```

Manual verification: Run ETL with `--enrichment-sync-budget 10 --execute` on a small dataset and confirm real EQC company_ids appear (non-`IN-` prefix).

### Notes

- The `eqc-gui` module is NOT affected — it bypasses the Dagster pipeline entirely.
- `annual_loss` and `annuity_income` domains also use `process_domain_op_v2` but do not have `requires_enrichment=True`, so they are unaffected by the budget logic.
- The `--no-enrichment` CLI guard in `main.py:332-341` remains the correct place for disabling enrichment at the CLI level; no changes needed there.
