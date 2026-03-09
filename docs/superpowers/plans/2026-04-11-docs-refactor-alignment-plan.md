# Docs Refactor And Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `docs/` so repository documentation matches the current codebase, active domains, CLI surface, and operational workflows.

**Architecture:** Treat code/config/tests as the source of truth, then rebuild the documentation layer around a small stable information architecture. Deliver the work in stages: fix entry points and broken links first, then restore missing domain/runbook contracts, then archive stale material and add automated guardrails so drift becomes visible in CI instead of in production.

**Tech Stack:** Markdown, PowerShell, `rg`, Python 3.10+, `pytest`, repository CLI entry points in `src/work_data_hub/cli`, config in `config/data_sources.yml`

---

## File Map

### Existing Files That Must Be Audited Or Modified

- `README.md`
- `docs/deployment_run_guide.md`
- `docs/deployment_run_guide_intranet.md`
- `docs/context-engineering/documentation-standards.md`
- `docs/guides/index.md`
- `docs/cleansing-rules/index.md`
- `docs/runbooks/annuity_performance.md`
- `config/data_sources.yml`
- `src/work_data_hub/domain/registry.py`
- `src/work_data_hub/cli/__main__.py`
- `src/work_data_hub/cli/etl/main.py`
- `tests/integration/test_annuity_config.py`

### New Files To Create

- `docs/index.md`
- `docs/domains/annuity_performance.md`
- `docs/domains/annuity_income.md`
- `docs/domains/annual_award.md`
- `docs/domains/annual_loss.md`
- `docs/domains/sandbox_trustee_performance.md`
- `docs/runbooks/annuity_income.md`
- `docs/runbooks/annual_award.md`
- `docs/runbooks/annual_loss.md`
- `docs/runbooks/sandbox_trustee_performance.md`
- `docs/archive/README.md`
- `docs/reference/README.md`
- `scripts/quality/check_docs_alignment.py`
- `tests/integration/test_domain_docs_complete.py`
- `tests/smoke/test_docs_alignment.py`

### Directories To Create Or Normalize

- `docs/domains/`
- `docs/archive/`
- `docs/reference/`

---

### Task 1: Establish The Target Documentation Architecture

**Files:**
- Create: `docs/index.md`
- Create: `docs/archive/README.md`
- Create: `docs/reference/README.md`
- Modify: `docs/guides/index.md`
- Modify: `docs/cleansing-rules/index.md`

- [ ] **Step 1: Capture the current inventory before moving anything**

Run:

```powershell
Get-ChildItem docs -Recurse -File | Select-Object FullName, LastWriteTime
rg -n "docs/" README.md docs src tests scripts .github
```

Expected: a complete list of current documents plus all in-repo `docs/...` references.

- [ ] **Step 2: Record the active-domain baseline before restructuring docs**

Run:

```powershell
rg -n "sandbox_trustee_performance:|annuity_performance:|annuity_income:|annual_award:|annual_loss:" config/data_sources.yml
rg -n 'register_domain\("annuity_performance"|register_domain\("annuity_income"|register_domain\("sandbox_trustee_performance"|register_domain\("annual_award"|register_domain\("annual_loss"' src/work_data_hub/domain/registry.py
```

Expected: the same five active ETL domains appear in both config and registry before any doc changes begin.

- [ ] **Step 3: Write the new top-level navigation document**

Create `docs/index.md` with this structure:

```md
# WorkDataHub Documentation

## Start Here
- [Repository Overview](../README.md)
- [Developer Guides](./guides/index.md)
- [Domain Documentation](./domains/)
- [Runbooks](./runbooks/)

## Architecture And Reference
- [Reference Notes](./reference/README.md)
- [Cleansing Rules](./cleansing-rules/index.md)
- [Business Background](./business-background/)

## Historical Material
- [Archive](./archive/README.md)
```

- [ ] **Step 4: Define what belongs in active docs vs archive**

Add this policy to `docs/archive/README.md`:

```md
# Archive Policy

Archive a document only when at least one of these is true:

- it is a one-off report, retrospective, or validation artifact
- it is superseded by a current active document
- it references repository paths or workflows that no longer exist
- it has no inbound links from `README.md`, active docs, tests, CI, `src/`, or `scripts/`
- it has not been materially verified in the last 6 months

Do not archive:
- active domain contracts
- active runbooks
- current deployment guides
- documentation referenced by tests or CI
```

- [ ] **Step 5: Reframe `docs/reference/README.md` as a stable bucket for technical reference**

Use this content:

```md
# Reference Documentation

This directory stores current technical reference material that supports implementation and operations but is not the primary onboarding path.

Typical contents:
- schema panoramas
- data-processing reference
- reusable architecture patterns that still match current code
```

- [ ] **Step 6: Update section indexes so they point at the new structure**

Edit:

- `docs/guides/index.md` to link `docs/index.md`, `docs/domains/`, and `docs/runbooks/`
- `docs/cleansing-rules/index.md` to remove dead legacy links and clarify which domains are active vs pending

- [ ] **Step 7: Verify the new IA is internally consistent**

Run:

```powershell
rg -n "docs/(index|archive|reference|domains|runbooks)" docs
```

Expected: the new top-level navigation is referenced only by real paths.

---

### Task 2: Fix Entry-Point Docs And Broken Contract Links

**Files:**
- Modify: `README.md`
- Modify: `docs/deployment_run_guide.md`
- Modify: `docs/deployment_run_guide_intranet.md`
- Modify: `docs/context-engineering/documentation-standards.md`

- [ ] **Step 1: Replace dead README links with live targets**

Current broken references include:

```text
docs/architecture/infrastructure-layer.md
docs/architecture-boundaries.md
docs/database-migrations.md
docs/sprint-artifacts/sprint-status.yaml
```

Update `README.md` so each link either:

- points to an existing document, or
- is removed until a real replacement exists.

- [ ] **Step 2: Align deployment guides with the actual ETL CLI**

Use `src/work_data_hub/cli/etl/main.py` and `src/work_data_hub/cli/__main__.py` as the source of truth.

Replace examples like:

```bash
python -m work_data_hub.cli etl --domain annuity_performance --period 202411 --execute
```

With:

```bash
python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute
```

Also update the parameter table so it documents `--domains`. Verify whether any alias exists before documenting it; do not assume `--domain` remains supported.

- [ ] **Step 3: Rewrite documentation standards for this repository instead of generic API examples**

`docs/context-engineering/documentation-standards.md` must be rewritten around repository realities:

- Markdown docs
- domain docs
- runbooks
- CLI examples
- verification dates
- source-of-truth links to code/config/tests

Remove FastAPI-specific sample content entirely.

- [ ] **Step 4: Add a required metadata block to operational docs**

Insert this header pattern into active runbooks and deployment guides:

```md
> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations
```

- [ ] **Step 5: Verify no active entry-point doc points at a missing file**

Run:

```powershell
$refs = rg -o --no-filename 'docs/[^` )\]\("''"]+\.(md|yaml|yml|csv)' README.md docs src tests scripts .github | Sort-Object -Unique
foreach ($ref in $refs) {
  $path = $ref -replace '/', '\'
  if (-not (Test-Path $path)) { $ref }
}
```

Expected: zero missing paths for active references after cleanup.

---

### Task 3: Restore Domain Documentation Coverage For Active Domains

**Files:**
- Create: `docs/domains/annuity_performance.md`
- Create: `docs/domains/annuity_income.md`
- Create: `docs/domains/annual_award.md`
- Create: `docs/domains/annual_loss.md`
- Create: `docs/domains/sandbox_trustee_performance.md`
- Create: `tests/integration/test_domain_docs_complete.py`

- [ ] **Step 1: Reconfirm the active-domain list from code and config before writing docs**

Run:

```powershell
rg -n "sandbox_trustee_performance:|annuity_performance:|annuity_income:|annual_award:|annual_loss:" config/data_sources.yml
rg -n 'register_domain\("annuity_performance"|register_domain\("annuity_income"|register_domain\("sandbox_trustee_performance"|register_domain\("annual_award"|register_domain\("annual_loss"' src/work_data_hub/domain/registry.py
```

Expected: the same five active ETL domains appear in both config and registry.

- [ ] **Step 2: Use one repeatable domain-doc template for every active ETL domain**

Every file in `docs/domains/` must contain these sections:

```md
# <domain>

## Overview
## Inputs
## File Discovery And Sheet Selection
## Transformation And Validation
## Output Tables
## CLI And Operational Entry Points
## Configuration
## Verification
## Related Runbooks And Rules
```

- [ ] **Step 3: Fill each domain doc from concrete repository sources**

For each domain, cite and align with:

- `config/data_sources.yml`
- matching domain module under `src/work_data_hub/domain/<domain>/`
- ETL CLI behavior in `src/work_data_hub/cli/etl/`
- runbook path in `docs/runbooks/`

The `Verification` section must include at least one real command, for example:

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --dry-run
```

- [ ] **Step 4: Add a dedicated domain-document completeness test instead of broadening the annuity config test scope**

Keep `tests/integration/test_annuity_config.py` focused on annuity configuration and annuity-specific documentation requirements.

Create `tests/integration/test_domain_docs_complete.py` to verify:

- active domain doc exists for every active ETL domain
- runbook exists for every operational ETL domain
- required sections exist in every active domain doc
- required runbook sections exist in every active runbook

- [ ] **Step 5: Run the doc-contract test**

Run:

```powershell
PYTHONPATH=src uv run pytest tests/integration/test_annuity_config.py -v
PYTHONPATH=src uv run pytest tests/integration/test_domain_docs_complete.py -v
```

Expected: PASS, with documentation existence and required-section checks succeeding.

---

### Task 4: Restore Runbook And Cleansing-Rule Coverage

**Files:**
- Create: `docs/runbooks/annuity_income.md`
- Create: `docs/runbooks/annual_award.md`
- Create: `docs/runbooks/annual_loss.md`
- Create: `docs/runbooks/sandbox_trustee_performance.md`
- Modify: `docs/runbooks/annuity_performance.md`
- Modify: `docs/cleansing-rules/index.md`
- Modify: `docs/cleansing-rules/annuity-performance.md`
- Modify: `docs/cleansing-rules/annuity-income.md`

- [ ] **Step 1: Normalize the runbook contract for active ETL domains**

Each runbook must contain:

```md
## Preconditions
## Manual Execution
## Common Errors
## Verification
## Rollback Or Safe Re-run
```

- [ ] **Step 2: Reconcile each runbook with the actual command surface**

Commands must come from current CLI modules and should use the real environment pattern:

```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains <domain> --period <YYYYMM> --dry-run
```

- [ ] **Step 3: Reclassify cleansing-rule docs as active, partial, or missing**

Update `docs/cleansing-rules/index.md` so the table distinguishes:

- `Active and verified`
- `Present but partial`
- `Missing`
- `Historical only`

The index must stop linking to deleted `legacy/` locations unless those links are explicitly marked historical.

- [ ] **Step 4: Add cross-links between domain docs, runbooks, and cleansing rules**

Each active domain doc should link to:

- its runbook
- its cleansing rules doc if present
- the relevant CLI entry point

Each runbook should link back to the domain doc.

- [ ] **Step 5: Re-run targeted link checks**

Run:

```powershell
rg -n "docs/domains/|docs/runbooks/|docs/cleansing-rules/" docs tests src
```

Expected: only live, normalized paths remain for active domains.

---

### Task 5: Archive Or Re-home Historical Material

**Files:**
- Modify: `docs/initial/implementation-readiness-report-2025-11-09.md`
- Modify: `docs/deprecations/company_master_table_deprecation.md`
- Modify: specific files under `docs/architecture-patterns/` identified in Task 5 Step 1

- [ ] **Step 1: Build a list of historical docs that still point to deleted structures**

Run:

```powershell
rg -n "docs/(PRD|architecture|epics|sprint-artifacts|specific|brownfield-architecture|bmm-index)" docs
Get-ChildItem docs/architecture-patterns -File | Select-Object -ExpandProperty Name
```

Expected: a bounded list of historical references plus an explicit inventory of `docs/architecture-patterns/` files for file-by-file disposition.

- [ ] **Step 2: Mark historical documents explicitly**

Add this banner to files that are kept only for traceability:

```md
> Historical document.
> This file is retained for context and may reference paths or structures that no longer exist in the active repository layout.
```

- [ ] **Step 3: Move only genuinely active technical references into `docs/reference/`**

Candidates to evaluate explicitly include:

- `docs/database-schema-panorama.md`
- `docs/data_processing_guide.md`
- each concrete file listed from `docs/architecture-patterns/`

Do not move them until inbound links are updated in the same change.

- [ ] **Step 4: Create a rollback path before any file move or archive operation**

Before moving or renaming docs:

- capture a pre-move inventory with paths
- perform moves in a dedicated commit using `git mv` where possible
- record old path -> new path mapping in the PR description or implementation notes

Rollback path:

- revert the move commit if links/tests fail
- restore old inbound links before retrying structure changes

- [ ] **Step 5: Remove archive material from onboarding paths**

Ensure `README.md`, `docs/index.md`, and `docs/guides/index.md` do not route new contributors into `docs/initial/` or one-off validation reports.

- [ ] **Step 6: Verify archive isolation**

Run:

```powershell
rg -n "docs/initial/|docs/archive/" README.md docs/index.md docs/guides/index.md
```

Expected: archive links appear only in explicit historical sections.

- [ ] **Step 7: Verify obsolete references were removed, not just shadowed by new files**

Run:

```powershell
$refs = rg -o --no-filename 'docs/[^` )\]\("''"]+\.(md|yaml|yml|csv)' README.md docs src tests scripts .github | Sort-Object -Unique
foreach ($ref in $refs) {
  $path = $ref -replace '/', '\'
  if (-not (Test-Path $path)) { $ref }
}
```

Expected: no dead links remain after archival, moves, and deletions.

---

### Task 6: Add Automated Documentation Drift Detection

**Files:**
- Create: `scripts/quality/check_docs_alignment.py`
- Create: `tests/smoke/test_docs_alignment.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Implement a lightweight docs-alignment checker**

Create `scripts/quality/check_docs_alignment.py` with these checks:

```python
from pathlib import Path

ACTIVE_DOMAINS = {
    "annuity_performance",
    "annuity_income",
    "annual_award",
    "annual_loss",
    "sandbox_trustee_performance",
}

def require(path: str) -> None:
    if not Path(path).exists():
        raise SystemExit(f"missing required doc: {path}")

for domain in ACTIVE_DOMAINS:
    require(f"docs/domains/{domain}.md")
    require(f"docs/runbooks/{domain}.md")
```

Extend it to fail on broken `docs/...` references discovered in `README.md`, `docs/`, `src/`, `tests/`, and `scripts/`.

- [ ] **Step 2: Add a smoke test wrapper**

Create `tests/smoke/test_docs_alignment.py`:

```python
import subprocess
import sys

def test_docs_alignment_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/quality/check_docs_alignment.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
```

- [ ] **Step 3: Register the command in local verification flow**

Add this command to the documentation standards or contributor docs:

```bash
PYTHONPATH=src uv run python scripts/quality/check_docs_alignment.py
```

- [ ] **Step 4: Run the drift checks locally**

Run:

```powershell
PYTHONPATH=src uv run python scripts/quality/check_docs_alignment.py
PYTHONPATH=src uv run pytest tests/smoke/test_docs_alignment.py -v
```

Expected: both commands PASS and emit no missing-document failures.

- [ ] **Step 5: Wire the checker into CI**

The repository currently uses `runs-on: ubuntu-latest`, so add one CI step using the existing bash/uv pattern:

```bash
PYTHONPATH=src uv run python scripts/quality/check_docs_alignment.py
```

Expected: future doc drift fails CI instead of lingering silently.

---

## Maintenance Rules

These rules must be codified in `docs/context-engineering/documentation-standards.md` and referenced from `README.md` or `docs/index.md`.

- [ ] Every change that alters domain behavior, CLI parameters, config schema, database workflow, or operator procedure must update the matching docs in the same PR.
- [ ] `README.md` may link only to active, stable documents.
- [ ] Domain docs are required for every active ETL domain defined in both `config/data_sources.yml` and `src/work_data_hub/domain/registry.py`.
- [ ] Runbooks are required for every domain that can be executed manually through the repository CLI.
- [ ] Operational command examples must be copied from real CLI behavior, not written from memory.
- [ ] Every active operational doc must include `Source of truth`, `Last verified`, and `Scope`.
- [ ] Historical docs must be labeled as historical and must not be referenced by tests, CI, or top-level onboarding pages.
- [ ] Broken `docs/...` links are release-blocking failures.
- [ ] The docs-alignment checker must run locally before merge and in CI on every PR.

---

## Verification Checklist

- [ ] `README.md` contains no dead `docs/...` links
- [ ] `docs/index.md` exists and routes to the active sections
- [ ] every active ETL domain has both `docs/domains/<domain>.md` and `docs/runbooks/<domain>.md`
- [ ] active runbooks use current CLI flags such as `--domains`
- [ ] `docs/context-engineering/documentation-standards.md` matches repository reality
- [ ] archive material is labeled and removed from onboarding paths
- [ ] `scripts/quality/check_docs_alignment.py` passes
- [ ] `tests/integration/test_annuity_config.py` passes
- [ ] `tests/integration/test_domain_docs_complete.py` passes
- [ ] `tests/smoke/test_docs_alignment.py` passes
- [ ] obsolete references and intentionally removed files are absent from active inbound links

---

## Self-Review

**Spec coverage:** This plan covers structure normalization, dead-link repair, domain/runbook contract recovery, archival rules, and automated drift detection.

**Placeholder scan:** No `TODO`, `TBD`, or deferred placeholders remain in task steps.

**Consistency check:** Active domain scope is aligned to the same five domains across the plan: `annuity_performance`, `annuity_income`, `annual_award`, `annual_loss`, and `sandbox_trustee_performance`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-11-docs-refactor-alignment-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
