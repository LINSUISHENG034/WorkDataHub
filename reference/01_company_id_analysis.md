# company_id 字段背景与方案综述

> 整理自 `reference/archive/context-engineering-intro/docs/company_id/*` 中的讨论、蓝图与实施记录，旨在向新团队交付一份兼顾背景、限制、既有成果与经验教训的单文档。

## 1. 问题定义与历史症结
- **识别目标**：为每条业务事实（尤其是规模明细）确定“稳定、唯一、可追溯”的客户主体标识 `company_id`，以 EQC 平台 ID 为权威主键（源自 `complicated/PROBLEM.CI-000_问题定义与解决方案.md`、`simplified/PROBLEM.CI-001_问题定义.md`）。
- **症结来源**：内部客户名称质量差（别名、错别字、不同历史阶段的写法）、计划/账户信息无统一映射，legacy 方案依赖手工爬虫与 Mongo/MySQL，缺乏闭环与可观测性。
- **两阶段策略**：①充分尊重历史：通过内部规则表（计划、账户、名称索引）尽量命中；②外部补全：调用 EQC 模糊搜索、曾用名与统一社会信用代码，获取权威 `company_id` 并反哺内部映射。
- **非目标**：不在当前阶段构建复杂 UI、审批流或重量级服务面；不一次性重写全部历史事实主键，而是通过别名映射/视图聚合逐步收敛。

## 2. 业务目标与成功标准
- **统一口径**：跨批次、跨域共享同一规范 `company_id`，下游通过视图或 Join `company_id_xref` 获得一致语义。
- **可回溯**：记录来源（internal/external）、匹配方式（exact/alias/fuzzy）、置信度、证据与更新时间线，支撑审计与人审。
- **渐进闭环**：主流程不中断，未命中样本写入请求队列/CSV，异步回填后命中率逐步提升。
- **量化门槛**：内部/外部命中率显著提升、未知样本占比持续下降、回填成功率与预算消耗可观测、同一客户多批次 ID 一致。

## 3. 约束与设计准则
- **技术栈**：Postgres 可扩展 schema/index/view；流程保持 CLI-first（`uv run python -m src.work_data_hub.orchestration.jobs ...`），避免 Dagster 守护或长生命周期服务（CI-002 蓝图）。
- **安全与合规**：凭据通过环境变量管理，日志不得泄露 Token；符合 `docs/security/SECRETS_POLICY.md`。
- **KISS / YAGNI**：先跑通最小闭环（A/B/D/E），按需引入同步小预算（C）或高级 Provider/评分。
- **可靠性优先**：外部故障不能阻塞主流程；异步作业具备重试、限速与错误记录。

## 4. 输入信号与数据资产
- **内部信号**：计划代码、年金计划（plan）、账户号/名、已有客户名称与其规范化版本、历史硬编码映射（`legacy/annuity_hub/data_handler/mappings.py`）。
- **外部信号**：EQC 搜索返回的官方名、统一社会信用代码、company_id、别名/曾用名及匹配分数（CI-002F、S-002 文档）。
- **内部映射表建议**（PROBLEM 文档第 10.3 节）：`plan_company_map`、`account_company_map`、`name_company_index`、`company_id_xref`。

## 5. 临时 ID 与治理策略
- **别名 ID**：未确认主体使用 `IN_<16位Base32>`，由 `HMAC_SHA1(alias_salt, business_key)` 前 128 bit 生成，保证稳定、脱敏与可追溯；盐值变量 `WDH_ALIAS_SALT`。
- **Business Key 组成**：规范化客户名称 +（可选）计划代码/账户号等强信号，以 `|` 连接，确保同源数据映射一致。
- **人审阈值**：置信度 ≥0.90 直接采纳；0.60–0.90 先采纳但标记 `needs_review`；<0.60 维持 `IN_` 并进入回填队列（PROBLEM 文档第 10.2 节）。
- **查询优先级**：配置覆盖 → 计划 → 账户 → 名称索引 → 同步在线 → 入队异步 → 兜底（CI-002 蓝图、CI-002C）。

## 6. CI-002 架构蓝图（复杂方案）

### 6.1 关键组件与数据流（`complicated/CI-002_*.md`）
- **Provider 层**：`EnterpriseInfoProvider` 协议（search_by_name / get_by_id），默认有 `StubProvider`（离线 fixtures）与真实 `EqcProvider`；可按需插入 Legacy 适配（CI-002A/F/G）。
- **Gateway**：`EnterpriseInfoGateway` 统一规范化、评分、降级策略及同步预算控制，命中后写缓存。
- **缓存与索引**：Postgres `enterprise.company_master`、`enterprise.company_name_index` 持久化主数据与规范化名称索引。
- **请求队列**：`enterprise.enrichment_requests` 承载未解析样本，支持 pending → processing → done/failed 的状态机。
- **数据流**：主作业中 discover → enrich(company_id)；未命中样本先尝试同步小预算，再写入队列并导出 CSV；回填作业消费队列 → Provider → 更新缓存 → 标记完成 → 下次主作业命中。

### 6.2 核心数据模型与 DDL（`CI-002B` 蓝图）
- `enterprise.company_master(company_id, official_name, unite_code, aliases[], source, updated_at)`
- `enterprise.company_name_index(norm_name PRIMARY KEY, company_id, match_type, updated_at)`
- `enterprise.enrichment_requests(id, raw_name, norm_name, status, attempts, last_error, requested_at, updated_at)`
- Pydantic 模型：`CompanyCandidate`、`CompanyDetail`、`LookupRequest`、`CompanyIdResult` 等（CI-002 蓝图、S-003）。

### 6.3 CLI 任务与配置
- **主流程**：
  ```bash
  uv run python -m src.work_data_hub.orchestration.jobs \
    --domain annuity_performance \
    --execute --max-files 1 --mode append \
    --sheet "规模明细" --debug --raise-on-error
  ```
- **回填作业**：
  ```bash
  uv run python -m src.work_data_hub.orchestration.jobs \
    --execute --job enrich_company_master --debug
  ```
- **关键开关**（`CONFIG.CI-ENV.md`、CI-002C）：`WDH_ENRICH_COMPANY_ID`、`WDH_ENRICH_SYNC_BUDGET`、`WDH_ENTERPRISE_PROVIDER`、`WDH_PROVIDER_EQC_TOKEN`。默认不开启富化以保持现有 E2E 稳定。
- **验证门**：`uv run ruff check src/ --fix`、`uv run mypy src/`、`uv run pytest -v -k company_id`，并以 CSV/日志确认命中分布与 unknown 缩减。

## 7. CI-002 子任务拆分回顾

| 编号 | 主题 | 关键要点 |
| --- | --- | --- |
| CI-002A | Provider 与 Gateway 最小闭环 | 定义 `EnterpriseInfoProvider` 协议、StubProvider、Gateway，先在内存/fixtures 验证评分与降级逻辑。 |
| CI-002B | 缓存与名称索引与请求队列 | 提供最小 DDL + DAO，建立 `company_master`、`company_name_index`、`enrichment_requests`。 |
| CI-002C | 同步小预算富化（可选） | 在 `process_annuity_performance_op` 中调用 Gateway，受 `WDH_ENRICH_SYNC_BUDGET` 控制，unknown 样本入队+CSV。 |
| CI-002D | 异步回填作业 | 新增 CLI 消费队列，调用 Provider，命中即 upsert 缓存并输出报告；失败重试+退避。 |
| CI-002E | 可观测性与运营指标 | 输出命中来源分布、预算消耗、队列规模/成功率、unknown CSV，支持多次运行对比。 |
| CI-002F | 真实 Provider (EQC) 与密钥 | 实现 `EqcProvider`，管理 `WDH_PROVIDER_EQC_TOKEN`，处理限流/超时/重试，日志脱敏。 |
| CI-002G | Legacy 爬虫适配 | 将 `legacy/annuity_hub/crawler` 无副作用化，或导出 NDJSON/CSV + 导入器，统一纳入 Provider 体系。 |
| CI-002H | 存量迁移与兼容导入 | 将 Mongo/MySQL 旧数据导入新缓存/索引（CSV/JSON → upsert），提升冷启动命中率。 |

## 8. EQC 接入与凭据管理经验
- **真实 Provider**：CI-002F 规范了 `EqcProvider` 的 headers（`token`、`Referer`、`User-Agent`）、限流与异常分类。`WDH_PROVIDER_EQC_BASE_URL` 可覆盖默认 API。
- **Token 获取自动化**：`plan/INITIAL.md` 提出了使用 Playwright 触发带头浏览器，监听 `kg-api-hfd/api/search` 请求自动捕获 token，并在超时/用户取消时优雅退出。
- **客户端规范（无抽象层）**：`plan/INITIAL.S-002.md`、`simplified/S-002_EQC客户端集成.md` 定义了 `EQCClient` 接口、Pydantic 模型、重试/限流策略及测试要求。
- **登录页面元素**：`docs/company_id/EQC/login_page_elements.md` 记录了账号/密码/滑块 DOM 选择器，便于自动化或手动操作指南。
- **安全约束**：日志禁止输出 Token；CI 环境使用 StubProvider；真实凭据仅在本地/受控环境注入。

## 9. 简化路线（KISS 版本，`docs/company_id/simplified/*`）
- **S-001 Legacy 映射迁移**：将 5 层映射（计划→账户→硬编码→客户名→账户名）统一到 `enterprise.company_mapping`，保留优先级字段 `priority`，新 loader + CLI `--job import_company_mappings`。
- **S-002 EQC 客户端**：直接实现 `EQCClient`，不引入 Gateway/Provider 抽象，关注 token 管理、基本重试与速率限制。
- **S-003 基础缓存机制**：`CompanyEnrichmentService` 整合 S-001/S-002，提供 `lookup_requests` 队列、`TEMP_000001` 序列生成器、配置 `WDH_COMPANY_ENRICHMENT_ENABLED` 等。
- **S-004 MVP 端到端验证**：在 `annuity_performance` 域集成 enrichment，生成统计、unknown CSV，与 legacy 结果对比 ≥95% 一致，并量化性能开销。
- **Phase 2 可选**：S-005 异步查询机制仅在并发/性能诉求触发后考虑。

## 10. Legacy 适配与数据迁移策略
- **Legacy 爬虫（CI-002G）**：强调“包裹而非重写”，通过 Provider 适配或规范化导出，移除交互式输入与直写数据库副作用。
- **存量导入（CI-002H / S-001）**：将 Mongo/MySQL `company_id_mapping`、`base_info`、`annuity_account_mapping` 导出 CSV/JSON，再 upsert 至 `company_master/name_index`，并记录 `source` 与规范化名称，确保幂等。
- **兼容策略**：保留 legacy 覆盖逻辑作为回退（feature flag `WDH_COMPANY_MAPPING_ENABLED`），导入前后做条数校验与备份。

## 11. 可观测性与运营指标
- **Summary 输出**：命中来源分布（overrides/plan/account/name/sync/unknown）、同步预算消耗、入队/处理量、unknown CSV 路径（CI-002E、S-004）。
- **异步报告**：回填作业报告处理条数、成功/失败、缓存新增量、错误摘要；支持多次运行对比 unknown 下降。
- **审计 artefacts**：`unresolved_company_ids.csv`、错误队列记录、`company_id_xref` 元数据（source、confidence、updated_at）。

## 12. 主要风险与经验
- **外部依赖风险**：EQC 限流/抖动，通过同步预算 + 队列 + 重试缓解；失败样本留痕以便排查。
- **名称歧义**：需要规范化与多信号评分，低置信度走人工复核或保持 `IN_`；必要时引入 `review_lock`。
- **凭据安全**：严格管理 `WDH_PROVIDER_EQC_TOKEN` / `WDH_EQC_TOKEN`，日志脱敏；Playwright 自动化仅用于捕获 Token，不保存账号。
- **并发/锁**：请求队列目前假设单实例消费者；若多实例需扩展锁/租约。
- **Schema 演化**：生产库可能已有不同 schema，需要视图或双写策略对接；先以 enterprise schema 为起点。
- **性能**：同步查询预算防止长尾阻塞；异步作业需限制批量大小，避免长事务。

## 13. 对新团队的建议性下一步
1. **确认需求路径**：在复杂（CI-002）与简化（S-001~S-004）方案之间做取舍，优先满足近期交付目标；必要时并行开展“迁移+异步闭环”与“自动获取 Token”。
2. **锁定最小落地包**：若时间紧，先完成 S-001/S-002/S-003，再以 S-004 验证，与 legacy 对比 >95% 一致后再切入 CI-002 的异步/可观测增强。
3. **完善凭据流程**：评估 Playwright 自动化 PoC（INITIAL.md），决定是否产品化；同时设计 EQC Token 轮换与监控。
4. **建立观测面**：根据 CI-002E 的 Summary/CSV 规范落地日志、表与报警，确保任何阶段可量化命中率与 unknown。
5. **准备数据迁移**：按 CI-002H/S-001 的脚本导出 legacy 数据，构建幂等导入 CLI + 验证报告，为后续异步回填提供“温启动”。

## 附录 A · 环境变量速览

| 变量 | 作用 | 备注 |
| --- | --- | --- |
| `WDH_ALIAS_SALT` | 生成 `IN_` 临时 ID 的 HMAC 盐 | 必配，存放于 secrets |
| `WDH_ENRICH_COMPANY_ID` | 是否启用富化流程 | 默认 0 |
| `WDH_ENRICH_SYNC_BUDGET` | 同步在线查询额度 | 默认 0（禁用） |
| `WDH_ENTERPRISE_PROVIDER` | Provider 选择（`stub`/`eqc`/`legacy`…） | 默认 `stub` |
| `WDH_PROVIDER_EQC_TOKEN` / `WDH_EQC_TOKEN` | EQC API Token | 30 分钟有效，日志禁用 |
| `WDH_PROVIDER_EQC_BASE_URL` | EQC API 覆盖地址 | 可选 |
| `WDH_COMPANY_ENRICHMENT_ENABLED` | S-003/S-004 服务开关 | 默认 0 |
| `WDH_COMPANY_SYNC_LOOKUP_LIMIT` | 同步查额度（S-003） | 默认 5 |
| `WDH_LOOKUP_QUEUE_BATCH_SIZE` | 队列批次大小 | 默认 50 |
| `WDH_LOOKUP_RETRY_MAX` / `WDH_LOOKUP_RETRY_DELAY` | 队列重试控制 | 默认 3 / 300s |

## 附录 B · 常用命令
- 代码质量：`uv run ruff check src/ --fix`、`uv run mypy src/`、`uv run pytest -v -k company_id`.
- 主作业（含 plan-only）：`uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only --max-files 1 --sheet "规模明细" --debug`.
- 异步回填：`uv run python -m src.work_data_hub.orchestration.jobs --execute --job enrich_company_master --debug`.
- Legacy 映射导入：`uv run python -m src.work_data_hub.orchestration.jobs --job import_company_mappings --plan-only/--execute`.
- Lookup 队列处理（S-003）：`uv run python -m src.work_data_hub.orchestration.jobs --job process_company_lookup_queue --execute`.

## 附录 C · 参考文档索引
- `.../complicated/PROBLEM.CI-000_问题定义与解决方案.md`
- `.../complicated/CI-002_企业信息查询集成与客户ID富化闭环_蓝图.md`
- `.../complicated/CI-002A~CI-002H*.md`（Provider、缓存、同步/异步、可观测、EQC、legacy、迁移）
- `.../complicated/CONFIG.CI-ENV.md`
- `.../plan/INITIAL*.md`（EQC Token 自动化、EQCClient、缓存服务）
- `.../EQC/login_page_elements.md`
- `.../simplified/README.md`、`S-001~S-004*.md`
- `.../simplified/S-005`（若未来触发 Phase 2）

> 阅读顺序建议：先 PROBLEM → 简化方案概览 → 复杂蓝图 → 子任务文档 → EQC/计划文档 → 迁移与观测；若聚焦凭据或 Browser-Automation，则补充阅读 `plan/INITIAL.md` 与 EQC DOM 记录。
