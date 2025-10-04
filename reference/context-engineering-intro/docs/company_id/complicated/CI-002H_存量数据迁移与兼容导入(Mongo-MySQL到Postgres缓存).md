# CI-002H — 存量数据迁移与兼容导入（Mongo/MySQL → Postgres 缓存）

## 背景与定位
- 目标：将 legacy Mongo/MySQL 存量数据导入到新的缓存/索引表中，以快速提升初始命中率并保持历史一致性。
- 关系：与 D（异步回填）协同，先“提纯历史”，再“增量回填”。

## 依赖与前置
- 输入：`legacy` 中相关来源（如 company_id_mapping/base_info 等）经导出为 CSV/JSON，或直连只读访问。
- 目标：`enterprise.company_master` 与 `enterprise.company_name_index`（来自 CI-002B）。

## 相关文档
- 主文：`docs/company_id/PROBLEM.CI-000_问题定义与解决方案.md`
- 蓝图：`docs/company_id/CI-002_企业信息查询集成与客户ID富化闭环_蓝图.md`

目的：将 legacy Mongo/MySQL 中与企业信息相关的存量数据（如 base_info、company_id_mapping、annuity_account_mapping）迁移/导入到新架构的 Postgres 缓存表，以便立即提升命中率并保持历史一致性。

## FEATURE
- 导入器 CLI：
  - 从 Mongo 导出 JSON/CSV（或直连读取，优先文件导入，降低耦合）
  - 从 MySQL 导出 CSV（或直连）
  - 统一映射字段后 upsert 至 `enterprise.company_master` 与 `enterprise.company_name_index`
  - 可选导入 `enterprise.annuity_account_mapping`（若采用该表）
- 数据清洗：规范化名称（去后缀/空白/大小写），去重与主键冲突处理，记录 source。

## SCOPE
- In-scope：CSV/JSON 读取、字段映射、主键/唯一索引处理、幂等 upsert、基本报告。
- Non-goals：不做复杂血缘与全量一致性校验；不要求在线双写。

## INPUT → OUTPUT（示例映射）
- MySQL enterprise.company_id_mapping(company_id, company_name, type) →
  - company_master(company_id, official_name=company_name if type='current', aliases+=former)
  - company_name_index(norm_name(company_name)) → company_id, match_type=type
- Mongo base_info/business_info →
  - company_master(unite_code/official_name/aliases)（按字段可用情况）

## VALIDATION
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k company_import

# 演示（以 CSV 为例）
uv run python -m scripts.company_id.import_legacy --from-mysql ./exports/company_id_mapping.csv --from-mongo ./exports/base_info.json --debug
```

## ACCEPTANCE CRITERIA
- 导入后缓存表规模上升，重复导入无副作用（幂等）；主作业命中率显著提升；报告包含导入量、跳过量、错误摘要。

## RISKS
- 字段/编码差异：在导入器层面集中做规范化和异常隔离；必要时提供问题行导出。
