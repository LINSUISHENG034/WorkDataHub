# INITIAL.md — 覆盖/非覆盖写入端到端测试（年金规模明细）

本 INITIAL 指导 Claude 基于“真实样本派生小数据集”完成覆盖写入（delete_insert）与非覆盖写入（append）的端到端与单元测试，确保功能可观测、可复现、可回归。

## FEATURE
使用真实业务样本（年金规模明细）派生多个小规模数据集，构建覆盖/非覆盖写入测试矩阵，校验 `--mode delete_insert/append` 与 `--pk` 运行时覆盖键的语义正确性与稳定性。

## SCOPE
- In‑scope:
  - 生成小数据集：从 `tests/fixtures/sample_data/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx` 派生 3 个子集（5/6/3 行）。
  - E2E 计划模式测试：验证按默认 PK 与运行时 `--pk` 覆盖时的 DELETE/INSERT 计划（计数、SQL 形态）。
  - Loader 单元测试：delete_insert 缺失 PK 报错；append 模式不依赖 PK。
  - CLI 覆盖键：`--pk` 可在运行时覆盖 `data_sources.yml` 的组合键。
- Non‑goals:
  - 引入 upsert（ON CONFLICT DO UPDATE）模式。
  - 修改领域转换或 DDL/表结构。
  - 部署 Dagster 服务端（UI/daemon）。

## CONTEXT SNAPSHOT
```bash
tests/fixtures/sample_data/
  【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx  # 大样本
  annuity_subsets/                                            # 由脚本生成
    2024年11月年金终稿数据_subset_distinct_5.xlsx
    2024年11月年金终稿数据_subset_overlap_pk_6.xlsx
    2024年11月年金终稿数据_subset_append_3.xlsx

src/work_data_hub/
  orchestration/
    jobs.py        # CLI + run_config（含 --pk 覆盖）
    ops.py         # discover/read/process/load 薄封装
  io/
    readers/excel_reader.py
    loader/warehouse_loader.py
  domain/annuity_performance/service.py
scripts/testdata/make_annuity_subsets.py   # 本次新增的小集生成脚本
```

## EXAMPLES（最重要）
- 生成小数据集：
```bash
uv run python -m scripts.testdata.make_annuity_subsets \
  --src tests/fixtures/sample_data/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx \
  --sheet 规模明细
```
- E2E 计划模式（默认 PK）：
```bash
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --plan-only --max-files 1
```
- E2E 计划模式（运行时覆盖 PK）：
```bash
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --plan-only --max-files 1 \
  --mode delete_insert --pk "月度,计划代码"
```
- 非覆盖写入（append）：
```bash
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance --plan-only --max-files 1 \
  --mode append
```

## DOCUMENTATION
- `README.md`（生成子集与 CLI 用法）
- `src/work_data_hub/config/data_sources.yml`（annuity_performance 的表名与默认 PK）
- `CLAUDE.md`（命名/DDL 规范）

## INTEGRATION POINTS
- ExcelReader → Domain Service（annuity）→ Loader（warehouse_loader）
- Orchestration（ops/jobs）与 Settings（`WDH_DATA_BASE_DIR`）

## DATA CONTRACTS
- delete_insert：需要 `pk=["月度","计划代码","company_id"]`（或运行时 `--pk` 覆盖）。
- append：不需要 PK。
- 处理后输出包含：`月度`、`计划代码`、`company_id`、若干财务/元数据字段；ops 以别名序列化并投影到允许列。

## GOTCHAS & QUIRKS
- 子集文件名需匹配 annuity 的 pattern（已用 `2024年11月年金终稿数据_subset_*.xlsx`）。
- Windows/PowerShell 环境变量设定与转义需注意（建议在 pytest 中用 `monkeypatch.setenv`）。
- 计划模式只返回 SQL 计划，不连接数据库；执行模式请仅用于本地测试数据库并打上 `-m postgres` 标记。

## IMPLEMENTATION NOTES（测试设计）
建议新增测试文件：`tests/e2e/test_annuity_overwrite_append_small_subsets.py`
- 准备：调用 subset 生成脚本或假定已生成子集；在测试中 `monkeypatch.setenv('WDH_DATA_BASE_DIR', subset_dir)`。
- 用例 A（distinct_5）：
  - delete_insert：期望 deleted == 子集中按默认 PK 的唯一组合数；inserted == 5；存在一条 DELETE 计划 + INSERT 计划。
  - append：期望 deleted == 0；inserted == 5；仅 INSERT 计划。
- 用例 B（overlap_pk_6）：
  - delete_insert：期望 deleted == 3（唯一组合数）；inserted == 6；DELETE + INSERT。
  - append：期望 deleted == 0；inserted == 6。
- 用例 C（pk 覆盖）：对 overlap_pk_6 用 `--pk "月度,计划代码"`，期望 deleted == 以两列聚合的唯一对数；inserted == 6。
- Loader 单测：
  - 构造 rows（含/不含某 PK 列），调用 `warehouse_loader.load(..., mode='delete_insert', pk=[...])`：缺失 PK → `DataWarehouseLoaderError`；`mode='append'` 正常（不校验 PK）。

可选：再补 1 条 E2E 执行模式（`-m postgres`）验证 delete_insert 真实删除/插入计数（需准备测试库与 DDL）。

## VALIDATION GATES
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k annuity_overwrite_append
```
可选覆盖：
```bash
uv run pytest --cov=src --cov-report=term-missing -k annuity_overwrite_append
```

## ACCEPTANCE CRITERIA
- 子集生成：成功生成 3 个文件（5/6/3 行），sheet 名为“规模明细”。
- E2E 计划模式：
  - distinct_5：delete_insert 的 deleted == 唯一 PK 组合数；append 的 deleted == 0；inserted == 5。
  - overlap_pk_6：delete_insert 的 deleted == 3；append 的 deleted == 0；inserted == 6。
  - pk 覆盖：`--pk "月度,计划代码"` 时 deleted == 以两列聚合的唯一对数。
- Loader 单测：缺失 PK（delete_insert）抛出 `DataWarehouseLoaderError`；append 不抛错。
- CI 门：ruff/mypy/pytest 全绿；测试在默认（非 postgres）环境下仅使用计划模式，不依赖数据库。

## ROLLOUT & RISK
- 风险：真实样本字段异构导致子集不含所需列 → 脚本已采用多级候选键并在缺少时回落；测试计算期望 deleted 时以 `ExcelReader` 结果自适应聚合。
- 风险：文件命名不匹配 pattern → 已统一 `2024年11月年金终稿数据_subset_*.xlsx`；若后续变更，更新 `data_sources.yml` 或命名规则。

## REFERENCES
- `README.md` — 小集生成与 CLI 用法
- `src/work_data_hub/config/data_sources.yml` — annuity 配置（sheet、表、PK）
- `src/work_data_hub/io/loader/warehouse_loader.py` — delete_insert/append 逻辑
- `src/work_data_hub/orchestration/jobs.py` — `--pk` 覆盖实现

