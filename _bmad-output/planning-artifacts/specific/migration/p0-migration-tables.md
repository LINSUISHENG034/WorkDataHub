# P0 Migration Tables Reference

> **更新日期**: 2025-12-28
> **状态**: 已确认
> **核对完成日期**: 2025-12-27
> **用途**: 新迁移脚本编写参考
> **参考文档**: [migration-checklist.md](migration-checklist.md) | [p0-table-diff-analysis.md](p0-table-diff-analysis.md)

---

## 概览

| 迁移阶段 | 表格数量 | 描述 |
|---------|---------|------|
| Phase 1: 基础设施 | 14 | ETL核心 + 企业信息 + 种子数据 |
| Phase 2: 域表 | 7 | 业务域表 + 参考映射表 |
| **总计** | **21** | (Postgres新建3张 + Legacy迁移18张) |

---

## Phase 1: 基础设施迁移 (14张)

### 1.1 ETL 基础设施 (2张 - Postgres 已有)

| # | Schema | Table Name | 行数 | 差异分析 | 备注 |
|---|--------|------------|------|----------|------|
| 1 | `public` | `pipeline_executions` | - | ⬜ 待分析 | ETL 执行追踪 |
| 2 | `public` | `data_quality_metrics` | - | ⬜ 待分析 | 数据质量度量 |

### 1.2 企业核心 (5张 - P0 纳入)

| # | Schema | Table Name | 行数 | 差异分析 | 风险 | 备注 |
|---|--------|------------|------|----------|------|------|
| 3 | `enterprise` | `base_info` | 28,576 | ✅ [分析](p0-table-diff-analysis.md#1-enterprisebase_info) | 🔴 +4字段+3索引 | Story 6.2-P7升级 |
| 4 | `enterprise` | `business_info` | 11,542 | ✅ [分析](p0-table-diff-analysis.md#2-enterprisebusiness_info) | 🔴 主键变更+6字段清洗 | Story 6.2-P7升级 |
| 5 | `enterprise` | `biz_label` | 126,332 | ✅ [分析](p0-table-diff-analysis.md#3-enterprisebiz_label) | 🔴 主键变更+NOT NULL | Story 6.2-P7升级 |
| 6 | `enterprise` | `company_types_classification` | 104 | ✅ [分析](p0-table-diff-analysis.md#5-enterprisecompany_types_classification) | 🟢 零风险 | 8字段完全一致 |
| 7 | `enterprise` | `industrial_classification` | 1,183 | ✅ [分析](p0-table-diff-analysis.md#6-enterpriseindustrial_classification) | 🟢 零风险 | 10字段完全一致 |

### 1.3 新架构功能表 (3张 - Postgres 独有)

> **说明**: 以下表仅存在于 Postgres，无需从 Legacy 迁移数据，仅需在迁移脚本中创建结构

| # | Schema | Table Name | 迁移纳入 | 备注 |
|---|--------|------------|----------|------|
| 8 | `enterprise` | `enrichment_index` | ✅ | 公司ID解析缓存 |
| 9 | `enterprise` | `enrichment_requests` | ✅ | 异步解析队列 |
| 10 | `enterprise` | `validation_results` | ✅ | 验证结果记录 |

### 1.4 种子数据表 (3张)

| # | Schema | Table Name | 行数 | 差异分析 | 风险 | 备注 |
|---|--------|------------|------|----------|------|------|
| 11 | `mapping` | `产品线` | 12→14 | ✅ [分析](p0-table-diff-analysis.md#7-mapping产品线) | 🟡 数据量差异 | 增量迁移ON CONFLICT |
| 12 | `mapping` | `组织架构` | 38→41 | ✅ [分析](p0-table-diff-analysis.md#8-mapping组织架构) | 🟡 数据量差异 | 增量迁移ON CONFLICT |
| 13 | `mapping` | `计划层规模` | 7 | ✅ [分析](p0-table-diff-analysis.md#9-mapping计划层规模) | 🟢 零风险 | 5字段完全一致 |

### 1.5 系统表 (1张)

| # | Schema | Table Name | 行数 | 差异分析 | 备注 |
|---|--------|------------|------|----------|------|
| 14 | `system` | `sync_state` | - | ⬜ 待分析 | 同步状态追踪 |

---

## Phase 2: 域表迁移 (7张)

### 2.1 业务域表 (2张)

| # | Schema | Table Name | 行数 | Domain | 差异分析 | 备注 |
|---|--------|------------|------|--------|----------|------|
| 15 | `business` | `规模明细` | 625,126 | annuity_performance | ⬜ 待分析 | 需对比Domain Registry |
| 16 | `business` | `收入明细` | 158,480 | annuity_income | ⬜ 待分析 | 需创建 |

### 2.2 参考映射表 (5张)

| # | Schema | Table Name | 迁移行数 | 原始行数 | 差异分析 | Domain | 备注 |
|---|--------|------------|----------|----------|----------|--------|------|
| 17 | `mapping` | `年金客户` | 10,204 | 10,997 | ✅ [分析](p0-table-diff-analysis.md#4-mapping年金客户) | - | 🟢 WHERE过滤IN% |
| 18 | `mapping` | `年金计划` | 1,159 | 1,159 | ⬜ 待分析 | annuity_plans | |
| 19 | `mapping` | `组合计划` | 1,338 | 1,338 | ⬜ 待分析 | portfolio_plans | |
| 20 | `mapping` | `产品明细` | 18 | 18 | ⬜ 待分析 | - | 种子数据 |
| 21 | `mapping` | `利润指标` | 12 | 12 | ⬜ 待分析 | - | 种子数据 |

---

## 差异分析完成状态

### 已完成分析 (9张) ✅

| 表名 | 风险等级 | 关键发现 |
|------|----------|---------|
| base_info | 🔴 高 | +4字段(JSONB), +3索引, Story 6.2-P7升级 |
| business_info | 🔴 高 | 主键变更(company_id→id), 6字段类型清洗, 9字段重命名 |
| biz_label | 🔴 高 | 主键变更(_id→id), NOT NULL约束, 126k行性能 |
| 年金客户 | 🟢 低 | 27字段完全一致, 仅需WHERE过滤793行 |
| company_types_classification | 🟢 零 | 8字段完全一致, 104行 |
| industrial_classification | 🟢 零 | 10字段完全一致, 1,183行 |
| 产品线 | 🟡 中 | 6字段一致, 数据量差异(12→14) |
| 组织架构 | 🟡 中 | 9字段一致, 数据量差异(38→41) |
| 计划层规模 | 🟢 零 | 5字段完全一致, 7行 |

### 待分析 (12张) ⬜

| 类别 | 表名 |
|------|------|
| ETL基础 | pipeline_executions, data_quality_metrics |
| 新架构 | enrichment_index, enrichment_requests, validation_results |
| 系统 | sync_state |
| 业务域 | 规模明细, 收入明细 |
| 参考映射 | 年金计划, 组合计划, 产品明细, 利润指标 |

---

## 迁移脚本开发原则

> 来源: migration-checklist.md 第10节

### 核心原则

- ✅ **保护升级**: 保留 Postgres 已有的约束、索引、默认值
- ✅ **增量插入**: 使用 `INSERT ... ON CONFLICT` 避免覆盖现有数据
- ❌ **禁止 DROP**: 不得删除 Postgres 已有的字段或约束
- ❌ **禁止 ALTER TYPE**: 不得修改已有字段的数据类型

### 风险等级说明

| 风险 | 含义 | 迁移策略 |
|------|------|---------|
| 🔴 高 | Legacy与Postgres存在重大差异 | 需要字段映射、数据清洗、ON CONFLICT处理 |
| 🟡 中 | 种子数据完整性需确认 | 增量迁移 + ON CONFLICT DO NOTHING |
| 🟢 低/零 | 结构完全一致或仅需过滤 | 直接迁移 + WHERE条件 |

---

## 排除项

| Schema | Table Name | 原因 |
|--------|------------|------|
| public | alembic_version | 系统自动管理 |
| enterprise | archive_base_info | 归档表 |
| enterprise | archive_business_info | 归档表 |
| enterprise | archive_biz_label | 归档表 |

---

## 变更历史

| 日期 | 变更内容 | 作者 |
|------|---------|------|
| 2025-12-27 | 初始创建 | Link, Claude |
| 2025-12-28 | 根据 migration-checklist.md 第12节更新 - P0表格调整为18张(+产品明细/利润指标), 添加9张表差异分析链接 | Link, Claude |
