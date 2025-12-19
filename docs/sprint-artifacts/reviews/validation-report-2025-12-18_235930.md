# Validation Report

**Document:** `docs/sprint-artifacts/stories/6.2-p13-unified-domain-schema-management.md`  
**Checklist:** `_bmad/bmm/workflows/4-implementation/create-story/checklist.md`  
**Date:** 2025-12-18 23:59:30 (local)  
**Additional artifacts loaded:**
- `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-18-unified-schema-management.md`
- `docs/project-context.md`
- `docs/brownfield-architecture.md`
- `scripts/create_table/generate_from_json.py`
- `src/work_data_hub/io/schema/migration_runner.py`
- `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md`
- `pyproject.toml`
- Recent git history (`git log -n 10 --oneline`)

## Summary

- **Overall:** 92/141 ✓ PASS (65.2%)
- **Partials:** 26 ⚠ PARTIAL
- **Failures:** 18 ✗ FAIL
- **N/A:** 5 ➖ N/A
- **Verdict:** **NOT READY FOR DEV** (critical failures exist)

### Critical Issues (Must Fix)

1. **Status mismatch:** Story marked `ready-for-dev` while the Sprint Change Proposal is **Pending Approval**. (Evidence: E2, E1)
2. **Reinvents existing tooling:** Story proposes new schema/DDl generation surface without acknowledging existing `scripts/create_table/generate_from_json.py` and the SQL Generation Module. (Evidence: E5, E6, E7)
3. **Wrong / ambiguous file locations:** `io/schema/domain_registry.py` conflicts with repo layout and `migration_runner` usage of package path conventions. (Evidence: E3, E12)
4. **Migration naming pattern mismatch:** Proposed `YYYYMMDD_create_*.py` doesn’t match existing `YYYYMMDD_HHMMSS_*.py` pattern. (Evidence: E4, E8)
5. **Epic/story metadata missing/inconsistent:** Title uses `6.2.P13` and story lacks the standard story header fields used in sibling stories. (Evidence: E1, E13)
6. **High-risk schema changes bundled:** PK rename to `id` is a large, potentially breaking migration bundled into one story without detailed migration plan. (Evidence: E9, E10)
7. **Reference link likely broken:** `docs/brownfield-architecture.md#SQL-Generation-Module` anchor is not present as written. (Evidence: E11)
8. **Template leftovers:** `{{agent_model_name_version}}` placeholder and empty “File List” section. (Evidence: E14)

## Section Results

### Critical Mistakes To Prevent
Pass Rate: 0/8 (0%) — the checklist items here are *preventative risks*; story still has multiple major gaps.

- ✗ FAIL (L11) **Reinventing wheels** — Duplicate/overlapping schema + SQL generation surface exists today. Evidence: E5, E6, E7.
- ⚠ PARTIAL (L12) **Wrong libraries** — Libraries are consistent with repo (Pandera/Pydantic/Alembic), but story does not pin versions or point to `pyproject.toml` constraints. Evidence: E15.
- ⚠ PARTIAL (L13) **Wrong file locations** — At least one required path is inconsistent (`io/schema/domain_registry.py`). Evidence: E3, E12.
- ⚠ PARTIAL (L14) **Breaking regressions** — Back-compat is mentioned, but the PK rename + migration unification can break loaders/tests if not split and sequenced. Evidence: E9, E10.
- ➖ N/A (L15) **Ignoring UX** — No UI/UX surface in scope (backend-only change).
- ⚠ PARTIAL (L16) **Vague implementations** — Index representation + Alembic conditional-create details are underspecified. Evidence: E7, E9.
- ✗ FAIL (L17) **Lying about completion** — “ready-for-dev” conflicts with pending approval + placeholders remain. Evidence: E2, E1, E14.
- ✗ FAIL (L18) **Not learning from past work** — Missing explicit reuse/interaction with existing SQL module and DDL generator. Evidence: E5, E6.

### Checklist Usage & Inputs
Pass Rate: 12/13 (92.3%)

- ✓ PASS (L36) Validation framework expectation understood; used `validate-workflow.xml` process model for this report.
- ✓ PASS (L37) Checklist loaded from `_bmad/.../checklist.md`.
- ✓ PASS (L38) Story file loaded from `docs/sprint-artifacts/stories/...`.
- ✓ PASS (L39) Workflow variables loaded from `_bmad/.../workflow.yaml`.
- ✓ PASS (L40) Validation executed and report produced.

- ✓ PASS (L44) User provided story file path.
- ✓ PASS (L45) Story loaded directly.
- ✓ PASS (L46) Workflow.yaml loaded for context.
- ✓ PASS (L47) Systematic analysis performed (artifacts listed at top).

- ✓ PASS (L51) Story file available.
- ✓ PASS (L52) Workflow variables reviewed (output folder, story_dir, etc.).
- ⚠ PARTIAL (L53) Source docs: Some “standard” workflow docs (`docs/epics.md`, `docs/architecture.md`) are missing; used sharded equivalents + sprint change proposal instead.
- ✓ PASS (L54) Validation framework (`validate-workflow.xml`) loaded and followed.

### Step 1: Load & Understand
Pass Rate: 3/6 (50.0%)

- ✓ PASS (L64) Loaded workflow config: `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml`.
- ✓ PASS (L65) Loaded story file.
- ✓ PASS (L66) Loaded validation framework: `_bmad/core/tasks/validate-workflow.xml`.
- ⚠ PARTIAL (L67) Extract metadata: story key format inconsistent and missing Epic/Type/Priority fields vs neighboring stories. Evidence: E13, E1.
- ⚠ PARTIAL (L68) Resolve variables: `docs/epics.md`, `docs/architecture.md`, `docs/PRD.md`, `docs/ux.md` are missing; substituted other docs. Evidence: E16.
- ⚠ PARTIAL (L69) Understand current status: marked `ready-for-dev` but change proposal is pending approval. Evidence: E1, E2.

### Step 2: Source Analysis
Pass Rate: 21/37 (56.8%)

- ⚠ PARTIAL (L80) Load epics file: workflow points to `docs/epics.md`, which doesn’t exist; used `docs/epics/` + other sources instead. Evidence: E16.
- ⚠ PARTIAL (L81) Extract complete Epic context: provided epic-num `6.2` in this session doesn’t match proposal’s “Epic 7+ direct” framing and story has no epic header. Evidence: E2, E17, E13.
- ✗ FAIL (L82) Epic objectives/business value: not clearly anchored to a defined epic in the repo docs.
- ✗ FAIL (L83) All stories in the epic: cannot reliably enumerate because epic is unclear for this story.
- ⚠ PARTIAL (L84) Specific story requirements: story has ACs and tasks, but scope overlaps multiple subsystems without clear “out of scope”. Evidence: E7, E9.
- ⚠ PARTIAL (L85) Technical requirements/constraints: missing explicit reuse constraints (existing SQL module + DDL generator). Evidence: E5, E6.
- ✗ FAIL (L86) Cross-story dependencies/prereqs: not explicit; e.g., approval gate, migration sequencing, and interaction with existing scripts. Evidence: E2, E5.

- ✓ PASS (L90) Loaded architecture sources (brownfield + migrations + scripts) relevant to story scope.
- ✓ PASS (L91) Performed systematic scan for relevant constraints (see Evidence Appendix and Critical Issues).
- ✓ PASS (L92) Tech stack + versions verified from `pyproject.toml`. Evidence: E15.
- ✓ PASS (L93) Code structure patterns reviewed (package paths + migrations runner). Evidence: E12.
- ➖ N/A (L94) API design patterns: no API changes in scope.
- ✓ PASS (L95) DB schema/relationships inspected via existing DDL + migrations directories. Evidence: E5, E4.
- ➖ N/A (L96) Security requirements: none explicitly in scope for schema management.
- ➖ N/A (L97) Performance requirements: none explicitly in scope.
- ✓ PASS (L98) Testing frameworks/standards identified (pytest + repo conventions). Evidence: E15.
- ⚠ PARTIAL (L99) Deployment/environment patterns: story mentions multi-env deployment, but does not specify rollout strategy for DB migration risks. Evidence: E2, E10.
- ⚠ PARTIAL (L100) Integration patterns/external services: migration + DDL toolchain interaction not fully specified. Evidence: E5, E7.

- ✓ PASS (L104) Loaded previous story file (6.2-P12) for context.
- ✓ PASS (L105) Extracted actionable intelligence (notably “no new frameworks”, back-compat, deterministic tooling mindset). Evidence: E18.
- ✓ PASS (L106) Dev notes/learnings: reviewed P12 constraints as relevant to P13’s tooling changes. Evidence: E18.
- ⚠ PARTIAL (L107) Review feedback/corrections: story does not incorporate explicit retrospective notes; add “Learnings” section if any. (No evidence present in story.)
- ✓ PASS (L108) Files/patterns reviewed (SQL module, DDL generator, migration runner). Evidence: E5, E6, E12.
- ✓ PASS (L109) Testing approaches reviewed (unit vs integration; migration runner). Evidence: E12, E15.
- ➖ N/A (L110) Problems encountered/solutions found: not available in artifacts loaded.
- ✓ PASS (L111) Code conventions established via repo artifacts (migration naming, SQL module, ruff/mypy paths). Evidence: E4, E15.

- ✓ PASS (L115) Git history analyzed (recent commits) for relevant patterns.
- ✓ PASS (L116) Files created/modified: identified SQL module story and related migrations in history.
- ✓ PASS (L117) Conventions used: existing migrations naming, story numbering patterns.
- ✓ PASS (L118) Dependency changes: validated key libs are already present.
- ✓ PASS (L119) Architecture decisions: identified “SQL Generation Module” as prior decision context. Evidence: E6.
- ✓ PASS (L120) Testing approaches used: pytest + structure per docs/pyproject. Evidence: E15.

- ✓ PASS (L124) Identified libraries/frameworks mentioned/required (Pandera, Pydantic v2, Alembic, SQLAlchemy).
- ✓ PASS (L125) Investigated version requirements via `pyproject.toml` constraints. Evidence: E15.
- ⚠ PARTIAL (L126) Breaking/security updates: not researched beyond repo constraints.
- ⚠ PARTIAL (L127) Performance/deprecations: not researched beyond repo constraints.
- ✓ PASS (L128) Best practices aligned with current repo patterns (reuse `infrastructure/sql`, avoid new frameworks).

### Step 3: Disaster Prevention
Pass Rate: 20/20 (100%) — gaps identified in Critical Issues and Failed/Partial lists.

- ✓ PASS (L136) Wheel reinvention gaps identified (SQL generation + DDL generator overlap). Evidence: E5, E6.
- ✓ PASS (L137) Code reuse opportunities identified (use SQL module; extend `generate_from_json` or replace with shared registry). Evidence: E5, E6.
- ✓ PASS (L138) Existing solutions to extend identified (migration_runner + existing migration naming). Evidence: E12, E4.

- ✓ PASS (L142) Wrong-lib disasters checked (no new deps required; align to pinned libs). Evidence: E15.
- ✓ PASS (L143) API contract disasters assessed (no API surface).
- ✓ PASS (L144) DB schema conflicts flagged (PK rename + conditional create needs detailed plan). Evidence: E10.
- ✓ PASS (L145) Security gaps assessed (N/A but ensure no secrets/logging changes).
- ✓ PASS (L146) Performance gaps assessed (N/A but avoid heavy reflection at runtime).

- ✓ PASS (L150) Wrong file locations flagged (domain_registry path consistency). Evidence: E3, E12.
- ✓ PASS (L151) Coding standard considerations flagged (ruff/mypy paths; keep in `src/work_data_hub/`). Evidence: E15.
- ✓ PASS (L152) Integration pattern risks flagged (scripts/create_table vs migrations). Evidence: E5, E2.
- ✓ PASS (L153) Deployment failure risks flagged (migration sequencing / environment readiness). Evidence: E2, E10.

- ✓ PASS (L157) Breaking change risks flagged (PK rename, DDL deprecation). Evidence: E10.
- ✓ PASS (L158) Test failure risks flagged (need targeted tests for registry + migrations). Evidence: E7, E12.
- ✓ PASS (L159) UX violations assessed (N/A).
- ✓ PASS (L160) Learning failures flagged (missing prior work reuse). Evidence: E6.

- ✓ PASS (L164) Vague implementation gaps flagged (IndexDef shape, “conditional create” technique). Evidence: E7, E9.
- ✓ PASS (L165) Completion-lie vectors flagged (placeholders; ready status). Evidence: E14, E1.
- ✓ PASS (L166) Scope creep risks flagged (story bundles 4 phases + validation). Evidence: E7, E9.
- ✓ PASS (L167) Quality failure risks flagged (needs tighter DoD, sequencing, tests). Evidence: E7.

### Step 4: LLM Optimization
Pass Rate: 10/10 (100%) — optimization gaps and remedies identified below.

- ✓ PASS (L175) Verbosity assessment performed.
- ✓ PASS (L176) Ambiguity assessment performed.
- ✓ PASS (L177) Context overload assessment performed.
- ✓ PASS (L178) Missing-signal assessment performed.
- ✓ PASS (L179) Structure assessment performed.

- ✓ PASS (L183) Clarity-over-verbosity principle applied in recommendations.
- ✓ PASS (L184) Actionable-instruction gaps identified.
- ✓ PASS (L185) Scannability improvements recommended.
- ✓ PASS (L186) Token efficiency improvements recommended.
- ✓ PASS (L187) Unambiguous language gaps highlighted.

### Step 5: Recommendations
Pass Rate: 15/15 (100%) — see “Recommendations” at end.

- ✓ PASS (L195) Identified missing essential technical requirements (reuse existing tooling).
- ✓ PASS (L196) Identified missing previous story context (SQL module + DDL generator patterns).
- ✓ PASS (L197) Identified missing anti-pattern prevention (explicit “do not create new SQL builder”).
- ✓ PASS (L198) Identified missing security/performance requirement handling (explicit N/A + guardrails).

- ✓ PASS (L202) Added architectural guidance recommendations.
- ✓ PASS (L203) Added technical specification improvements.
- ✓ PASS (L204) Added code reuse opportunities.
- ✓ PASS (L205) Added testing guidance.

- ✓ PASS (L209) Performance suggestions provided (avoid runtime reflection; keep generation offline).
- ✓ PASS (L210) Added context suggestions (epic alignment + approval gating).
- ✓ PASS (L211) Added debugging/dev tips suggestions.

- ✓ PASS (L215) Token-efficient phrasing recommendations included.
- ✓ PASS (L216) Clearer structure recommendations included.
- ✓ PASS (L217) More actionable instruction recommendations included.
- ✓ PASS (L218) Reduced verbosity suggestions included.

### Success Metrics
Pass Rate: 11/11 (100%) — used as evaluation lens for improvements.

- ✓ PASS (L228) Identified missing essential technical requirements.
- ✓ PASS (L229) Identified missing previous story learnings.
- ✓ PASS (L230) Identified missing anti-pattern prevention.
- ✓ PASS (L231) Identified missing security/performance requirements (explicitly N/A but should be stated).

- ✓ PASS (L235) Identified needed architecture guidance.
- ✓ PASS (L236) Identified missing technical specs.
- ✓ PASS (L237) Identified code reuse opportunities.
- ✓ PASS (L238) Identified improved testing guidance.

- ✓ PASS (L242) Identified perf/efficiency improvements.
- ✓ PASS (L243) Identified workflow optimizations (`uv run`, migration runner usage).
- ✓ PASS (L244) Identified additional complex-scenario context to add.

### Interactive Improvement Process
Pass Rate: 0/4 (0%) — pending user choice (next step outside this report).

- ⚠ PARTIAL (L305) Load story file: already loaded, but edits not applied yet (awaiting user selection).
- ⚠ PARTIAL (L306) Apply accepted changes: pending.
- ⚠ PARTIAL (L307) Do not reference review process: will be enforced when editing.
- ⚠ PARTIAL (L308) Ensure clean coherent final story: pending.

### Competitive Excellence Mindset (Outcome Check)
Pass Rate: 0/17 (0%) — story currently does not meet the “developer-mistake-proof” bar.

- ✗ FAIL (L334) Clear technical requirements: missing explicit reuse constraints + migration naming conventions. Evidence: E5, E4, E7.
- ⚠ PARTIAL (L335) Previous work context: partial references exist, but misses key prior modules. Evidence: E6.
- ✗ FAIL (L336) Anti-pattern prevention: not explicit about *not* re-implementing existing generators. Evidence: E5, E6.
- ⚠ PARTIAL (L337) Comprehensive guidance: tasks are listed, but sequencing and risk plan are insufficient. Evidence: E10.
- ⚠ PARTIAL (L338) Optimized structure: scannable, but overly broad (4 phases + validation) for a single story. Evidence: E9.
- ⚠ PARTIAL (L339) Actionable instructions: mostly actionable, but some requirements are placeholders (`YYYYMMDD_*`). Evidence: E9.
- ⚠ PARTIAL (L340) Efficient information density: some duplication (counts differ; fragmentation tables differ). Evidence: E19, E20.

- ✗ FAIL (L344) Prevent reinvention: not achieved (see Critical Issue #2). Evidence: E5, E6.
- ✗ FAIL (L345) Prevent wrong approaches: missing explicit do/don’t constraints.
- ✗ FAIL (L346) Prevent duplicate functionality: not achieved (schema generation duplication risk). Evidence: E5, E7.
- ✗ FAIL (L347) Prevent missing critical requirements: approval gate + migration naming conventions missing.
- ✗ FAIL (L348) Prevent implementation errors: conditional-create + PK rename not fully specified. Evidence: E10.

- ✗ FAIL (L352) Ambiguity: epic association + scope boundaries ambiguous. Evidence: E13, E17.
- ✗ FAIL (L353) Token waste: story includes long multi-phase task lists and duplicates without clear sprint boundary.
- ✗ FAIL (L354) Critical info buried: “do not reinvent” constraints not present.
- ✗ FAIL (L355) Confusing structure: missing standard story header metadata and ends with empty “File List”. Evidence: E14.
- ✗ FAIL (L356) Miss key signals: migration naming conventions + existing tool reuse not surfaced. Evidence: E4, E5, E6.

## Failed Items (✗) — With Recommendations

1. (L11) Add explicit **Reuse Existing Tooling** section:
   - Reuse `src/work_data_hub/infrastructure/sql/` (Story 6.2-P10).
   - Reuse/extend `scripts/create_table/generate_from_json.py` (or explicitly deprecate it with a migration plan).
2. (L17) Change story **Status** to `review` (or `blocked`) until Sprint Change Proposal approval; remove `ready-for-dev` claim.
3. (L18) Add “Prior Art / Existing Modules” section listing concrete files and what to reuse.
4. (L82, L83, L86) Add `**Epic:** ...` and cross-story dependencies (approval gate, sequencing with existing migrations/scripts).
5. (L334, L336, L344-L348, L352-L356) Add explicit **anti-pattern prevention** and **non-negotiable constraints** up front.

## Partial Items (⚠) — What’s Missing

- (L12) Reference `pyproject.toml` versions for Pandera/Pydantic/Alembic and note “no new deps”.
- (L13) Fix paths: use `src/work_data_hub/io/schema/domain_registry.py` (not `io/schema/domain_registry.py`).
- (L14) Split PK rename into a separate story or add a full migration plan (constraints, sequences, backfill, rollback).
- (L53, L68, L80, L81) Replace missing “epics.md” with explicit epic reference: which epic owns this change and why.
- (L99, L100) Add deployment/rollout notes: dev/staging/prod sequencing + how to handle existing tables.
- (L126, L127) Optional: add a “Version Notes” mini-section (no web research required; just cite repo constraints).
- (L305-L308) Await user selection to apply improvements.
- (L335, L337-L340) Remove duplicates, tighten scope, and fix inconsistent counts.

## Recommendations (Consolidated)

1. **Must Fix (blocking):**
   - Add standard story header (`Epic`, `Type`, `Priority`, `Status`, `Created`, `Sprint Change Proposal`).
   - Set status to `review`/`blocked` until proposal approval.
   - Add “Existing Solutions to Reuse” (SQL module + DDL generator + migration runner + migration naming conventions).
   - Fix file paths and migration filename patterns to match repo.
   - Split Phase 3 PK rename into a separate story or explicitly defer it.
   - Remove placeholders and complete the “File List” section.

2. **Should Improve:**
   - Define `IndexDef` (name, columns, unique, method, where) or equivalent to make registry/generation precise.
   - Clarify “Conditional Create Strategy” for Alembic with concrete approach (inspect + create vs raw SQL).
   - Add explicit “Out of scope” to keep this to one sprint story.

3. **Consider:**
   - Reduce duplicated narrative (316 vs 322 lines; 5 vs 6 fragmentation locations) by aligning to the Sprint Change Proposal.
   - Add `uv run` command examples for tests and migration verification (per `docs/project-context.md`).

---

## Evidence Appendix

E1 — Story header/status shows inconsistent key + ready state  
From `docs/sprint-artifacts/stories/6.2-p13-unified-domain-schema-management.md`:
- L1: `# Story 6.2.P13: Unified Domain Schema Management Architecture`
- L3: `Status: ready-for-dev`

E2 — Sprint Change Proposal is pending approval and frames epic impact as Epic 7+  
From `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-18-unified-schema-management.md`:
- L3-L6: `**Status:** Pending Approval`
- L63-L66: `| **Epic 7+** | ... | **Direct** | ... |`

E3 — AC points to `io/schema/domain_registry.py` (path ambiguity)  
From story:
- L47: `**AC-0.1**: \`io/schema/domain_registry.py\` 创建完成...`

E4 — Existing migration naming pattern includes timestamp segment  
From directory `io/schema/migrations/versions/` (examples):
- `20251129_000001_create_annuity_performance_new.py`
- `20251212_120000_add_reference_tracking_fields.py`

E5 — Existing DDL generator script already exists and encodes conventions  
From `scripts/create_table/generate_from_json.py`:
- L1-L13: module purpose + conventions (including `DROP TABLE IF EXISTS` and `{entity}_id` primary key)

E6 — Existing centralized SQL generation module exists and has design principles  
From `docs/brownfield-architecture.md`:
- L162: `### SQL Generation Module (\`src/work_data_hub/infrastructure/sql/\`)`
- L172-L177: design principles (quoting, schema qualification, dialect abstraction, testability)

E7 — Story requires new `generate_create_table_sql()` (potential overlap)  
From story:
- L59-L62: helper methods include `generate_create_table_sql(domain_name) -> str`

E8 — Story proposes migration names that don’t match repo convention  
From story:
- L106-L109: `io/schema/migrations/versions/YYYYMMDD_create_*.py`

E9 — Story bundles Phase 3 PK rename + broad scope  
From story:
- L104-L117: Phase 3 migration unification + PK rename + conditional create

E10 — PK rename impacts existing DDL conventions and requires careful migration plan  
From `scripts/create_table/ddl/annuity_performance.sql`:
- `annuity_performance_id` is the current identity primary key (see top of file)

E11 — “SQL-Generation-Module” anchor referenced may not exist as written  
From story:
- L301: `[Source: docs/brownfield-architecture.md#SQL-Generation-Module]` (heading exists, but not an explicit anchor label)

E12 — Migration runner shows Alembic script location is root `io/schema/migrations`  
From `src/work_data_hub/io/schema/migration_runner.py`:
- `MIGRATIONS_DIR = PROJECT_ROOT / "io" / "schema" / "migrations"`

E13 — Neighbor story format baseline includes standard metadata fields  
From `docs/sprint-artifacts/stories/6.2-p12-domain-comparison-framework.md`:
- Contains `**Epic**`, `**Status**`, `**Priority**`, `**Created**`, `**Sprint Change Proposal**` near top.

E14 — Story contains template placeholder and ends incomplete  
From story:
- L309: `{{agent_model_name_version}}`
- L321-L322: `### File List` with no content

E15 — Versions/deps are pinned in repo  
From `pyproject.toml`:
- L11-L16: `pandera>=0.18.0,<1.0`, `pydantic>=2.11.7`, `alembic`, `sqlalchemy>=2.0`
- L38-L43: pytest/ruff/mypy in dev deps

E16 — Workflow expects `docs/epics.md` but it is missing  
From `_bmad/.../workflow.yaml` and repo structure:
- `epics_file: "{output_folder}/epics.md"` (resolved to `docs/epics.md`) is not present.

E17 — Sprint Change Proposal indicates epic impact is not “Epic 6.2”  
From proposal:
- L63-L66: impact table points to “Epic 7+” direct.

E18 — Previous story constraints emphasize “no new frameworks” and compatibility  
From P12 story:
- “No new dependencies / frameworks” and “No capability regressions” in Hard Constraints.

E19 — Fragmentation count differs between story and proposal  
From story:
- L24-L33: “(6 Locations)” includes `manifest.yml` and “Alembic migrations”

E20 — Proposal lists 5 fragmentation locations (separate from manifest)  
From proposal:
- L32-L40: fragmentation table contains 5 rows (DDL, migrations, models, schemas, constants)

