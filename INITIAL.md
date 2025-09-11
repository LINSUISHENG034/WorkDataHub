# INITIAL.md — Cleansing Framework Hardening (KISS/YAGNI) with Minimal Domain Changes

This INITIAL defines a minimal, KISS‑compliant enhancement to the shared cleansing framework and a few domain‑level tweaks so we achieve parity with critical legacy cleansing behavior without over‑engineering.

## FEATURE
Strengthen numeric cleansing and input header normalization to remove cross‑domain duplication and align with legacy behavior, while keeping business‑specific logic in domain or the future Mapping Service.

## SCOPE
- In‑scope:
  - Numeric rules: support negative percentages and full‑width percent sign (％) in `handle_percentage_conversion`; preserve sign and only treat numbers as percent when `abs(value) > 1` for rate fields.
  - Input layer: normalize Excel header strings by removing newlines and tabs so `project_columns` never drops columns due to formatting.
  - Annuity domain: strip `^F` prefix from `组合代码` to match legacy behavior.
  - Keep public cleansing APIs stable (`comprehensive_decimal_cleaning`, `decimal_fields_cleaner`).
  - Add focused tests for the above.
- Non‑goals:
  - Company name normalization, multi‑source `company_id` backfill, special plan‑code replacements, default institution code; these remain in domain or the planned Mapping Service (M2).
  - No DDL or orchestration changes; no DSL/pipeline engine for rules.

## CONTEXT SNAPSHOT (optional)
```bash
src/work_data_hub/
  cleansing/
    rules/numeric_rules.py              # numeric rules to extend
    integrations/pydantic_adapter.py    # Pydantic decorator (no API change)
  io/readers/excel_reader.py            # header normalization to add
  domain/
    annuity_performance/service.py      # strip ^F from 组合代码
    trustee_performance/                # already using shared numeric rules
tests/
  test_cleansing_framework.py           # strengthen numeric tests
  domain/annuity_performance/test_service.py
  io/readers/ ... (add header normalization tests)
```

## EXAMPLES (most important)
- Path: `src/work_data_hub/cleansing/rules/numeric_rules.py` — reuse the staged flow: null standardization → currency symbol removal → percent handling → decimal quantization.
- Path: `tests/test_cleansing_framework.py` — mirror test style for currency, percent, null, and quantization assertions.
- Path: `src/work_data_hub/io/readers/excel_reader.py` — extend `_dataframe_to_rows` column cleaning to include `.replace("\n", "").replace("\t", "")`.
- Path: `src/work_data_hub/domain/annuity_performance/service.py` — minimally strip `^F` prefix from `组合代码` while leaving other domain logic unchanged.

Snippet — negative and full‑width percentage handling (pattern to follow):
```python
# Example expectation
from decimal import Decimal
from src.work_data_hub.cleansing.rules.numeric_rules import comprehensive_decimal_cleaning

assert comprehensive_decimal_cleaning("-5%", "当期收益率") == Decimal("-0.050000")
assert comprehensive_decimal_cleaning("12.3％", "当期收益率") == Decimal("0.123000")
assert comprehensive_decimal_cleaning(-12.3, "当期收益率") == Decimal("-0.123000")
```

## DOCUMENTATION
- File: `README.md` — Developer quickstart and commands
- File: `ROADMAP.md` — Single source of truth for scope/status (mark this task under current milestone)
- File: `docs/overview/MIGRATION_REFERENCE.md` — Migration plan and role boundaries (Mapping Service in M2)
- File: `docs/overview/LEGACY_WORKFLOW_ANALYSIS.md` — Objective legacy behavior reference
- URL: https://docs.pydantic.dev/2.7/ — Pydantic v2 validators and model config

## INTEGRATION POINTS
- Data models: No schema changes; both trustee and annuity models already call the shared numeric pipeline.
- IO layer: `ExcelReader._dataframe_to_rows` — normalize header strings to avoid column projection issues.
- Domain logic: Annuity service strips `^F` from `组合代码` (no other domain coupling introduced).
- Database/DDL: None.
- Config/ENV: None.
- API/Routes: None.
- Jobs/Events: None.

## DATA CONTRACTS (schemas & payloads)
```python
# Public cleansing API remains unchanged
from decimal import Decimal
from typing import Any, Optional, Dict

def comprehensive_decimal_cleaning(
    value: Any,
    field_name: str = "",
    precision: int | None = None,
    handle_percentage: bool = True,
    precision_config: Optional[Dict[str, int]] = None,
) -> Optional[Decimal]:
    ...  # unchanged public contract
```

```python
# Pydantic integration stays the same
from src.work_data_hub.cleansing import decimal_fields_cleaner

@decimal_fields_cleaner("期初资产规模", "当期收益率", precision_config={"当期收益率": 6, "期初资产规模": 4})
class AnnuityModel(BaseModel):
    ...
```

## GOTCHAS & LIBRARY QUIRKS
- Pydantic v2 only; use `field_validator(..., mode="before")` appropriately.
- Chinese field names in validators (e.g., "当期收益率").
- Full‑width percent sign `％` frequently appears in Excel; treat like `%`.
- Numeric percent heuristics: only convert numbers to decimals for rate fields when `abs(value) > 1`.
- Quantization uses `ROUND_HALF_UP`; keep precision from `precision_config`.
- Prefer `rg` for search; avoid `grep/find`.

## IMPLEMENTATION NOTES
- KISS: keep enhancements tiny; do not introduce a rule pipeline/DSL.
- YAGNI: do not move company name cleaning or mapping rules into the shared component.
- Put header normalization where the data enters (ExcelReader) to prevent column mismatches early.
- Keep the annuity `^F` handling in the domain service to avoid over‑generalizing the shared layer.

## VALIDATION GATES (must pass)
```bash
uv venv && uv sync
uv run ruff format .
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v
```

Targeted tests:
```bash
# Numeric cleansing (negative percent, full‑width percent, currency‑only -> None)
uv run pytest -v tests/test_cleansing_framework.py -k "percent or percentage or currency"

# ExcelReader header normalization (newline/tab in headers)
uv run pytest -v tests/io/readers/test_excel_reader.py -k "header or column or newline or tab"

# Annuity: strip ^F prefix from 组合代码
uv run pytest -v tests/domain/annuity_performance/test_service.py -k "组合代码 or portfolio or prefix"
```

## ACCEPTANCE CRITERIA
- [ ] "-5%" → Decimal("-0.050000") for rate fields; `"12.3％"` equals `"12.3%"` result.
- [ ] Numeric values in rate fields: only `abs(value) > 1` are treated as percentage inputs (e.g., `-12.3` → `-0.123000`).
- [ ] Non‑rate numeric fields do not get percentage conversion.
- [ ] Currency/formatting‑only strings become `None` after null/currency normalization as applicable.
- [ ] ExcelReader returns headers without `\n` or `\t`; `project_columns` no longer drops columns due to header formatting.
- [ ] Annuity `组合代码` no longer contains leading `F` when present.
- [ ] All existing tests remain green; new targeted tests pass.

## ROLLOUT & RISK
- No feature flags required; changes are local and reversible.
- Rollback:
  - Numeric: revert `handle_percentage_conversion` additions.
  - Header: remove `.replace("\n", "").replace("\t", "")` in ExcelReader.
  - Annuity: remove the `^F` prefix stripping in the service.
- Performance impact is negligible (simple string ops and conditionals).

## APPENDICES (optional snippets)
```python
# Test skeleton — Excel header normalization
def test_header_normalization_removes_newlines_and_tabs(tmp_path):
    # Arrange: write a tiny XLSX with headers containing \n/\t
    # Act: read via ExcelReader
    # Assert: headers no longer contain \n/\t and column projection succeeds
    assert True
```

```bash
# Useful ripgrep searches while implementing
rg -n "handle_percentage_conversion|comprehensive_decimal_cleaning" src/
rg -n "_dataframe_to_rows|ExcelReader" src/work_data_hub/io/readers
rg -n "组合代码" src/work_data_hub/domain/annuity_performance
```

