# INITIAL.md — Bugfix PRP: Pydantic v2 ValidationError Misuse (trustee_performance)

Selected task: ROADMAP.md → Milestone 1 → C-016 (READY_FOR_PRP)

Purpose: Fix incorrect usage of pydantic.ValidationError in trustee_performance service that leads to a TypeError crash when encountering invalid input (e.g., month == 13). Restore graceful validation behavior and align error semantics with existing tests and design.

## FEATURE
Correct exception handling and validation flow in `src/work_data_hub/domain/trustee_performance/service.py` so that:
- Invalid date parts (e.g., month 13) do not crash; they are treated as non-processable rows (return None) or as clean validation failures that are logged/accumulated.
- Do not construct new `pydantic.ValidationError` instances manually in v2; either let the original Pydantic ValidationError bubble or raise a standard `ValueError` where appropriate.

## SCOPE
- In-scope changes:
  - Replace manual `ValidationError(...)` constructions with correct handling:
    - In `_transform_single_row`: let original `ValidationError` bubble (don’t wrap/recreate).
    - In `_extract_report_date`: do not raise `ValidationError` for invalid year/month; log and return `None` per function contract.
  - Ensure `process()` continues to record filtered rows and does not crash.
  - Adjust/extend tests to cover the bug and the corrected behaviors.
- Non-goals:
  - No changes to schema of `TrusteePerformanceIn/Out` models.
  - No changes to orchestration logic or loader semantics beyond exception behavior.

## CONTEXT SNAPSHOT
Key files and lines to fix (confirmed in repo):
- `src/work_data_hub/domain/trustee_performance/service.py`
  - L119–121: `except ValidationError as e: raise ValidationError(f"Input validation failed: {e}")`
  - L153–154: `except ValidationError as e: raise ValidationError(f"Output validation failed: {e}")`
  - L203–215: in `_extract_report_date`, multiple `raise ValidationError(...)` when year/month invalid
- Failing repro test (added): `tests/domain/trustee_performance/test_service_bug.py`
- Existing tests expecting date extraction to return None on invalid data: `tests/domain/trustee_performance/test_service.py` (see `test_extract_date_invalid_month` and `test_extract_date_invalid_year`).

Environment:
- Pydantic v2.x (uv.lock shows `pydantic==2.11.7`)
- Run tools via `uv run ...`

## ROOT CAUSE
Pydantic v2 `ValidationError` should generally not be manually constructed. The current code creates `ValidationError` with a string (e.g., `raise ValidationError("Invalid month ...")`), which is invalid and triggers `TypeError`. Proper patterns:
- Let Pydantic raise its own `ValidationError` during model parsing and validation; do not wrap or reconstruct.
- For domain-level checks (e.g., invalid month/year while extracting fields), return `None` per function contract or raise a standard `ValueError` depending on the design. Here, `_extract_report_date` contract already supports `None` for “cannot determine date”.

## PROPOSED CHANGES
1) `_transform_single_row`:
   - Replace both wrappers with a bare re-raise of the original ValidationError for clarity and correct type:
   - From:
     - `except ValidationError as e: raise ValidationError(f"Input validation failed: {e}")`
   - To:
     - `except ValidationError:
            raise`

2) `_extract_report_date`:
   - Treat invalid ranges (year not in 2000..2030, month not in 1..12) as “cannot determine date”: log debug and return `None` instead of raising `ValidationError`.
   - If `date(year, month, 1)` raises `ValueError`, also log and return `None` (not `ValidationError`).

3) Tests:
   - Keep `tests/domain/trustee_performance/test_service.py` expectations: invalid year/month → `_extract_report_date(...) is None`.
   - Update the new reproducer test `tests/domain/trustee_performance/test_service_bug.py` to validate the corrected behavior (no `TypeError`). Two viable options:
     - Assert `_transform_single_row(...) is None` for invalid month, or
     - Wrap call in `try/except` to assert no `TypeError` and (optionally) that a validation path was taken.

## CODE EXAMPLES (targeted diffs)
Use these patterns when editing `service.py`:

- Do not wrap Pydantic errors:
```python
# Before
except ValidationError as e:
    raise ValidationError(f"Input validation failed: {e}")

# After
except ValidationError:
    raise
```

- In `_extract_report_date` return None on invalid ranges:
```python
# Before
if not (1 <= month <= 12):
    raise ValidationError(f"Invalid month {month} in row {row_index}")

# After
if not (1 <= month <= 12):
    logger.debug(f"Row {row_index}: Invalid month {month}; returning None")
    return None

# Also, if date(...) raises ValueError:
try:
    return date(year, month, 1)
except ValueError as e:
    logger.debug(
        f"Row {row_index}: Cannot construct date from year={year}, month={month}: {e}"
    )
    return None
```

## VALIDATION GATES (Definition of Done)
Run locally (use `-m "not postgres"` if needed to skip DB-marked tests):
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "trustee_performance"
```
Focused checks while iterating:
```bash
uv run pytest -q tests/domain/trustee_performance/test_service_bug.py
uv run pytest -q -k test_extract_date_invalid_month
```

Expected outcomes:
- No `TypeError` anywhere in trustee_performance service for invalid month input.
- `_extract_report_date` returns `None` for invalid month/year.
- `_transform_single_row` either returns `None` for non-processable rows or raises a clean Pydantic `ValidationError` when model-level validation fails.
- All existing domain tests for trustee_performance pass.

## GOTCHAS
- Pydantic v2 `ValidationError` is not intended to be constructed with arbitrary strings; rely on Pydantic to raise it or raise standard exceptions yourself.
- Ensure logging remains informative when returning `None` from `_extract_report_date` so operators can diagnose data issues.
- Keep behavior consistent with existing tests: invalid date parts → filtered row (`None`).

## INTEGRATION POINTS
- `src/work_data_hub/domain/trustee_performance/service.py`: implement the changes above.
- `tests/domain/trustee_performance/test_service_bug.py`: convert from a crashing reproducer to an assertion of expected behavior.
- Orchestration ops/jobs remain unchanged; they already handle filtered rows and error logging.

## REFERENCES
- Pydantic v2 error handling and validators:
  - https://docs.pydantic.dev/latest/usage/validators/
  - https://docs.pydantic.dev/latest/errors/
- Project guidelines: `AGENTS.md`, `CLAUDE.md`

## ACCEPTANCE CRITERIA
- [ ] C-016 updated to PRP_GENERATED with link to PRP after generation.
- [ ] No `TypeError` is raised for invalid date inputs; rows are filtered or raise clean `ValidationError` only where appropriate.
- [ ] All validation gates pass: ruff, mypy, pytest.

## NEXT STEPS FOR CLAUDE
1) Generate PRP from this INITIAL: `.claude/commands/generate-prp.md` using this file as context.
2) Execute PRP step-by-step and run validation gates.
3) Update ROADMAP.md task C-016 status and PRP link.
