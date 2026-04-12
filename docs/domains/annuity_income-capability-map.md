# annuity_income Capability, Mechanism, And Field Trace Map

## Purpose

This document applies the system capability/mechanism/field-trace template to
the active `annuity_income` domain. It focuses on the shared annuity workbook
read path, income-specific normalization, service-delegation execution model,
customer master backfill, and explainability gaps around `company_id`
generation and unknown-name export.

---

## 1. Document Metadata

| Item | Value |
|------|-------|
| Scope | `domain` |
| Target Name | `annuity_income` |
| Author | `Codex` |
| Reviewers | `{pending}` |
| Last Verified Date | `2026-04-11` |
| Repository Version / Commit | `main@e93afbe (working tree)` |
| Confidence Level | `medium-high` |

### 1.1 Scope Boundary

- Included:
  - single-sheet file discovery and sheet loading
  - Bronze-to-Silver transformation for income rows
  - `company_id` resolution and unknown-name export path
  - reference and customer master backfill driven by income facts
  - fact load to `business."收入明细"`
  - service-delegation execution path used by the adapter
- Excluded:
  - `annuity_performance` post-ETL hooks
  - event-domain (`annual_award`, `annual_loss`) ETL internals
  - GUI or manual enrichment tooling outside the ETL path

### 1.2 Documentation Rules

- Source of truth is verified repository behavior as of `2026-04-11`.
- When migration-era docs disagree with runtime code, the mismatch is recorded
  explicitly instead of silently normalized.
- This map documents current active behavior, not historical migration intent.

---

## 2. System Capability Map

### 2.1 Capability Inventory

| Capability ID | Capability Name | Business Purpose | Trigger | Primary Inputs | Primary Outputs | Affected Objects | Source Of Truth |
|---------------|-----------------|------------------|---------|----------------|-----------------|------------------|-----------------|
| CAP-AI-001 | Income workbook discovery and sheet loading | Find the current annuity workbook and extract the `收入明细` worksheet for the requested period | ETL CLI / Dagster generic job | `--period`, `config/data_sources.yml`, monthly annuity workbook | in-memory row dictionaries | discovery logs, selected workbook, extracted rows | `config/data_sources.yml`, `discover_files_op`, `read_data_op`, `tests/integration/io/test_file_discovery_integration.py` |
| CAP-AI-002 | Normalize and validate annuity income fact rows | Convert raw `收入明细` rows into canonical fact rows with normalized plan code, branch code, portfolio code, product line, fee defaults, and cleansed names | `process_with_enrichment()` / `process_domain_op_v2` | raw income rows, shared transforms, domain cleansing rules | normalized fact rows | transformed DataFrame / validated models | `src/work_data_hub/domain/annuity_income/pipeline_builder.py`, `src/work_data_hub/domain/annuity_income/service.py`, `tests/unit/domain/annuity_income/test_pipeline.py` |
| CAP-AI-003 | Resolve enterprise identity and export unresolved names | Derive `company_id` for income rows and emit unknown-name artifacts for manual review when enabled | service execution | normalized rows, enrichment resolver inputs, enrichment cache, optional EQC budget | rows with `company_id`, enrichment stats, optional `unknown_names_csv` | transformed rows, exported CSV path, logs | `src/work_data_hub/domain/annuity_income/service.py`, `src/work_data_hub/domain/annuity_income/pipeline_builder.py`, `tests/unit/domain/annuity_income/test_income_failed_records_export.py` |
| CAP-AI-004 | Backfill reference and customer master tables from income facts | Derive missing plan/portfolio/product-line/organization/customer reference rows before loading income facts | `generic_backfill_refs_op` | normalized income rows, `config/foreign_keys.yml` | insert-missing candidate records and backfill summary | `mapping."年金计划"`, `mapping."组合计划"`, `mapping."产品线"`, `mapping."组织架构"`, `customer."客户明细"` | `config/foreign_keys.yml`, `src/work_data_hub/domain/reference_backfill/generic_service.py`, `docs/reference/data_processing_guide.md` |
| CAP-AI-005 | Publish normalized income facts | Persist normalized income rows to the business schema with idempotent refresh semantics | `load_op` / service execute path | gated normalized income rows | refreshed income fact rows | `business."收入明细"` | `config/data_sources.yml`, `src/work_data_hub/orchestration/ops/loading.py`, `tests/integration/test_cli_execute_validation.py` |

### 2.2 Capability Notes

- `annuity_income` uses the service-delegation pattern rather than direct adapter
  orchestration.
- The domain produces an additional operator-facing artifact,
  `unknown_names_csv`, that is not part of the fact table itself.
- `annuity_income` does not have post-ETL hooks in the current registry.

### 2.3 Capability Dependency Map

| Capability ID | Depends On | Dependency Type | Why It Matters | Evidence |
|---------------|------------|-----------------|----------------|----------|
| `CAP-AI-002` | `CAP-AI-001` | upstream | transformation requires a discovered workbook and the `收入明细` sheet | `docs/domains/annuity_income.md`, `tests/integration/io/test_file_discovery_integration.py` |
| `CAP-AI-003` | `CAP-AI-002` | upstream | identity resolution uses normalized plan/customer/account fields, not raw Excel columns | `build_bronze_to_silver_pipeline()`, `process_with_enrichment()` |
| `CAP-AI-004` | `CAP-AI-003` | upstream | customer/reference backfill relies on final canonical fields including `company_id` and fee amounts | `config/foreign_keys.yml`, `docs/reference/data_processing_guide.md` |
| `CAP-AI-005` | `CAP-AI-004` | order/gate | the unified ETL chain gates fact load behind backfill completion | `docs/reference/data_processing_guide.md` |
| `CAP-AI-005` | hook registry | downstream absence | current hook registry executes no Customer MDM hooks for `annuity_income`, which is part of the domain contract | `src/work_data_hub/cli/etl/hooks.py`, `tests/integration/customer_mdm/test_hook_chain.py` |

---

## 3. Implementation Mechanism Map

### 3.1 Mechanism Inventory

| Mechanism ID | Capability ID | Stage | Activation Condition | Entry Point | Core Modules | Rule Source Type | Rule Source Location(s) | Side Effects | Failure Signal | Verification Anchor |
|--------------|---------------|-------|----------------------|-------------|--------------|------------------|-------------------------|--------------|----------------|---------------------|
| MEC-AI-001 | `CAP-AI-001` | discover/read | always | `discover_files_op`, `read_data_op` | `src/work_data_hub/orchestration/ops/file_processing.py`, `src/work_data_hub/io/readers/excel_reader.py` | `config + code` | `config/data_sources.yml` | file selection and row extraction from `收入明细` | discovery/read error, wrong sheet selection | `tests/integration/io/test_file_discovery_integration.py`, `docs/domains/annuity_income.md` |
| MEC-AI-002 | `CAP-AI-002` | transform | always | `process_with_enrichment()` -> `build_bronze_to_silver_pipeline()` | `src/work_data_hub/domain/annuity_income/service.py`, `src/work_data_hub/domain/annuity_income/pipeline_builder.py` | `mixed` | pipeline step definitions, cleansing rules, shared mappings/helpers | field mutation, fee defaulting, legacy-column drop | bad normalized fields, model/schema validation failure | `tests/unit/domain/annuity_income/test_pipeline.py`, `tests/unit/domain/annuity_income/test_schemas.py` |
| MEC-AI-003 | `CAP-AI-003` | resolve | always in the service path; `build_bronze_to_silver_pipeline()` requires `eqc_config` | `CompanyIdResolutionStep.apply()` | `src/work_data_hub/domain/annuity_income/pipeline_builder.py`, `src/work_data_hub/infrastructure/enrichment/` | `mixed` | resolver strategy in `pipeline_builder.py`, enrichment modules and override configs | writes `company_id`; may create temp IDs depending on strategy | wrong priority order, unexpected empty/temp IDs | `tests/unit/domain/annuity_income/test_pipeline.py`, `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` |
| MEC-AI-004 | `CAP-AI-003` | service side effect | active when `export_unknown_names=True` or failed-record export conditions are met | `process_with_enrichment()` | `src/work_data_hub/domain/annuity_income/service.py`, failure export utilities | `code` | unknown-name export and failed-record export in `service.py` | writes CSV artifacts and logs | missing CSV when expected, silent drop behavior | `tests/unit/domain/annuity_income/test_income_failed_records_export.py` |
| MEC-AI-005 | `CAP-AI-004` | backfill | always when domain backfill is enabled | `generic_backfill_refs_op` -> `GenericBackfillService.derive_candidates()` | `src/work_data_hub/orchestration/ops/generic_backfill.py`, `src/work_data_hub/domain/reference_backfill/generic_service.py` | `config + code` | `config/foreign_keys.yml` | inserts/updates plan, portfolio, product line, organization, and customer detail candidates | bad aggregation outputs or missing reference rows | `docs/reference/data_processing_guide.md`, `config/foreign_keys.yml` |
| MEC-AI-006 | `CAP-AI-005` | load | always | `load_op` / warehouse loader path | `src/work_data_hub/orchestration/ops/loading.py`, `src/work_data_hub/domain/annuity_income/service.py` | `config + code` | `config/data_sources.yml`, output config | delete-insert fact write to `business."收入明细"` | SQL plan mismatch / table write failure | `tests/integration/test_cli_execute_validation.py`, `tests/integration/test_multi_domain_pipeline.py` |
| MEC-AI-007 | `CAP-AI-005` | downstream absence | always absent in current registry | `run_post_etl_hooks()` | `src/work_data_hub/cli/etl/hooks.py` | `hook registry` | hook registry lookup | no Customer MDM post-hook side effects for this domain | unexpected hook execution would be a regression | `tests/integration/customer_mdm/test_hook_chain.py` |

### 3.2 Stage Contract Summary

| Stage | Expected Input Contract | Expected Output Contract | Mutable Fields | Notes |
|-------|-------------------------|--------------------------|----------------|-------|
| discover/read | domain + period + `收入明细` sheet config | raw income row dictionaries | none | same workbook family as `annuity_performance`, different sheet |
| transform | raw income rows | canonical income rows with normalized `计划代码`, `机构代码`, `组合代码`, `产品线代码`, fee fields, and `公司_id` target column | high | income-specific defaults fill missing names and fee columns |
| company_id resolve | transformed rows with plan/customer/account fields | rows with resolved or generated `company_id` | medium-high | strategy uses `计划代码` and `年金账户名`; no source company-id passthrough column |
| artifact export | transformed rows, validation outcome, export flags | `unknown_names_csv` and/or failed-record CSV | none in fact rows | operator-facing side effect, not fact schema |
| backfill | normalized income rows + FK config | candidate reference/master rows | medium | `fk_customer` uses `固费` as `max_by` weight and template value `新客*` |
| load | gated normalized income rows + output config | fact write to `business."收入明细"` | none | delete scope is `月度`, `业务类型`, `计划类型` |
| post-hook | loaded income fact rows | no registered domain-specific post-hook behavior | none | absence is part of current contract |

### 3.3 Rule Ownership Summary

| Rule Category | Owned By | Typical Location | Change Risk | Review Requirement |
|---------------|----------|------------------|-------------|--------------------|
| Income-row normalization | annuity income domain pipeline | `domain/annuity_income/pipeline_builder.py` | medium-high | domain review |
| Company ID resolution | infrastructure enrichment + income service/pipeline wiring | `infrastructure/enrichment/`, `domain/annuity_income/pipeline_builder.py`, `domain/annuity_income/service.py` | high | enrichment + domain review |
| Unknown-name export behavior | annuity income service | `domain/annuity_income/service.py` | medium | domain review |
| Reference/customer backfill | reference backfill layer | `config/foreign_keys.yml`, `domain/reference_backfill/generic_service.py` | high | data-contract review |
| Hook behavior absence | ETL hook registry | `cli/etl/hooks.py` | low-medium | orchestration review |

### 3.4 Execution Ordering And Gates

| Before | After | Why The Order Matters | Evidence |
|--------|-------|-----------------------|----------|
| `MEC-AI-001` | `MEC-AI-002` | pipeline assumes the `收入明细` sheet has already been selected and loaded | `docs/domains/annuity_income.md` |
| `MEC-AI-002` | `MEC-AI-003` | resolver depends on normalized plan/customer/account fields and preserved `年金账户名` | `build_bronze_to_silver_pipeline()` |
| `MEC-AI-003` | `MEC-AI-004` | unknown-name export depends on post-resolution outcomes, including unresolved names/temp IDs | `process_with_enrichment()` |
| `MEC-AI-005` | `MEC-AI-006` | unified ETL contract gates fact load behind backfill completion | `docs/reference/data_processing_guide.md` |
| `MEC-AI-006` | `MEC-AI-007` | no hooks should run for this domain after load | `tests/integration/customer_mdm/test_hook_chain.py` |

---

## 4. Key Field Trace Table

### 4.1 Field Trace Inventory

| Field ID | Capability ID | Output Field | Business Meaning | Raw Source | Stage Chain | Named Rules Applied | Rule Location | Final Sink | Verification Anchor |
|----------|---------------|--------------|------------------|------------|-------------|---------------------|---------------|------------|---------------------|
| FLD-AI-001 | `CAP-AI-002` | `计划代码` | canonical plan identifier for income facts and backfill joins | raw workbook `计划号/计划代码`, plus `计划类型` when blank | read -> uppercase -> correction -> default -> load/backfill | uppercase normalization, `PLAN_CODE_CORRECTIONS`, `apply_plan_code_defaults()` | `src/work_data_hub/domain/annuity_income/pipeline_builder.py` | `business."收入明细"."计划代码"` and reference backfill keys | `tests/unit/domain/annuity_income/test_pipeline.py` |
| FLD-AI-002 | `CAP-AI-002` | `客户名称` | canonical customer name used in enrichment and customer backfill | raw `客户名称` and `计划名称` | read -> fill-from-plan-name -> cleanse -> resolve/backfill | `_fill_customer_name_from_plan_name()`, cleansing rules | `src/work_data_hub/domain/annuity_income/pipeline_builder.py`, `src/work_data_hub/infrastructure/cleansing/settings/cleansing_rules.yml` | `business."收入明细"."客户名称"` and downstream enrichment/backfill inputs | `tests/unit/domain/annuity_income/test_pipeline.py`, `docs/business-background/年金计划类型与客户名称业务背景.md` |
| FLD-AI-003 | `CAP-AI-003` | `company_id` | enterprise identity for income facts and customer master derivation | `计划代码`, `客户名称`, `年金账户名` | read -> normalize -> resolver chain -> load/backfill | plan override / DB cache / EQC / temp ID depending on strategy | `src/work_data_hub/domain/annuity_income/pipeline_builder.py`, `src/work_data_hub/infrastructure/enrichment/` | `business."收入明细".company_id` and reference/customer backfill | `tests/unit/infrastructure/enrichment/test_company_id_resolver.py`, `docs/guides/infrastructure/company-enrichment-service.md` |
| FLD-AI-004 | `CAP-AI-002` | `固费` | fixed-fee amount used in fact analytics and customer-master aggregation weight | raw workbook `固费` | read -> null-to-zero normalization -> load/backfill | fillna to `0` | `src/work_data_hub/domain/annuity_income/pipeline_builder.py` | `business."收入明细"."固费"` and `fk_customer.max_by(order_column="固费")` | `tests/unit/domain/annuity_income/test_pipeline.py`, `config/foreign_keys.yml` |
| FLD-AI-005 | `CAP-AI-004` | `customer."客户明细".tags` | customer-level tag trail derived from income facts | normalized `月度` per company | transform -> backfill candidate aggregation -> customer detail write | `jsonb_append` with `%y%m + 新建` | `config/foreign_keys.yml`, `domain/reference_backfill/generic_service.py` | `customer."客户明细".tags` | `config/foreign_keys.yml`, `docs/verification_guide_real_data.md` |
| FLD-AI-006 | `CAP-AI-004` | `customer."客户明细"."年金客户类型"` | customer master classification contributed by income facts | grouped income facts per company | transform -> backfill candidate aggregation -> customer detail write | `template: 新客*` | `config/foreign_keys.yml` | `customer."客户明细"."年金客户类型"` | `config/foreign_keys.yml`, `docs/verification_guide_real_data.md` |
| FLD-AI-007 | `CAP-AI-003` | `unknown_names_csv` | operator-facing export of unresolved names for manual review | unresolved names after model conversion | resolve -> model conversion -> export | `export_unknown_names_csv()` | `src/work_data_hub/domain/annuity_income/service.py` | filesystem CSV path returned in processing result | `tests/unit/domain/annuity_income/test_income_failed_records_export.py` |

### 4.2 Step-By-Step Trace Details

#### `FLD-AI-003` `company_id`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | normalized `计划代码`, `客户名称`, preserved `年金账户名` | build resolver strategy for income domain | `CompanyIdResolutionStep.apply()` | priority inputs prepared | `pipeline_builder.py` |
| 2 | resolver inputs | apply resolver chain | plan override / DB cache / EQC / temp ID | resolved `company_id` string | `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` |
| 3 | unresolved outcomes | export unknown names when enabled | `export_unknown_names_csv()` | CSV path or `None` | `tests/unit/domain/annuity_income/test_income_failed_records_export.py` |

#### `FLD-AI-004` `固费`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | raw `固费` value, possibly null | normalize missing values to zero | income fee defaulting | numeric `0` or original fee | `tests/unit/domain/annuity_income/test_pipeline.py` |
| 2 | normalized `固费` values grouped by `company_id` | select customer backfill branch/plan using highest fixed fee | `max_by(order_column="固费")` | customer master candidate values | `config/foreign_keys.yml` |
| 3 | grouped rows | count/distinct/template/jsonb aggregation for customer master | `count_distinct`, `concat_distinct`, `template`, `jsonb_append` | customer detail rows and tags | `config/foreign_keys.yml`, `docs/verification_guide_real_data.md` |

### 4.3 Ambiguities And Unknowns

No verified unresolved field-trace ambiguities remain in this slice after the
current contract fixes for temp-ID generation and unknown-name CSV output.

---

## 5. Test And Validation Coverage

### 5.1 Protection Matrix

| Capability ID | Mechanism ID | Validation Type | File / Command | What It Proves | Gaps |
|---------------|--------------|-----------------|----------------|----------------|------|
| `CAP-AI-001` | `MEC-AI-001` | integration | `tests/integration/io/test_file_discovery_integration.py` | `收入明细` sheet discovery and loading | less direct slice coverage than other domains |
| `CAP-AI-002` | `MEC-AI-002` | unit + integration | `tests/unit/domain/annuity_income/test_pipeline.py`, `tests/unit/domain/annuity_income/test_schemas.py`, `tests/integration/test_multi_domain_pipeline.py` | normalization steps, schemas, shared infrastructure behavior | no dedicated domain capability-map test yet |
| `CAP-AI-003` | `MEC-AI-003`, `MEC-AI-004` | unit | `tests/unit/domain/annuity_income/test_income_failed_records_export.py`, `tests/unit/infrastructure/enrichment/test_company_id_resolver.py` | temp-ID/unknown-name related behavior and export side effects | active runtime path vs stale docs still needs explicit guard |
| `CAP-AI-004` | `MEC-AI-005` | config + docs reference | `config/foreign_keys.yml`, `docs/reference/data_processing_guide.md` | configured backfill surface and aggregation intent | fewer direct income-specific derivation tests than for event domains |
| `CAP-AI-005` | `MEC-AI-006`, `MEC-AI-007` | integration | `tests/integration/test_cli_execute_validation.py`, `tests/integration/test_multi_domain_pipeline.py`, `tests/integration/customer_mdm/test_hook_chain.py` | `收入明细` table exists/writes and no hooks run for this domain | no single dedicated E2E contract focused only on income load + no-hook outcome |

### 5.2 Real-Data Or Snapshot Anchors

| Artifact | Location | Coverage | Refresh Policy |
|----------|----------|----------|----------------|
| annuity income cleansing/rule reference | `docs/cleansing-rules/annuity-income.md` | migration-era rule inventory and parity notes | refresh or deprecate stale sections when active behavior is clarified |
| parity validation guide | `docs/guides/validation/legacy-parity-validation.md` | annuity income parity workflow and assumptions | refresh when active parity scripts or assumptions change |
| multi-domain integration baseline | `tests/integration/test_multi_domain_pipeline.py`, `tests/fixtures/performance_baseline.json` | shared infrastructure behavior and performance baseline for income + performance | refresh when service contract or output schema changes |

---

## 6. Refactoring Risk Assessment

### 6.1 High-Risk Areas

| Area | Why Risky | Impact If Broken | Required Safeguard |
|------|-----------|------------------|--------------------|
| customer-name fill from plan name | income domain can derive customer identity from plan metadata rather than only explicit customer fields | weaker `company_id` resolution and wrong customer backfill | preserve unit tests around name fill and update docs with field trace |
| `company_id` behavior drift | docs and code appear to disagree on unresolved-ID behavior | maintainers may refactor toward the wrong target contract | add explicit temp-ID contract tests and align stale docs |
| customer backfill weighted by `固费` | income facts influence customer master using a different weight column than other domains | customer master “main branch / key plan” can drift unexpectedly | add domain-specific derivation tests if this area is changed |
| diagnostic artifact behavior | `unknown_names_csv` and failed-record exports are easy to drop during refactors because they are side effects, not schema fields | operators lose observability into unresolved names | keep artifact-export tests and make the contract explicit |
| no-hook contract | if a future refactor accidentally enables hooks for income, downstream behavior changes materially | surprise customer MDM side effects after income ETL | preserve no-hook integration check |

### 6.2 Safe Refactoring Boundaries

- Safe to change:
  - internal helper decomposition
  - logging detail and performance instrumentation
- Change with contract checks:
  - income-specific defaulting rules
  - `company_id` strategy wiring
  - unknown-name export behavior
  - customer backfill aggregation details
- Do not change without explicit migration design:
  - unresolved `company_id` behavior
  - customer-master derivation semantics using `固费`
  - absence or presence of post-ETL hooks

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

This document is the fourth practical fill of the mapping template. It shows
that the template can also describe a service-delegation fact domain with
operator-facing diagnostic artifacts, not only direct-pipeline or hook-driven
domains.
