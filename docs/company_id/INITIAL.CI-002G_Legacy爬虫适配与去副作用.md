# INITIAL.CI-002G — Legacy 爬虫适配与去副作用（Provider 化/输出规范）

目的：将 legacy 爬虫能力以适配层方式纳入新架构 Provider 体系，移除交互式与直写数据库的副作用，统一为“标准输出/文件 + 导入器”的无副作用形态。

## WHY
- 现状 `legacy/annuity_hub/crawler/run.py` 交互式、直写 Mongo/MySQL、与主流程割裂。
- 目标：无侵入、可复用、可测试。将其行为重构为 Provider 适配或生成规范化中间文件供导入。

## FEATURE
- 提供两条路径，按环境选择（KISS）：
  1) 适配层 Provider：在 `src/work_data_hub/integrations/legacy/` 提供 `LegacyEqcAdapterProvider`，内部复用既有抓取逻辑/解析器，但去除 DB 写入，返回 `CompanyCandidate/CompanyDetail`。
  2) 规范化输出：保留独立抓取 CLI，将结果输出为 NDJSON/CSV（staging 目录），配套导入器将其写入 `enterprise.company_master/company_name_index`。
- 移除/禁用交互式 `input()`；通过 CLI 参数或配置传入关键词/ID 列表。
- 秘钥管理：与 CI-002F 一致使用环境变量，集中读取。

## SCOPE
- In-scope：适配层/或输出器；移除直写数据库；CLI 参数化；基础日志与错误处理。
- Non-goals：不重写全部 legacy 爬虫；不改变其核心抓取算法，仅包裹/抽取结果。

## CONTRACTS
- 适配 Provider：实现 `EnterpriseInfoProvider` 协议；内部不得写 DB，只返回结果。
- 规范化文件：
  - NDJSON：每行单对象 `{official_name, company_id?, unite_code?, aliases[], source}`。
  - CSV：同字段（UTF-8）。

## VALIDATION
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k legacy_adapter
```

## ACCEPTANCE CRITERIA
- 适配 Provider 在无网络/有网络条件下可替换 EqcProvider（功能等价）；或 CLI 能输出规范化文件并通过导入器完整入库；无 DB 直写副作用。

## RISKS
- legacy 模块耦合度高：优先“包裹而非重写”，逐步减法。

