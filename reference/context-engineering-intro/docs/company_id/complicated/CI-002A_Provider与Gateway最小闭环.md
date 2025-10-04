# CI-002A — Provider 与 Gateway 最小闭环

## 背景与定位
- 目标：提供可插拔的外部企业信息查询能力，形成“查询→候选→评分→返回”的最小闭环，用于验证整体方案中“外部补全”的关键一环。
- 不落库：本子任务不引入数据库改动，仅以内存/fixtures 验证 Provider 与 Gateway 的协议与评分逻辑。
- 关联：作为 CI-002 蓝图的起点，优先完成以便后续 B/D 等任务复用接口。

## 依赖与前置
- 环境：无网络也可运行（使用 StubProvider + 本地 fixtures）。
- 配置：参考 `docs/company_id/CONFIG.CI-ENV.md`（`WDH_ENTERPRISE_PROVIDER=stub`）。

## 相关文档
- 问题与方案（主文）：`docs/company_id/PROBLEM.CI-000_问题定义与解决方案.md`
- 蓝图导航：`docs/company_id/CI-002_企业信息查询集成与客户ID富化闭环_蓝图.md`
- 环境配置：`docs/company_id/CONFIG.CI-ENV.md`

目的：提供可插拔外部企业信息查询能力（无网络亦可验证），抽象 Provider 接口与 Gateway 聚合，形成最小闭环（查询→候选→评分→返回）。暂不写 DB，仅内存/fixtures 验证。

## FEATURE
- 定义 `EnterpriseInfoProvider` 协议（search_by_name/get_by_id）。
- 提供 `StubProvider`（读取本地 fixtures，便于 CI/无网络环境）。
- 聚合 `EnterpriseInfoGateway`：名称规范化、基础评分、Provider 选择与降级。

## SCOPE
- In-scope：协议、StubProvider、Gateway、最小模型（CompanyCandidate/CompanyDetail）、名称规范化工具。
- Non-goals：不涉及数据库、缓存、请求队列；不改动现有 pipeline；不接入真实 Provider。

## CONTRACTS
- CompanyCandidate: { official_name:str, company_id:str?, unite_code:str?, score:float, aliases:list[str]? }
- CompanyDetail: { company_id:str, official_name:str, unite_code:str?, aliases:list[str], source:str }
- Provider:
  - search_by_name(name:str) -> list[CompanyCandidate]
  - get_by_id(id:str) -> CompanyDetail | None

## VALIDATION
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k provider_gateway
```

## ACCEPTANCE CRITERIA
- 无网络环境使用 fixtures 即可稳定返回候选；Gateway 对规范化后名称能给出 determinisitc 最高分候选；类型检查与测试通过。

## RISKS
- 评分策略欠精细：先提供可替换策略接口，后续按需要扩展；保持 KISS。
