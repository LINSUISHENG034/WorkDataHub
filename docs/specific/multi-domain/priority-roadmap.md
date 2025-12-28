# Multi-Domain Architecture Repair Plan

> **Created:** 2025-12-29
> **Status:** Prioritized
> **Context:** Outcome of analyzing architecture gap documents in `docs/specific/multi-domain/`

## Strategy: Correctness → Integrity → Maintainability

We will address issues in the following order to minimize data risk.

### 1. 🚨 Phase 1: Data Correctness & Schema Consistency (Critical / P0)

**Source:** [`shared-field-validators-analysis.md`](./shared-field-validators-analysis.md)

**Issue:**
There are critical conflicts in how `annuity_income` and `annuity_performance` handle null values for `company_id` (PK component) and `客户名称` (Customer Name). The `annuity_income` domain incorrectly marks these as `Required` in Pydantic but `NOT NULL` in DB (for customer name involved in logic), while they should be nullable or consistently handled.

**Risks:**

- ETL failures during the Load phase due to schema validation mismatches.
- Inconsistent data states between two similar business domains.

**Action Items:**

1.  **Refactor Validators:** Extract common logic to `infrastructure/cleansing/validators.py`.
2.  **Fix Domain Registry:** Update `annuity_income` definition to allow NULLs where appropriate.
3.  **Update Models:** Align Pydantic models with the Registry SSOT.

### 2. 🔗 Phase 2: Referential Integrity & Backfill (High / P1)

**Source:** [`fk-backfill-gap-analysis.md`](./fk-backfill-gap-analysis.md)

**Issue:**
`annuity_income` is completely missing Foreign Key (FK) backfill configurations. `annuity_performance` is missing the crucial backfill for `年金客户` (Annuity Customer) via `company_id`.

**Risks:**

- Fact tables (income/performance) populated without corresponding Dimension records.
- Reports and Cross-Domain queries failing due to missing joins.

**Action Items:**

1.  **Config Update:** Add `annuity_income` section to `config/foreign_keys.yml`.
2.  **Add Missing Key:** Add `fk_customer` configuration to `annuity_performance`.

### 3. 🛠️ Phase 3: Maintainability & Scalability (Medium / P2)

**Source:** [`new-domain-checklist.md`](./new-domain-checklist.md)

**Issue:**
Adding a new domain currently requires modifying 5-7 distinct files due to hardcoded if/else dispatch logic in the CLI and Job orchestration layers.

**Risks:**

- High friction for adding new data domains.
- Increased likelihood of copy-paste errors.

**Action Items:**

1.  **Registry Pattern:** Implement a `JobRegistry` to map domains to jobs dynamically.
2.  **Config Driven:** Move domain capabilities (backfill, enrichment support) into `data_sources.yml` metadata.
