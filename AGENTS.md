# AGENTS.md

This file is a README for agents. It gives any AI coding assistant a predictable, minimal set of rules and commands to work effectively in this repository.

## Development Tips

- **Package Management:** `uv` for all dependency and virtual environment management.
- **WSL**: `source .venv_linux/bin/activate`; **PowerShell**: `.\.venv\Scripts\Activate.ps1`; **CMD**: `.\.venv\Scripts\activate.bat`.
- Use `uv` for everything: `uv venv && uv sync` to set up; run tools via `uv run ...`.
- Search fast: prioritize using MCP Serena. As an alternative, prefer `rg` (ripgrep) over `grep/find` for code and files.
- Keep changes small and focused; follow existing patterns and conventions.

## PRP Workflow (Plan → Execute → Prove)

We use a PRP (Product Requirements Prompt) workflow to produce high‑quality, repeatable changes.

1) Prepare INITIAL.md (Definition of Ready)
   - Define the feature and boundaries (non‑goals).
   - Add concrete examples: existing files, code snippets, or patterns to follow.
   - Link precise external docs (URLs, sections) and internal standards (file paths).
   - Do more web searches and codebase exploration as needed; Use `gemini -p "your requirements"` for web searches. You should express your requirements clearly in natural language, for example: `gemini -p "Please search online for 'best practices for python dependency injection'."`
   - Note integration points: data models, APIs, migrations, configs.
   - Call out gotchas: library quirks, rate limits, concurrency/timeouts, version traps.
   - Include validation commands and expected outcomes.
   - Start from template: `PRPs/templates/INITIAL.template.md`

2) Generate PRP
   - If your assistant supports slash commands: `/generate-prp INITIAL.md` (see `.claude/commands/generate-prp.md`).
   - Otherwise: open `.claude/commands/generate-prp.md`, copy the instructions into a prompt, and provide `INITIAL.md` as context.
   - Output file: `PRPs/<feature-name>.md`.

3) Execute PRP
   - If supported: `/execute-prp PRPs/<feature-name>.md` (see `.claude/commands/execute-prp.md`).
   - Otherwise: follow the PRP plan step‑by‑step; implement code, then run validation gates.

4) Validation Gates (Definition of Done)
   - All checks must pass before marking complete:
     - `uv run ruff check src/ --fix`
     - `uv run mypy src/`
     - `uv run pytest -v`
   - Add/adjust tests so critical paths are covered; fix failures, re‑run gates to green.
   - Update documentation impacted by the change.

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

- `INITIAL.md`: Seed file for PRP with feature, examples, docs, gotchas, validation.
- `PRPs/`: Stores generated PRP files (implementation blueprints).
- `.claude/commands/generate-prp.md`: How to generate a PRP from INITIAL.md.
- `.claude/commands/execute-prp.md`: How to execute a PRP and validate.
- `CLAUDE.md`: Project‑specific rules (style, structure, tooling, search, DB/API standards).

## Assistant Notes

- If your assistant supports custom commands, prefer the commands above; otherwise copy the command file contents into your prompt with the appropriate arguments.
- Keep instructions concrete and runnable; prefer the shortest viable commands.
- Ask for clarification when requirements are ambiguous; do not guess.
