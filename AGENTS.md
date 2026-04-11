# Repository Guidelines

## Project Structure & Module Organization
Runtime code lives in `src/work_data_hub/`. Keep business rules in `domain/`, shared services in `infrastructure/`, external system access in `io/`, Dagster wiring in `orchestration/`, settings in `config/`, entry points in `cli/`, GUI code in `gui/`, and pure helpers in `utils/`. Tests live in `tests/` with `unit/`, `integration/`, `e2e/`, `smoke/`, and `performance/` suites plus shared data under `tests/fixtures/` and helpers under `tests/support/`. Docs live in `docs/`; automation lives in `scripts/`.

## Build, Test, and Development Commands
Use `uv` for dependency and environment management. Install with `uv sync --group dev`. Run Python through `PYTHONPATH=src uv run ...` (PowerShell: `$env:PYTHONPATH='src'; uv run ...`).

- `PYTHONPATH=src uv run pytest -v` runs the default test suite.
- `PYTHONPATH=src uv run pytest -m unit` runs fast unit tests.
- `PYTHONPATH=src uv run pytest -m "integration or postgres"` runs DB-backed tests.
- `PYTHONPATH=src uv run ruff check src/work_data_hub docs` runs lint checks.
- `PYTHONPATH=src uv run ruff format src/work_data_hub docs` formats code and docs.
- `PYTHONPATH=src uv run mypy src/ --strict` enforces strict typing.
- `PYTHONPATH=src uv run python scripts/quality/check_docs_alignment.py` verifies required doc updates.

## Coding Style & Naming Conventions
Target Python 3.10+, 88-character lines, double quotes, trailing commas in multiline literals, and explicit type hints. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes and type aliases; `UPPER_SNAKE_CASE` for constants. Name tests `test_*.py`. Respect clean-architecture boundaries: `domain/` must not import `io/` or `orchestration/`. Add dependencies with `uv add` or `uv remove`; do not edit dependency lists in `pyproject.toml` by hand.

## Testing Guidelines
Prefer `tests/unit/` unless the change requires filesystem, database, Dagster, or end-to-end coverage. Use the configured markers (`unit`, `integration`, `postgres`, `performance`, `legacy_suite`, `e2e_suite`) so suites stay selectable in CI. Keep overall coverage at or above the repo’s 80% gate, and place reusable sample data in `tests/fixtures/`.

## Commit & Pull Request Guidelines
Follow the commit style already in history: `feat(scope): subject`, `fix(etl): ...`, `docs: ...`. Keep scopes specific. PRs should include a clear summary, linked story or issue, commands run, and evidence for behavior changes when relevant (logs, screenshots, or sample outputs). If you change domain behavior, CLI parameters, config schema, database workflow, or operator procedures, update the matching docs in the same PR.

## Agent-Specific Notes
For library, framework, SDK, API, CLI, or cloud-service questions, fetch documentation through Context7 before answering. When editing docs, use repository files as the source of truth.

## Serena Memory Maintenance
Serena memory is not self-refreshing. Its file discovery and symbol lookup may reflect the current repository, but `.serena/memories/` can become stale after repo changes. Agents must treat repository files as the source of truth and refresh Serena memory when durable project facts change.

Update Serena memory after changes to any of the following:
- repository structure or top-level docs layout
- active domains, CLI entry points, or operator workflows
- build, test, lint, mypy, or migration command conventions
- architecture boundaries, coding standards, or completion criteria

At minimum, review and update these memories when relevant:
- `project_overview`
- `code_style_conventions`
- `suggested_commands`
- `task_completion_guidelines`

Use Serena memory tools intentionally:
- `read_memory` before relying on an existing summary
- `write_memory` or `edit_memory` after confirmed repository changes
- keep memories limited to stable, reusable facts; do not store temporary branch state or one-off task notes

Before finishing a task that changes project conventions or structure, verify Serena memory still matches the current repository.
