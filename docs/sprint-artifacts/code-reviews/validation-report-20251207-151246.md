# Validation Report

**Document:** docs/sprint-artifacts/stories/6-6-eqc-api-provider-sync-lookup-with-budget.md  
**Checklist:** .bmad/bmm/workflows/4-implementation/create-story/checklist.md  
**Date:** 2025-12-07 15:12:46

## Summary
- Overall: 31/47 passed (66%)
- Critical Issues: 6

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
- ✓ Story-specific requirements/ACs present and now cache to `company_name_index` (lines 41-54, 134-136; epic ref docs/epics/epic-6-company-enrichment-service.md:136-317)
- ⚠ Technical constraints partially: story caches to `company_name_index` but caching logic still references mapping-style fields (alias/priority, lines 717-728) without confidence/index expectations from epic
- ✓ Cross-story dependencies noted (lines 58-65)

### Architecture Deep-Dive
Pass Rate: 7/9 (78%)
- ✓ Technical stack/versions noted (requests/SQLAlchemy/structlog/pytest at lines 743-748)
- ✓ Code structure patterns and violations called out (lines 20-32, 100-115)
- ✓ API contract sketched (lines 466-502)
- ⚠ Database write shape still mapping-oriented (`insert_batch_with_conflict_check` payload lines 717-728) vs `company_name_index` schema (epic lines 136-317)
- ✓ Security requirements: no token/PII logging (lines 775-783)
- ✓ Performance guards: budget/timeouts/retries targets (lines 848-854)
- ✓ Testing standards: unit test matrix + >85% coverage (lines 786-798, AC14)
- ✓ Deployment/env patterns improved: unified `WDH_EQC_TOKEN` and `WDH_EQC_API_BASE_URL` default (lines 50, 195-272, 516-520, 760-768)
- ✗ API contract still marked placeholder (line 501) with no concrete EQC endpoint confirmation

### History & Research
Pass Rate: 2/3 (67%)
- ✓ Previous story learnings captured (lines 802-816)
- ✓ Git history analyzed (lines 818-827)
- ✗ Latest technical research absent (no version comparison/breaking-change review)

### Disaster Prevention Gaps
Pass Rate: 12/19 (63%)
- ✓ Reinvention avoided: reuse existing EQC client (lines 187-198) and “Do NOT reinvent” guardrails (lines 839-846)
- ✓ Code reuse opportunities identified (lines 187-198, 839-846)
- ✓ Existing solutions emphasized (lines 187-198)
- ✓ Library/config consistency fixed: unified `WDH_EQC_TOKEN` / `WDH_EQC_API_BASE_URL` (lines 50, 195-272, 516-520, 760-768)
- ⚠ API/db contract mismatch risk: cache target is `company_name_index` but write example uses mapping fields and no confidence/index guidance (lines 134-136, 717-728; epic lines 136-317)
- ✓ Security disasters addressed (no token logging, PII sanitized at lines 775-783)
- ✓ Performance guardrails intact (budget/timeouts at lines 848-854)
- ⚠ File structure: domain→I/O violation noted (lines 20-31) but no explicit deprecation/removal path for `domain/company_enrichment/service.py`
- ✓ Coding standards: structlog guidance and dataclass patterns retained (lines 743-748, 775-783)
- ✓ Integration pattern: CompanyIdResolver hook/backward compatibility (lines 858-865)
- ✓ Deployment/env risks reduced via unified env keys (lines 50, 195-272, 516-520, 760-768)
- ✗ Deployment/rollout guidance still thin: no startup/rollback steps, only env list (lines 760-773)
- ✓ Regression protection: backward compatibility kept (lines 140-145)
- ✓ Testing coverage expected (lines 786-798)
- ➖ UX not applicable
- ✓ Learning reuse: prior story insights listed (lines 802-816)
- ⚠ Implementation detail gaps: API contract marked placeholder (line 501); schema write shape unclear (lines 717-728)
- ✗ Scope creep vs tech-spec: AC15/AC16 token auto-save/precheck remain in story (lines 85-99) though tech-spec marks token automation out-of-scope (docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md:40-42)
- ⚠ Quality risk: cache write payload does not mention confidence or index fields needed by `company_name_index` (lines 717-728; epic lines 136-317)

### LLM Dev-Agent Optimization
Pass Rate: 1/5 (20%)
- ✓ Env/token/base URL now unambiguous (lines 50, 195-272, 516-520, 760-768)
- ✗ Verbosity/duplication: ~900 lines with long Dev Notes and repeated token sections; no condensed “do first” list
- ✗ Ambiguity: cache write shape vs target table (`company_name_index`) not clarified (lines 134-136, 717-728)
- ✗ Missing critical signals: still notes API contract as placeholder (line 501) and lacks explicit migration/removal steps for `auth/` and domain dependency
- ⚠ Structure: unchecked task lists dominate; key directives not elevated for quick execution

## Failed Items
- Cache write schema unclear: story targets `enterprise.company_name_index` but caching payload still mapping-style without confidence/index alignment (lines 134-136, 717-728; epic expectation docs/epics/epic-6-company-enrichment-service.md:136-317).
- API contract remains placeholder with no confirmed endpoint/headers beyond default base URL (line 501).
- Scope conflict: token auto-save/precheck (AC15/AC16, lines 85-99) still included though tech-spec marks token automation out-of-scope (docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md:40-42).
- Deployment/runbook gap: story lists envs (760-773) but lacks startup/rollback steps, budget defaults, or disable/enable instructions.
- File-structure remediation: domain→I/O violation identified (lines 20-31) but no deprecation/cleanup path for `domain/company_enrichment/service.py`.
- LLM usability: document still long and duplicative; key directives (cache schema, confirmed API contract) not surfaced succinctly for dev agent consumption.

## Partial Items
- Workflow vars: epics_file missing at expected path; epic markdown used instead.
- Technical constraint: cache target aligned but write shape/confidence/index fields unspecified.
- Deployment: envs present, but no operational runbook.
- Implementation: API contract placeholder pending confirmation.
- Scope: token automation items remain despite tech-spec scope note.
- Structure: tasks unchecked; key priorities not distilled.

## Recommendations
1. Must Fix: Specify exact `company_name_index` write contract (normalized_name, company_id, confidence, match_type, timestamps) and align repository/payload to it; drop mapping-style fields in example (lines 717-728).
2. Must Fix: Replace placeholder API contract with confirmed endpoint/headers/body/response schema, including auth header and error mapping; cite source.
3. Must Fix: Re-scope or justify AC15/AC16 against tech-spec out-of-scope; if kept, mark as scope change with safeguards.
4. Should Add: Deployment/runbook steps (enable/disable EQC sync, default budget, rollback on 401/5xx, env verification) and `auth/`→`io/auth/` migration/deprecation plan.
5. Should Optimize: Provide a concise “Implementation plan” section summarizing critical directives (env keys, base URL, cache schema, integration points) to reduce token load and ambiguity.
