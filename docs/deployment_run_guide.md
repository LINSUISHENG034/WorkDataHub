# WorkDataHub 部署与运行指南

> Source of truth: `src/work_data_hub/cli/etl/main.py`, `config/data_sources.yml`
> Last verified: `2026-04-11`
> Scope: ETL execution and deployment operations

本文档面向可联网或常规开发环境，说明如何准备运行环境、执行活动 ETL 域，以及核对 CLI 的真实参数面。

## 相关文档

- [文档总览](./index.md)
- [参考资料](./reference/README.md)
- [内网部署与运行指南](./deployment_run_guide_intranet.md)
- [运行手册](./runbooks/)

## 环境准备

1. 克隆仓库并同步依赖：

```bash
git clone <repository_url>
cd WorkDataHub
uv sync
uv run pre-commit install
```

2. 在仓库根目录创建 `.wdh_env`，至少包含：

```env
PYTHONPATH=src
DATABASE_URL=postgresql://user:password@localhost:5432/postgres
```

3. 如需企业解析或 GUI 能力，再补充 `EQC_API_KEY`、`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 等环境变量。

## 数据库准备

```bash
uv run --env-file .wdh_env alembic upgrade head
```

## 活动 ETL 域

| Domain | Source Path | Sheet Selection | Output |
|--------|-------------|-----------------|--------|
| `annuity_performance` | `data/real_data/{YYYYMM}/收集数据/数据采集` | `规模明细` | `business."规模明细"` |
| `annuity_income` | `data/real_data/{YYYYMM}/收集数据/数据采集` | `收入明细` | `business."收入明细"` |
| `annual_award` | `data/real_data/{YYYYMM}/收集数据/业务收集` | `企年受托中标(空白)` + `企年投资中标(空白)` | `customer."中标客户明细"` |
| `annual_loss` | `data/real_data/{YYYYMM}/收集数据/业务收集` | `企年受托流失(解约)` + `企年投资流失(解约)` | `customer."流失客户明细"` |
| `sandbox_trustee_performance` | `data/real_data/202411/收集数据/业务收集` | sheet `0` | `sandbox.sandbox_trustee_performance` |

## CLI 诊断命令

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --help
uv run --env-file .wdh_env python -m work_data_hub.cli etl --check-db
```

## 手动执行 ETL

单域运行仍然使用 `--domains`，只传一个域名即可。

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --plan-only
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --execute
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance,annuity_income \
  --period 202411 \
  --execute
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains \
  --period 202411 \
  --file-selection newest \
  --execute
```

需要跳过企业解析或后置 Hook 时：

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annual_award \
  --period 202411 \
  --no-enrichment \
  --execute
```

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance \
  --period 202411 \
  --execute \
  --no-post-hooks
```

## 参数参考

| 参数 | 说明 |
|------|------|
| `--domains` | 单域或多域执行入口；多个域以逗号分隔 |
| `--all-domains` | 运行所有已配置且非特殊编排域 |
| `--period` | 账期，格式为 `YYYYMM` |
| `--plan-only` | 仅生成执行计划，不写库 |
| `--execute` | 真正落库执行 |
| `--file-selection` | 多文件匹配时的选择策略：`error`、`newest`、`oldest`、`first` |
| `--no-enrichment` | 关闭企业解析 |
| `--no-post-hooks` | 关闭 Post-ETL Hooks |
| `--check-db` | 只验证数据库连接 |
| `--no-auto-refresh-token` | 跳过启动时的 EQC token 自动刷新 |

## 验证

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --plan-only
uv run --env-file .wdh_env python scripts/quality/check_docs_alignment.py
```

## 后置操作

`annuity_performance` 成功执行后，默认会继续触发客户主数据相关 Hook。若需要手动补跑：

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202411
```
