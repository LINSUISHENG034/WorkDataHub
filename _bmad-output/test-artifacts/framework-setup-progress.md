---
stepsCompleted: ['step-01-preflight', 'step-02-select-framework', 'step-03-scaffold-framework', 'step-04-docs-and-scripts', 'step-05-validate-and-summary']
lastStep: 'step-05-validate-and-summary'
lastSaved: '2026-02-27'
mode: 'refactor-existing'
---

# Step 1: Preflight Results

## Stack Detection
- **detected_stack**: backend
- **language**: Python 3.10+
- **package_manager**: uv
- **framework**: Dagster + SQLAlchemy 2.0 + Pandas + Pandera
- **test_framework**: pytest (already installed and configured)

## Existing Test Infrastructure
- **conftest.py files**: 7
- **test files**: ~155
- **test directories**: 20+
- **fixtures**: tests/fixtures/ (data factory, golden datasets, sample data)
- **markers**: unit, integration, postgres, e2e, performance, legacy_suite, e2e_suite, sandbox_domain

## Decision
- User requested: **Refactor existing test suite** based on latest planning docs
- Reason: Accumulated redundancy from multiple iteration rounds, lack of structural planning
- Approach: Audit → Plan → Restructure (not greenfield initialization)

# Step 2: Framework Selection

## Selected Framework
- **Framework**: pytest
- **Version**: Already installed via dev dependencies
- **Stack type**: backend (Python 3.10+)

## Rationale
1. Project already has mature pytest infrastructure (7 conftest.py, ~155 test files, 8 custom markers)
2. Python backend project — pytest is the ecosystem standard
3. Mode is refactor-existing, not greenfield initialization
4. All required plugins already in dev dependencies (pytest-cov, pytest-postgresql, pytest-asyncio)
5. No browser-based testing needed — pure data processing platform (Dagster + SQLAlchemy + Pandas)

# Step 3: Scaffold Framework

## Deliverables Created

| # | Deliverable | Type | Path |
|---|---|---|---|
| 3.1 | Target directory structure | Directories | `tests/unit/architecture/`, `tests/support/`, `tests/support/helpers/` |
| 3.2 | Migration verification script | Tool | `scripts/verify_test_migration.py` |
| 3.3 | Architecture guardrail test | Test | `tests/unit/architecture/test_test_structure.py` |
| 3.4 | Migration execution plan | Document | This section (below) |
| 3.5 | Migration baseline snapshot | Data | `tests/.migration_baseline.txt` |

## Migration Execution Plan (7 Batches)

### Safety Protocol
1. **Before any migration**: Run `PYTHONPATH=src uv run python scripts/verify_test_migration.py collect`
2. **After each batch**: Run `PYTHONPATH=src uv run python scripts/verify_test_migration.py verify`
3. **Each batch = 1 git commit** (easy rollback with `git revert`)

### Batch 1: tests/architecture → tests/unit/architecture (2 files)
- `tests/architecture/test_domain_sources.py` → `tests/unit/architecture/test_domain_sources.py`
- `tests/architecture/test_protocol_compliance.py` → `tests/unit/architecture/test_protocol_compliance.py`
- **Risk**: Low — smallest batch, validates process
- **Commit**: `refactor(tests): migrate tests/architecture → tests/unit/architecture`

### Batch 2: tests/auth → tests/unit/auth (1 file)
- `tests/auth/test_eqc_auth_handler.py` → `tests/unit/auth/test_eqc_auth_handler.py`
- **Risk**: Low — single file, no conftest dependencies
- **Prereq**: Create `tests/unit/auth/__init__.py`
- **Commit**: `refactor(tests): migrate tests/auth → tests/unit/auth`

### Batch 3: tests/config → tests/unit/config (4 files)
- `tests/config/test_data_sources_schema.py`
- `tests/config/test_mapping_loader.py`
- `tests/config/test_settings.py`
- `tests/config/test_settings_env.py`
- **Risk**: Low — independent tests, no shared conftest
- **Note**: `tests/unit/config/` already has 3 files; check for naming conflicts
- **Commit**: `refactor(tests): migrate tests/config → tests/unit/config`

### Batch 4: tests/orchestration → tests/unit/orchestration (8 files)
- `test_backfill_ops.py`, `test_cleanup_verification.py`, `test_generic_ops.py`
- `test_jobs.py`, `test_jobs_run_config.py`, `test_job_config_contract.py`
- `test_ops.py`, `test_ops_domain_registry.py`
- **Risk**: Medium — 3 files already deleted in git (test_repository, test_schedules, test_sensors migrated)
- **Note**: Verify no duplicate filenames with existing `tests/unit/orchestration/`
- **Commit**: `refactor(tests): migrate tests/orchestration → tests/unit/orchestration`

### Batch 5: tests/infrastructure → tests/unit/infrastructure (8 files)
- `enrichment/resolver/test_backflow.py`, `enrichment/resolver/test_cache_warming.py`, `enrichment/resolver/test_progress.py`
- `enrichment/test_csv_exporter.py`, `enrichment/test_eqc_confidence_config.py`, `enrichment/test_eqc_provider_confidence.py`
- `test_enrichment_factory.py`, `validation/test_failure_exporter.py`
- **Risk**: Medium — nested subdirectories; ensure `tests/unit/infrastructure/enrichment/resolver/` exists
- **Commit**: `refactor(tests): migrate tests/infrastructure → tests/unit/infrastructure`

### Batch 6: tests/io → tests/unit/io (9 files)
- `connectors/test_adapters.py`, `connectors/test_eqc_client.py`
- `schema/test_domain_registry.py`, `schema/test_migrations.py`, `schema/test_seed_resolver.py`
- `test_excel_reader.py`, `test_file_connector.py`
- `test_warehouse_loader.py`, `test_warehouse_loader_backfill.py`
- **Risk**: Medium — ensure `tests/unit/io/schema/` directory created
- **Note**: `tests/unit/io/readers/test_excel_reader.py` already exists; check for conflict with `tests/io/test_excel_reader.py`
- **Commit**: `refactor(tests): migrate tests/io → tests/unit/io`

### Batch 7: tests/domain → tests/unit/domain (15 files)
- `annuity_performance/test_models.py`, `annuity_performance/test_model_validation.py`, `annuity_performance/test_service.py`
- `company_enrichment/test_enrichment_service.py`, `company_enrichment/test_lookup_queue.py`, `company_enrichment/test_models.py`, `company_enrichment/test_observability.py`
- `pipelines/test_adapters.py`, `pipelines/test_config_builder.py`, `pipelines/test_pipeline_config_factory.py`
- `reference_backfill/test_service.py`
- `test_company_enrichment.py`
- `trustee_performance/test_models.py`, `trustee_performance/test_service.py`, `trustee_performance/test_validation_error_handling.py`
- **Risk**: HIGH — largest batch; `pipelines/conftest.py` has hardcoded import paths (`tests.domain.pipelines.conftest.UpperCaseStep`) that must be updated
- **Prereq**: Create missing subdirs under `tests/unit/domain/` (company_enrichment, pipelines, etc.)
- **Special**: Merge `tests/domain/pipelines/conftest.py` fixtures into `tests/unit/domain/pipelines/` conftest
- **Commit**: `refactor(tests): migrate tests/domain → tests/unit/domain`

### Post-Migration (Step 5)
- Update `testpaths` in `pyproject.toml` to exclude legacy dirs
- Delete empty legacy directories
- Final baseline verification
- Run full test suite to confirm green

# Step 4: Documentation & Scripts

## Deliverables
- `tests/README.md` — Test suite documentation with quick start, directory structure, markers, best practices, CI commands, and migration tools
- No Makefile created — `uv run pytest` is sufficient (KISS principle)
- Test commands documented in README rather than duplicated in build config

# Step 5: Validate & Summary

## Validation Results

### Prerequisites
- ✅ `pyproject.toml` exists with pytest configuration
- ✅ Project type: Python 3.10+ backend (Dagster + SQLAlchemy + Pandas)
- ✅ pytest already installed and configured with 8 custom markers

### Directory Structure
- ✅ All 18 target directories exist
- ✅ All `tests/unit/` subdirectories have `__init__.py` (12 missing files fixed)
- ✅ `tests/support/` and `tests/support/helpers/` created

### File Deliverables
- ✅ `scripts/verify_test_migration.py` — collect/verify subcommands working
- ✅ `tests/unit/architecture/test_test_structure.py` — guardrail test operational
- ✅ `tests/README.md` — complete documentation
- ✅ `tests/.migration_baseline.txt` — 2957 test IDs captured
- ✅ `_bmad-output/test-artifacts/framework-setup-progress.md` — this document

### Guardrail Test Status
- ✅ `test_unit_subdirs_have_init_py` — PASSED
- ⏳ `test_no_tests_in_legacy_directories` — 8 EXPECTED FAILURES (will pass after migration)

## Completion Summary

**Framework**: pytest (existing, refactor-existing mode)
**Baseline**: 2957 test IDs captured
**Migration plan**: 7 batches, 49 files, risk-ordered (low → high)
**Safety tools**: Baseline script + guardrail test + per-batch commit strategy

## Next Steps

1. Execute 7-batch migration (see Migration Execution Plan above)
2. After all batches: update `testpaths` in `pyproject.toml`
3. Delete empty legacy directories
4. Run final baseline verification
5. Commit guardrail test (currently expected-fail → all-pass)
