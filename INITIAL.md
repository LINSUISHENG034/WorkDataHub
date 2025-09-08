# INITIAL.md — C‑013 Mapping Loader Portability + Config Hardening

Selected task: ROADMAP.md → Milestone 1 → C‑013

Purpose: Make the mapping loader portable across execution contexts and support an environment override, and (optionally) add a single fail‑fast validation for data_sources.yml. No behavior change beyond path resolution; no EAST, DB, or network usage.

Reference: Use VALIDATION.md as baseline; do not regress existing gates.

## FEATURE
Enhance `mapping_loader` to:
- Resolve YAML seed locations relative to the module by default.
- Support `WDH_MAPPINGS_DIR` environment override (directory must exist).
- Add tests proving portability and override behavior.
- Optional: Integrate a single validation call for `data_sources.yml` (fail fast, clear logs).

## SCOPE
- In‑scope:
  - `src/work_data_hub/config/mapping_loader.py`:
    - Add `get_mappings_dir() -> Path`.
    - Update all loader functions to use `get_mappings_dir()` instead of hardcoded repo paths.
    - Keep return types and `MappingLoaderError` semantics unchanged.
  - Tests in `tests/config/test_mapping_loader.py`:
    - Add portability and env override tests (details below).
  - Optional: `src/work_data_hub/orchestration/ops.py` — add one validation call with clear error logging; no other behavior changes.
- Non‑goals:
  - No EAST functionality (deprecated).
  - No DB/network calls.
  - No domain/service logic refactors.

## CONTEXT SNAPSHOT
- Seeds: `src/work_data_hub/config/mappings/*.yml` (Chinese keys; keep content unchanged).
- Loader: `src/work_data_hub/config/mapping_loader.py` (currently uses repo‑relative paths).
- Schema: `src/work_data_hub/config/schema.py` (provides `validate_data_sources_config`).
- Ops: `src/work_data_hub/orchestration/ops.py` (optional validation location).
- Tests: `tests/config/test_mapping_loader.py`, `tests/config/test_data_sources_schema.py`.

## IMPLEMENTATION
1) Loader portability and override
```python
# src/work_data_hub/config/mapping_loader.py
from pathlib import Path
import os

def get_mappings_dir() -> Path:
    env_dir = os.environ.get("WDH_MAPPINGS_DIR")
    if env_dir:
        p = Path(env_dir)
        if not p.exists() or not p.is_dir():
            raise MappingLoaderError(
                f"WDH_MAPPINGS_DIR not found or not a directory: {env_dir}"
            )
        return p
    return Path(__file__).parent / "mappings"

def load_company_branch() -> dict[str, str]:
    return load_yaml_mapping(str(get_mappings_dir() / "company_branch.yml"))

def load_default_portfolio_code() -> dict[str, str]:
    return load_yaml_mapping(str(get_mappings_dir() / "default_portfolio_code.yml"))

def load_company_id_overrides_plan() -> dict[str, str]:
    return load_yaml_mapping(str(get_mappings_dir() / "company_id_overrides_plan.yml"))

def load_business_type_code() -> dict[str, str]:
    return load_yaml_mapping(str(get_mappings_dir() / "business_type_code.yml"))
```

2) Tests — portability & override (add to tests/config/test_mapping_loader.py)
```python
def test_module_relative_paths_portable(tmp_path, monkeypatch):
    import os
    from src.work_data_hub.config.mapping_loader import (
        load_company_branch, load_default_portfolio_code,
        load_company_id_overrides_plan, load_business_type_code,
    )
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Should still load repo seeds via module‑relative paths
        assert load_company_branch()["内蒙"] == "G31"
        assert load_default_portfolio_code()["集合计划"] == "QTAN001"
        assert "FP0001" in load_company_id_overrides_plan()
        assert load_business_type_code()["职年受托"] == "ZNST"
    finally:
        os.chdir(cwd)

def test_env_override_directory(tmp_path, monkeypatch):
    # Create override mappings dir with minimal content
    override = tmp_path / "mappings"
    override.mkdir()
    (override / "company_branch.yml").write_text("内蒙: OVERRIDE\n", encoding="utf-8")
    (override / "default_portfolio_code.yml").write_text("集合计划: OVCODE\n", encoding="utf-8")
    (override / "company_id_overrides_plan.yml").write_text("FP0001: 123\n", encoding="utf-8")
    (override / "business_type_code.yml").write_text("职年受托: OV\n", encoding="utf-8")
    
    monkeypatch.setenv("WDH_MAPPINGS_DIR", str(override))
    from src.work_data_hub.config.mapping_loader import (
        load_company_branch, load_default_portfolio_code,
        load_company_id_overrides_plan, load_business_type_code,
    )
    assert load_company_branch()["内蒙"] == "OVERRIDE"
    assert load_default_portfolio_code()["集合计划"] == "OVCODE"
    assert load_company_id_overrides_plan()["FP0001"] == "123"
    assert load_business_type_code()["职年受托"] == "OV"

def test_env_override_missing_dir(monkeypatch):
    monkeypatch.setenv("WDH_MAPPINGS_DIR", "/nonexistent/dir")
    from src.work_data_hub.config.mapping_loader import load_company_branch, MappingLoaderError
    with pytest.raises(MappingLoaderError, match="WDH_MAPPINGS_DIR not found or not a directory"):
        load_company_branch()
```

3) Optional: fail‑fast validation in ops (low‑touch)
```python
# src/work_data_hub/orchestration/ops.py
from ..config.schema import validate_data_sources_config, DataSourcesValidationError
try:
    validate_data_sources_config()
except DataSourcesValidationError as e:
    logger.error(f"data_sources.yml validation failed: {e}")
    raise
```

## VALIDATION GATES
Run locally:
- `uv run ruff check src/ --fix`
- `uv run mypy src/`
- `uv run pytest -v -k "(mapping_loader or data_sources_schema or orchestration) and not postgres"`

Expected:
- Portability and env override tests pass from any CWD.
- Clear error when `WDH_MAPPINGS_DIR` is invalid.
- Optional ops validation does not break tests with current config.

## GOTCHAS
- Restore CWD in portability test (try/finally) to avoid cascading failures.
- Include the problematic path in override error messages for troubleshooting.
- Avoid circular imports; keep schema import at module top with care.
- Do not change YAML seed contents.

## ACCEPTANCE CRITERIA
- [ ] Loaders use `get_mappings_dir()`; support `WDH_MAPPINGS_DIR`.
- [ ] New tests cover portability and env override (valid/invalid).
- [ ] (Optional) Single validation call added to ops with clear logging.
- [ ] All validation gates pass (ruff, mypy, pytest).

## NEXT STEPS FOR CLAUDE
1) Generate PRP from this INITIAL and implement exactly as scoped.
2) Run validation gates to green.
3) Update ROADMAP.md: mark C‑013 → COMPLETED with PRP link (P‑009).
