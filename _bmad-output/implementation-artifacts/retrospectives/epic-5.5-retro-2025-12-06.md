# Epic 5.5 Retrospective: Pipeline Architecture Validation (AnnuityIncome Domain)

**Date:** 2025-12-06
**Epic:** 5.5 - Pipeline Architecture Validation
**Status:** Completed

---

## Executive Summary

Epic 5.5 successfully validated the Infrastructure Layer architecture by implementing a second domain (`annuity_income`) and conducting end-to-end MVP validation with real production data. Both `annuity_performance` and `annuity_income` domains now have complete pipelines from file discovery to database write.

---

## What We Accomplished

### Stories Completed

| Story | Title | Status |
|-------|-------|--------|
| 5.5-1 | Legacy Cleansing Rules Documentation | Done |
| 5.5-2 | AnnuityIncome Domain Implementation | Done |
| 5.5-3 | Legacy Parity Validation | Done |
| 5.5-4 | Multi-Domain Integration Test and Optimization | Done |
| 5.5-5 | AnnuityIncome Schema Correction | Done |

### MVP Validation Results

| Metric | annuity_performance | annuity_income |
|--------|---------------------|----------------|
| Source File | V2 (auto-detected) | V2 (auto-detected) |
| Input Rows | 33,615 | 2,631 |
| Output Rows (after aggregation) | 7,742 | 1,120 |
| Database Rows Loaded | 7,742 | 1,120 |
| Data Integrity (company_id) | 100% | 100% |
| Unique Key Violations | 0 | 0 |
| Processing Time | ~15s | ~2s |

### Key Deliverables

1. **Runbook Created:** `docs/runbooks/mvp-validation-end-to-end.md`
2. **Schema Updates:** Added `组合代码` to composite keys for both domains
3. **Aggregation Logic:** Implemented duplicate key aggregation in Gold layer validation
4. **Database Tables:** Created `annuity_performance_new` and `annuity_income_new` with proper constraints

---

## What Went Well

### 1. Architecture Validation Success
- The Infrastructure Layer architecture proved to be **generalizable** - implementing `annuity_income` followed the same patterns as `annuity_performance`
- File discovery with automatic version detection worked flawlessly
- Pipeline framework handled both domains with minimal domain-specific code

### 2. Real Data Testing
- Using real production data (`tests/fixtures/real_data/202412/`) revealed actual data quality issues
- Discovered that source data has multiple records per composite key (plan + portfolio + company)
- This led to important schema improvements

### 3. Cleansing Framework
- The cleansing registry pattern worked well for both domains
- Domain-specific cleansing rules were easy to configure via YAML

### 4. Story 5.5.5 Quick Response
- Schema mismatch discovered in 5.5.4 was quickly addressed
- Corrected income fields from single `收入金额` to four fields: `固费`, `浮费`, `回补`, `税`

---

## What Could Be Improved

### 1. Primary Key Design
**Issue:** Original composite key `(月度, 计划代码, company_id)` was insufficient for real data.

**Root Cause:** Source data contains multiple records per plan with different portfolios (`组合代码`).

**Resolution:** Extended composite key to `(月度, 计划代码, 组合代码, company_id)` and added aggregation logic.

**Action Item:** Review primary key design for future domains before implementation.

### 2. Gold Layer Validation
**Issue:** `validate_gold_dataframe` was not being called in `annuity_performance` service.

**Root Cause:** Inconsistent implementation between domains.

**Resolution:** Added inline aggregation logic to `process_with_enrichment` function.

**Action Item:** Standardize Gold validation pattern across all domains.

### 3. Schema Strictness
**Issue:** Gold schema validation failed due to:
- Missing columns (`年化收益率`, `年金账户号`)
- Negative values after aggregation (`期初资产规模`, `供款`)

**Resolution:** Relaxed schema validation for MVP, using inline aggregation instead.

**Action Item:** Review Gold schema definitions to match actual data characteristics.

### 4. Rows Failed Metric
**Issue:** `rows_failed` metric is misleading - it shows rows reduced by aggregation, not actual failures.

**Action Item:** Rename or clarify this metric to distinguish between:
- Rows dropped due to validation failures
- Rows reduced due to aggregation

---

## Technical Debt Identified

| Item | Priority | Description |
|------|----------|-------------|
| TD-1 | Medium | Standardize Gold validation pattern across domains |
| TD-2 | Low | Clarify `rows_failed` vs `rows_aggregated` metrics |
| TD-3 | Low | Add `年化收益率` and `年金账户号` columns to pipeline output |
| TD-4 | Medium | Review negative value handling in aggregated numeric fields |

---

## Lessons Learned

### 1. Test with Real Data Early
Real production data revealed issues that synthetic test data would not have caught. Future epics should include real data validation earlier in the process.

### 2. Primary Key Design is Critical
The composite key design significantly impacts data loading. Consider all possible data variations when designing keys.

### 3. Aggregation is a Business Decision
Whether to aggregate duplicate keys or reject them is a business decision that should be documented and validated with stakeholders.

### 4. Runbooks are Valuable
Creating the MVP validation runbook (`docs/runbooks/mvp-validation-end-to-end.md`) provided a systematic approach to validation and will be useful for future deployments.

---

## Recommendations for Next Epic

### For Epic 6 (if applicable):

1. **Start with Primary Key Analysis**
   - Analyze source data for potential duplicate keys before implementation
   - Document expected aggregation behavior

2. **Standardize Service Pattern**
   - Ensure all domains follow the same pattern for Gold validation
   - Consider creating a base service class

3. **Improve Metrics**
   - Add separate metrics for validation failures vs aggregation
   - Include aggregation statistics in pipeline results

4. **Database Schema Management**
   - Consider using Alembic for database migrations
   - Document table creation scripts in version control

---

## Validation Checklist (Completed)

- [x] Phase 1: Environment Verification
- [x] Phase 2: Data Discovery Verification
- [x] Phase 3: Pipeline Processing (Dry Run)
- [x] Phase 4: Database Schema Verification
- [x] Phase 5: Full E2E (DB Write)
- [x] Phase 6: Database Verification

---

## Sign-off

| Role | Name | Status |
|------|------|--------|
| Scrum Master | Bob | Approved |
| Product Owner | Alice | Pending |
| Tech Lead | Charlie | Approved |
| Developer | Link | Approved |

---

**Document Version:** 1.0
**Created:** 2025-12-06
**Author:** WorkDataHub Team
