# INITIAL.md — Milestone 0: Security & Quality Baseline (CI + Secrets Hygiene)

Purpose: Deliver the Security & Quality Baseline per ROADMAP.md Milestone 0. Implement CI (ruff, mypy, pytest), establish a clear secrets policy with environment-based configuration, and provide a `.env.example`. Keep scope tightly focused and non-invasive.

ROADMAP alignment:
- R-001: Research and document secrets policy (env vars, patterns, scanning)
- C-001: Add `.env.example` with required `WDH_*` variables and usage docs
- C-002: Set up GitHub Actions CI (ruff, mypy, pytest)
- C-003: Optional secret scanning (pre-commit/gitleaks) — optional deliverable

Note for Claude: Use uv for environment and tooling — `uv venv && uv sync`; run tools as `uv run ...`.

## FEATURE
Provide a robust CI pipeline and secrets hygiene baseline that: (1) runs ruff, mypy, and tests on PRs/pushes; (2) documents secrets handling with environment variables; (3) supplies a safe `.env.example` for local development; (4) optionally integrates a lightweight secrets scan.

## SCOPE
- In-scope:
  - Add CI workflow at `.github/workflows/ci.yml` with jobs for ruff, mypy, pytest.
  - Ensure CI uses uv to install and run tooling; keep runs fast and deterministic.
  - Create `docs/security/SECRETS_POLICY.md` summarizing env var strategy and do/don’t rules.
  - Add `.env.example` with all required variables and safe defaults; cross-link from docs.
  - Ensure `.env` is ignored by git (confirm/augment `.gitignore`).
  - Tests in CI: run unit/integration tests excluding DB-required tests via marker (`-m "not postgres"`).
  - Optional: add a secrets scanning job (e.g., gitleaks) gated as non-blocking or separate workflow.
- Non-goals:
  - No changes to runtime application logic, database schemas, Dagster assets, or deployment.
  - No production alerting/schedules; those belong to later milestones.

## CONTEXT SNAPSHOT
```bash
ROADMAP.md
.gitignore
pyproject.toml
src/work_data_hub/config/settings.py   # Pydantic BaseSettings with WDH_ prefix
tests/                                 # contains "postgres" marker for DB-required tests
```

## EXAMPLES
- GitHub Actions (uv-based CI) — `.github/workflows/ci.yml`:
```yaml
name: CI
on:
  pull_request:
  push:
    branches: [ main, master ]

jobs:
  build-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install uv
        run: pipx install uv
      - name: Set up venv and sync deps
        run: |
          uv venv
          uv sync
      - name: Ruff
        run: uv run ruff check src/
      - name: Mypy
        run: uv run mypy src/
      - name: Pytest (skip DB-required tests)
        run: uv run pytest -v -m "not postgres"

  # Optional non-blocking secrets scan (enable when desired)
  secrets-scan:
    if: ${{ github.event_name == 'pull_request' || github.ref == 'refs/heads/main' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Gitleaks scan
        uses: gitleaks/gitleaks-action@v2
        with:
          args: "detect --no-git --redact --source=."
```

- `.env.example` (do not include real secrets):
```env
# WorkDataHub — Local development example env (do not commit real secrets)

# Core app
WDH_APP_NAME=WorkDataHub
WDH_DEBUG=false
WDH_LOG_LEVEL=INFO

# Data directories
WDH_DATA_BASE_DIR=./data
WDH_DATA_SOURCES_CONFIG=./src/work_data_hub/config/data_sources.yml

# Database (prefer URI if available)
WDH_DATABASE__HOST=localhost
WDH_DATABASE__PORT=5432
WDH_DATABASE__USER=wdh_user
WDH_DATABASE__PASSWORD=changeme
WDH_DATABASE__DB=wdh
# Alternatively provide a full URI (overrides discrete fields)
# WDH_DATABASE__URI=postgresql://wdh_user:changeme@localhost:5432/wdh
```

- Secrets Policy — `docs/security/SECRETS_POLICY.md` (skeleton):
```md
# Secrets Policy (WorkDataHub)

## Principles
- No plaintext secrets in code, commits, or CI logs.
- Use environment variables with prefix `WDH_` (see `.env.example`).
- Treat `.env` as local-only; keep `.env` git-ignored.

## Storage & Loading
- Local: `.env` managed by developers; never commit.
- CI: Provide secrets via repository/environment secrets; avoid printing values.
- App: Load via Pydantic Settings (`src/work_data_hub/config/settings.py`).

## Reviews & Scans
- Mandatory review for changes touching config or connection strings.
- Optional: run gitleaks locally (`gitleaks detect --redact`) before PR.

## Incident Handling
- If a secret leaks, rotate immediately; purge from history if necessary; document in a short incident note.
```

## DOCUMENTATION
- Pydantic v2 Settings: ensure env prefix `WDH_` is used — `src/work_data_hub/config/settings.py`.
- Ruff CLI: https://docs.astral.sh/ruff/cli/
- Mypy CLI: https://mypy.readthedocs.io/en/stable/command_line.html
- Pytest markers: https://docs.pytest.org/en/stable/example/markers.html
- uv: https://docs.astral.sh/uv/
- Gitleaks (optional): https://github.com/gitleaks/gitleaks

## INTEGRATION POINTS
- `src/work_data_hub/config/settings.py`: Confirm env var names align with `.env.example` (WDH_ prefix; nested `WDH_DATABASE__*`). No code changes required.
- `.gitignore`: Ensure `.env` and other secret files are ignored (add if missing).
- GitHub Actions: Create `.github/workflows/ci.yml` as shown; use `pipx install uv` for portability.
- Tests: Use marker to skip DB-required tests in CI (`-m "not postgres"`).

## DATA CONTRACTS
N/A (no runtime payload changes). Environment contract defined by `.env.example` keys and `Settings` model.

## GOTCHAS & LIBRARY QUIRKS
- Do not run `ruff --fix` in CI (read-only CI); run plain `ruff check`. Use `--fix` locally only.
- Ensure uv installs dev tooling: `uv sync` is already the project standard; do not introduce pip/poetry.
- Some tests depend on a live Postgres DB (marked `postgres`); skip them in CI to avoid flaky runs.
- Avoid echoing secrets in CI logs; never print connection strings.

## IMPLEMENTATION NOTES
- Follow repository conventions in AGENTS.md and CLAUDE.md (short commands, vertical slices, tests green).
- Keep workflow small and fast; a single job for style/type/test is acceptable at this stage.
- Make the secrets scan job optional/non-blocking initially to avoid false positive disruptions.

## VALIDATION GATES (must pass locally and in CI)
```bash
uv run ruff check src/
uv run mypy src/
uv run pytest -v -m "not postgres"
```
Optional coverage:
```bash
uv run pytest --cov=src --cov-report=term-missing -m "not postgres"
```

## ACCEPTANCE CRITERIA
- [ ] CI workflow exists at `.github/workflows/ci.yml` and runs on PRs and pushes to main/master.
- [ ] CI runs ruff, mypy, and pytest; fails the build on violations/failures.
- [ ] `.env.example` contains all relevant `WDH_*` keys and safe defaults; `.env` is git-ignored.
- [ ] `docs/security/SECRETS_POLICY.md` created and referenced from ROADMAP or README.
- [ ] Local validation gates pass on a clean checkout.

## ROLLOUT & RISK
- Low risk; only adds CI and documentation.
- No behavior change to application runtime.
- If CI speed is a concern later, add caches or split jobs; initial version prioritizes correctness and clarity.

## APPENDICES
- Useful ripgrep checks:
```bash
rg -n "(password|api_key|secret|URI=postgresql)" -S -g '!uv.lock'
```

- Sample local usage:
```bash
uv venv && uv sync
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -m "not postgres"
```
