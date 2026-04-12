# annuity_performance Capability, Mechanism, And Field Trace Map

## Purpose

This document applies the system capability/mechanism/field-trace template to
the active `annuity_performance` domain. It is intended to make the current
implementation understandable without having to reconstruct behavior from
pipeline code, YAML config, hooks, and tests by hand.

---

## 1. Document Metadata

| Item | Value |
|------|-------|
| Scope | `domain` |
| Target Name | `annuity_performance` |
| Author | `Codex` |
| Reviewers | `{pending}` |
| Last Verified Date | `2026-04-11` |
| Repository Version / Commit | `main@e93afbe (working tree)` |
| Confidence Level | `medium-high` |

### 1.1 Scope Boundary

- Included:
  - file discovery and sheet loading for `annuity_performance`
  - Bronze-to-Silver normalization and `company_id` resolution
  - FK backfill triggered from normalized annuity performance rows
  - fact-table load to `business."规模明细"`
  - post-ETL hooks triggered only by `annuity_performance`
- Excluded:
  - implementation internals of `annual_award` and `annual_loss` ETL pipelines
  - sandbox domain behavior
  - GUI and EQC manual tooling flows outside the ETL path

### 1.2 Documentation Rules

- Source of truth is verified repository behavior as of `2026-04-11`.
- Where config, comments, and implementation disagree, the mismatch is called
  out explicitly instead of normalized away.
- Snapshot statuses that consume `annual_award` or `annual_loss` are documented
  here only as downstream dependencies of `annuity_performance`.

---

## 2. System Capability Map

### 2.1 Capability Inventory

| Capability ID | Capability Name | Business Purpose | Trigger | Primary Inputs | Primary Outputs | Affected Objects | Source Of Truth |
|---------------|-----------------|------------------|---------|----------------|-----------------|------------------|-----------------|
| CAP-AP-001 | Source workbook discovery and sheet loading | Find the correct monthly `规模收入数据` workbook and extract `规模明细` rows for the requested period | ETL CLI / Dagster generic job | `--period`, `config/data_sources.yml`, monthly Excel files | in-memory row dictionaries | discovery logs, selected file path, extracted rows | `config/data_sources.yml`, `discover_files_op`, `read_data_op`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| CAP-AP-002 | Normalize and enrich annuity performance fact rows | Convert raw `规模明细` rows into canonical fact rows with derived plan code, product line, organization code, cleansing, and `company_id` | `process_domain_op_v2` | raw rows, shared transform steps, cleansing rules, enrichment resolver inputs | normalized rows for load and backfill | transformed DataFrame / row payload | `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`, `src/work_data_hub/infrastructure/cleansing/settings/cleansing_rules.yml`, `tests/slice_tests/test_b_annuity_performance_pipeline.py`, `tests/slice_tests/test_j_real_effect_guards.py` |
| CAP-AP-003 | Reference and customer master backfill | Derive candidate records from normalized facts and maintain reference/master tables before fact load | `generic_backfill_refs_op` | normalized annuity performance rows, `config/foreign_keys.yml` | candidate records / insert-missing operations | `mapping."年金计划"`, `mapping."组合计划"`, `mapping."产品线"`, `mapping."组织架构"`, `customer."客户明细"` | `config/foreign_keys.yml`, `src/work_data_hub/domain/reference_backfill/generic_service.py`, `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| CAP-AP-004 | Publish normalized annuity fact table | Persist current-period normalized rows to the business fact table with idempotent delete-insert semantics | `load_op` after backfill gate | gated normalized rows, output config PK | refreshed fact-table rows or SQL plan | `business."规模明细"` | `config/data_sources.yml`, `src/work_data_hub/orchestration/ops/loading.py`, `tests/slice_tests/test_f_load_upsert.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| CAP-AP-005 | Maintain customer contract and snapshot views | Keep customer contract SCD2 state and monthly snapshots aligned after annuity performance ETL succeeds | post-ETL hooks for `annuity_performance` | `business."规模明细"`, current customer contract rows, status rules, annual award/loss fact tables | refreshed `客户年金计划`, `客户业务月度快照`, `客户计划月度快照` | customer MDM tables, hook logs | `src/work_data_hub/cli/etl/hooks.py`, `src/work_data_hub/customer_mdm/contract_sync.py`, `src/work_data_hub/customer_mdm/snapshot_refresh.py`, `config/customer_status_rules.yml`, `tests/integration/customer_mdm/test_hook_chain.py` |

### 2.2 Capability Notes

- `CAP-AP-002` is where most field-level black-box behavior currently lives.
- `CAP-AP-003` is config-driven in appearance, but actual behavior is executed by
  `GenericBackfillService`; config comments alone are not sufficient.
- `CAP-AP-005` is triggered only for `annuity_performance`, but some status
  outcomes depend on `annual_award` and `annual_loss` tables already being
  populated.

### 2.3 Capability Dependency Map

| Capability ID | Depends On | Dependency Type | Why It Matters | Evidence |
|---------------|------------|-----------------|----------------|----------|
| `CAP-AP-002` | `CAP-AP-001` | upstream | transformation can only run after a workbook is selected and rows are read | `tests/slice_tests/test_h_end_to_end_flows.py` |
| `CAP-AP-003` | `CAP-AP-002` | upstream | backfill candidates are derived from normalized rows, not raw Excel rows | `src/work_data_hub/domain/reference_backfill/generic_service.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| `CAP-AP-004` | `CAP-AP-003` | order/gate | the orchestration contract gates fact load behind backfill completion | `tests/slice_tests/test_h_end_to_end_flows.py` |
| `CAP-AP-005` | `CAP-AP-004` | upstream | hooks operate after successful ETL completion and consume loaded fact behavior | `src/work_data_hub/cli/etl/hooks.py`, `tests/integration/customer_mdm/test_hook_chain.py` |
| `CAP-AP-005` | `customer."中标客户明细"` / `customer."流失客户明细"` | cross-domain | snapshot statuses such as `is_winning_this_year` and `is_loss_reported` depend on award/loss fact tables | `config/customer_status_rules.yml`, `tests/integration/customer_mdm/test_status_evaluation.py`, `docs/verification_guide_real_data.md` |

---

## 3. Implementation Mechanism Map

### 3.1 Mechanism Inventory

| Mechanism ID | Capability ID | Stage | Entry Point | Core Modules | Rule Source Type | Rule Source Location(s) | Side Effects | Failure Signal | Verification Anchor |
|--------------|---------------|-------|-------------|--------------|------------------|-------------------------|--------------|----------------|---------------------|
| MEC-AP-001 | `CAP-AP-001` | discover | `discover_files_op` | `src/work_data_hub/orchestration/ops/file_processing.py`, `src/work_data_hub/io/connectors/discovery/service.py` | `config + code` | `config/data_sources.yml` | file selection, logs | discovery error / ambiguous file error | `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| MEC-AP-002 | `CAP-AP-001` | read | `read_data_op` | `src/work_data_hub/orchestration/ops/file_processing.py`, `src/work_data_hub/io/readers/excel_reader.py` | `config + code` | `config/data_sources.yml` | row extraction from Excel | sheet/file read error | `tests/slice_tests/test_h_end_to_end_flows.py`, `tests/integration/io/test_excel_reader_integration.py` |
| MEC-AP-003 | `CAP-AP-002` | transform | `process_domain_op_v2` -> `build_bronze_to_silver_pipeline()` | `src/work_data_hub/domain/annuity_performance/pipeline_builder.py` | `mixed` | pipeline step definitions in `pipeline_builder.py`; cleansing rules in `src/work_data_hub/infrastructure/cleansing/settings/cleansing_rules.yml` | field mutation, legacy-column drop | validation error / missing derived fields / wrong parity | `tests/slice_tests/test_b_annuity_performance_pipeline.py`, `tests/e2e/test_pipeline_vs_legacy.py` |
| MEC-AP-004 | `CAP-AP-002` | resolve | `CompanyIdResolutionStep.apply()` | `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`, `src/work_data_hub/infrastructure/enrichment/` | `mixed` | YAML overrides, enrichment index lookup, existing source column, EQC provider, temp-ID generation | writes `company_id`; may query cache or EQC provider | unresolved IDs, wrong priority order, enrichment logs | `tests/slice_tests/test_j_real_effect_guards.py`, `tests/slice_tests/test_b_annuity_performance_pipeline.py` |
| MEC-AP-005 | `CAP-AP-003` | backfill | `generic_backfill_refs_op` -> `GenericBackfillService.derive_candidates()` | `src/work_data_hub/orchestration/ops/generic_backfill.py`, `src/work_data_hub/domain/reference_backfill/generic_service.py` | `config + code` | `config/foreign_keys.yml` and backfill aggregation code | inserts/updates reference and customer master tables | missing candidate rows, wrong aggregation outputs | `tests/slice_tests/test_e_backfill_engine.py`, `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| MEC-AP-006 | `CAP-AP-004` | load | `load_op` | `src/work_data_hub/orchestration/ops/loading.py` | `config + code` | output target and PK in `config/data_sources.yml` | delete-insert fact-table write | SQL plan mismatch / idempotency regression | `tests/slice_tests/test_f_load_upsert.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| MEC-AP-007 | `CAP-AP-005` | hook | `run_post_etl_hooks()` -> `sync_contract_status()` and `initialize_year_status()` | `src/work_data_hub/cli/etl/hooks.py`, `src/work_data_hub/customer_mdm/contract_sync.py`, `src/work_data_hub/customer_mdm/year_init.py` | `hook + sql + code` | hook registry and customer MDM modules | SCD2 updates in `customer."客户年金计划"`; January-only year initialization | hook failure log / wrong status rows | `tests/integration/customer_mdm/test_hook_chain.py`, `tests/integration/customer_mdm/test_status_fields.py` |
| MEC-AP-008 | `CAP-AP-005` | hook | `run_post_etl_hooks()` -> `refresh_monthly_snapshot()` | `src/work_data_hub/cli/etl/hooks.py`, `src/work_data_hub/customer_mdm/snapshot_refresh.py`, `src/work_data_hub/customer_mdm/status_evaluator.py` | `hook + sql + config` | `config/customer_status_rules.yml` plus snapshot SQL generation | upserts into monthly snapshot tables | bad SQL fragments / missing status fields / hook order regression | `tests/slice_tests/test_g_snapshot_status.py`, `tests/slice_tests/test_i_snapshot_refresh_contract.py`, `tests/integration/customer_mdm/test_status_evaluation.py` |

### 3.2 Stage Contract Summary

| Stage | Expected Input Contract | Expected Output Contract | Mutable Fields | Notes |
|-------|-------------------------|--------------------------|----------------|-------|
| discover | domain + period + discovery config | one selected file path list | none | version strategy defaults to `highest_number` for this domain |
| read | selected file paths + `规模明细` sheet name | raw row dictionaries | none | workbook is single-sheet in active config |
| transform | raw rows with source workbook columns | normalized rows with canonical columns including `计划代码`, `机构代码`, `产品线代码`, `company_id` | high | 13 explicit steps in `build_bronze_to_silver_pipeline()` |
| backfill | normalized rows + FK config | candidate records / insert-missing summaries | medium | aggregation behavior is declared in YAML but executed in Python |
| gate | transformed rows + backfill summary | same rows if backfill completed | none | preserves orchestration order before load |
| load | gated normalized rows + output config | SQL plan or fact-table refresh | none | delete scope is `月度`, `业务类型`, `计划类型` |
| post-hook contract | period + fact-table state | SCD2 rows in `customer."客户年金计划"` | high | `contract_status_sync` uses period-derived end date |
| post-hook snapshot | period + customer contract state + status rules | upserted ProductLine / Plan snapshot rows | high | status SQL is generated from config, not hardcoded inline |

### 3.3 Rule Ownership Summary

| Rule Category | Owned By | Typical Location | Change Risk | Review Requirement |
|---------------|----------|------------------|-------------|--------------------|
| Field cleansing | annuity domain pipeline + infrastructure cleansing | `pipeline_builder.py`, `infrastructure/cleansing/settings/cleansing_rules.yml` | high | domain + infrastructure review |
| Company ID resolution | infrastructure enrichment | `infrastructure/enrichment/`, plan override YAML, resolver strategy | high | enrichment + domain review |
| Cross-table derivation | reference backfill + customer MDM | `config/foreign_keys.yml`, `domain/reference_backfill/`, `customer_mdm/` | high | data-contract review |
| Post-ETL hook behavior | ETL CLI hook registry + customer MDM | `cli/etl/hooks.py`, `customer_mdm/` | high | orchestration + MDM review |
| External enrichment fallback | enrichment resolver and EQC integration | `infrastructure/enrichment/`, `io/connectors/eqc*` | medium-high | enrichment review |

### 3.4 Execution Ordering And Gates

| Before | After | Why The Order Matters | Evidence |
|--------|-------|-----------------------|----------|
| `MEC-AP-001` | `MEC-AP-002` | reading requires a resolved path list and sheet selection context | `tests/slice_tests/test_h_end_to_end_flows.py` |
| `MEC-AP-003` | `MEC-AP-005` | backfill is based on transformed canonical fields, not raw source columns | `tests/slice_tests/test_h_end_to_end_flows.py` |
| `MEC-AP-005` | `MEC-AP-006` | `gate_after_backfill` protects fact load ordering | `tests/slice_tests/test_h_end_to_end_flows.py` |
| `MEC-AP-007` | `MEC-AP-008` | snapshot refresh depends on fresh `客户年金计划` contract state | `src/work_data_hub/cli/etl/hooks.py`, `tests/integration/customer_mdm/test_hook_chain.py` |

---

## 4. Key Field Trace Table

Document only the critical fields first.

### 4.1 Field Trace Inventory

| Field ID | Capability ID | Output Field | Business Meaning | Raw Source | Stage Chain | Named Rules Applied | Rule Location | Final Sink | Verification Anchor |
|----------|---------------|--------------|------------------|------------|-------------|---------------------|---------------|------------|---------------------|
| FLD-AP-001 | `CAP-AP-002` | `计划代码` | canonical plan identifier used for fact, plan backfill, and contract sync | workbook `规模明细.计划代码` plus `计划类型` when blank | read -> mapping -> correction -> defaulting -> load/backfill/hooks | `PLAN_CODE_CORRECTIONS`, `apply_plan_code_defaults()` | `src/work_data_hub/domain/annuity_performance/pipeline_builder.py` | `business."规模明细".计划代码` and downstream plan references | `tests/slice_tests/test_b_annuity_performance_pipeline.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| FLD-AP-002 | `CAP-AP-002` | `产品线代码` | stable product-line join key for backfill and snapshots | workbook `业务类型` | read -> transform -> load -> hook | `BUSINESS_TYPE_CODE_MAPPING` | `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`, `src/work_data_hub/infrastructure/mappings/shared.py` | `business."规模明细".产品线代码`, snapshot join key | `tests/slice_tests/test_h_end_to_end_flows.py`, `tests/slice_tests/test_i_snapshot_refresh_contract.py` |
| FLD-AP-003 | `CAP-AP-002` | `company_id` | normalized enterprise identifier used across fact, MDM, and snapshots | `计划代码`, `客户名称`, `年金账户名`, `集团企业客户号`, optional source company code | read -> derive account name -> cleanse -> resolution priority chain -> load/backfill/hooks | YAML override -> DB cache -> existing column -> EQC -> temp ID | `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`, `src/work_data_hub/infrastructure/enrichment/`, company-id override configs | `business."规模明细".company_id` and downstream customer MDM tables | `tests/slice_tests/test_j_real_effect_guards.py`, `tests/e2e/test_pipeline_vs_legacy.py` |
| FLD-AP-004 | `CAP-AP-003` | `customer."客户明细".tags` | customer-level accumulated business-event tags derived from source facts | normalized `月度` field from annuity performance facts | transform -> backfill candidate aggregation -> customer detail insert/update | `jsonb_append` tag formatter -> `yyMM新建` | `config/foreign_keys.yml`, `src/work_data_hub/domain/reference_backfill/generic_service.py` | `customer."客户明细".tags` | `tests/slice_tests/test_h_end_to_end_flows.py`, `docs/verification_guide_real_data.md` |
| FLD-AP-005 | `CAP-AP-005` | `customer."客户年金计划".contract_status` | current contract activity status for each customer-plan-product-line tuple | `business."规模明细".期末资产规模` plus 12-month contribution presence | load -> contract sync hook -> SQL CTEs -> SCD2 insert | `determine_contract_status()` and SCD2 close/insert flow | `src/work_data_hub/customer_mdm/contract_sync.py` | `customer."客户年金计划".contract_status` and downstream plan snapshot contract status | `tests/integration/customer_mdm/test_status_fields.py`, `docs/verification_guide_real_data.md` |
| FLD-AP-006 | `CAP-AP-005` | `customer."客户业务月度快照".is_new` | new-arrival customer status at customer / product-line granularity only | current contract rows (`is_existing`) plus annual award facts | contract sync/year_init -> snapshot refresh -> generated status SQL | `is_winning_this_year AND NOT BOOL_OR(is_existing)` | `config/customer_status_rules.yml`, `src/work_data_hub/customer_mdm/status_evaluator.py`, `src/work_data_hub/customer_mdm/snapshot_refresh.py` | `customer."客户业务月度快照".is_new` | `tests/slice_tests/test_g_snapshot_status.py`, `tests/integration/customer_mdm/test_status_evaluation.py` |

### 4.2 Step-By-Step Trace Details

#### `FLD-AP-003` `company_id`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | raw `客户名称` | copy original customer name to `年金账户名` before cleansing | preserve original account-name clue | raw account-name clue available for resolver | `build_bronze_to_silver_pipeline()` |
| 2 | plan code / customer name / account fields | run resolver priority chain | YAML -> DB cache -> existing -> EQC -> temp | resolved `company_id` string | `tests/slice_tests/test_j_real_effect_guards.py` |
| 3 | resolved `company_id` | persist into fact rows and use as grouping key for backfill and hooks | downstream identity propagation | `company_id` appears in fact, customer detail, contract, and snapshot tables | `tests/slice_tests/test_h_end_to_end_flows.py`, `tests/e2e/test_pipeline_vs_legacy.py` |

#### `FLD-AP-004` `customer."客户明细".tags`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | normalized `月度` such as `2025-10-01` | group rows by `company_id` in FK customer backfill | candidate grouping | one customer-level group | `GenericBackfillService.derive_candidates()` |
| 2 | grouped `月度` values | format first non-null date as `%y%m` and append suffix `新建` | `jsonb_append` lambda in `fk_customer.tags` | JSON array containing values such as `2510新建` | `config/foreign_keys.yml` |
| 3 | tag array | write/update customer detail payload | customer master enrichment | `customer."客户明细".tags` | `tests/slice_tests/test_h_end_to_end_flows.py` |

#### `FLD-AP-005` `customer."客户年金计划".contract_status`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | fact rows grouped by `company_id + 计划代码 + 产品线代码` | compute period end date and contribution window in sync SQL | period-based SCD2 contract sync | candidate current contract rows | `sync_contract_status()` |
| 2 | `期末资产规模` + contribution presence | evaluate active vs paused contract | `determine_contract_status()` | `正常` or `停缴` | `src/work_data_hub/customer_mdm/contract_sync.py`, `tests/integration/customer_mdm/test_status_fields.py` |
| 3 | current vs prior status | close old rows and insert new rows | SCD Type 2 close/insert | current and historical contract rows | `sync_contract_status()` |

### 4.3 Ambiguities And Unknowns

No verified unresolved field-trace ambiguities remain in this slice after the
current contract fixes for temp-ID backfill filtering and status-definition
metadata alignment.

---

## 5. Test And Validation Coverage

### 5.1 Protection Matrix

| Capability ID | Mechanism ID | Validation Type | File / Command | What It Proves | Gaps |
|---------------|--------------|-----------------|----------------|----------------|------|
| `CAP-AP-001` | `MEC-AP-001`, `MEC-AP-002` | slice | `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` | version selection, sheet loading, merged read contract | does not cover full real-data directory variance |
| `CAP-AP-002` | `MEC-AP-003`, `MEC-AP-004` | slice + e2e | `tests/slice_tests/test_b_annuity_performance_pipeline.py`, `tests/slice_tests/test_j_real_effect_guards.py`, `tests/e2e/test_pipeline_vs_legacy.py` | transform-step contracts, resolver priority, legacy parity baseline | resolver behavior with real DB/EQC mix still depends on integration coverage |
| `CAP-AP-003` | `MEC-AP-005` | slice | `tests/slice_tests/test_e_backfill_engine.py`, `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py` | FK config parsing and aggregation outputs | `skip_blank_values` semantics are not explicitly proven |
| `CAP-AP-004` | `MEC-AP-006` | slice | `tests/slice_tests/test_f_load_upsert.py`, `tests/slice_tests/test_h_end_to_end_flows.py` | delete-insert SQL plan and orchestration chain | real PostgreSQL side effects rely on integration tests |
| `CAP-AP-005` | `MEC-AP-007`, `MEC-AP-008` | slice + integration + SQL runbook | `tests/slice_tests/test_g_snapshot_status.py`, `tests/slice_tests/test_i_snapshot_refresh_contract.py`, `tests/integration/customer_mdm/test_hook_chain.py`, `tests/integration/customer_mdm/test_status_evaluation.py`, `tests/integration/customer_mdm/test_status_fields.py`, `docs/verification_guide_real_data.md` | hook order, generated SQL contracts, status-field behavior, real-data verification workflow | January-specific `year_init` behavior is only indirectly covered here |

### 5.2 Real-Data Or Snapshot Anchors

| Artifact | Location | Coverage | Refresh Policy |
|----------|----------|----------|----------------|
| golden dataset requirements | `tests/fixtures/golden_dataset/curated/dataset_requirements.md` | scenario inventory for cleansing, enrichment, backfill, and parity | refresh when scope of annuity performance behavior changes |
| legacy parity baseline | `tests/fixtures/annuity_performance/golden_legacy.parquet` | pipeline-vs-legacy output comparison | refresh whenever legacy baseline script or protected transformation behavior changes |
| real-data verification guide | `docs/verification_guide_real_data.md` | operator SQL checks for fact load, MDM sync, and snapshot outputs | refresh whenever hook chain, status rules, or target tables change |

---

## 6. Refactoring Risk Assessment

### 6.1 High-Risk Areas

| Area | Why Risky | Impact If Broken | Required Safeguard |
|------|-----------|------------------|--------------------|
| plan-code defaulting and correction | affects fact PK scope, plan backfill, and downstream contract rows | duplicated or missing plan identities | keep slice contracts and parity checks green |
| company ID resolution chain | mixes YAML, DB cache, source passthrough, EQC, and temp IDs | customer identity fragmentation across all downstream tables | preserve priority-chain tests and representative real-data samples |
| FK customer aggregation | produces cross-table derived master data such as `主拓机构`, `关联计划数`, and `tags` | customer master data drifts from facts | add targeted derivation tests before refactoring |
| hook-chain ordering | snapshots depend on fresh contract rows | downstream analytics and status fields become stale or wrong | preserve hook-order integration tests |
| status-rule config drift | descriptive metadata and generated SQL can diverge | operators and maintainers trust the wrong source | add drift checks between config metadata and generated SQL behavior |

### 6.2 Safe Refactoring Boundaries

- Safe to change:
  - logging detail and internal helper decomposition when outputs stay the same
  - file/module layout that preserves existing contracts and imports
- Change with parity checks:
  - pipeline step internals
  - resolver orchestration
  - backfill aggregation implementation
  - snapshot SQL generation internals
- Do not change without explicit migration design:
  - fact-table PK semantics
  - `company_id` priority order
  - SCD2 contract versioning behavior
  - snapshot status semantics exposed to operators

---

## 7. Open Questions

No active open questions remain for this slice after the current contract fixes.

---

## 8. Completion Checklist

- [x] Capability inventory is complete for the chosen scope.
- [x] Every capability points to at least one source-of-truth file.
- [x] Every critical mechanism names its rule source type.
- [x] Every critical field has a trace row.
- [x] Every critical field points to a validation anchor.
- [x] Unknowns are listed explicitly instead of implied away.
- [x] Config/comment/implementation drift discovered during mapping is recorded explicitly.

---

## 9. Minimal Example Guidance

This document is the first practical fill of the mapping template. It is not a
complete repository map. It should be used as the pilot reference for future
domain fills and template adjustments.
