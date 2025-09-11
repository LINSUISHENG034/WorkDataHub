# INITIAL_en.md — P‑023 Finalization (C‑028): Alias Serialization, DB Auto IDs, Narrowed F‑Prefix, Tests Alignment

This INITIAL guides Claude to complete the P‑023 validation loop with minimal, KISS‑aligned changes. It codifies the required clarifications and acceptance criteria to align the annuity domain (and all business data) with the new architecture.

## Feature / Roadmap
- Epic/Chore: C‑028 Cleansing framework hardening (negative/full‑width percentage, Excel header normalization, F‑prefix handling)
- PRP: P‑023 (validation and hardening loop)
- Domains: annuity_performance (规模明细) + shared cleansing components

## Scope
- In scope:
  - Enable alias‑based, null‑excluding serialization in Dagster ops for JSON handoff to the loader: `model_dump(mode="json", by_alias=True, exclude_none=True)`.
  - Adopt DB auto‑increment primary keys for the annuity domain and all business data; adjust DDL accordingly while keeping column names compliant with database naming rules in `CLAUDE.md`.
  - Narrow F‑prefix stripping to affect only the portfolio code field (Chinese: `组合代码`) and only when it matches the strict pattern `^F[0-9A-Z]+$`. Do not strip from the plan code (`计划代码`).
  - Keep Excel header normalization and column standardization as implemented (e.g., full/half‑width parentheses normalization; newlines/tabs removed).
  - Update tests: unify annuity tests to `company_id`; remove assertions on fields that no longer exist (e.g., `data_source`, `processed_at`, `validation_warnings`).
- Out of scope:
  - Introducing a new Mapping Service, or moving company name normalization/backfill logic; keep domain‑specific mapping out of this PRP.
  - Changing trustee domain contracts (beyond `by_alias=True` serialization which is a no‑op there).

## Key Decisions
- JSON output alignment
  - Issue: The annuity output model maps `流失_含待遇支付` to the DB column `流失(含待遇支付)` via aliases, but ops previously did not serialize by alias or exclude `None` fields.
  - Decision: In `src/work_data_hub/orchestration/ops.py`, use `model_dump(mode="json", by_alias=True, exclude_none=True)` in all three places where Pydantic models are serialized.

- DB primary key strategy and naming
  - Clarification: The annuity domain and ALL business data adopt DB‑generated auto‑increment primary keys.
  - Decision: Update the annuity DDL (`scripts/dev/annuity_performance_real.sql`) to use an auto identity for `id` (e.g., `GENERATED ALWAYS AS IDENTITY`), while ensuring column names follow the database naming rules described in `CLAUDE.md` (including proper quoting and identifier conventions for Chinese column names).

- F‑prefix handling (annuity)
  - Clarification: Narrow F‑prefix stripping to apply ONLY to the portfolio code (`组合代码`), NOT the plan code (`计划代码`), and ONLY when the portfolio code matches `^F[0-9A-Z]+$`.
  - Decision: Adjust the annuity service logic accordingly; do not alter `计划代码`.

- Column standardization and aliasing chain
  - Input: `ExcelReader` + `column_normalizer` standardize headers (e.g., `流失（含待遇支付）` → `流失_含待遇支付`).
  - Output: Annity model uses alias to serialize back to the actual DB column name `流失(含待遇支付)`; ops ensure alias serialization.

- Primary key in data_sources
  - Continue using `pk: ["月度", "计划代码", "company_id"]` in `data_sources.yml` for annuity, consistent with output and loader expectations.

## Files to Touch (Claude)
- `src/work_data_hub/orchestration/ops.py`
  - Replace all `model_dump(...)` calls that serialize domain output with:
    - `model_dump(mode="json", by_alias=True, exclude_none=True)`
  - Locations:
    - `process_trustee_performance_op`
    - `process_annuity_performance_op`
    - `read_and_process_trustee_files_op`

- `scripts/dev/annuity_performance_real.sql`
  - Change `"id" INTEGER NOT NULL` to an auto identity (e.g., `"id" INTEGER GENERATED ALWAYS AS IDENTITY`) while preserving the primary key.
  - Keep column names and quoting consistent with `CLAUDE.md` database rules.

- `src/work_data_hub/domain/annuity_performance/service.py`
  - Modify F‑prefix stripping logic:
    - Apply ONLY to the field `组合代码` (portfolio code), and ONLY when it matches `^F[0-9A-Z]+$`.
    - Do NOT modify `计划代码` based on F‑prefix.

- Tests under `tests/domain/annuity_performance/` and adjacent unit/e2e tests
  - Update annuity tests to use `company_id`.
  - Remove assertions for deleted fields (`data_source`, `processed_at`, `validation_warnings`).
  - Add/adjust assertions verifying alias serialization (e.g., serialized output contains `"流失(含待遇支付)"`).

## Validation Commands (copy‑paste)
```bash
uv venv && uv sync
uv run ruff format .
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# Plan‑only (safe): verify SQL plans contain the correct aliased column names
WDH_DATA_BASE_DIR=./reference/monthly \
  uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --plan-only --max-files 1

# Execute (requires DB + DDL applied)
psql "$WDH_DATABASE__URI" -f scripts/dev/annuity_performance_real.sql
WDH_DATA_BASE_DIR=./reference/monthly \
  uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --execute --max-files 1 --mode delete_insert
```

## Acceptance Criteria (DoD)
- Alias & null‑exclusion: Ops use `by_alias=True, exclude_none=True`; E2E plan shows `"流失(含待遇支付)"` in INSERT columns; no SQL errors due to column mismatches or null‑only columns.
- DB auto IDs: The annuity table `id` is auto‑generated by the DB; execute mode inserts succeed without providing `id`.
- F‑prefix rule: Only strips when `组合代码` matches `^F[0-9A-Z]+$`; never strips from `计划代码`; words like `FIDELITY001` remain intact.
- Header/column chain: Excel headers normalized; `流失（含待遇支付）` → `流失_含待遇支付` → serialized as `流失(含待遇支付)` for DB.
- PK consistency: `pk=["月度","计划代码","company_id"]` matches output; DELETE SQL uses properly quoted identifiers.
- Tests: All existing tests pass; annuity tests updated to `company_id` and no longer reference removed fields; alias serialization assertions pass.
- Docs/Status: Update README/ROADMAP if necessary to reflect the final behaviors; keep ROADMAP as the single source of truth.

## Risks & Mitigations
- Risk: DB not updated with auto identity → execute mode fails on `id`.
  - Mitigation: Enforce DDL application before execute tests; do not re‑introduce synthetic `id` generation in code.
- Risk: `by_alias=True` unexpectedly changes trustee output.
  - Mitigation: Trustee models do not rely on alias for DB column names; add a quick E2E sanity run.
- Risk: Tight F‑prefix rule may leave some historical anomalies.
  - Mitigation: Escalate to Mapping Service (M2) for exceptional cases; keep domain logic simple.

## References
- `CLAUDE.md` — Database naming/quoting conventions must be followed.
- `README.md` — Commands and local run instructions.
- `ROADMAP.md` — Status and dependencies (single source of truth).
- `docs/overview/MIGRATION_REFERENCE.md`, `docs/overview/LEGACY_WORKFLOW_ANALYSIS.md` — Migration and legacy behaviors.

