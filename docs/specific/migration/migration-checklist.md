# Migration Checklist

> **文档状态**: Active Tracking
> **创建日期**: 2024-12-24
> **数据来源**: Legacy (legacy-mysql MCP) vs Postgres (postgres MCP)

---

## 1. 数据库对比概览

| 来源 | Schema 数量 | 表格总数 | 备注 |
|------|------------|----------|------|
| **Legacy** | 6 (business, config, customer, enterprise, finance, mapping) | 58 | 历史数据源 |
| **Postgres** | 7 (public, business, customer, enterprise, finance, mapping, system) | 22 | 目标数据库 |

---

## 2. Schema: public (ETL 基础设施)

> **来源**: Postgres 新增，Legacy 不存在

| 表名 | Legacy | Postgres | 迁移纳入 | 状态 | 备注 |
|------|--------|----------|----------|------|------|
| alembic_version | ❌ | ✅ | ⬜ 排除 | N/A | Alembic 系统表，自动管理 |
| pipeline_executions | ❌ | ✅ | ✅ 纳入 | ⬜ 待迁移 | ETL 执行追踪 |
| data_quality_metrics | ❌ | ✅ | ✅ 纳入 | ⬜ 待迁移 | 数据质量度量 |

---

## 3. Schema: enterprise (企业信息)

> **Legacy**: 9 表 | **Postgres**: 11 表

### 3.1 核心表 (两边都有)

| 表名 | Legacy | Postgres | 迁移纳入 | 状态 | 备注 |
|------|--------|----------|----------|------|------|
| base_info | ✅ 28,576行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 公司基础信息 |
| business_info | ✅ 11,542行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 工商信息 |
| biz_label | ✅ 126,332行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 业务标签 |
| company_types_classification | ✅ 104行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 公司类型分类 (种子数据) |
| industrial_classification | ✅ 1,183行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 行业分类 (种子数据) |

### 3.2 Postgres 新增表 (Legacy 无)

| 表名 | Legacy | Postgres | 迁移纳入 | 状态 | 备注 |
|------|--------|----------|----------|------|------|
| enrichment_index | ❌ | ✅ | ✅ 纳入 | ⬜ 待迁移 | 公司ID解析缓存 |
| enrichment_requests | ❌ | ✅ | ✅ 纳入 | ⬜ 待迁移 | 异步解析队列 |
| validation_results | ❌ | ✅ | ✅ 纳入 | ⬜ 待迁移 | 验证结果记录 |
| archive_base_info | ❌ | ✅ | ⬜ 排除 | N/A | 归档表 (不纳入) |
| archive_business_info | ❌ | ✅ | ⬜ 排除 | N/A | 归档表 (不纳入) |
| archive_biz_label | ❌ | ✅ | ⬜ 排除 | N/A | 归档表 (不纳入) |

### 3.3 Legacy 独有表 (Postgres 无)

| 表名 | Legacy 行数 | Postgres | 迁移纳入 | 状态 | 备注 |
|------|------------|----------|----------|------|------|
| annuity_account_mapping | 18,248 | ❌ | ⬜ 待定 | ⬜ 未评估 | 年金账户映射 |
| blank_company_id | 494 | ❌ | ⬜ 待定 | ⬜ 未评估 | 空白公司ID记录 |
| company_id_mapping | 19,141 | ❌ | ⬜ 待定 | ⬜ 未评估 | 公司ID映射 (可能被 enrichment_index 替代) |
| eqc_search_result | 11,820 | ❌ | ⬜ 待定 | ⬜ 未评估 | EQC 搜索结果缓存 |

---

## 4. Schema: business (业务数据)

> **Legacy**: 9 表 | **Postgres**: 1 表

### 4.1 已存在表

| 表名 | Legacy | Postgres | 迁移纳入 | 状态 | 备注 |
|------|--------|----------|----------|------|------|
| 规模明细 | ✅ 625,126行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 年金规模明细 (Domain: annuity_performance) |

### 4.2 需要新建表 (Legacy 有)

| 表名 | Legacy 行数 | Postgres | 迁移纳入 | 状态 | 备注 |
|------|------------|----------|----------|------|------|
| 收入明细 | 158,480 | ❌ | ✅ 纳入 | ⬜ 待迁移 | Domain: annuity_income |
| 企康缴费 | 2,087 | ❌ | ⬜ 待定 | ⬜ 未评估 | 企业年金健康缴费 |
| 团养缴费 | 2,907 | ❌ | ⬜ 待定 | ⬜ 未评估 | 团体养老缴费 |
| 组合业绩 | 571 | ❌ | ⬜ 待定 | ⬜ 未评估 | 组合业绩数据 |
| 账管数据 | 8,776 | ❌ | ⬜ 待定 | ⬜ 未评估 | 账户管理数据 |
| 手工调整 | 60 | ❌ | ⬜ 待定 | ⬜ 未评估 | 手工调整记录 |
| 灌入数据 | 60 | ❌ | ⬜ 待定 | ⬜ 未评估 | 数据灌入记录 |
| 提费扩面 | 812 | ❌ | ⬜ 待定 | ⬜ 未评估 | 提费扩面数据 |

---

## 5. Schema: mapping (参考映射)

> **Legacy**: 11 表 | **Postgres**: 6 表

### 5.1 两边都有

| 表名 | Legacy | Postgres | 迁移纳入 | 状态 | 备注 |
|------|--------|----------|----------|------|------|
| 年金计划 | ✅ 1,159行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | Domain: annuity_plans |
| 组合计划 | ✅ 1,338行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | Domain: portfolio_plans |
| 年金客户 | ✅ 10,997行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 年金客户主数据 |
| 产品线 | ✅ 12行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 种子数据 |
| 组织架构 | ✅ 38行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 种子数据 |
| 计划层规模 | ✅ 7行 | ✅ | ✅ 纳入 | ⬜ 待迁移 | 种子数据 |

### 5.2 Legacy 独有表

| 表名 | Legacy 行数 | Postgres | 迁移纳入 | 状态 | 备注 |
|------|------------|----------|----------|------|------|
| 产品明细 | 18 | ❌ | ⬜ 待定 | ⬜ 未评估 | 产品明细 (种子数据) |
| 利润指标 | 12 | ❌ | ⬜ 待定 | ⬜ 未评估 | 利润指标 (种子数据) |
| 管理架构 | 28 | ❌ | ⬜ 待定 | ⬜ 未评估 | 管理架构 (种子数据) |
| 客户灌入 | 144 | ❌ | ⬜ 待定 | ⬜ 未评估 | 客户灌入配置 |
| 全量客户 | 0 | ❌ | ⬜ 排除 | N/A | 空表 |

---

## 6. Schema: system (系统表)

> **来源**: Postgres 新增

| 表名 | Legacy | Postgres | 迁移纳入 | 状态 | 备注 |
|------|--------|----------|----------|------|------|
| sync_state | ❌ | ❌ (迁移定义存在) | ✅ 纳入 | ⬜ 待迁移 | 同步状态追踪 |

---

## 7. Schema: customer (客户管理)

> **Legacy**: 21 表 | **Postgres**: 0 表 (Schema 存在但无表)

| 表名 | Legacy 行数 | Postgres | 迁移纳入 | 状态 | 备注 |
|------|------------|----------|----------|------|------|
| 企年受托中标 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年受托已客 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年受托战客 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年受托流失 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年投资中标 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年投资估值流失 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年投资已客 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年投资战客 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年投资新增组合 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 企年投资流失 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 团养中标 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 外部受托客户 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 年金已客名单2023 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 年金已客名单2024 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 战区客户名单 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 投资客户分摊比例表 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 续签客户清单 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 职年受托已客 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 职年投资已客 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 职年投资待遇支付 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 职年投资新增组合 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |

---

## 8. Schema: finance (财务数据)

> **Legacy**: 7 表 | **Postgres**: 0 表 (Schema 存在但无表)

| 表名 | Legacy 行数 | Postgres | 迁移纳入 | 状态 | 备注 |
|------|------------|----------|----------|------|------|
| 减值计提 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 历史浮费 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 固费分摊比例 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 年金费率统计 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 考核收入明细 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 考核收入预算 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |
| 风准金余额表 | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | |

---

## 9. Schema: config (配置)

> **Legacy**: 1 表 | **Postgres**: 无此 Schema

| 表名 | Legacy 行数 | Postgres | 迁移纳入 | 状态 | 备注 |
|------|------------|----------|----------|------|------|
| data_sources | ? | ❌ | ⬜ 待定 | ⬜ 未评估 | 数据源配置 |

---

## 10. 迁移优先级汇总

### 优先级策略说明

| 优先级 | 迁移时机 | 策略 |
|--------|---------|------|
| **P0** | 初始迁移 | 必须纳入，当前系统运行所需 |
| **P1/P2** | 增量迁移 | 按 domain 开发进度逐步添加 |

> **原则**: 不一次性完成全部迁移，按需增量补充

### P0: 核心迁移 (必须纳入)

> 当前架构运行所需

| Schema | 表名 | 分类 | 来源 |
|--------|------|------|------|
| public | pipeline_executions | 基础设施 | 现有迁移 |
| public | data_quality_metrics | 基础设施 | 现有迁移 |
| enterprise | base_info | 企业核心 | 现有迁移 |
| enterprise | business_info | 企业核心 | 现有迁移 |
| enterprise | biz_label | 企业核心 | 现有迁移 |
| enterprise | enrichment_index | 解析服务 | 现有迁移 |
| enterprise | enrichment_requests | 解析服务 | 现有迁移 |
| enterprise | company_types_classification | 种子数据 | 现有迁移 |
| enterprise | industrial_classification | 种子数据 | 现有迁移 |
| enterprise | validation_results | 验证辅助 | 现有结构 |
| business | 规模明细 | 域表 | Domain Registry |
| business | 收入明细 | 域表 | Domain Registry |
| mapping | 年金计划 | 域表 | Domain Registry |
| mapping | 组合计划 | 域表 | Domain Registry |
| mapping | 年金客户 | 参考数据 | 现有结构 |
| mapping | 产品线 | 种子数据 | 现有结构 |
| mapping | 组织架构 | 种子数据 | 现有结构 |
| mapping | 计划层规模 | 种子数据 | 现有结构 |
| system | sync_state | 同步状态 | 现有迁移 |

**总计: 19 表**

### P1: 建议纳入 (Legacy 种子数据)

| Schema | 表名 | 行数 | 备注 |
|--------|------|------|------|
| mapping | 产品明细 | 18 | 种子数据 |
| mapping | 利润指标 | 12 | 种子数据 |
| mapping | 管理架构 | 28 | 种子数据 |
| mapping | 客户灌入 | 144 | 配置数据 |

### P2: 待评估 (Legacy 业务数据)

| Schema | 表名 | 行数 | 备注 |
|--------|------|------|------|
| business | 7张业务表 | 各不同 | 需评估是否纳入 ETL |
| enterprise | 4张映射表 | 各不同 | 可能被新架构替代 |
| customer | 21张客户表 | 各不同 | 需评估业务需求 |
| finance | 7张财务表 | 各不同 | 需评估业务需求 |

### 排除项

| Schema | 表名 | 原因 |
|--------|------|------|
| public | alembic_version | 系统自动管理 |
| enterprise | archive_* (3张) | 归档表，不纳入正式迁移 |
| mapping | 全量客户 | 空表 |

---

## 11. 迁移执行追踪

### Phase 1: 基础设施迁移 (`001_initial_infrastructure.py`)

| 序号 | Schema | 表名 | 状态 | 完成日期 | 备注 |
|------|--------|------|------|----------|------|
| 1 | public | pipeline_executions | ⬜ | | |
| 2 | public | data_quality_metrics | ⬜ | | |
| 3 | enterprise | base_info | ⬜ | | |
| 4 | enterprise | business_info | ⬜ | | |
| 5 | enterprise | biz_label | ⬜ | | |
| 6 | enterprise | enrichment_requests | ⬜ | | |
| 7 | enterprise | enrichment_index | ⬜ | | |
| 8 | enterprise | company_types_classification | ⬜ | | 仅结构 |
| 9 | enterprise | industrial_classification | ⬜ | | 仅结构 |
| 10 | enterprise | validation_results | ⬜ | | |
| 11 | mapping | 产品线 | ⬜ | | |
| 12 | mapping | 组织架构 | ⬜ | | |
| 13 | mapping | 计划层规模 | ⬜ | | |
| 14 | system | sync_state | ⬜ | | |

### Phase 2: 域表迁移 (`002_initial_domains.py`)

| 序号 | Schema | 表名 | Domain | 状态 | 完成日期 | 备注 |
|------|--------|------|--------|------|----------|------|
| 1 | business | 规模明细 | annuity_performance | ⬜ | | |
| 2 | business | 收入明细 | annuity_income | ⬜ | | 需创建 |
| 3 | mapping | 年金计划 | annuity_plans | ⬜ | | |
| 4 | mapping | 组合计划 | portfolio_plans | ⬜ | | |
| 5 | mapping | 年金客户 | - | ⬜ | | |

### Phase 3: 种子数据 (`003_seed_classification.py`)

| 序号 | Schema | 表名 | 行数 | 状态 | 完成日期 | 备注 |
|------|--------|------|------|------|----------|------|
| 1 | enterprise | company_types_classification | 104 | ⬜ | | |
| 2 | enterprise | industrial_classification | 1,183 | ⬜ | | |

---

## 12. 变更历史

| 日期 | 变更内容 | 作者 |
|------|---------|------|
| 2024-12-24 | 初始创建 - 完成 Legacy vs Postgres 对比 | Link, Claude |
