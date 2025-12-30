# Validation Report

**Document:** docs/sprint-artifacts/stories/7.4-3-generic-process-domain-op.md
**Checklist:** _bmad/bmm/workflows/4-implementation/create-story/checklist.md
**Date:** 2025-12-30T14:23:00+08:00

## Summary

- Overall: 28/33 passed (85%)
- Critical Issues: 3
- Enhancement Opportunities: 2

---

## Section Results

### Step 1: Load and Understand the Target

Pass Rate: 5/5 (100%)

**[✓] Story file loaded and metadata extracted**
Evidence: Lines 1-7 - Story 7.4-3: Generic Process Domain Op, Status: ready-for-dev

**[✓] Epic number and story number correctly identified**
Evidence: Lines 122-127 - References correctly link to Epic 7.4 and Sprint Change Proposal

**[✓] Workflow variables resolved**
Evidence: Story correctly placed in `docs/sprint-artifacts/stories/` per project conventions

**[✓] Current status understood**
Evidence: Line 3 - `Status: ready-for-dev` with implementation guidance

**[✓] Story key and title present**
Evidence: Line 1 - `# Story 7.4-3: Generic Process Domain Op`

---

### Step 2.1: Epics and Stories Analysis

Pass Rate: 4/4 (100%)

**[✓] Epic objectives and business value present**
Evidence: Lines 10-12 - User story format clearly states goal: "so that adding new domains only requires registering them in a service registry"

**[✓] Acceptance criteria complete**
Evidence: Lines 14-44 - AC1 through AC5 are well-defined with specific, testable requirements

**[✓] Cross-story dependencies documented**
Evidence: Lines 124-126 - References to Story 7.4-1, 7.4-2 and technical debt analysis

**[✓] Previous story context extracted**
Evidence: Lines 309-328 - "Previous Story Intelligence" section with actionable learnings from 7.4-1 and 7.4-2

---

### Step 2.2: Architecture Deep-Dive

Pass Rate: 6/7 (86%)

**[✓] Technical stack with versions identified**
Evidence: Lines 132-147 - Target code pattern shows dataclass, typing imports, Dagster op decorator

**[✓] Code structure patterns documented**
Evidence: Lines 90-93 - Registry location decision in `orchestration/ops/pipeline_ops.py` alongside JOB_REGISTRY pattern

**[✓] API design patterns specified**
Evidence: Lines 92-99 - Service function contract clearly defined with signature requirements

**[✓] Performance requirements addressed**
Evidence: N/A - Story is extensibility-focused, not performance-critical

**[✗] CRITICAL: Service Interface Mismatch Not Fully Addressed**
Evidence: Lines 267-279 show interface differences:
- `annuity_performance.process_with_enrichment()` accepts `eqc_config: Optional[EqcLookupConfig]` (Story 6.2-P17)
- `annuity_income.process_with_enrichment()` does NOT accept `eqc_config`, only `sync_lookup_budget: int`

Impact: Story Task 4.3 "Handle enrichment setup conditionally" cannot use a unified interface without additional adaptation layer

**[✓] Database schemas addressed**
Evidence: N/A - Story does not involve database changes

**[✓] Testing standards documented**
Evidence: Lines 284-301 - Testing strategy with unit tests, manual validation, and regression check commands

---

### Step 2.3: Previous Story Intelligence

Pass Rate: 4/4 (100%)

**[✓] Dev notes and learnings extracted**
Evidence: Lines 309-328 - Key learnings include:
- Follow JobEntry dataclass pattern
- Place registry after service imports
- Use consistent error formatting with sorted keys

**[✓] Files created/modified patterns identified**
Evidence: Lines 256-263 - "Files to Modify" table with specific line numbers and change types

**[✓] Code patterns and conventions established**
Evidence: Story 7.4-1 completion notes at Lines 215-259 provide concrete patterns:
- `frozen=True` for immutability
- Auto-generated error messages from `registry.keys()`

**[✓] Git intelligence analyzed**
Evidence: Lines 330-335 - Recent commits referenced for pattern validation

---

### Step 2.4: Git History Analysis

Pass Rate: 1/1 (100%)

**[✓] Recent patterns analyzed**
Evidence: Lines 330-335 - Git intelligence confirms JOB_REGISTRY pattern and config-driven backfill

---

### Step 2.5: Latest Technical Research

Pass Rate: 1/1 (100%)

**[✓] Framework versions confirmed**
Evidence: Dagster and Pydantic usage patterns consistent with existing codebase (`@op` decorator, `Config` class)

---

### Step 3.1: Reinvention Prevention Gaps

Pass Rate: 1/2 (50%)

**[✓] Existing solutions identified**
Evidence: Lines 130-195 - Target code pattern reuses existing service functions, no new domain logic created

**[⚠] PARTIAL: Result Normalization Pattern Already Exists**
Evidence: `pipeline_ops.py` lines 76-81 and 393-395 already have the `model_dump()` normalization pattern.
Gap: Story could reference these existing patterns more explicitly to prevent reimplementation.

---

### Step 3.2: Technical Specification DISASTERS

Pass Rate: 2/3 (67%)

**[✓] API contract violations prevented**
Evidence: Lines 92-99 define clear service function contract

**[✗] CRITICAL: annuity_income Service Interface Incompatible**
Evidence: Examining actual service signatures:
- `annuity_performance.process_with_enrichment(rows, data_source, eqc_config=None, enrichment_service=None, sync_lookup_budget=0, export_unknown_names=True)` returns `ProcessingResultWithEnrichment`
- `annuity_income.process_with_enrichment(rows, data_source, enrichment_service=None, sync_lookup_budget=0, export_unknown_names=True)` returns `ProcessingResultWithEnrichment`
- `sandbox_trustee_performance.process(rows, data_source)` returns `List[TrusteePerformanceOut]`

The proposed registry entry (Lines 152-179) maps ALL domains to their actual service functions, but:
1. `annuity_performance` needs `eqc_config` parameter (not mentioned in Task 2.2 mapping)
2. Generic op sketch (Lines 220-228) only passes `data_source` - missing `eqc_config`

Impact: Generic op will fail for `annuity_performance` when enrichment is enabled because `eqc_config` is not passed.

**[✓] Database schema conflicts prevented**
Evidence: N/A - No database changes in this story

---

### Step 3.3: File Structure DISASTERS

Pass Rate: 2/2 (100%)

**[✓] File locations correctly specified**
Evidence: Lines 258-263 - All changes in `orchestration/ops/` and `tests/orchestration/` which exist

**[✓] Coding standards followed**
Evidence: Target code uses consistent patterns: `frozen=True`, type hints, docstrings

---

### Step 3.4: Regression DISASTERS

Pass Rate: 2/2 (100%)

**[✓] Breaking changes prevented**
Evidence: Lines 28-33 (AC3) - Backward compatibility explicitly required; existing ops remain functional

**[✓] Test requirements specified**
Evidence: Lines 42-44 (AC5) - All existing tests must pass, CI green

---

### Step 3.5: Implementation DISASTERS

Pass Rate: 2/3 (67%)

**[✓] Vague implementations prevented**
Evidence: Lines 130-254 - Comprehensive target code patterns with complete implementation sketches

**[⚠] PARTIAL: Enrichment Setup Logic Missing**
Evidence: Lines 223-225 show placeholder `...` for enrichment setup:
```python
if entry.supports_enrichment and config.enrichment_enabled:
    # Setup enrichment service (similar to process_annuity_performance_op)
    ...
```
Gap: This is a critical ~100 lines of code (see `pipeline_ops.py:128-241`) that requires explicit guidance or reference.

**[✓] Scope boundaries clearly defined**
Evidence: Lines 107-119 - IN SCOPE / OUT OF SCOPE sections are explicit

---

### Step 4: LLM-Dev-Agent Optimization Analysis

Pass Rate: 4/5 (80%)

**[✓] Verbosity appropriate**
Evidence: Story is well-structured with clear sections; not overly verbose

**[✓] Actionable instructions provided**
Evidence: Tasks have specific subtasks (1.1, 1.2, etc.) with clear deliverables

**[✓] Scannable structure used**
Evidence: Markdown headings, tables, code blocks used effectively

**[✓] Token efficiency reasonable**
Evidence: ~350 lines is appropriate for this complexity level

**[⚠] PARTIAL: Critical signals could be more prominent**
Gap: The interface mismatch issue (annuity_performance needs eqc_config, others don't) is buried in code examples rather than explicitly called out as a critical implementation consideration.

---

## Failed Items

### ✗ Service Interface Mismatch (Critical)

**Issue:** The three domain services have different interfaces:
- `annuity_performance.process_with_enrichment()` requires `eqc_config: EqcLookupConfig` for enrichment
- `annuity_income.process_with_enrichment()` uses older `sync_lookup_budget: int` interface
- `sandbox_trustee_performance.process()` is minimal

**Recommendation:** Add explicit interface adaptation guidance in Dev Notes:
```markdown
### Interface Adaptation Required

The generic op must handle interface differences:

1. **annuity_performance**: Pass `eqc_config` (EqcLookupConfig from ProcessDomainOpConfig)
2. **annuity_income**: Pass `sync_lookup_budget` (derive from config.enrichment_sync_budget)
3. **sandbox_trustee_performance**: Pass only `rows, data_source`

Consider adding `interface_adapter` field to DomainServiceEntry or use **kwargs with service-specific unpacking.
```

---

### ✗ Enrichment Setup Logic Not Referenced (Critical)

**Issue:** Task 4.3 says "Handle enrichment setup conditionally" but the actual enrichment setup is ~100 lines of complex code involving:
- Lazy psycopg2 import
- Database connection with validation
- CompanyEnrichmentLoader, LookupQueue, EQCClient, EnrichmentObserver setup

**Recommendation:** Add explicit reference or copy key code:
```markdown
### Enrichment Setup Reference

For enrichment setup, reference `pipeline_ops.py:128-241` which contains:
- Database connection validation (lines 175-196)
- psycopg2 lazy loading (lines 161-169)
- Service component initialization (lines 228-241)

The generic op should REUSE this pattern, not reimplement.
```

---

## Partial Items

### ⚠ Result Normalization Pattern

**Gap:** The `model_dump()` normalization pattern exists in multiple places:
- `pipeline_ops.py:76-81` (sandbox)
- `pipeline_ops.py:288-291` (annuity_performance)
- `pipeline_ops.py:393-395` (annuity_income)

**Missing:** Story could explicitly reference these patterns to ensure consistency.

---

### ⚠ Critical Interface Warning

**Gap:** The eqc_config requirement for annuity_performance is only visible by reading the actual service code. Story should call this out explicitly in a "Known Complexity" section.

---

## Recommendations

### 1. Must Fix: Critical Failures

1. **Add Interface Adaptation Section** to Dev Notes explaining how to handle different service signatures
2. **Add Enrichment Setup Reference** pointing to exact lines in `pipeline_ops.py` to reuse
3. **Update Task 2.2** to note that `annuity_performance` mapping needs `eqc_config` handling

### 2. Should Improve: Important Gaps

1. **Add "Known Complexity" Warning** about interface differences between domains
2. **Reference Test File** correctly - `tests/orchestration/test_ops.py` exists, not `test_pipeline_ops.py`
3. **Add EqcLookupConfig Import** to target code pattern (Lines 130-147 missing this import)

### 3. Consider: Minor Improvements

1. Add explicit mention that `ProcessingResultWithEnrichment` has `.records` attribute vs `List[Model]`
2. Reference the existing `ProcessingConfig` class to explain relationship with new `ProcessDomainOpConfig`
3. Consider adding smoke test command for registry validation

---

## Validation Summary

| Category | Count | Percentage |
|----------|-------|------------|
| ✓ PASS | 28 | 85% |
| ⚠ PARTIAL | 3 | 9% |
| ✗ FAIL | 2 | 6% |

**Overall Assessment:** Story is well-structured but has **2 critical gaps** that could cause implementation failures:
1. Service interface mismatch between domains is not addressed
2. Complex enrichment setup logic needs explicit reference

**Recommendation:** Apply critical fixes before proceeding to dev-story.
