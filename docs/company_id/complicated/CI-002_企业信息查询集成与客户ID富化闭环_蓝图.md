# CI-002 — 外部企业信息查询集成 + company_id 富化闭环（蓝图 | 同步预算 可选 + 异步回填）

本 INITIAL 针对“规模明细”事实中的 `company_id` 归属判定提出全新架构：将外部企业信息查询系统纳入数据闭环，结合缓存与回填机制，提高客户主数据质量与解析命中率。方案聚焦动机与目标（而非复刻 legacy 实现细节），在保持 CLI-first 与最小侵入的前提下，实现“同步小预算 + 异步批量回填”的高效工作流。

注意：为便于追踪与逐步交付，CI-002 已拆分为以下结构化子任务（各自有独立文档）：
- CI-002A_Provider与Gateway最小闭环.md
- CI-002B_缓存与名称索引与请求队列.md
- CI-002D_异步回填作业与队列消费者.md
- CI-002E_可观测性与运营指标.md
- CI-002F_真实Provider(EQC)实现与密钥管理.md
- CI-002G_Legacy爬虫适配与去副作用.md
- CI-002H_存量数据迁移与兼容导入(Mongo-MySQL到Postgres缓存).md
- CI-002C_同步小预算富化集成.md（可选，默认关闭）

请以以上子文档为执行单元开展 PRP 与实现，本文保留为总体蓝图与索引。

参照：KISS、YAGNI；README/ROADMAP；MIGRATION_REFERENCE；LEGACY_WORKFLOW_ANALYSIS。

## WHY（动机）

- 内部客户名称质量不稳，别名/简称/错别字多，纯内部映射命中率有限。
- legacy 将爬虫手动运行且与主流程割裂，缺乏闭环与可观测性。
- 目标是“更好且优雅”的新实现：引入外部企业信息查询为权威数据源，形成“请求→缓存→匹配→回填”的闭环，提升质量同时控制复杂度与成本。

## FEATURE（主目标）

1) 引入标准化 Provider 接口对接外部企业信息查询系统（可插拔，多实现）。
2) 建立两段式富化策略：
   - 同步小预算（Sync Budget）：主作业执行期内对少量未解析样本进行在线查询，受额度/速率限制，保障实时性。
   - 异步批量回填（Async Backfill）：将剩余未解析样本写入请求队列，由独立 CLI 任务批量查询并落库缓存，供后续运行命中。
3) 建立缓存与索引：统一“公司主数据 + 名称映射”缓存表，支持规范化名称索引查询与别名回溯。
4) 全链路可观测：命中来源分布、同步消耗预算、未解析导出、回填进度与命中提升报告。

## SCOPE（范围）

- In-scope
  - Provider 抽象：`EnterpriseInfoProvider`（search_by_name / get_by_id），默认提供 StubProvider（读取本地 fixtures，便于无网络测试）；真实 Provider（如 EQC）在具备凭据时启用。
  - 网关聚合：`EnterpriseInfoGateway`（优先级匹配 + 统一评分），隐藏多 Provider 细节与降级策略。
  - 缓存存储：企业主数据与名称映射（见“数据契约/DDL”），以及“富化请求队列表”。
  - 解析策略整合：
    1) 配置覆盖（计划代码 → company_id）
    2) DB 参考/账户映射（年金计划、账户映射）
    3) 名称映射缓存（统一别名索引）
    4) 同步在线查询（小预算）
    5) 异步请求入队（批量回填）
    6) 安全兜底（仅在计划与客户名均空时使用默认值）
  - CLI-first 集成：
    - 主作业：读取 → 处理 → 富化（含小预算同步） → 引用回填（plans/portfolios）→ 装载。
    - 回填作业：消费请求队列 → 调用 Provider → 更新缓存 → 统计报告。
  - 可观测性：富化汇总日志 + CSV 未解析导出；回填作业输出增量命中率。

- Non-goals
  - 不部署 Dagster 守护/服务面（C-050 gate 未触发）；保持 CLI-first。
  - 不一次性重构 MappingService（C-014），先以 Gateway + 缓存最小可用；后续可演进为通用规则引擎。
  - 不引入复杂分布式队列；请求队列用数据库表实现（简洁可控）。

## ARCHITECTURE（关键设计）

组件划分（建议位置）：
- `src/work_data_hub/domain/shared/company_id_gateway.py`
  - `EnterpriseInfoProvider` 协议：`search_by_name(name:str)->List[CompanyCandidate]`，`get_by_id(id:str)->CompanyDetail|None`
  - `StubProvider`：基于 `tests/fixtures/enterprise_provider/*.json` 返回固定数据（便于离线验收）。
  - `EnterpriseInfoGateway`：聚合多 Provider，并实现：
    - 名称规范化与评分（精确匹配 > 别名/曾用名 > 相似度阈值）
    - 速率/额度控制（Sync Budget）
    - 命中后写缓存（主数据 + 名称映射）

- 缓存与请求队列（数据库侧，见下方 DDL）：
  - `enterprise.company_master`：公司主数据（company_id、统一社会信用代码、官方名、别名/曾用名）
  - `enterprise.company_name_index`：规范化名称 → company_id 的索引表（多对一）
  - `enterprise.enrichment_requests`：富化请求队列（name、状态、尝试次数、最后错误、入队时间）
  - 兼容现有表：可保留 `enterprise.company_id_mapping` 作为历史兼容视图/导入来源

数据流（主作业，简化视图）：
```
discover → read_excel → domain.process → enrich(company_id) → derive_*_refs → backfill_refs → load
                                         └─ 未解析：
                                              - 同步小预算查询（实时命中）
                                              - 仍未命中 → 入队 enrichment_requests + 导出 CSV
```

数据流（回填作业）：
```
consume enrichment_requests → provider.search → upsert company_master/name_index → mark done/failed
```

## DATA CONTRACTS（数据契约与 DDL）

核心模型（Pydantic 简化）：
- CompanyCandidate：{ company_id:str?, official_name:str, unite_code:str?, score:float, aliases:list[str]? }
- CompanyDetail：{ company_id:str, official_name:str, unite_code:str?, aliases:list[str], source:str }

PostgreSQL 最小 DDL（测试环境；生产按需调整 schema/索引）：
```sql
CREATE SCHEMA IF NOT EXISTS enterprise;

CREATE TABLE IF NOT EXISTS enterprise.company_master (
  company_id  VARCHAR(50) PRIMARY KEY,
  official_name TEXT NOT NULL,
  unite_code  TEXT,
  aliases     TEXT[],
  source      TEXT,
  updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise.company_name_index (
  norm_name   TEXT PRIMARY KEY,
  company_id  VARCHAR(50) NOT NULL REFERENCES enterprise.company_master(company_id),
  match_type  TEXT, -- exact|alias|fuzzy
  updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise.enrichment_requests (
  id          BIGSERIAL PRIMARY KEY,
  raw_name    TEXT NOT NULL,
  norm_name   TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending', -- pending|processing|done|failed
  attempts    INT  NOT NULL DEFAULT 0,
  last_error  TEXT,
  requested_at TIMESTAMPTZ DEFAULT now(),
  updated_at   TIMESTAMPTZ DEFAULT now()
);
```

匹配优先级（按序短路）：
1) 配置覆盖（计划代码 → company_id）
2) 参考/账户映射（年金计划、账户映射）
3) 名称索引表 `company_name_index`（norm_name 精确/别名命中）
4) 同步小预算在线查询（命中后写入 company_master/name_index）
5) 入队请求（异步回填），主流程继续（记录未解析数）
6) 兜底：仅在计划与客户名均空时使用默认值（与 legacy 一致），否则保持空以驱动后续回填

## INTEGRATION（与现有架构的对接）

- Domain 层（最小侵入）：
  - 在 annuity_performance `service.py` 的 company_id 提取处，改为委托 `CompanyIdGateway`（通过开关控制），保留现有轻启发式为最后保底。
- Ops 层：
  - process_annuity_performance_op：
    - 注入 Gateway（从 settings/env 读取 provider/预算配置）。
    - 输出 CompanyId Enrichment Summary（来源命中计数、sync 消耗、unknown 数量）。
    - 将 unknown 写入 `enterprise.enrichment_requests` 并导出 CSV。
  - 新增回填 CLI：`uv run python -m src.work_data_hub.orchestration.jobs --execute --job enrich_company_master`（或独立脚本），消费队列批量更新缓存并产出报告。

## CONFIG（开关与环境变量）

- `WDH_ENRICH_COMPANY_ID=1`：启用 Gateway。
- `WDH_ENRICH_SYNC_BUDGET=20`：每次运行允许的同步在线查询最大条数（控制成本）。
- `WDH_ENTERPRISE_PROVIDER=stub|eqc|...`：选择 Provider 实现。
- `WDH_PROVIDER_EQC_TOKEN=...`：真实 Provider 凭据（仅当选择 eqc 时需要）。

## VALIDATION（验证与命令）

基础门：
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k company_id
```

计划模式（不触库，仅演示解析计数与入队预览；StubProvider 可用）：
```bash
export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
export WDH_ENRICH_COMPANY_ID=1
export WDH_ENTERPRISE_PROVIDER=stub
export WDH_ENRICH_SYNC_BUDGET=10
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --plan-only \
  --max-files 1 \
  --sheet "规模明细" \
  --debug
```

执行模式（需 DB，可先创建最小 DDL；若无真实 Provider，仍可用 stub 验证闭环流程与命中提升）：
```bash
export WDH_DATABASE__URI=postgresql://user:pwd@host:5432/db
export WDH_ENRICH_COMPANY_ID=1
export WDH_ENTERPRISE_PROVIDER=stub # 或 eqc（凭据就绪后）
export WDH_ENRICH_SYNC_BUDGET=20

# 主作业（会写入 enrichment_requests + 导出 CSV）
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --max-files 1 \
  --mode append \
  --sheet "规模明细" \
  --debug --raise-on-error

# 回填作业（消费队列、更新缓存、生成报告）
uv run python -m src.work_data_hub.orchestration.jobs \
  --execute \
  --job enrich_company_master \
  --debug

# 二次运行主作业（命中率应提升，unknown 降低）
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute \
  --max-files 1 \
  --mode append \
  --sheet "规模明细" \
  --debug
```

期望结果：
- 首次执行：Summary 显示覆盖/参考/名称索引/同步命中分布，未知样本入队并导出 CSV。
- 回填后：company_master/name_index 增长，二次运行未知显著下降，命中率提升可量化。

## ACCEPTANCE CRITERIA（验收）

- 功能：
  - 同步预算严格生效；超预算样本全部入队异步回填。
  - Provider 可切换（stub/eqc），无网络时 stub 测试可完整跑通闭环。
  - 命中来源分布、预算消耗、入队/处理数量、未知样本 CSV 均可观测。
- 质量：
  - ruff/mypy/pytest 全绿；新增单测覆盖优先级与预算控制；E2E 验证 unknown 下降。
- 非侵入：
  - 默认不开启富化不影响现有 E2E；开启后对装载结果的稳定性与幂等性有保障（同一名称重复查询应命中缓存）。

## RISKS & MITIGATIONS（风险与缓解）

- 外部服务不稳定/限流：采用预算 + 队列 + 缓存；失败重试带退避，错误入库便于排查。
- 名称歧义：采用规范化 + 多信号评分（官方名/统一社会信用代码/别名）并保守阈值；低置信度先入队人工复核。
- 凭据安全：使用 .env 与 secrets，遵循 `docs/security/SECRETS_POLICY.md`；CI 不注入真实凭据。
- schema 差异：以最小 DDL 为起步；生产库可通过视图/ETL 与既有数据域衔接。

## ROLLOUT（分阶段推进）

P1 最小闭环（本 PRP 范围）
- Gateway + StubProvider + 缓存/队列表 + 主/回填 CLI + 基本统计与 CSV 导出。

P2 接入真实 Provider（如 EQC）
- 新增 Provider 实现、凭据配置、速率限制；补充更多字段落库（可选）。

P3 统一 MappingService（可选）
- 将 Gateway 能力纳入通用 MappingService（C-014），服务更多域模型。

---

Exit Criteria（退出标准）
- 主/回填两条 CLI 流程可在无网络（stub）与有网络（真实 Provider）两种模式下通过；unknown 规模在二次运行显著下降；日志/CSV/统计齐全；ruff/mypy/pytest 全绿。
