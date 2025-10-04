# AGENTS.md v1.04

This file is a README for agents. It gives any AI coding assistant a predictable, minimal set of rules and commands to work effectively in this repository.

Scope: This guide targets the supporting agent that maintains ROADMAP/README, prepares INITIAL.md, and reviews Claude’s PRP and code. Claude runs the fixed “Generate PRP” and “Execute PRP” flows.

## Development Tips

**CRITICAL** Environment-specific paths: When in a Linux Shell (including WSL), the virtual environment path is ~/.virtualenvs/work-data-hub. Do not make any changes to the project's root .venv directory.

- Package management: use `uv` for all dependencies and virtualenvs.
- Virtualenv usage: prefer `uv run <command>` over manual activation.
- Setup: `uv venv && uv sync`. Run tools via `uv run ...`.
- Search fast: prioritize MCP Serena; otherwise use `rg` (ripgrep) over `grep/find` for code and files.
- Baseline checks (keep green before PRs):
  - Format: `uv run ruff format .`
  - Lint: `uv run ruff check src/ --fix`
  - Types: `uv run mypy src/`
  - Tests: `uv run pytest -v` (focus with `-k <pattern>`)
  - Optional coverage: `uv run pytest --cov=src --cov-report=term-missing`
- Keep changes small and focused; follow existing patterns and conventions.
- Network/tooling constraints: if external search tools or network are unavailable, rely on in-repo docs/code, state assumptions, and proceed incrementally.

## PRP Workflow (Plan → Execute → Prove)

This repository uses a PRP (Product Requirements Prompt) workflow. Claude is responsible for generating and executing PRPs. The agent following this document is responsible for maintaining docs, preparing the INITIAL, and reviewing Claude’s work.

0) Keep ROADMAP and README current (This agent)

- Update ROADMAP.md when tasks are added, re‑scoped, completed, or blocked.
- Reflect any user intent changes or scope clarifications.
- Keep README commands and pointers aligned with current reality.

1) Prepare INITIAL.md (Definition of Ready) — This agent

Using PRPs/templates/INITIAL.template.md as a template:

- Select or create a Task in ROADMAP.md; define boundaries (non‑goals).
- Provide concrete examples: files, code snippets, patterns to follow.
- Link precise docs: external (URLs/sections) and internal standards (file paths).
- Identify integration points: models, ops/jobs, loader, config/`data_sources.yml`.
- Call out risks: library quirks, precision, schedules/sensors behavior, config traps.
- Include validation commands and expected outcomes.
- Optional research if available: use web search judiciously; otherwise rely on repo docs and state assumptions.

Exit criteria for INITIAL.md:

- Clear scope and acceptance criteria, copy‑pastable commands for validation, and explicit constraints/assumptions for Claude to follow.

2) Handoff: Generate PRP — Claude

- If supported: `/generate-prp INITIAL.md` (see `.claude/commands/generate-prp.md`).
- Otherwise: open `.claude/commands/generate-prp.md`, copy the instructions into a prompt, and provide `INITIAL.md` as context.
- Output: `PRPs/<feature-name>.md`.

3) Handoff: Execute PRP — Claude

- If supported: `/execute-prp PRPs/<feature-name>.md` (see `.claude/commands/execute-prp.md`).
- Otherwise: Claude follows the PRP step‑by‑step; implements code, runs validation gates.

4) Review & Validation Gates (Definition of Done) — This agent

- All checks must pass before marking complete:
  - `uv run ruff check src/ --fix`
  - `uv run mypy src/`
  - `uv run pytest -v` (optional coverage: `uv run pytest --cov=src --cov-report=term-missing`)
- Review Claude’s PRP and code:
  - Alignment with INITIAL.md and ROADMAP.md (scope, acceptance criteria).
  - Tests cover critical paths; E2E behavior matches expectations.
  - Docs updated (README/CLAUDE/AGENTS if affected).
- If discrepancies exist: request changes and update ROADMAP.md status accordingly.
- When green: update ROADMAP.md task status and document any flags/migrations.

Notes

- Do not guess requirements. Ask for clarifications when ambiguous.
- Keep instructions and comments runnable and minimal.

## Testing & Linting (Python)

- Lint: `uv run ruff check src/ --fix`
- Type check: `uv run mypy src/`
- Tests: `uv run pytest -v` (use `-k <pattern>` to focus)
- Optional coverage: `uv run pytest --cov=src --cov-report=term-missing`

## Pull Requests

- Branch naming: `feature/<name>`, `fix/<name>`, `docs/<name>`.
- Before commit: run lint, type check, tests locally; keep commits scoped.
- Commit message style: conventional commits (`<type>(<scope>): <subject>`). See `CLAUDE.md` for project specifics.
- PR description: summarize the change, link issues, note any migrations/flags.

## Files to Know

- `ROADMAP.md`: The project’s master plan and dependency graph. Single source of truth for status.
- `README.md`: Quickstart and run commands. Update when stable entry points or commands change.
- `INITIAL.md`: Seed file for PRP with feature, examples, docs, risks, validation.
- `PRPs/`: Stores generated PRP files (implementation blueprints).
- `.claude/commands/generate-prp.md`: How Claude generates a PRP from INITIAL.md.
- `.claude/commands/execute-prp.md`: How Claude executes a PRP and validates.
- `CLAUDE.md`: Project-specific rules (style, structure, tooling, search, orchestration/DB standards).
- `src/work_data_hub/orchestration/repository.py`: Dagster Definitions entry (jobs, schedules, sensors).
- `src/work_data_hub/config/data_sources.yml`: Domain discovery patterns, selection strategies, table/pk.
- `.env.example`: `WDH_*` variables (paths, DB, flags) — do not commit `.env` files.
- `tests/`: E2E and unit tests; fixtures under `tests/fixtures/` for sample data.

## Assistant Notes

- Roles and boundaries:
  - Claude runs the fixed “Generate PRP” and “Execute PRP” flows.
  - This agent maintains ROADMAP/README, prepares INITIAL.md, and reviews Claude’s PRP and code.
- Priorities and constraints:
  - Keep instructions concrete and runnable; prefer the shortest viable commands (`uv run ...`).
  - Search smart: use MCP Serena; otherwise prefer `rg` over `grep/find`.
  - Respect environment limits (no network when restricted); rely on in-repo docs and state assumptions.
- Mandatory pre‑review checklist (before approving work):
  - ROADMAP.md alignment (task, scope, status, dependencies) is correct and updated.
  - Validation gates are green: ruff, mypy, pytest (optional coverage).
  - Docs updated where applicable (README/CLAUDE/AGENTS, configs).
- Do not bypass the PRP workflow or change scope mid‑stream without updating ROADMAP.md and INITIAL.md.
- Ask for clarification when requirements are ambiguous; do not guess.

**CRITICAL**: Before any code review, cross‑reference the changes with their ROADMAP task(s). If discrepancies exist (new tasks, completed work, or scope changes), update ROADMAP.md immediately to keep it as the single source of truth.
