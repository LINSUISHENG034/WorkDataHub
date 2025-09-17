INITIAL — S-004 Regression Recovery (Definition of Ready)

This INITIAL replaces the previous S-004 brief. Claude already landed the first enrichment pass, but review uncovered two blockers: the `annuity_performance` service now breaks existing callers/tests and plan-only runs still try to open live database connections. Use this document as the single source of truth for the remediation PRP.

---

## FEATURE

Restore S-004 to the Definition-of-Done bar by:
1. Reinstating the original `annuity_performance.process` contract while still surfacing enrichment stats for orchestration.
2. Making enrichment setup respect plan-only execution (no database connections, no psycopg2 usage) and ensuring opened connections are always cleaned up.

## SCOPE
- In-scope
  - Adjust `src/work_data_hub/domain/annuity_performance/service.py` so `process(...)` remains backward compatible (returns `list[AnnuityPerformanceOut]`). Provide an additive way to expose enrichment metadata without breaking existing imports/tests.
  - Update orchestration (`src/work_data_hub/orchestration/ops.py` and dependent code) to use the new enrichment metadata hook while keeping the Dagster op return payload unchanged.
  - Ensure plan-only runs skip enrichment DB work: no psycopg2 import/connection, no loader/queue construction. When execute mode opens a connection, close it in all paths (success, error, partial setup).
  - Refresh/extend tests to pin the regression fixes (service unit tests, ops tests for plan-only behaviour, any new helper tests).

- Non-goals
  - Do NOT rework enrichment matching logic or statistics content beyond what is required for compatibility.
  - No new CLI flags or configuration knobs unless strictly necessary for plan-only detection.
  - No broader refactors outside annuity_performance + orchestration enrichment paths.

## CONTEXT SNAPSHOT
```bash
src/work_data_hub/
  domain/
    annuity_performance/
      __init__.py                  # Exports expected public API (process)
      models.py                    # EnrichmentStats, ProcessingResultWithEnrichment definitions
      service.py                   # Regression: process return type + enrichment loop
  orchestration/
    ops.py                         # process_annuity_performance_op sets up enrichment + logs stats
    jobs.py                        # CLI config -> run_config wiring, plan-only/execute flags
  config/
    settings.py                    # Holds defaults, may already expose plan_only hints

tests/
  domain/annuity_performance/test_service.py   # Still asserts process() returns list
  orchestration/test_ops.py                    # Add/adjust coverage for plan-only behaviour
```

## EXAMPLES / REFERENCES
- `tests/domain/annuity_performance/test_service.py`: keep these assertions green. Use them as the definition of the legacy API.
- `tests/orchestration/test_ops.py::TestProcessTrusteePerformanceOp`: mirrors Dagster op patterns—replicate the mocking style when adding plan-only coverage for annuity.
- `src/work_data_hub/orchestration/ops.py::load_op`: example of guarding DB work behind `plan_only` and cleaning up connections.
- `CLAUDE.md` + `docs/VALIDATION.md`: project-wide conventions and required command set.

## IMPLEMENTATION NOTES
- Consider adding a thin wrapper (e.g., `process_with_enrichment(...) -> ProcessingResultWithEnrichment`) or a dataclass return that keeps `.records` while maintaining compatibility for existing list-callers. Whatever route you pick, `process(...)` must remain importable and behave exactly like pre-S-004 code for consumers/tests that do not opt in to enrichment metadata.
- Orchestration can call the richer helper while other call sites stay untouched. Keep serialization logic inside the op focused on `List[AnnuityPerformanceOut]` to avoid downstream changes.
- Pass plan-only intent from CLI/run_config down to `ProcessingConfig` (ops.py) to allow the op to short-circuit enrichment setup. In plan-only mode ensure:
  - psycopg2 import is not attempted.
  - Loader/queue instances are not created.
  - Connection objects are not instantiated.
- When execute mode creates a connection, close it in `finally` blocks even if enrichment setup fails midway.
- Update tests to assert:
  1. `process([])` returns `[]` (not a custom model) and enrichment-off path matches baseline.
  2. New helper/API exposes enrichment stats (if added) without changing legacy behaviour.
  3. `process_annuity_performance_op` skips psycopg2/connect when plan-only.
  4. Execute mode closes the enrichment connection (e.g., mock connection’s `close` is called).

## INTEGRATION POINTS
- Domain service API: maintain exports in `src/work_data_hub/domain/annuity_performance/__init__.py`.
- Dagster config: extend `ProcessingConfig` to carry plan_only/enrichment flags as needed; ensure CLI wiring (`src/work_data_hub/orchestration/jobs.py`) populates the new field using existing plan-only logic.
- Tests: add/adjust fixtures under `tests/domain/annuity_performance/` and `tests/orchestration/` to pin behaviour.

## RISKS & CALL-OUTS
- Forgetting to update `__all__` in `annuity_performance/__init__.py` after introducing a helper keeps imports broken.
- Unit tests may need rewiring if you introduce additional return types—ensure type hints align with mypy expectations.
- psycopg2 is optional in CI; tests must mock it so they do not rely on the real library.

## VALIDATION GATES (must run & pass)
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# Focused suites while iterating
uv run pytest -k "annuity_performance and service"
uv run pytest tests/orchestration/test_ops.py::TestProcessAnnuityPerformanceOp
```

## ACCEPTANCE CRITERIA
- `annuity_performance.process(...)` returns `list[AnnuityPerformanceOut]` and existing callers/tests run without modification.
- Enrichment stats remain available to orchestration (document how) without leaking through baseline interfaces.
- Plan-only runs complete without opening database connections or instantiating psycopg2 (verified by tests).
- Execute-mode enrichment connections are closed deterministically.
- All validation gates above pass without manual intervention.

## OPTIONAL VERIFICATION (if DB available)
```bash
uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only --max-files 1 --enrichment-enabled --enrichment-sync-budget 3

uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --execute --mode append --max-files 1 --enrichment-enabled --enrichment-sync-budget 3
```
