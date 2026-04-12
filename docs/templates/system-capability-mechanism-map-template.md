# System Capability, Mechanism, And Field Trace Template

## Purpose

Use this template to document:

1. what a system or domain capability does
2. how it is implemented in the repository
3. how critical output fields are derived

This template is intended for brownfield understanding, refactoring design, and
agent-friendly maintenance.

## When To Use

- before major refactoring
- when onboarding a new domain
- when documenting a black-box workflow
- when an agent needs a stable top-down map of behavior

## How To Fill This Template

- Fill the document one domain or one vertical slice at a time.
- Prefer repository paths over narrative summaries.
- Keep rows atomic. If one row needs "and then" repeatedly, split it.
- Use IDs to connect capability rows, mechanism rows, and field rows.
- Document only verified behavior.

## Recommended Source Files

- `config/data_sources.yml`
- `config/foreign_keys.yml`
- `config/customer_status_rules.yml`
- `src/work_data_hub/domain/registry.py`
- `src/work_data_hub/domain/*/pipeline_builder.py`
- `src/work_data_hub/orchestration/`
- `src/work_data_hub/cli/etl/`
- `tests/slice_tests/`
- `tests/e2e/`
- `docs/reference/data_processing_guide.md`
- `docs/verification_guide_real_data.md`

---

## 1. Document Metadata

| Item | Value |
|------|-------|
| Scope | `{system | domain | vertical slice}` |
| Target Name | `{example: annuity_performance}` |
| Author | `{name}` |
| Reviewers | `{names}` |
| Last Verified Date | `YYYY-MM-DD` |
| Repository Version / Commit | `{commit or branch}` |
| Confidence Level | `{high | medium | low}` |

### 1.1 Scope Boundary

- Included:
  - `{capability or module 1}`
  - `{capability or module 2}`
- Excluded:
  - `{out-of-scope item 1}`
  - `{out-of-scope item 2}`

### 1.2 Documentation Rules

- Source of truth is repository behavior, not memory or assumptions.
- If behavior differs across domains, document each domain separately.
- If a rule is inferred, label it explicitly as an inference.

---

## 2. System Capability Map

### 2.1 Capability Inventory

| Capability ID | Capability Name | Business Purpose | Trigger | Primary Inputs | Primary Outputs | Affected Objects | Source Of Truth |
|---------------|-----------------|------------------|---------|----------------|-----------------|------------------|-----------------|
| CAP-001 | `{name}` | `{why it exists}` | `{cli / schedule / hook / manual}` | `{input data, tables, files}` | `{tables, files, states}` | `{schemas, tables, logs, snapshots}` | `{path(s)}` |
| CAP-002 |  |  |  |  |  |  |  |

### 2.2 Capability Notes

For each capability, answer only if needed:

- Preconditions:
  - `{what must be true before it runs}`
- Postconditions:
  - `{what must be true after it runs}`
- Non-obvious behavior:
  - `{important caveat}`

### 2.3 Capability Dependency Map

Use this section when a capability depends on other domains, tables, hooks, or
external systems.

| Capability ID | Depends On | Dependency Type | Why It Matters | Evidence |
|---------------|------------|-----------------|----------------|----------|
| `CAP-001` | `{capability/table/system}` | `{upstream/downstream/external/order}` | `{reason}` | `{path/test}` |

---

## 3. Implementation Mechanism Map

### 3.1 Mechanism Inventory

| Mechanism ID | Capability ID | Stage | Activation Condition | Entry Point | Core Modules | Rule Source Type | Rule Source Location(s) | Side Effects | Failure Signal | Verification Anchor |
|--------------|---------------|-------|----------------------|-------------|--------------|------------------|-------------------------|--------------|----------------|---------------------|
| MEC-001 | `CAP-001` | `{discover/read/transform/backfill/load/hook}` | `{always | when X}` | `{function/cli/op}` | `{paths}` | `{code/config/sql/hook/external/mixed}` | `{path(s)}` | `{db write/api/log/snapshot}` | `{exception/log/check}` | `{test/runbook/sql}` |
| MEC-002 |  |  |  |  |  |  |  |  |  |  |

### 3.2 Stage Contract Summary

| Stage | Expected Input Contract | Expected Output Contract | Mutable Fields | Notes |
|-------|-------------------------|--------------------------|----------------|-------|
| `{stage}` | `{shape/schema}` | `{shape/schema}` | `{field list}` | `{important rule}` |

### 3.3 Rule Ownership Summary

Use this table to prevent black-box ownership drift.

| Rule Category | Owned By | Typical Location | Change Risk | Review Requirement |
|---------------|----------|------------------|-------------|--------------------|
| Field cleansing | `{team/module}` | `{yaml/python}` | `{low/medium/high}` | `{who must review}` |
| Cross-table derivation |  |  |  |  |
| Post-ETL hook behavior |  |  |  |  |
| External enrichment fallback |  |  |  |  |

### 3.4 Execution Ordering And Gates

Use this section for order-sensitive stages and hook chains.

| Before | After | Why The Order Matters | Evidence |
|--------|-------|-----------------------|----------|
| `MEC-001` | `MEC-002` | `{reason}` | `{path/test}` |
| `MEC-00X` | `MEC-00Y` | `{reason}` | `{path/test}` |

---

## 4. Key Field Trace Table

Document only the critical fields first.

### 4.1 Field Trace Inventory

| Field ID | Capability ID | Output Field | Business Meaning | Raw Source | Stage Chain | Named Rules Applied | Rule Location | Final Sink | Verification Anchor |
|----------|---------------|--------------|------------------|------------|-------------|---------------------|---------------|------------|---------------------|
| FLD-001 | `CAP-001` | `{field}` | `{meaning}` | `{file/column/table}` | `{stage1 -> stage2 -> stage3}` | `{rule names}` | `{path(s)}` | `{table/column}` | `{test/sql/runbook}` |
| FLD-002 |  |  |  |  |  |  |  |  |  |

### 4.2 Step-By-Step Trace Details

Use this section only for the most complex fields.

#### `FLD-001` `{field name}`

| Step | Input Value | Operation | Rule Name | Output Value | Evidence |
|------|-------------|-----------|-----------|--------------|----------|
| 1 | `{raw}` | `{normalize}` | `{rule}` | `{value}` | `{path/test}` |
| 2 | `{value}` | `{derive}` | `{rule}` | `{value}` | `{path/test}` |
| 3 | `{value}` | `{backfill or sink}` | `{rule}` | `{final}` | `{path/test}` |

### 4.3 Ambiguities And Unknowns

| Field ID | Open Question | Why It Is Unclear | Next Verification Step |
|----------|---------------|-------------------|------------------------|
| `FLD-001` | `{question}` | `{reason}` | `{how to verify}` |

---

## 5. Test And Validation Coverage

### 5.1 Protection Matrix

| Capability ID | Mechanism ID | Validation Type | File / Command | What It Proves | Gaps |
|---------------|--------------|-----------------|----------------|----------------|------|
| `CAP-001` | `MEC-001` | `{unit/integration/e2e/slice/sql/manual}` | `{path or command}` | `{behavior}` | `{remaining risk}` |
| `CAP-001` | `MEC-002` |  |  |  |  |

### 5.2 Real-Data Or Snapshot Anchors

| Artifact | Location | Coverage | Refresh Policy |
|----------|----------|----------|----------------|
| `{golden dataset}` | `{path}` | `{scenario scope}` | `{when to refresh}` |
| `{legacy snapshot}` | `{path}` | `{scenario scope}` | `{when to refresh}` |

---

## 6. Refactoring Risk Assessment

### 6.1 High-Risk Areas

| Area | Why Risky | Impact If Broken | Required Safeguard |
|------|-----------|------------------|--------------------|
| `{field cleansing}` | `{reason}` | `{impact}` | `{tests/trace/golden data}` |
| `{cross-table backfill}` |  |  |  |
| `{hook chain}` |  |  |  |

### 6.2 Safe Refactoring Boundaries

- Safe to change:
  - `{internal implementation detail}`
- Change with parity checks:
  - `{shared transform logic}`
- Do not change without explicit migration design:
  - `{external contract or persisted behavior}`

---

## 7. Open Questions

| ID | Question | Blocking Level | Owner | Resolution Plan |
|----|----------|----------------|-------|-----------------|
| Q-001 | `{question}` | `{high/medium/low}` | `{name}` | `{action}` |

---

## 8. Completion Checklist

- [ ] Capability inventory is complete for the chosen scope.
- [ ] Every capability points to at least one source-of-truth file.
- [ ] Every critical mechanism names its rule source type.
- [ ] Conditional mechanisms state when they are active.
- [ ] Every critical field has a trace row.
- [ ] Every critical field points to a validation anchor.
- [ ] Unknowns are listed explicitly instead of implied away.
- [ ] Any config/comment/implementation drift discovered during mapping is recorded explicitly.

---

## 9. Minimal Example Guidance

If you need a first pass, start with only:

1. 3-7 capability rows
2. 1-3 mechanism rows per capability
3. 5-10 critical field rows

Expand only after the first slice is understandable.
