# WorkDataHub 数据处理指南

> Source of truth: `config/data_sources.yml`, `config/foreign_keys.yml`, `config/customer_status_rules.yml`, `src/work_data_hub/orchestration/jobs.py`, `src/work_data_hub/orchestration/ops/`, `src/work_data_hub/cli/etl/main.py`, `src/work_data_hub/cli/customer_mdm/`, `src/work_data_hub/domain/*/pipeline_builder.py`
> Last verified: `2026-04-11`
> Scope: Current processing flow and operator-facing data movement overview

## 1. 整体处理链路

当前主 ETL 作业使用 `generic_domain_job`，标准链路如下：

1. `discover_files_op`
2. `read_data_op`
3. `process_domain_op_v2`
4. `generic_backfill_refs_op`
5. `gate_after_backfill`
6. `load_op`

沙箱域 `sandbox_trustee_performance` 在多文件场景下还会走 `generic_domain_multi_file_job`。

关键运行事实：

- 不传 `--execute` 时默认是 plan-only
- 单域和多域入口统一使用 `--domains`
- `--all-domains` 会跳过特殊域，例如 `sandbox_trustee_performance`
- `--file-selection` 控制多文件匹配时的行为，支持 `error`、`newest`、`oldest`、`first`

## 2. 当前活动 ETL 域

| Domain | 输入 | 输出 | 回填 |
|--------|------|------|------|
| `annuity_performance` | `数据采集` / `规模明细` | `business."规模明细"` | 是 |
| `annuity_income` | `数据采集` / `收入明细` | `business."收入明细"` | 是 |
| `annual_award` | `业务收集` / 多 Sheet 中标页 | `customer."中标客户明细"` | 是 |
| `annual_loss` | `业务收集` / 多 Sheet 流失页 | `customer."流失客户明细"` | 是 |
| `sandbox_trustee_performance` | `业务收集` / sheet `0` | `sandbox.sandbox_trustee_performance` | 否，通常无有效回填配置 |

活动域定义以 `config/data_sources.yml` 与 `src/work_data_hub/domain/registry.py` 的交集为准。

## 3. Company ID 解析

活动流水线中的 `CompanyIdResolutionStep` 走共享解析路径。当前代码对应的核心事实：

- 优先命中 YAML / 本地映射与数据库缓存
- 数据库缓存核心表是 `enterprise.enrichment_index`
- EQC 查询结果会写入 `enterprise.base_info`，并尽量缓存到 `enterprise.enrichment_index`
- 无法解析时可以生成 `IN*` 临时 ID

实现入口主要位于：

- `src/work_data_hub/infrastructure/enrichment/resolver/`
- `src/work_data_hub/infrastructure/enrichment/eqc_provider.py`
- `src/work_data_hub/io/loader/company_enrichment_loader.py`

## 4. 外键回填

回填由 `config/foreign_keys.yml` 和 `generic_backfill_refs_op` 驱动。当前活动范围：

- `annuity_performance` 和 `annuity_income` 会回填多类主数据
- `annual_award` 和 `annual_loss` 当前主要回填客户相关维度
- `sandbox_trustee_performance` 一般不依赖有效回填配置

回填在 `load_op` 前通过 `gate_after_backfill` 串联，保证依赖顺序成立。

## 5. Post-ETL Hooks

当前只有 `annuity_performance` 会触发 Post-ETL Hooks，顺序固定为：

1. `contract_status_sync`
2. `year_init`
3. `snapshot_refresh`

实现位于 `src/work_data_hub/cli/etl/hooks.py`。

## 6. Customer MDM

当前人工入口：

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync --period 202601
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202601
```

说明：

- `sync` 支持 `--period`，不传时会同步所有可用数据
- `snapshot` 必须传 `--period`

## 7. 常用命令

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202601 --plan-only
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance --period 202601 --execute
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202601 --execute
uv run --env-file .wdh_env python -m work_data_hub.cli etl --all-domains --period 202601 --file-selection newest --execute
```

完整 CLI 说明见 [部署与运行指南](../deployment_run_guide.md)。

## 8. 真相源文件

| 职责 | 文件 |
|------|------|
| 域发现与输出 | `config/data_sources.yml` |
| 回填规则 | `config/foreign_keys.yml` |
| 客户状态规则 | `config/customer_status_rules.yml` |
| Dagster 作业 | `src/work_data_hub/orchestration/jobs.py` |
| 通用 op | `src/work_data_hub/orchestration/ops/` |
| ETL CLI | `src/work_data_hub/cli/etl/main.py` |
| Post-ETL hooks | `src/work_data_hub/cli/etl/hooks.py` |
| Customer MDM CLI | `src/work_data_hub/cli/customer_mdm/` |
| 各域流水线 | `src/work_data_hub/domain/*/pipeline_builder.py` |

如果代码与本文不一致，以这些文件为准，并更新本文。
