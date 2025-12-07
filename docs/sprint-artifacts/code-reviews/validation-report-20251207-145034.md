# Validation Report

**Document:** docs/sprint-artifacts/stories/6-6-eqc-api-provider-sync-lookup-with-budget.md  
**Checklist:** .bmad/bmm/workflows/4-implementation/create-story/checklist.md  
**Date:** 2025-12-07 14:50:34

## Summary
- Overall: 27/47 passed (57%)
- Critical Issues: 9

## Section Results

### Setup
Pass Rate: 5/6 (83%)
- ✓ Loaded workflow config and checklist: .bmad/bmm/workflows/4-implementation/create-story/workflow.yaml, checklist.md
- ✓ Loaded target story file
- ✓ Loaded validation framework: .bmad/core/tasks/validate-workflow.xml
- ✓ Extracted story metadata (epic6, story 6.6, status ready-for-dev at lines 1-4)
- ⚠ Resolved workflow vars: epics_file expected at docs/epics.md (workflow.yaml) but absent; used docs/epics/epic-6-company-enrichment-service.md instead
- ✓ Current status/guidance captured from story header and tasks (lines 1-175)

### Epic & Story Context
Pass Rate: 4/5 (80%)
- ✓ Epic objectives/business value covered (lines 7-14)
- ✓ Epic roster/dependencies listed (lines 58-65)
- ✓ Story-specific requirements/ACs present (lines 41-54)
- ⚠ Technical constraints from epic partially reflected; epic requires caching to `enterprise.company_name_index` (docs/epics/epic-6-company-enrichment-service.md:305-317) but story targets `enterprise.company_mapping` (lines 46, 134-136)
- ✓ Cross-story dependencies noted (lines 58-65)

### Architecture Deep-Dive
Pass Rate: 7/9 (78%)
- ✓ Technical stack/versions noted (requests/SQLAlchemy/structlog/pytest at lines 743-748)
- ✓ Code structure patterns and violations called out (lines 20-32, 100-115)
- ✓ API contract sketched (lines 466-502)
- ✗ Database target misaligned: caches to `enterprise.company_mapping` (lines 46, 134-136) while epic/tech-spec expect `enterprise.company_name_index` (docs/epics/epic-6-company-enrichment-service.md:305-317)
- ✓ Security requirements: no token/PII logging (lines 775-783)
- ✓ Performance guards: budget/timeouts/retries targets (lines 848-854)
- ✓ Testing standards: unit test matrix + >85% coverage (lines 786-798, AC14)
- ⚠ Deployment/environment patterns light; only env var list (lines 760-773), no pipeline/startup guidance or failure handling
- ✓ Integration patterns: CompanyIdResolver hook/backward compatibility (lines 858-865)

### History & Research
Pass Rate: 2/3 (67%)
- ✓ Previous story learnings captured (lines 802-816)
- ✓ Git history analyzed (lines 818-827)
- ✗ Latest technical research absent (no version comparison/breaking-change review)

### Disaster Prevention Gaps
Pass Rate: 9/19 (47%)
- ✓ Reinvention avoided: reuse existing EQC client (lines 187-198) and “Do NOT reinvent” guardrails (lines 839-846)
- ✓ Code reuse opportunities identified (lines 187-198, 839-846)
- ✓ Existing solutions emphasized (lines 187-198)
- ⚠ Library/config consistency: mixed token env names (`WDH_EQC_TOKEN` at lines 195-197 vs `WDH_PROVIDER_EQC_TOKEN` at lines 50, 517-519, 760-767) creates risk of wrong credentials
- ✗ API/db contract mismatch: story caches to `enterprise.company_mapping` (lines 46, 134-136) but epic requires `enterprise.company_name_index` (docs/epics/epic-6-company-enrichment-service.md:305-317); confidence fields/indexing missing
- ✗ DB schema alignment missing for company_master/company_name_index updates (epic: lines 305-317; story only mentions company_mapping)
- ✓ Security disasters addressed (no token logging, PII sanitized at lines 775-783)
- ⚠ Performance disaster risk: budget logic described, but cache target mismatch undermines lookup latency expectations
- ⚠ File structure: notes domain→I/O violation (lines 20-31) yet no explicit plan to remove `domain/company_enrichment/service.py` import chain; migration steps not tied to deprecation
- ✓ Coding standards: structlog guidance and dataclass patterns retained (lines 743-748, 775-783)
- ⚠ Integration pattern: placeholder API base URL and mixed env names could break resolver integration (lines 517-519, 760-767)
- ✗ Deployment/rollout risks: no startup/runbook steps or rollback guidance; only env list (lines 760-773)
- ✓ Regression protection: backward compatibility kept (lines 140-145)
- ✓ Testing coverage expected (lines 786-798)
- ➖ UX not applicable
- ✓ Learning reuse: prior story insights listed (lines 802-816)
- ⚠ Implementation detail gaps: API contract marked placeholder (line 501) and tasks unchecked; caching target unresolved
- ✓ No completion misrepresentation (status ready-for-dev, tasks unchecked)
- ✗ Scope creep: adds AC15/AC16 token auto-save/precheck (lines 85-98) despite tech-spec out-of-scope for token automation (docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md:40-42)
- ⚠ Quality risks: cache table mismatch and env ambiguity leave ambiguity on correctness

### LLM Dev-Agent Optimization
Pass Rate: 0/5 (0%)
- ✗ Verbosity/duplication: ~900 lines with repeated token/env sections and long Dev Notes hinder scanability
- ✗ Ambiguity: conflicting env vars (`WDH_EQC_TOKEN` vs `WDH_PROVIDER_EQC_TOKEN`), placeholder base URL (lines 517-520), and dual cache targets
- ⚠ Context overload: large unchecked task lists and repeated guidance without priority
- ✗ Missing critical signals: no directive to use `enterprise.company_name_index` or to align with existing EQC client headers; no clear budget/default wiring to pipeline
- ⚠ Structure: long Dev Notes without distilled “do first” steps; important constraints buried mid-document

## Failed Items
- Cache target misaligned: story writes to `enterprise.company_mapping` (lines 46, 134-136) while epic mandates `enterprise.company_name_index` (docs/epics/epic-6-company-enrichment-service.md:305-317); risk of wrong schema and missing index/confidence fields.
- Env/config ambiguity: mixed token env names (`WDH_EQC_TOKEN` lines 195-197 vs `WDH_PROVIDER_EQC_TOKEN` lines 50, 517-519, 760-767) and placeholder base URL (lines 517-520) can break auth calls.
- Deployment/runbook gap: no startup/rollback guidance beyond env list (lines 760-773); leaves operators without steps to enable/disable EQC sync safely.
- Scope creep vs tech-spec: new AC15/AC16 token auto-save/precheck (lines 85-98) conflicts with tech-spec out-of-scope for token automation (docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md:40-42).
- LLM usability: document length/duplication and missing decisive cache/env directives make it hard for dev agent to execute correctly (lines 466-520, 743-848).

## Partial Items
- Workflow vars: epics_file missing at expected path; used epic-6 markdown as fallback.
- Epic constraints: cache table requirement partially reflected; see cache mismatch above.
- Deployment/env patterns: env list present but no pipeline/startup guidance.
- Library/config consistency: token env names conflict (`WDH_EQC_TOKEN` vs `WDH_PROVIDER_EQC_TOKEN`).
- Performance guard: cache target mismatch may negate latency goals.
- File structure/integration: domain→I/O violation noted but no removal plan; API base URL placeholder.
- Implementation detail: API contract marked placeholder; unchecked tasks without acceptance linkage.
- Quality risk: cache table mismatch and env ambiguity leave correctness unclear.
- Context/structure: long Dev Notes without prioritized actions.

## Recommendations
1. Must Fix: Align cache target and schema with epic—use `enterprise.company_name_index` for EQC results and define how to update `company_master`; remove `company_mapping` as cache target for EQC sync or justify divergence with migrations/tests.
2. Must Fix: Resolve token/env naming and base URL—pick one env prefix (epic uses `WDH_PROVIDER_EQC_TOKEN`), align with existing `EQCClient` expectations, and specify exact headers/URL (no placeholders).
3. Must Fix: Re-scope token work—drop or restate AC15/AC16 per tech-spec out-of-scope; if kept, justify scope change and add security safeguards.
4. Should Improve: Add deployment/runbook steps (enable/disable EQC sync, budget defaults, rollback plan) and integration wiring to CompanyIdResolver with budget handoff.
5. Should Improve: Clarify API/cache contract (request/response fields, caching rules, error mapping) with concrete examples and remove placeholder language.
6. Consider: Condense Dev Notes into a short “Implementation Plan” section and move verbose research to appendix to improve LLM consumption.
