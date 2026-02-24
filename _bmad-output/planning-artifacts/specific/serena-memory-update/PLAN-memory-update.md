# Implementation Plan: Serena Memory Files Update

> **Created:** 2026-01-30
> **Source:** `.serena/memory-update-recommendations.md`
> **Scope:** Update 4 Serena memory files to align with current project state

---

## Overview

The Serena Memory files contain outdated information that could cause AI agents to generate incorrect code or execute failing commands. This plan updates all 4 memory files to reflect the current project architecture (post-Epic 7 modularization).

---

## Tasks

### Task 1: Update `code_style_conventions.md` (P0 - Critical)

**File:** `.serena/memories/code_style_conventions.md`

**Changes Required:**

1. **Fix file line limit:** Change `500 lines` → `800 lines`
2. **Fix line length:** Change `100 characters` → `88 characters`
3. **Add Ruff PLR complexity rules section:**
   - `max-statements = 50`
   - `max-branches = 12`
4. **Add Pre-commit hooks section**
5. **Add Clean Architecture enforcement section (TID251 rules)**

**Verification:**
- Values match `pyproject.toml` lines 54, 125-126
- TID251 rules documented at lines 118-122

---

### Task 2: Update `suggested_commands.md` (P0 - Critical)

**File:** `.serena/memories/suggested_commands.md`

**Changes Required:**

1. **Fix command pattern:** Add `--env-file .wdh_env` to all `uv run` commands
2. **Add Environment Configuration section** explaining PYTHONPATH requirement
3. **Add complete pytest markers list** (10+ markers from pyproject.toml lines 138-150):
   - unit, integration, postgres
   - eqc_integration, monthly_data, legacy_data
   - e2e, performance
   - legacy_suite, e2e_suite (opt-in)
   - sandbox_domain
4. **Add pre-commit command** to validation gates

**Verification:**
- Commands execute successfully with `--env-file .wdh_env`
- Markers match `pyproject.toml` [tool.pytest.ini_options].markers

---

### Task 3: Update `project_overview.md` (P1 - Medium)

**File:** `.serena/memories/project_overview.md`

**Changes Required:**

1. **Update architecture description** to reflect 6-layer structure:
   - config/, domain/, infrastructure/, io/, orchestration/, customer_mdm/, gui/, cli/, utils/
2. **Update domain layer** to show multi-domain architecture:
   - annuity_performance, annuity_income, annual_award, annual_loss
   - company_enrichment, reference_backfill, sandbox_trustee_performance
   - pipelines/, registry.py
3. **Update tech stack** with missing dependencies:
   - pandera (data validation)
   - playwright, playwright-stealth, opencv-python-headless (web scraping)
   - gmssl (encryption)
   - pyarrow (data interchange)
   - sqlglot, PyMySQL (SQL tools)
   - rich, pyperclip (utilities)
4. **Fix linting line length:** Change `100-char` → `88-char`
5. **Add Domain Registry Pattern description**

**Verification:**
- Architecture matches actual `src/work_data_hub/` structure
- Dependencies match `pyproject.toml` [project].dependencies

---

### Task 4: Update `task_completion_guidelines.md` (P1 - Medium)

**File:** `.serena/memories/task_completion_guidelines.md`

**Changes Required:**

1. **Add pre-commit as mandatory validation gate**
2. **Update pytest markers list** to include all 10+ markers
3. **Add file length validation** (800 lines limit)
4. **Update code review checklist:**
   - Add "88-char line limit" specification
   - Add "File length under 800 lines"
   - Add "Clean Architecture compliance (no domain→io imports)"
5. **Add marker-based testing examples**

**Verification:**
- Checklist items align with `pyproject.toml` Ruff configuration
- Markers match pytest configuration

---

## Execution Order

1. **Task 1** - `code_style_conventions.md` (P0)
2. **Task 2** - `suggested_commands.md` (P0)
3. **Task 3** - `project_overview.md` (P1)
4. **Task 4** - `task_completion_guidelines.md` (P1)

---

## Validation Checklist

After all updates:

- [ ] All line/length limits match `pyproject.toml` (88 chars, 800 lines)
- [ ] All command examples include `--env-file .wdh_env`
- [ ] pytest markers list matches pyproject.toml exactly (10+ markers)
- [ ] Architecture description reflects actual 6-layer structure
- [ ] Tech stack includes all dependencies from pyproject.toml
- [ ] Domain Registry Pattern is documented
- [ ] Clean Architecture rules (TID251) are explained

---

## Reference Documents

- `pyproject.toml` - Source of truth for configuration values
- `docs/project-context.md` - Detailed development standards
- `.serena/memory-update-recommendations.md` - Original analysis
