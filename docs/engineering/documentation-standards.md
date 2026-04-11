# Documentation Standards

## Scope

These rules apply to `README.md` and all active documentation under `docs/`.

## Source Of Truth

Use repository artifacts, not memory, when writing or updating docs:

- CLI behavior: `src/work_data_hub/cli/__main__.py`, `src/work_data_hub/cli/etl/main.py`
- Active ETL domains: `config/data_sources.yml`, `src/work_data_hub/domain/registry.py`
- Domain-specific behavior: `src/work_data_hub/domain/<domain>/`
- Verification and contracts: `tests/`

## Required Maintenance Rules

- Every PR that changes domain behavior, CLI parameters, config schema, database workflow, or operator procedure must update the matching docs in the same PR.
- `README.md` may link only to active, stable documents.
- Domain docs are required for every active ETL domain defined in both `config/data_sources.yml` and `src/work_data_hub/domain/registry.py`.
- Runbooks are required for every domain that can be executed manually through the repository CLI.
- Operational command examples must be copied from real CLI behavior.
- Every active operational doc must include `Source of truth`, `Last verified`, and `Scope`.
- Historical docs must be labeled as historical and must not be referenced by tests, CI, or top-level onboarding pages.
- Broken `docs/...` links are release-blocking failures.
- The docs-alignment checker must run locally before merge and in CI on every PR.

## Active Document Contracts

### Domain Docs

Every active file under `docs/domains/` must include:

- `Overview`
- `Inputs`
- `File Discovery And Sheet Selection`
- `Transformation And Validation`
- `Output Tables`
- `CLI And Operational Entry Points`
- `Configuration`
- `Verification`
- `Related Runbooks And Rules`

### Runbooks

Every active file under `docs/runbooks/` for a CLI-executable domain must include:

- `Preconditions`
- `Manual Execution`
- `Common Errors`
- `Verification`
- `Rollback Or Safe Re-run`

## Reference And Archive Rules

- Use `docs/reference/` for stable technical reference that supports operations or implementation but is not the primary onboarding path.
- Use `docs/archive/` only for explicitly historical material.
- Do not route new contributors from `README.md`, `docs/index.md`, or `docs/guides/index.md` into historical material.

## Verification Commands

Use the command form that matches your shell. For PowerShell:

```powershell
$env:PYTHONPATH='src'
uv run python scripts/quality/check_docs_alignment.py
uv run pytest tests/integration/test_annuity_config.py -v
uv run pytest tests/integration/test_domain_docs_complete.py -v
uv run pytest tests/smoke/test_docs_alignment.py -v
```

For Bash:

```bash
PYTHONPATH=src uv run python scripts/quality/check_docs_alignment.py
PYTHONPATH=src uv run pytest tests/integration/test_annuity_config.py -v
PYTHONPATH=src uv run pytest tests/integration/test_domain_docs_complete.py -v
PYTHONPATH=src uv run pytest tests/smoke/test_docs_alignment.py -v
```
