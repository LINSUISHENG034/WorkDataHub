# annual_loss Capability, Mechanism, And Field Trace Map

## Purpose

This document applies the system capability/mechanism/field-trace template to
the active `annual_loss` domain. It focuses on the event-style ETL path for
loss reporting, especially the multi-sheet read contract, conditional
`company_id` resolution, conditional plan-code enrichment, and downstream use
of loss facts in customer churn status evaluation.

---

## 1. Document Metadata

| Item | Value |
|------|-------|
| Scope | `domain` |
| Target Name | `annual_loss` |
| Author | `Codex` |
| Reviewers | `{pending}` |
| Last Verified Date | `2026-04-11` |
| Repository Version / Commit | `main@e93afbe (working tree)` |
| Confidence Level | `medium-high` |

### 1.1 Scope Boundary

- Included:
  - multi-sheet file discovery and merged sheet loading
  - Bronze-to-Silver transformation for annual loss rows
  - optional `company_id` resolution
  - conditional `年金计划号` enrichment from `customer."客户年金计划"`
  - customer master backfill derived from loss facts
  - fact load to `customer."流失客户明细"`
  - downstream use of loss facts in product-line and plan-level churn status
- Excluded:
  - `annual_award` ETL internals
  - `annuity_performance` hook implementation details
  - GUI or manual enrichment tooling outside the ETL path

### 1.2 Documentation Rules

- Source of truth is verified repository behavior as of `2026-04-11`.
- Runtime activation conditions are recorded from actual adapter behavior, not
  from comments alone.
- Downstream snapshot behavior is included only where `annual_loss` acts as a
  source fact table.

---

## 2. System Capability Map

### 2.1 Capability Inventory

| Capability ID | Capability Name | Business Purpose | Trigger | Primary Inputs | Primary Outputs | Affected Objects | Source Of Truth |
|---------------|-----------------|------------------|---------|----------------|-----------------|------------------|-----------------|
| CAP-AL-001 | Loss workbook discovery and multi-sheet loading | Find the current loss workbook and merge trustee/investee sheets into one ETL input stream | ETL CLI / Dagster generic job | `--period`, `config/data_sources.yml`, monthly business workbook | merged in-memory row dictionaries | discovery logs, selected workbook, merged rows | `config/data_sources.yml`, `discover_files_op`, `read_data_op`, `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| CAP-AL-002 | Normalize and cleanse annual loss event rows | Convert raw loss rows into canonical event rows with standardized columns, dates, plan type, product line, branch code, and customer name | `process_domain_op_v2` | raw loss rows, shared transforms, domain cleansing rules | normalized event rows | transformed DataFrame / row payload | `src/work_data_hub/domain/annual_loss/pipeline_builder.py`, `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| CAP-AL-003 | Resolve identities and fill missing plan codes | Preserve or resolve `company_id`, then infer missing `年金计划号` using customer-plan history and fallback defaults | loss pipeline execution | normalized loss rows, optional company_id resolver inputs, `customer."客户年金计划"` lookup rows | event rows with `company_id` and `年金计划号` populated when possible | transformed rows before load/backfill | `src/work_data_hub/domain/annual_loss/pipeline_builder.py`, `tests/slice_tests/test_j_real_effect_guards.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| CAP-AL-004 | Backfill customer master with loss-derived signals | Derive customer-level aggregates such as main branch, plan counts, event tags, and customer type from loss facts | `generic_backfill_refs_op` | normalized loss rows, `config/foreign_keys.yml` | insert-missing candidate records for customer detail | `customer."客户明细"` | `config/foreign_keys.yml`, `src/work_data_hub/domain/reference_backfill/generic_service.py`, `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| CAP-AL-005 | Publish loss fact rows for downstream loss-report logic | Persist annual loss declaration facts to the customer schema so later snapshot refresh can compute `is_loss_reported` and related analysis fields | `load_op` | gated normalized loss rows | refreshed `流失客户明细` fact rows | `customer."流失客户明细"` and downstream status SQL consumers | `config/data_sources.yml`, `src/work_data_hub/orchestration/ops/loading.py`, `config/customer_status_rules.yml`, `tests/integration/customer_mdm/test_status_evaluation.py` |

### 2.2 Capability Notes

- `annual_loss` is an event domain with no post-ETL hook chain of its own.
- Like `annual_award`, the adapter itself performs pipeline orchestration.
- `CAP-AL-003` is the main black-box area because it mixes source
  `company_id`, resolver priority, customer-plan lookup, and fallback defaults.

### 2.3 Capability Dependency Map

| Capability ID | Depends On | Dependency Type | Why It Matters | Evidence |
|---------------|------------|-----------------|----------------|----------|
| `CAP-AL-002` | `CAP-AL-001` | upstream | transformation requires merged trustee/investee row input | `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| `CAP-AL-003` | `customer."客户年金计划"` | upstream lookup | missing `年金计划号` values are enriched from customer-plan rows | `PlanCodeEnrichmentStep._build_plan_code_mapping()`, `tests/slice_tests/test_j_real_effect_guards.py` |
| `CAP-AL-004` | `CAP-AL-003` | upstream | customer master backfill relies on resolved identity and final `年金计划号` values | `tests/slice_tests/test_h_end_to_end_flows.py` |
| `CAP-AL-005` | `CAP-AL-004` | order/gate | orchestration contract gates event fact load behind backfill completion | `tests/slice_tests/test_j_real_effect_guards.py` |
| `CAP-AL-005` | `annuity_performance` hook chain | downstream | `annuity_performance` snapshot refresh later reads `customer."流失客户明细"` to compute reported-loss statuses while churn itself is computed from `规模明细` | `config/customer_status_rules.yml`, `tests/integration/customer_mdm/test_status_evaluation.py`, `docs/verification_guide_real_data.md` |

---

## 3. Implementation Mechanism Map

### 3.1 Mechanism Inventory

| Mechanism ID | Capability ID | Stage | Activation Condition | Entry Point | Core Modules | Rule Source Type | Rule Source Location(s) | Side Effects | Failure Signal | Verification Anchor |
|--------------|---------------|-------|----------------------|-------------|--------------|------------------|-------------------------|--------------|----------------|---------------------|
| MEC-AL-001 | `CAP-AL-001` | discover/read | always | `discover_files_op`, `read_data_op` | `src/work_data_hub/orchestration/ops/file_processing.py`, `src/work_data_hub/io/readers/excel_reader.py` | `config + code` | `config/data_sources.yml` | file selection, merged multi-sheet row extraction | discovery/read error, wrong sheet merge behavior | `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| MEC-AL-002 | `CAP-AL-002` | transform | always | `AnnualLossService.process()` -> `build_bronze_to_silver_pipeline()` | `src/work_data_hub/domain/annual_loss/adapter.py`, `src/work_data_hub/domain/annual_loss/pipeline_builder.py` | `mixed` | pipeline step definitions, domain constants, cleansing rules | field mutation, date parsing, branch mapping, legacy-column drop | wrong normalized columns, bad date parsing, missing cleansed fields | `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| MEC-AL-003 | `CAP-AL-003` | resolve | active in the standard adapter path; adapter always passes an `EqcLookupConfig`, using a disabled config when no explicit EQC settings are provided | `CompanyIdResolutionStep.apply()` | `src/work_data_hub/domain/annual_loss/pipeline_builder.py`, `src/work_data_hub/infrastructure/enrichment/` | `mixed` | resolver strategy in `pipeline_builder.py`, enrichment modules and override configs | writes `company_id`; may use source company_id, DB cache, or temp ID | wrong priority order or misleading docs about step activation | `tests/slice_tests/test_j_real_effect_guards.py`, `tests/unit/domain/test_event_domain_adapters.py` |
| MEC-AL-004 | `CAP-AL-003` | transform | active when a DB connection is provided; adapter opens `repo_connection` and passes it when possible | `PlanCodeEnrichmentStep.apply()` | `src/work_data_hub/domain/annual_loss/pipeline_builder.py`, `customer."客户年金计划"` lookup query | `code + sql` | `_build_plan_code_mapping()`, `_select_plan_code()` | reads customer-plan history; fills empty `年金计划号` | enrichment warning log, wrong P/S prefix selection, silent fallback to defaults | `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_j_real_effect_guards.py`, `docs/verification_guide_real_data.md` |
| MEC-AL-005 | `CAP-AL-003` | transform | always | `_apply_plan_code_defaults_for_annual_loss` in pipeline | `src/work_data_hub/domain/annual_loss/pipeline_builder.py` | `code` | annual-loss fallback default step | fills unmatched empty `年金计划号` with `AN001`/`AN002` | remaining empty plan codes after transform | `tests/slice_tests/test_h_end_to_end_flows.py` |
| MEC-AL-006 | `CAP-AL-004` | backfill | always when domain backfill is enabled | `generic_backfill_refs_op` -> `GenericBackfillService.derive_candidates()` | `src/work_data_hub/orchestration/ops/generic_backfill.py`, `src/work_data_hub/domain/reference_backfill/generic_service.py` | `config + code` | `config/foreign_keys.yml` | inserts/updates customer detail attributes, tags, and customer type | bad aggregation outputs or missing customer master rows | `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| MEC-AL-007 | `CAP-AL-005` | load | always | `load_op` | `src/work_data_hub/orchestration/ops/loading.py` | `config + code` | `config/data_sources.yml` | delete-insert writes to `customer."流失客户明细"` | SQL plan mismatch / duplicate or missing event rows | `tests/slice_tests/test_f_load_upsert.py`, `tests/slice_tests/test_j_real_effect_guards.py` |
| MEC-AL-008 | `CAP-AL-005` | downstream consumption | active only when `annuity_performance` hook chain later refreshes snapshots | `StatusEvaluator.generate_sql_fragment()` and snapshot refresh SQL | `src/work_data_hub/customer_mdm/status_evaluator.py`, `src/work_data_hub/customer_mdm/snapshot_refresh.py` | `config + sql + code` | `config/customer_status_rules.yml` | loss facts influence `is_loss_reported`; churn semantics are evaluated from `规模明细` in the same snapshot refresh path | wrong reported-loss/churn statuses despite correct facts | `tests/integration/customer_mdm/test_status_evaluation.py`, `docs/verification_guide_real_data.md` |

### 3.2 Stage Contract Summary

| Stage | Expected Input Contract | Expected Output Contract | Mutable Fields | Notes |
|-------|-------------------------|--------------------------|----------------|-------|
| discover/read | domain + period + multi-sheet config | merged raw loss rows from both configured sheets | none | `sheet_name` is fallback; `sheet_names` is the real multi-sheet contract |
| transform | raw loss rows | canonical event rows with `业务类型`, `产品线代码`, `计划类型`, parsed dates, `客户名称`, optional `company_id` | high | adapter creates and runs the pipeline directly |
| company_id resolve | transformed rows with name/plan/source-id columns | rows with `company_id` preserved or resolved | medium-high | source `company_id` from input is part of the priority chain |
| plan code enrichment | rows with missing `年金计划号` and `company_id + 产品线代码` | rows with inferred `年金计划号` where lookup succeeds | high | prefers `P` prefix for `集合计划`, `S` for `单一计划` |
| fallback plan defaults | rows still missing `年金计划号` | rows with `AN001`/`AN002` fallback defaults | medium | runs after DB lookup as final fallback |
| backfill | normalized event rows + FK config | customer master candidate records | medium | only `fk_customer` is configured for this domain |
| load | gated normalized event rows + output config | SQL plan or fact write to customer schema | none | PK is `上报月份`, `业务类型` |
| downstream snapshot use | loaded `流失客户明细` rows + snapshot year | status SQL fragments and snapshot rows | none in loss domain | annual_loss does not run hooks itself; it supplies data to later hooks |

### 3.3 Rule Ownership Summary

| Rule Category | Owned By | Typical Location | Change Risk | Review Requirement |
|---------------|----------|------------------|-------------|--------------------|
| Multi-sheet input contract | domain config + file-processing layer | `config/data_sources.yml`, `orchestration/ops/file_processing.py` | medium | domain + IO review |
| Event-row normalization | annual loss domain pipeline | `domain/annual_loss/pipeline_builder.py` | medium-high | domain review |
| Company ID resolution | infrastructure enrichment + domain strategy wiring | `infrastructure/enrichment/`, `domain/annual_loss/pipeline_builder.py` | high | enrichment + domain review |
| Plan-code inference | annual loss domain pipeline + customer contract table | `domain/annual_loss/pipeline_builder.py` | high | domain + customer MDM review |
| Customer backfill aggregation | reference backfill layer | `config/foreign_keys.yml`, `domain/reference_backfill/generic_service.py` | high | data-contract review |
| Downstream churn status | customer MDM status rules | `config/customer_status_rules.yml`, `customer_mdm/status_evaluator.py` | high | MDM review |

### 3.4 Execution Ordering And Gates

| Before | After | Why The Order Matters | Evidence |
|--------|-------|-----------------------|----------|
| `MEC-AL-001` | `MEC-AL-002` | transform logic assumes trustee/investee rows are already merged into one input frame | `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| `MEC-AL-003` | `MEC-AL-004` | plan-code enrichment needs the final `company_id` used as part of the lookup key | `_complete_pipeline()` |
| `MEC-AL-004` | `MEC-AL-005` | fallback defaults must only run after DB-based enrichment has had a chance to fill empty values | `_complete_pipeline()`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| `MEC-AL-006` | `MEC-AL-007` | orchestration contract gates event fact load behind backfill completion | `tests/slice_tests/test_j_real_effect_guards.py` |
| `MEC-AL-007` | `MEC-AL-008` | snapshot status evaluation can only see loss signals after event facts are loaded | `config/customer_status_rules.yml`, `docs/verification_guide_real_data.md` |

---

## 4. Key Field Trace Table

### 4.1 Field Trace Inventory

| Field ID | Capability ID | Output Field | Business Meaning | Raw Source | Stage Chain | Named Rules Applied | Rule Location | Final Sink | Verification Anchor |
|----------|---------------|--------------|------------------|------------|-------------|---------------------|---------------|------------|---------------------|
| FLD-AL-001 | `CAP-AL-002` | `上报月份` | reporting-period date used for PK, yearly churn checks, and downstream event time filters | raw workbook `上报月份` | read -> parse -> load -> downstream status query | `parse_chinese_date()` | `src/work_data_hub/domain/annual_loss/pipeline_builder.py` | `customer."流失客户明细"."上报月份"` | `tests/slice_tests/test_h_end_to_end_flows.py`, `tests/integration/customer_mdm/test_status_evaluation.py` |
| FLD-AL-002 | `CAP-AL-002` | `流失日期` | normalized loss-event date retained in the event fact table | raw workbook `流失日期` | read -> parse -> load | `parse_chinese_date()` | `src/work_data_hub/domain/annual_loss/pipeline_builder.py` | `customer."流失客户明细"."流失日期"` | `tests/slice_tests/test_d_annual_loss_pipeline.py` |
| FLD-AL-003 | `CAP-AL-003` | `年金计划号` | normalized or inferred plan identifier for the loss event | raw workbook `年金计划号`, `计划类型`, `company_id`, `产品线代码` | read -> normalize -> optional DB lookup -> fallback default -> load/backfill | `PlanCodeEnrichmentStep`, `_select_plan_code()`, `_apply_plan_code_defaults_for_annual_loss()` | `src/work_data_hub/domain/annual_loss/pipeline_builder.py` | `customer."流失客户明细"."年金计划号"` and customer backfill fields | `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_j_real_effect_guards.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| FLD-AL-004 | `CAP-AL-003` | `company_id` | enterprise identity for event rows and downstream customer/snapshot joins | source `company_id`, `年金计划号`, `客户名称` | read -> normalize -> resolver priority chain -> load/backfill | source company_id passthrough, YAML override, DB cache, temp ID fallback | `src/work_data_hub/domain/annual_loss/pipeline_builder.py`, `src/work_data_hub/infrastructure/enrichment/` | `customer."流失客户明细".company_id` and downstream joins | `tests/slice_tests/test_j_real_effect_guards.py`, `docs/verification_guide_real_data.md` |
| FLD-AL-005 | `CAP-AL-004` | `customer."客户明细".tags` | customer-level tag trail showing this customer had a loss event in the reporting period | loaded/normalized `上报月份` per company | transform -> backfill candidate aggregation -> customer detail write | `jsonb_append` with `%y%m + 流失` | `config/foreign_keys.yml`, `domain/reference_backfill/generic_service.py` | `customer."客户明细".tags` | `tests/slice_tests/test_h_end_to_end_flows.py`, `docs/verification_guide_real_data.md` |
| FLD-AL-006 | `CAP-AL-004` | `customer."客户明细"."年金客户类型"` | customer master classification contributed by loss facts | grouped loss facts per company | transform -> backfill candidate aggregation -> customer detail write | `template: 流失客户` | `config/foreign_keys.yml` | `customer."客户明细"."年金客户类型"` | `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py` |
| FLD-AL-007 | `CAP-AL-005` | `customer."客户业务月度快照".is_loss_reported` | downstream indicator that a customer had a loss report in the snapshot year | loaded loss facts in `customer."流失客户明细"` | load -> later annuity_performance snapshot refresh -> status SQL | `exists_in_year` against annual_loss source | `config/customer_status_rules.yml`, `customer_mdm/status_evaluator.py`, `snapshot_refresh.py` | `customer."客户业务月度快照".is_loss_reported` | `tests/integration/customer_mdm/test_status_evaluation.py`, `tests/integration/customer_mdm/test_e2e_pipeline.py` |

### 4.2 Step-By-Step Trace Details

#### `FLD-AL-003` `年金计划号`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | raw `年金计划号` plus `计划类型` | keep existing non-empty values unchanged | preserve source plan code | existing plan codes such as `P9101` remain | `tests/slice_tests/test_h_end_to_end_flows.py` |
| 2 | empty `年金计划号` + `company_id + 产品线代码` | query `customer."客户年金计划"` and collect available plan codes | `PlanCodeEnrichmentStep._build_plan_code_mapping()` | candidate code list | `tests/slice_tests/test_j_real_effect_guards.py` |
| 3 | candidate code list + `计划类型` | select preferred prefix | `_select_plan_code()` (`集合计划 -> P`, `单一计划 -> S`) | inferred `年金计划号` | `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_j_real_effect_guards.py` |
| 4 | still-empty `年金计划号` | apply domain fallback defaults | `_apply_plan_code_defaults_for_annual_loss()` | `AN001` / `AN002` | `tests/slice_tests/test_h_end_to_end_flows.py` |

#### `FLD-AL-007` `customer."客户业务月度快照".is_loss_reported`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | loaded loss fact rows with `company_id`, `产品线代码`, `上报月份` | persist loss events to `customer."流失客户明细"` | event fact publication | queryable loss facts | `tests/slice_tests/test_f_load_upsert.py`, `docs/verification_guide_real_data.md` |
| 2 | snapshot refresh request with `snapshot_year` | generate status SQL fragment referencing annual loss source | `exists_in_year` for `is_loss_reported` | SQL EXISTS fragment | `tests/integration/customer_mdm/test_status_evaluation.py` |
| 3 | loss facts + current customer contracts | write reported-loss result into ProductLine snapshot rows | config-driven status evaluation | `customer."客户业务月度快照".is_loss_reported = true/false` | `tests/integration/customer_mdm/test_e2e_pipeline.py`, `docs/verification_guide_real_data.md` |

### 4.3 Ambiguities And Unknowns

No verified unresolved field-trace ambiguities remain in this slice after the
current contract fixes for current-contract lookup, churn semantics, and
reported-loss field surfacing.

---

## 5. Test And Validation Coverage

### 5.1 Protection Matrix

| Capability ID | Mechanism ID | Validation Type | File / Command | What It Proves | Gaps |
|---------------|--------------|-----------------|----------------|----------------|------|
| `CAP-AL-001` | `MEC-AL-001` | slice | `tests/slice_tests/test_a_file_discovery.py`, `tests/slice_tests/test_h_end_to_end_flows.py` | multi-sheet config and merged read contract | does not exercise every real workbook naming variation |
| `CAP-AL-002` | `MEC-AL-002` | slice | `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_h_end_to_end_flows.py` | mapping, date parsing, cleansing, direct pipeline behavior | parity against legacy is less direct than for `annuity_performance` |
| `CAP-AL-003` | `MEC-AL-003`, `MEC-AL-004`, `MEC-AL-005` | slice | `tests/slice_tests/test_d_annual_loss_pipeline.py`, `tests/slice_tests/test_j_real_effect_guards.py`, `tests/slice_tests/test_h_end_to_end_flows.py` | resolver priority, plan-code lookup selection, fallback defaults | no explicit current-vs-historical contract-row test for plan-code lookup |
| `CAP-AL-004` | `MEC-AL-006` | slice | `tests/slice_tests/test_e_backfill_per_domain.py`, `tests/slice_tests/test_h_end_to_end_flows.py` | fk_customer config shape, tags, template value, aggregated customer outputs | no full DB write verification for customer detail in this doc path |
| `CAP-AL-005` | `MEC-AL-007`, `MEC-AL-008` | slice + integration + SQL runbook | `tests/slice_tests/test_f_load_upsert.py`, `tests/slice_tests/test_g_snapshot_status.py`, `tests/integration/customer_mdm/test_status_evaluation.py`, `docs/verification_guide_real_data.md` | event-fact load contract and downstream churn-status SQL references | no single end-to-end test from annual_loss ETL run to both product-line and plan snapshot rows |

### 5.2 Real-Data Or Snapshot Anchors

| Artifact | Location | Coverage | Refresh Policy |
|----------|----------|----------|----------------|
| real-data verification guide | `docs/verification_guide_real_data.md` | operational checks for merged read, plan-code enrichment logs, customer tags, and downstream churn status use | refresh when event load, backfill, or status rules change |
| annual loss slice fixture | `tests/fixtures/.../annual_loss/slice_流失台账.xlsx` via `tests/slice_tests/conftest.py` | representative event-domain transformation and backfill behaviors | refresh when protected event-field scenarios change |
| customer MDM integration fixtures | `tests/integration/customer_mdm/conftest.py` | downstream status evaluation behavior using loss facts | refresh when snapshot/status semantics change |

---

## 6. Refactoring Risk Assessment

### 6.1 High-Risk Areas

| Area | Why Risky | Impact If Broken | Required Safeguard |
|------|-----------|------------------|--------------------|
| multi-sheet merge contract | trustee and investee event rows share one ETL path | silent sheet loss or duplicated rows | preserve file-discovery and merged-read slice tests |
| plan-code enrichment | event domain depends on customer contract history rather than only source fields | wrong `年金计划号` values lead to broken customer/plan joins | add current-vs-historical lookup tests and keep prefix-selection tests |
| conditional mechanism understanding | code comments describe optional mechanisms but runtime path may always activate them | maintainers make wrong refactor assumptions | document activation conditions and add adapter-level tests |
| customer backfill tags and type | loss facts update customer master with derived labels | customer detail no longer shows loss history | preserve backfill aggregation tests and real-data SQL checks |
| downstream churn status dependency | annual loss facts feed snapshot status evaluation indirectly | snapshots show false negatives or wrong churn plan-level rows | keep status-evaluator integration tests and operator SQL checks |

### 6.2 Safe Refactoring Boundaries

- Safe to change:
  - internal decomposition of annual loss transform helpers
  - logging and helper naming
- Change with contract checks:
  - multi-sheet read wiring
  - `company_id` resolution strategy wiring
  - plan-code enrichment query and selection logic
  - customer backfill aggregation details
- Do not change without explicit migration design:
  - meaning of `年金计划号` fallback defaults
  - fact-table PK semantics
  - downstream interpretation of loss facts for churn statuses

---

## 7. Open Questions

No active open questions remain for this slice after the current contract fixes.

---

## 8. Completion Checklist

- [x] Capability inventory is complete for the chosen scope.
- [x] Every capability points to at least one source-of-truth file.
- [x] Every critical mechanism names its rule source type.
- [x] Conditional mechanisms state when they are active.
- [x] Every critical field has a trace row.
- [x] Every critical field points to a validation anchor.
- [x] Unknowns are listed explicitly instead of implied away.
- [x] Config/comment/implementation drift discovered during mapping is recorded explicitly.

---

## 9. Minimal Example Guidance

This document is the third practical fill of the mapping template. It confirms
that the same template can describe the sibling event domain without requiring
additional structure changes.
