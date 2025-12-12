# Validation Report

**Document:** docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md
**Checklist:** .bmad/bmm/workflows/4-implementation/create-story/checklist.md
**Date:** 20251208-072926

## Summary
- Overall: 4/12 passed (33%)
- Critical Issues: 2

## Section Results

### Systematic Setup
Pass Rate: 2/2 (100%)

✓ Loaded workflow config/checklist/story inputs (workflow.yaml, checklist.md, story file).
✓ Story metadata captured (epic/story id, title, status) `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:1-4`.

### Epics & Change Context
Pass Rate: 1/3 (33%)

⚠ Epic objective/business value only partially reflected; story focuses on table creation and cache hit rate, but does not restate Epic 6 goal of flexible provider abstraction `docs/epics/epic-6-company-enrichment-service.md:1-18` vs story scope `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:7-9`.
⚠ Cross-story dependencies lightly noted as prerequisite for later stories but missing links to dependency graph in change proposal `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-08-layer2-enrichment-enhancement.md:244-250`; story only notes it is prerequisite `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:195-198` without detailing handoff expectations.
✓ Story acceptance criteria and tasks align with change proposal’s Story 6.1.1 scope `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-08-layer2-enrichment-enhancement.md:128-143` and are captured in AC/Tasks `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:13-72`.

### Architecture & Data Design
Pass Rate: 0/5 (0%)

⚠ Multi-tier architecture alignment is implicit; story does not instruct how repository methods feed DB-P1..P5 flow in CompanyIdResolver as shown in architecture guide `docs/guides/company-enrichment-service.md:35-86`.
✗ Normalization/lookup-key formation lacks direction (which normalizer to use, casing, trimming) even though design doc requires normalized customer_name and plan_customer keys `docs/specific/company-enrichment-service/layer2-enrichment-index-enhancement.md:102-109`; story lists types but no normalization rules or reuse of existing normalizer `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:123-130`.
✗ Conflict/upsert semantics for enrichment_index missing: design calls for GREATEST(confidence) and hit_count update on conflict `docs/specific/company-enrichment-service/layer2-enrichment-index-enhancement.md:189-207`, but story only says “ON CONFLICT handling” without required update fields `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:35-38,60`.
⚠ Data type/constraint consistency: story fixes company_id at VARCHAR(50) `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:17,96` while existing enterprise schema uses 100 chars `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py:84-98`; no CHECK constraints on lookup_type/source/confidence to prevent invalid values.
⚠ Idempotent migration/index pattern not spelled out: tasks mention IF NOT EXISTS `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:40,47-51,69-71` but omit explicit `_table_exists`/`_index_exists` guards used in prior migration `io/schema/migrations/versions/20251206_000001_create_enterprise_schema.py:76-211`, and lack expectations for rerun/downgrade validation or performance targets.

### Disaster Prevention & Testing
Pass Rate: 0/1 (0%)

⚠ Reinvention/regression safeguards are thin: coexistence with existing caches (`company_name_index`, `company_mapping`) and integration plan for new table are unspecified, risking duplicate sources without resolver direction; no guidance on regression metrics or coverage beyond generic unit tests `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:52-68,151-159`.

### LLM Optimization
Pass Rate: 1/1 (100%)

✓ Structure is clear (ACs, tasks, dev notes) and scoped, suitable for dev agents `docs/sprint-artifacts/stories/6.1-1-enrichment-index-schema-enhancement.md:11-205`.

## Failed Items
✗ Normalization/lookup-key formation rules (see Architecture & Data Design).
✗ Conflict/upsert semantics and confidence/hit_count handling on enrichment_index conflicts (see Architecture & Data Design).

## Partial Items
⚠ Epic objective alignment; cross-story dependency handoffs.
⚠ Multi-tier architecture integration guidance for DB-P1..P5.
⚠ Data type/constraint consistency and idempotent migration specifics.
⚠ Reinvention/regression safeguards and testing depth.

## Recommendations
1. Must Fix: Define normalization rules and reuse existing normalizer for `customer_name` and `plan_customer` keys; specify key formats and casing.
2. Must Fix: Spell out ON CONFLICT behavior for `insert_enrichment_index_batch` (GREATEST confidence, increment hit_count, update last_hit_at/updated_at) to satisfy domain learning/backflow requirements.
3. Should Improve: Align schema constraints with enterprise tables (company_id length, CHECK on lookup_type/source/confidence, optional FK to company_master) and adopt `_table_exists`/`_index_exists` guards plus rerun/downgrade verification.
4. Should Improve: Describe how new repository methods plug into DB-P1..P5 flow and how to avoid conflicting with existing `company_name_index`/`company_mapping`; include regression metrics/coverage expectations.
