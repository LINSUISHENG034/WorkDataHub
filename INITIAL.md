# INITIAL.md — C-012 Convert Legacy Handler/Mapping DB to YAML Seeds

Selected task: ROADMAP.md → Milestone 1 → C-012 (READY_FOR_PRP)

Purpose: Replace legacy DB-resident handler/mapping lookups with configuration-driven YAML seeds and a typed loader. This removes DB coupling, aligns with declarative config, and prepares the ground for migrating additional domains beyond trustee_performance.

IMPORTANT: EAST (legacy EAST text→table pipeline) is deprecated and MUST NOT be implemented or scoped here.

## FEATURE
Deliver YAML seed files and a typed loader that model key legacy mappings and handler configuration in code, without any database dependency:
- Define stable YAML schemas for:
  - Domain discovery and loader targets (already in `data_sources.yml` but validate via schema).
  - Organization/branch mappings, default portfolio codes, company_id overrides, and other small constant maps previously pulled from MySQL.
- Provide a `mapping_loader` module with Pydantic models to validate/parse these YAMLs.
- Add unit tests for schema validation and mapping loading.

## SCOPE
- In-scope:
  - Add Pydantic schema for `data_sources.yml` to validate fields (domain name, pattern, select, sheet, table, pk).
  - Create new YAML seeds under `src/work_data_hub/config/mappings/`:
    - `company_branch.yml` (机构→机构代码；含现有补丁映射，例如 内蒙→G31、北京其他→G37 等)
    - `default_portfolio_code.yml`（集合计划→QTAN001，单一计划→QTAN002，职业年金→QTAN003）
    - `company_id_overrides_plan.yml`（迁移 legacy COMPANY_ID3_MAPPING 小字典）
    - `business_type_code.yml`（产品线→代码；用样例占位，后续可以通过数据提供来完善）
  - Implement `src/work_data_hub/config/mapping_loader.py` with functions:
    - `load_company_branch() -> dict[str, str]`
    - `load_default_portfolio_code() -> dict[str, str]`
    - `load_company_id_overrides_plan() -> dict[str, str]`
    - `load_business_type_code() -> dict[str, str]`
    - Use shared helpers: `load_yaml_mapping(path)`, Pydantic `BaseModel` for structure.
  - Unit tests under `tests/config/test_mapping_loader.py` covering:
    - Happy-path load for each mapping (assert a few known keys)
    - Invalid YAML/invalid types raise clear exceptions
  - Optional: Add `src/work_data_hub/config/schema.py` (Pydantic) + test to validate `data_sources.yml` shape at load time (enforce presence of `table` and `pk` for each domain).
- Out of scope / Non-goals:
  - EAST 相关实现（停用，不做）
  - 网络/DB连接、动态拉取、或写回数据库
  - 构建新的领域服务逻辑（仅提供映射与验证能力）
  - 新增采集连接器（HTTP/SFTP）或 Mongo 退役实现（另有任务）

## CONTEXT SNAPSHOT
- Legacy references to convert (no DB calls in new stack):
  - `legacy/annuity_hub/data_handler/mappings.py`:
    - `DEFAULT_PORTFOLIO_CODE_MAPPING` (static)
    - `COMPANY_ID3_MAPPING` (inline dict; migrate as overrides yaml)
    - `company_branch_dic.update({...})` (补丁映射；迁至 company_branch.yml)
    - DB-backed mappings (business type, branch full map, company ids) → seed with sample entries now; grow later via data ops.
- Current new-arch config:
  - `src/work_data_hub/config/data_sources.yml` (trustee_performance already present: pattern/select/sheet/table/pk)
  - `src/work_data_hub/io/connectors/file_connector.py` consumes YAML for discovery

## EXAMPLES
YAML seeds (examples; ensure UTF-8 + allow_unicode when writing):

`src/work_data_hub/config/mappings/company_branch.yml`
```yaml
# 机构名称 -> 机构代码（示例与补丁条目）
内蒙: G31
战略: G37
中国: G37
济南: G21
北京其他: G37
北分: G37
```

`src/work_data_hub/config/mappings/default_portfolio_code.yml`
```yaml
集合计划: QTAN001
单一计划: QTAN002
职业年金: QTAN003
```

`src/work_data_hub/config/mappings/company_id_overrides_plan.yml`
```yaml
FP0001: 614810477
FP0002: 614810477
FP0003: 610081428
P0809: 608349737
SC002: 604809109
SC007: 602790403
XNP466: 603968573
XNP467: 603968573
XNP596: 601038164
```

`src/work_data_hub/config/mappings/business_type_code.yml`
```yaml
# 示例：后续根据数据源逐步完善
职年受托: ZNST
职年投资: ZNTZ
```

Schema model for data_sources.yml (Pydantic, sketch):
```python
class DomainConfig(BaseModel):
    description: str | None = None
    pattern: str
    select: Literal["latest_by_year_month", "latest_by_mtime"]
    sheet: int | str = 0
    table: str
    pk: list[str]
    required_columns: list[str] | None = None
    validation: dict[str, Any] | None = None

class DataSourcesConfig(BaseModel):
    domains: dict[str, DomainConfig]
    discovery: dict[str, Any] | None = None
```

Loader helpers (sketch):
```python
def load_yaml_mapping(path: str) -> dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, (str, int)) for k, v in data.items()):
        raise ValueError("Invalid mapping YAML structure")
    return {str(k): str(v) for k, v in data.items()}
```

## VALIDATION GATES (Definition of Done)
Commands:
- `uv run ruff check src/ --fix`
- `uv run mypy src/`
- `uv run pytest -v -k "(mapping_loader or data_sources_schema) and not postgres"`

Expected outcomes:
- Mapping loader loads YAML seeds; tests assert known keys/values.
- Invalid YAML raises clear exceptions.
- Optional schema validation passes for current `data_sources.yml` and would fail on missing `table`/`pk`.
- No dependency on DB/network; EAST not added anywhere.

## INTEGRATION POINTS
- Add files:
  - `src/work_data_hub/config/mapping_loader.py`
  - `src/work_data_hub/config/schema.py` (optional but recommended)
  - `src/work_data_hub/config/mappings/*.yml` (four seed files listed above)
- Tests:
  - `tests/config/test_mapping_loader.py`
  - `tests/config/test_data_sources_schema.py` (optional)
- No changes required to domain services or ops for this task; this is foundational config work.

## GOTCHAS & NOTES
- Use `yaml.safe_load`; always open with `encoding="utf-8"`.
- Keep YAML keys in natural (Chinese) names — loader should not force ASCII.
- Avoid introducing runtime DB calls; this task is to eliminate them for mappings.
- EAST 处理已停用，不要在任何地方新增 EAST 相关代码或任务。

## REFERENCES
- Legacy mappings: `legacy/annuity_hub/data_handler/mappings.py`
- Current config: `src/work_data_hub/config/data_sources.yml`
- Project rules: `AGENTS.md`, `CLAUDE.md`
- Pydantic models: https://docs.pydantic.dev/latest/

## ACCEPTANCE CRITERIA
- [ ] YAML seeds created with sample content and placed under `src/work_data_hub/config/mappings/`
- [ ] `mapping_loader.py` implemented with typed helpers; unit tests cover success and failure paths
- [ ] Optional `schema.py` validates `data_sources.yml`; unit test pass with current file
- [ ] No EAST-related code added; no DB/network dependency introduced
- [ ] All validation gates pass (ruff, mypy, pytest)

## NEXT STEPS FOR CLAUDE
1) Generate PRP from this INITIAL (`.claude/commands/generate-prp.md`) with this file as context.
2) Implement files and tests exactly as scoped above; do not change domain logic.
3) Run validation gates and iterate to green.
4) Update ROADMAP.md: mark C-012 → COMPLETED with PRP link; if `schema.py` delivered, note it under Milestone 1 as part of config hardening.
