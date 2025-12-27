# P0 迁移表结构差异分析

> **分析日期**: 2025-12-27 ~ 2025-12-28
> **目的**: 对比 Legacy MySQL vs Postgres 表结构差异，确保迁移脚本保留项目架构升级
> **参考**: Story 6.2-P7 (Enterprise Schema Consolidation)
> **进度**: 9/18 张表 (50%) 已完成结构差异分析

---

## ⚠️ 重要说明：迁移脚本的范围

### 迁移脚本的职责

**迁移脚本仅负责数据迁移**，不包含DDL操作：

- ✅ **应该做**: `INSERT INTO target_table SELECT ... FROM source_table`
- ✅ **应该做**: 数据类型转换、字段映射、数据清洗
- ✅ **应该做**: WHERE 过滤、外键验证
- ❌ **不应该做**: CREATE TABLE、ALTER TABLE、DROP CONSTRAINT
- ❌ **不应该做**: 修改主键、索引、约束等DDL操作

### 表结构管理

**Postgres 表结构由 Alembic 迁移管理**：

1. **表结构定义**: 通过 Alembic migration scripts (`alembic/versions/*.py`) 创建
2. **主键定义**: 包含在 Alembic 迁移中，不是数据迁移脚本的责任
3. **约束和索引**: 同样由 Alembic 管理

### "主键变更"的真实含义

文档中提到的"主键变更"（如 `company_id` → `id`）是指：

- ✅ **Legacy 表结构**: 使用 `company_id` (VARCHAR) 作为主键
- ✅ **Postgres 表结构**: 使用 `id` (SERIAL) 作为主键
- ⚠️ **这是表结构差异**，不是迁移脚本需要处理的转换
- 📋 **迁移脚本只需**: 按照 Postgres 表结构插入数据即可

### 风险评估调整

因此，"主键变更"不再是迁移风险，真正的风险因素是：

| 风险类型 | 说明 | 影响迁移脚本 |
|---------|------|-------------|
| **数据清洗** | 需要类型转换、正则处理 | ✅ 是 |
| **字段映射** | 需要字段重命名 | ✅ 是 |
| **WHERE 过滤** | 需要剔除部分数据 | ✅ 是 |
| **数据量差异** | Postgres 已有额外数据 | ✅ 是 |
| **NOT NULL 约束** | 需要过滤 NULL 值 | ✅ 是 |
| **主键变更** | 表结构定义差异 | ❌ 否（由Alembic管理） |

---

---

## 分析方法

根据 `migration-checklist.md` 第10节的要求，对每张 P0 迁移表执行以下分析：

1. ✅ 表结构对比 (使用 `mcp__postgres__get_object_details` 和 `mcp__legacy-mysql__get_object_details`)
2. ✅ Domain Registry 对比 (`domain_registry.py`)
3. ✅ Alembic 迁移历史查看 (Story 6.2-P7 文档)
4. ✅ 差异清单记录

---

## P0 表清单概览

> **总计**: 18 张表
> **已完成分析**: 9 张 (50%)
> **待分析**: 9 张 (50%)

### 按Schema分类

#### enterprise Schema (5 张) - ✅ 100% 完成

| 序号 | 表名 | 行数 | 状态 | 章节 |
|------|------|------|------|------|
| 3 | base_info | 28,576 | ✅ 已完成 | [第1节](#1-enterprisebase_info) |
| 4 | business_info | 11,542 | ✅ 已完成 | [第2节](#2-enterprisebusiness_info) |
| 5 | biz_label | 126,332 | ✅ 已完成 | [第3节](#3-enterprisebiz_label) |
| 6 | company_types_classification | 104 | ✅ 已完成 | [第5节](#5-enterprisecompany_types_classification) |
| 7 | industrial_classification | 1,183 | ✅ 已完成 | [第6节](#6-enterpriseindustrial_classification) |

#### mapping Schema (8 张) - ✅ 62.5% 完成

| 序号 | 表名 | 迁移行数 | 状态 | 章节 |
|------|------|----------|------|------|
| 10 | 年金客户 | 10,204 | ✅ 已完成 | [第4节](#4-mapping年金客户) |
| 11 | 组合计划 | 1,338 | ⬜ 待分析 | - |
| 12 | 年金计划 | 1,159 | ⬜ 待分析 | - |
| 13 | 组织架构 | 38 | ✅ 已完成 | [第8节](#8-mapping组织架构) |
| 14 | 产品线 | 12 | ✅ 已完成 | [第7节](#7-mapping产品线) |
| 15 | 计划层规模 | 7 | ✅ 已完成 | [第9节](#9-mapping计划层规模) |
| 16 | 产品明细 | 18 | ⬜ 待分析 | - |
| 17 | 利润指标 | 12 | ⬜ 待分析 | - |

#### business Schema (2 张) - ⬜ 0% 完成

| 序号 | 表名 | 行数 | 状态 | 章节 |
|------|------|------|------|------|
| 8 | 规模明细 | 625,126 | ⬜ 待分析 | - |
| 9 | 收入明细 | 158,480 | ⬜ 待分析 | - |

#### public Schema (2 张) - ⬜ 0% 完成

| 序号 | 表名 | 行数 | 状态 | 章节 |
|------|------|------|------|------|
| 1 | pipeline_executions | - | ⬜ 待分析 | - |
| 2 | data_quality_metrics | - | ⬜ 待分析 | - |

#### system Schema (1 张) - ⬜ 0% 完成

| 序号 | 表名 | 行数 | 状态 | 章节 |
|------|------|------|------|------|
| 18 | sync_state | - | ⬜ 待分析 | - |

---

## 1. enterprise.base_info

### 1.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | enterprise | enterprise | - |
| **表名** | base_info | base_info | - |
| **行数** | 28,576 | - | Legacy 源数据 |
| **字段数** | 35 | 39 | **+4 字段** |
| **主键** | company_id | company_id | - |
| **索引数** | 1 | 4 | **+3 索引** |

### 1.2 字段差异对比

#### 1.2.1 Postgres 新增字段 (4个)

| 字段名 | 数据类型 | Nullable | 来源 | 业务用途 |
|--------|---------|----------|------|----------|
| `raw_business_info` | JSONB | YES | Story 6.2-P7 AC3 | 存储 EQC API `findDepart` 响应的完整 JSON |
| `raw_biz_label` | JSONB | YES | Story 6.2-P7 AC4 | 存储 EQC API `findLabels` 响应的完整 JSON |
| `api_fetched_at` | TIMESTAMP WITH TIME ZONE | YES | Story 6.2-P7 AC5 | 追踪 API 数据获取时间，用于数据新鲜度查询 |
| `_id` | VARCHAR | YES | Legacy 遗留 | Legacy MongoDB 迁移遗留字段（Postgres 中可能已废弃） |

> **注意**: `_id` 字段在 Legacy 中存在，但在 Postgres 的实际表结构中未显示，可能已在重构中移除。

#### 1.2.2 共同字段 (35个)

| 字段名 | Legacy 类型 | Postgres 类型 | Nullable | 差异 |
|--------|------------|---------------|----------|------|
| company_id | VARCHAR | VARCHAR | NO | ✅ 一致 (主键) |
| search_key_word | VARCHAR | VARCHAR | YES | ✅ 一致 |
| name | VARCHAR | VARCHAR | YES | ✅ 一致 |
| name_display | VARCHAR | VARCHAR | YES | ✅ 一致 |
| symbol | VARCHAR | VARCHAR | YES | ✅ 一致 |
| rank_score | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| country | VARCHAR | VARCHAR | YES | ✅ 一致 |
| company_en_name | VARCHAR | VARCHAR | YES | ✅ 一致 |
| smdb_code | VARCHAR | VARCHAR | YES | ✅ 一致 |
| is_hk | INTEGER | INTEGER | YES | ✅ 一致 |
| coname | VARCHAR | VARCHAR | YES | ✅ 一致 |
| is_list | INTEGER | INTEGER | YES | ✅ 一致 |
| company_nature | VARCHAR | VARCHAR | YES | ✅ 一致 |
| _score | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| type | VARCHAR | VARCHAR | YES | ✅ 一致 |
| registeredStatus | VARCHAR | VARCHAR | YES | ✅ 一致 |
| organization_code | VARCHAR | VARCHAR | YES | ✅ 一致 |
| le_rep | TEXT | TEXT | YES | ✅ 一致 |
| reg_cap | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| is_pa_relatedparty | INTEGER | INTEGER | YES | ✅ 一致 |
| province | VARCHAR | VARCHAR | YES | ✅ 一致 |
| companyFullName | VARCHAR | VARCHAR | YES | ✅ 一致 |
| est_date | VARCHAR | VARCHAR | YES | ✅ 一致 |
| company_short_name | VARCHAR | VARCHAR | YES | ✅ 一致 |
| id | VARCHAR | VARCHAR | YES | ✅ 一致 |
| is_debt | INTEGER | INTEGER | YES | ✅ 一致 |
| unite_code | VARCHAR | VARCHAR | YES | ✅ 一致 |
| registered_status | VARCHAR | VARCHAR | YES | ✅ 一致 |
| cocode | VARCHAR | VARCHAR | YES | ✅ 一致 |
| default_score | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| company_former_name | VARCHAR | VARCHAR | YES | ✅ 一致 |
| is_rank_list | INTEGER | INTEGER | YES | ✅ 一致 |
| trade_register_code | VARCHAR | VARCHAR | YES | ✅ 一致 |
| companyId | VARCHAR | VARCHAR | YES | ✅ 一致 |
| is_normal | INTEGER | INTEGER | YES | ✅ 一致 |
| company_full_name | VARCHAR | VARCHAR | YES | ✅ 一致 |

### 1.3 索引差异对比

#### 1.3.1 Postgres 新增索引 (3个)

| 索引名 | 字段 | 类型 | 来源 | 用途 |
|--------|------|------|------|------|
| `idx_base_info_unite_code` | unite_code | btree | Story 6.2-P7 Task 2.1 | 支持 EQC/credit-code 风格查询 |
| `idx_base_info_search_key` | search_key_word | btree | Story 6.2-P7 Task 2.1 | 支持搜索键过滤 |
| `idx_base_info_api_fetched` | api_fetched_at | btree | Story 6.2-P7 Task 2.1 | 支持数据新鲜度查询 |

#### 1.3.2 共同索引 (1个)

| 索引名 | 字段 | 类型 | 差异 |
|--------|------|------|------|
| base_info_pkey / base_info_pkey1 | company_id | btree (UNIQUE) | ✅ 一致 (主键) |

### 1.4 约束差异

| 约束类型 | Legacy | Postgres | 差异 |
|---------|--------|----------|------|
| PRIMARY KEY | base_info_pkey (company_id) | base_info_pkey1 (company_id) | ✅ 功能一致，名称不同 |
| CHECK | 36913_37092_3_not_null | 30666_133946_1_not_null | ✅ 功能一致 |

### 1.5 升级来源与原因

**升级故事**: Story 6.2-P7 (Enterprise Schema Consolidation)

**升级原因**:
1. **对齐 Legacy archive_base_info 结构**: 从 6 列扩展到 37 列，补齐 31 个缺失字段
2. **支持 EQC API 完整数据持久化**: 新增 `raw_business_info` 和 `raw_biz_label` JSONB 列
3. **数据新鲜度追踪**: 新增 `api_fetched_at` 列用于追踪 API 数据获取时间
4. **查询性能优化**: 新增 3 个索引提升查询效率

**参考文档**: `docs/sprint-artifacts/stories/6.2-p7-enterprise-schema-consolidation.md`

---

## 2. 迁移脚本开发建议

### 2.1 核心原则 (来自 migration-checklist.md 第10节)

- ✅ **保护升级**: 保留 Postgres 已有的约束、索引、默认值
- ✅ **增量插入**: 使用 `INSERT ... ON CONFLICT` 避免覆盖现有数据
- ❌ **禁止 DROP**: 不得删除 Postgres 已有的字段或约束
- ❌ **禁止 ALTER TYPE**: 不得修改已有字段的数据类型

### 2.2 迁移策略

#### 策略 A: 全字段迁移 (推荐)

**SQL 伪代码**:
```sql
INSERT INTO enterprise.base_info (
    -- Legacy 字段 (35个)
    company_id, search_key_word, name, name_display, symbol, rank_score,
    country, company_en_name, smdb_code, is_hk, coname, is_list,
    company_nature, _score, type, registeredStatus, organization_code,
    le_rep, reg_cap, is_pa_relatedparty, province, companyFullName,
    est_date, company_short_name, id, is_debt, unite_code,
    registered_status, cocode, default_score, company_former_name,
    is_rank_list, trade_register_code, companyId, is_normal, company_full_name,

    -- Postgres 新增字段 (3个，设置 NULL)
    raw_business_info, raw_biz_label, api_fetched_at
)
SELECT
    -- Legacy 字段映射
    company_id, search_key_word, name, name_display, symbol, rank_score,
    country, company_en_name, smdb_code, is_hk, coname, is_list,
    company_nature, _score, type, registeredStatus, organization_code,
    le_rep, reg_cap, is_pa_relatedparty, province, companyFullName,
    est_date, company_short_name, id, is_debt, unite_code,
    registered_status, cocode, default_score, company_former_name,
    is_rank_list, trade_register_code, companyId, is_normal, company_full_name,

    -- Postgres 新增字段设为 NULL (后续由 API 填充)
    NULL, NULL, NULL
FROM legacy.enterprise.base_info
ON CONFLICT (company_id) DO NOTHING;  -- 避免重复插入
```

**优点**:
- 完整保留 Legacy 数据
- 保留所有 Postgres 新增字段和索引
- 不覆盖现有数据

**缺点**:
- 迁移后 `raw_business_info`、`raw_biz_label`、`api_fetched_at` 为 NULL，需要后续 API 回填

#### 策略 B: 仅迁移缺失数据 (增量)

**SQL 伪代码**:
```sql
INSERT INTO enterprise.base_info (
    -- 所有字段
    company_id, search_key_word, name, ...
)
SELECT
    company_id, search_key_word, name, ...
FROM legacy.enterprise.base_info
WHERE NOT EXISTS (
    SELECT 1 FROM enterprise.base_info
    WHERE enterprise.base_info.company_id = legacy.enterprise.base_info.company_id
);
```

**优点**:
- 仅补充缺失数据
- 保留已有 Postgres 数据（包括 API 回填的 JSONB 字段）

**缺点**:
- 如果 Postgres 中已有数据但不完整，无法更新

### 2.3 必须保留的 Postgres 对象

**禁止删除/修改**:
- ❌ 字段: `raw_business_info`, `raw_biz_label`, `api_fetched_at`
- ❌ 索引: `idx_base_info_unite_code`, `idx_base_info_search_key`, `idx_base_info_api_fetched`
- ❌ 主键: `base_info_pkey1` (company_id)

**验证方法**:
```sql
-- 迁移前验证
SELECT count(*) FROM enterprise.base_info;  -- 记录现有行数

-- 迁移后验证
SELECT
    count(*) as total_rows,
    count(raw_business_info) as has_raw_business_info,
    count(raw_biz_label) as has_raw_biz_label,
    count(api_fetched_at) as has_api_fetched_at
FROM enterprise.base_info;

-- 验证索引存在
SELECT indexname FROM pg_indexes
WHERE schemaname = 'enterprise' AND tablename = 'base_info';
```

### 2.4 数据完整性验证

**验证清单**:
- [ ] Legacy 行数 = 28,576
- [ ] Postgres 迁移后行数 ≥ Legacy 行数
- [ ] 所有 company_id 无丢失
- [ ] 新增 JSONB 字段允许 NULL
- [ ] 新增索引全部存在
- [ ] 查询性能测试 (unite_code, search_key_word, api_fetched_at)

---

## 2. enterprise.business_info

### 2.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | enterprise | enterprise | - |
| **表名** | business_info | business_info | - |
| **行数** | 11,542 | - | Legacy 源数据 |
| **字段数** | 40 | 43 | **+3 字段** |
| **主键** | company_id (VARCHAR) | id (SERIAL) | **⚠️ 表结构差异** (见2.3.1说明) |
| **外键** | 无 | company_id → base_info | **+ FK 约束** |
| **索引数** | 1 | 2 | **+1 索引** |

### 2.2 字段差异对比

#### 2.2.1 Postgres 新增字段 (4个)

| 字段名 | 数据类型 | Nullable | 默认值 | 来源 | 业务用途 |
|--------|---------|----------|--------|------|----------|
| `id` | SERIAL | NO | nextval(...) | Story 6.2-P7 | 自增主键，替代 Legacy 的 MongoDB `_id` |
| `_cleansing_status` | JSONB | YES | NULL | Story 6.2-P7 AC6 | 清洗状态跟踪 (如 `{\"registered_capital\": \"cleansed\"}`) |
| `created_at` | TIMESTAMPTZ | NO | now() | Story 6.2-P7 | 记录创建时间 |
| `updated_at` | TIMESTAMPTZ | NO | now() | Story 6.2-P7 | 记录更新时间 |

> **注意**: `_cleansing_status` 字段在 Story 6.2-P7 中定义，但实际 Postgres 表结构中可能未包含，需验证。

#### 2.2.2 字段重命名 (camelCase → snake_case)

| Legacy 字段 | Legacy 类型 | Postgres 字段 | Postgres 类型 | 变更类型 |
|------------|------------|---------------|---------------|----------|
| `registerCaptial` | VARCHAR | `registered_capital` | NUMERIC(20,2) | **重命名 + 类型规范化** |
| `legalPersonId` | VARCHAR | `legal_person_id` | VARCHAR | **重命名** |
| `logoUrl` | TEXT | `logo_url` | TEXT | **重命名** |
| `typeCode` | VARCHAR | `type_code` | VARCHAR | **重命名** |
| `updateTime` | DATE | `update_time` | DATE | **重命名** |
| `actualCapi` | VARCHAR | `actual_capital` | NUMERIC(20,2) | **重命名 + 类型规范化** |
| `registeredCapitalCurrency` | VARCHAR | `registered_capital_currency` | VARCHAR | **重命名** |
| `fullRegisterTypeDesc` | VARCHAR | `full_register_type_desc` | VARCHAR | **重命名** |
| `industryCode` | VARCHAR | `industry_code` | VARCHAR | **重命名** |

#### 2.2.3 数据类型规范化 (需要清洗)

| Legacy 字段 | Legacy 类型 | Postgres 字段 | Postgres 类型 | 清洗规则 | 示例 |
|------------|------------|---------------|---------------|----------|------|
| `registered_date` | VARCHAR | `registered_date` | **DATE** | 解析日期字符串 | "2015-01-15" → DATE |
| `registered_capital` | VARCHAR | `registered_capital` | **NUMERIC(20,2)** | 去除单位，转换数值 | "80000.00万元" → 800000000.00 |
| `start_date` | VARCHAR | `start_date` | **DATE** | 解析日期字符串 | "2015-01-15" → DATE |
| `end_date` | VARCHAR | `end_date` | **DATE** | 解析日期字符串 | "长期" 或 NULL |
| `collegues_num` | VARCHAR | `colleagues_num` | **INTEGER** | 修正拼写，转换整数 | "50" → 50 (注意拼写修正) |
| `actual_capital` | VARCHAR | `actual_capital` | **NUMERIC(20,2)** | 去除单位，转换数值 | "50000.00万元" → 500000000.00 |

> **⚠️ 关键**: `collegues_num` 在 Postgres 中修正拼写为 `colleagues_num` (正确英语)

#### 2.2.4 其他字段类型变更

| Legacy 字段 | Legacy 类型 | Postgres 字段 | Postgres 类型 | 变更原因 |
|------------|------------|---------------|---------------|----------|
| `email_address` | TEXT | `email_address` | VARCHAR(255) | 统一字符串类型，提升查询性能 |

#### 2.2.5 保持一致的共同字段 (30个)

以下字段在 Legacy 和 Postgres 中保持一致（名称和类型无变化）：

```
registered_status, legal_person_name, address, codename, company_id,
company_name, company_en_name, currency, credit_code, register_code,
organization_code, company_type, industry_name, registration_organ_name,
start_end, business_scope, telephone, website, company_former_name,
control_id, control_name, bene_id, bene_name, province, department
```

### 2.3 主键与外键差异

#### 2.3.1 主键差异说明

| 数据库 | 主键字段 | 主键类型 | 业务含义 |
|--------|---------|---------|----------|
| **Legacy MySQL** | company_id | VARCHAR | 业务主键 (关联 base_info) |
| **Postgres** | id | SERIAL | 技术主键 (自增ID) |

**重要说明**: 
- ⚠️ **这是表结构差异，不是迁移脚本需要处理的转换**
- ✅ **Postgres 表结构由 Alembic 管理**，`id` (SERIAL) 主键已在表结构定义中
- ✅ **迁移脚本职责**: 按照 Postgres 表结构插入数据，`company_id` 作为外键关联 base_info
- 📋 **迁移时注意**: 确保 `company_id` 的唯一性（通过 Alembic 定义的 UNIQUE 约束）

**数据迁移重点**:
- 真正的迁移风险在**数据清洗**（6字段类型转换）和**字段映射**（9字段重命名）
- 不需要处理"主键变更"，因为这是由表结构定义（Alembic）管理的

#### 2.3.2 外键约束

| 约束名 | 字段 | 引用表 | 引用字段 | 状态 |
|--------|------|--------|----------|------|
| `fk_business_info_company_id` | company_id | enterprise.base_info | company_id | ✅ Postgres 新增 |

**约束用途**: 确保每条 business_info 记录关联到有效的 base_info 记录

### 2.4 索引差异对比

#### 2.4.1 Postgres 新增索引 (1个)

| 索引名 | 字段 | 类型 | 来源 | 用途 |
|--------|------|------|------|------|
| `idx_business_info_company_id` | company_id | btree | Story 6.2-P7 Task 2.1 | FK 索引，优化 JOIN 查询 |

#### 2.4.2 主键索引变更

| 数据库 | 主键索引 | 索引字段 | 类型 |
|--------|---------|---------|------|
| Legacy | business_info_pkey | company_id | btree (UNIQUE) |
| Postgres | business_info_pkey1 | id | btree (UNIQUE) |

**影响**: 查询优化从 `company_id` 主键查询变为 `id` 主键查询，需通过 `idx_business_info_company_id` 优化 `company_id` 查询

### 2.5 升级来源与原因

**升级故事**: Story 6.2-P7 (Enterprise Schema Consolidation) - AC6

**升级原因**:
1. **范式化数据类型**: 将 6 个 VARCHAR 字段转换为 DATE/NUMERIC/INTEGER，提升数据质量和查询性能
2. **统一命名规范**: 将 9 个 camelCase 字段重命名为 snake_case，符合 Python/Postgres 规范
3. **主键重构**: 从业务主键 (company_id) 改为技术主键 (id SERIAL)，符合现代数据库设计规范
4. **外键约束**: 新增 FK 约束确保引用完整性
5. **清洗状态跟踪**: 新增 `_cleansing_status` JSONB 字段支持增量清洗流程
6. **拼写修正**: `collegues_num` 修正为 `colleagues_num` (正确英语拼写)

**参考文档**: `docs/sprint-artifacts/stories/6.2-p7-enterprise-schema-consolidation.md` 第236-291行

---

## 3. enterprise.biz_label

### 3.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | enterprise | enterprise | - |
| **表名** | biz_label | biz_label | - |
| **行数** | 126,332 | - | Legacy 源数据 (最大表) |
| **字段数** | 7 | 9 | **+2 字段** |
| **主键** | _id (VARCHAR) | id (SERIAL) | **⚠️ 表结构差异** (见3.3.1说明) |
| **外键** | 无 | company_id → base_info | **+ FK 约束** |
| **索引数** | 1 | 3 | **+2 索引** |

### 3.2 字段差异对比

#### 3.2.1 Postgres 新增字段 (3个)

| 字段名 | 数据类型 | Nullable | 默认值 | 来源 | 业务用途 |
|--------|---------|----------|--------|------|----------|
| `id` | SERIAL | NO | nextval(...) | Story 6.2-P7 | 自增主键，替代 Legacy 的 MongoDB `_id` |
| `created_at` | TIMESTAMPTZ | NO | now() | Story 6.2-P7 | 记录创建时间 |
| `updated_at` | TIMESTAMPTZ | NO | now() | Story 6.2-P7 | 记录更新时间 |

#### 3.2.2 字段重命名 (camelCase → snake_case)

| Legacy 字段 | Legacy 类型 | Nullable | Postgres 字段 | Postgres 类型 | Nullable | 变更类型 |
|------------|------------|----------|---------------|---------------|----------|----------|
| `companyId` | VARCHAR | YES | `company_id` | VARCHAR | **NO** | **重命名 + NOT NULL + FK** |
| `lv1Name` | VARCHAR | YES | `lv1_name` | VARCHAR | YES | **重命名** |
| `lv2Name` | VARCHAR | YES | `lv2_name` | VARCHAR | YES | **重命名** |
| `lv3Name` | VARCHAR | YES | `lv3_name` | VARCHAR | YES | **重命名** |
| `lv4Name` | VARCHAR | YES | `lv4_name` | VARCHAR | YES | **重命名** |

> **⚠️ 关键变更**: `companyId` → `company_id` 同时增加了 **NOT NULL** 约束和 **FK 约束**

#### 3.2.3 保持一致的共同字段 (1个)

以下字段在 Legacy 和 Postgres 中保持一致：

```
type (VARCHAR) - 标签类型
```

### 3.3 主键与外键差异

#### 3.3.1 主键差异说明

| 数据库 | 主键字段 | 主键类型 | 业务含义 |
|--------|---------|---------|----------|
| **Legacy MySQL** | _id | VARCHAR | MongoDB 技术主键 |
| **Postgres** | id | SERIAL | 自增技术主键 |

**重要说明**:
- ⚠️ **这是表结构差异，不是迁移脚本需要处理的转换**
- ✅ **Postgres 表结构由 Alembic 管理**，`id` (SERIAL) 主键已在表结构定义中
- ✅ **迁移脚本职责**: 按照 Postgres 表结构插入数据，不需要处理主键映射
- 📋 **迁移时注意**: Legacy 的 `_id` 字段不需要保留

**数据迁移重点**:
- 真正的迁移风险在 **NOT NULL 约束** (`companyId` 可能为 NULL，需过滤)
- 需要 **字段映射** (5个 camelCase → snake_case)
- 需要 **外键验证** (确保 `company_id` 在 `base_info` 中存在)
- 数据量最大 (126,332 行)，需特别关注性能

#### 3.3.2 外键约束

| 约束名 | 字段 | 引用表 | 引用字段 | 状态 |
|--------|------|--------|----------|------|
| `fk_biz_label_company_id` | company_id | enterprise.base_info | company_id | ✅ Postgres 新增 |

**约束用途**: 确保每条 biz_label 记录关联到有效的 base_info 记录

**⚠️ 数据完整性**:
- Legacy 中 `companyId` 可能为 NULL
- Postgres 中 `company_id` 为 NOT NULL
- 迁移时需要过滤或处理 NULL 的 `companyId`

### 3.4 索引差异对比

#### 3.4.1 Postgres 新增索引 (2个)

| 索引名 | 字段 | 类型 | 来源 | 用途 |
|--------|------|------|------|------|
| `idx_biz_label_company_id` | company_id | btree | Story 6.2-P7 Task 2.1 | FK 索引，优化 JOIN 查询 |
| `idx_biz_label_hierarchy` | company_id, type, lv1_name, lv2_name | btree | Story 6.2-P7 Task 2.1 (Optional) | 复合索引，优化标签层级查询 |

#### 3.4.2 主键索引变更

| 数据库 | 主键索引 | 索引字段 | 类型 |
|--------|---------|---------|------|
| Legacy | biz_label_pkey | _id | btree (UNIQUE) |
| Postgres | biz_label_pkey1 | id | btree (UNIQUE) |

**影响**: 查询优化从 `_id` 主键查询变为 `id` 主键查询

### 3.5 升级来源与原因

**升级故事**: Story 6.2-P7 (Enterprise Schema Consolidation) - AC7

**升级原因**:
1. **统一命名规范**: 将 5 个 camelCase 字段重命名为 snake_case，符合 Python/Postgres 规范
2. **主键重构**: 从 MongoDB `_id` 改为 SERIAL `id`，符合关系型数据库设计规范
3. **外键约束**: 新增 FK 约束确保引用完整性，同时将 `company_id` 设为 NOT NULL
4. **复合索引优化**: 新增 `idx_biz_label_hierarchy` 优化标签层级查询性能
5. **审计字段**: 新增 `created_at` 和 `updated_at` 支持数据追踪

**参考文档**: `docs/sprint-artifacts/stories/6.2-p7-enterprise-schema-consolidation.md` 第293-314行，第434-459行

---

## 4. mapping.年金客户

### 4.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | mapping | mapping | - |
| **表名** | 年金客户 | 年金客户 | - |
| **行数** | 10,997 (原始) → 10,204 (迁移) | - | **需过滤 793 行** |
| **字段数** | 27 | 27 | ✅ **完全一致** |
| **主键** | company_id | company_id | ✅ **无变更** |
| **索引数** | 1 | 1 | ✅ **无变更** |

### 4.2 字段差异对比

#### 4.2.1 完整字段列表 (27个 - 完全一致)

| 字段名 | Legacy 类型 | Postgres 类型 | Nullable | 差异 |
|--------|------------|---------------|----------|------|
| id | INTEGER | INTEGER | NO | ✅ 一致 |
| company_id | VARCHAR | VARCHAR | NO | ✅ 一致 (主键) |
| 客户名称 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 年金客户标签 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 年金客户类型 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 年金计划类型 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 关键年金计划 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 主拓机构代码 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 主拓机构 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 其他年金计划 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 客户简称 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 更新时间 | DATE | DATE | YES | ✅ 一致 |
| 最新受托规模 | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| 最新投管规模 | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| 管理资格 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 规模区间 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 计划层规模 | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| 年缴费规模 | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| 外部受托规模 | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| 上报受托规模 | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| 上报投管规模 | DOUBLE PRECISION | DOUBLE PRECISION | YES | ✅ 一致 |
| 关联机构数 | INTEGER | INTEGER | YES | ✅ 一致 |
| 其他开拓机构 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 计划状态 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 关联计划数 | INTEGER | INTEGER | YES | ✅ 一致 |
| 备注 | TEXT | TEXT | YES | ✅ 一致 |

> **✅ 特殊发现**: 这是所有 P0 迁移表中唯一**结构完全一致**的表！无需字段映射、无需数据清洗。

### 4.3 索引与约束差异

#### 4.3.1 主键与索引

| 对比项 | Legacy | Postgres | 差异 |
|--------|--------|----------|------|
| 主键 | company_id | company_id | ✅ 一致 |
| 主键索引 | 年金客户_pkey | 年金客户_pkey | ✅ 一致 |
| 索引类型 | btree (UNIQUE) | btree (UNIQUE) | ✅ 一致 |

#### 4.3.2 约束

| 约束类型 | Legacy | Postgres | 差异 |
|---------|--------|----------|------|
| PRIMARY KEY | 年金客户_pkey (company_id) | 年金客户_pkey (company_id) | ✅ 一致 |
| CHECK | 35991_40361_1_not_null | 36750_36849_1_not_null | ✅ 功能一致 (名称不同) |
| CHECK | 35991_40361_2_not_null | 36750_36849_2_not_null | ✅ 功能一致 (名称不同) |

### 4.4 数据过滤需求 (唯一差异)

#### 4.4.1 过滤条件

**来源**: migration-checklist.md 第245-249行

| 项目 | 数值 |
|------|------|
| **原始行数** | 10,997 |
| **剔除行数** | 793 (7.21%) |
| **迁移行数** | 10,204 (92.79%) |
| **WHERE 条件** | `company_id NOT LIKE 'IN%' OR company_id IS NULL` |

**过滤原因**: 剔除 company_id 以 "IN" 开头的记录（可能是测试数据或无效数据）

#### 4.4.2 过滤前后数据对比

```sql
-- Legacy 数据统计
SELECT
    count(*) as total_rows,                          -- 10,997
    count(*) FILTER (WHERE company_id LIKE 'IN%') as to_exclude,  -- 793
    count(*) FILTER (WHERE company_id NOT LIKE 'IN%' OR company_id IS NULL) as to_migrate  -- 10,204
FROM legacy.mapping.年金客户;
```

### 4.5 升级来源与原因

**升级状态**: ✅ **无架构升级**

**分析**:
- Legacy 和 Postgres 表结构**完全一致** (27 个字段，无变更)
- 主键、索引、约束均无变更
- 唯一差异是**数据过滤需求** (业务规则，非架构升级)

**迁移特点**:
- 🟢 **最简单的 P0 迁移表** (无需字段映射、无需数据清洗)
- 🟡 **需要 WHERE 过滤** (剔除 793 行无效数据)
- 🟢 **低风险迁移** (直接迁移 + WHERE 条件)

---

## 5. 迁移脚本开发建议

### 5.1 核心原则 (来自 migration-checklist.md 第10节)

- ✅ **保护升级**: 保留 Postgres 已有的约束、索引、默认值
- ✅ **增量插入**: 使用 `INSERT ... ON CONFLICT` 避免覆盖现有数据
- ❌ **禁止 DROP**: 不得删除 Postgres 已有的字段或约束
- ❌ **禁止 ALTER TYPE**: 不得修改已有字段的数据类型

### 5.2 迁移策略

#### 策略 A: 年金客户 直接迁移 (最简单)

**特点**: 结构完全一致，仅需 WHERE 过滤

**SQL 伪代码**:
```sql
INSERT INTO mapping.年金客户 (
    -- 所有 27 个字段 (无需映射)
    id, company_id, 客户名称, 年金客户标签, 年金客户类型, 年金计划类型,
    关键年金计划, 主拓机构代码, 主拓机构, 其他年金计划, 客户简称,
    更新时间, 最新受托规模, 最新投管规模, 管理资格, 规模区间,
    计划层规模, 年缴费规模, 外部受托规模, 上报受托规模, 上报投管规模,
    关联机构数, 其他开拓机构, 计划状态, 关联计划数, 备注
)
SELECT
    -- 所有 27 个字段 (直接映射)
    id, company_id, 客户名称, 年金客户标签, 年金客户类型, 年金计划类型,
    关键年金计划, 主拓机构代码, 主拓机构, 其他年金计划, 客户简称,
    更新时间, 最新受托规模, 最新投管规模, 管理资格, 规模区间,
    计划层规模, 年缴费规模, 外部受托规模, 上报受托规模, 上报投管规模,
    关联机构数, 其他开拓机构, 计划状态, 关联计划数, 备注
FROM legacy.mapping.年金客户
WHERE company_id NOT LIKE 'IN%' OR company_id IS NULL  -- ⚠️ 关键: 过滤条件
ON CONFLICT (company_id) DO NOTHING;
```

**⚠️ 关键注意事项**:
1. **字段无需映射**: 27 个字段名称完全一致，直接 SELECT 即可
2. **WHERE 过滤**: 使用 `company_id NOT LIKE 'IN%' OR company_id IS NULL` 剔除 793 行无效数据
3. **数据量**: 迁移 10,204 行 (92.79% of 10,997)
4. **ON CONFLICT**: 使用 `company_id` 作为冲突键（主键）

**验证方法**:
```sql
-- 迁移前验证 (Legacy)
SELECT
    count(*) as total_rows,                          -- 10,997
    count(*) FILTER (WHERE company_id LIKE 'IN%') as in_rows,  -- 793 (将被剔除)
    count(*) FILTER (WHERE company_id NOT LIKE 'IN%' OR company_id IS NULL) as valid_rows  -- 10,204 (将迁移)
FROM legacy.mapping.年金客户;

-- 迁移后验证 (Postgres)
SELECT
    count(*) as total_rows,                          -- 应该 = 10,204
    count(*) FILTER (WHERE company_id LIKE 'IN%') as in_rows   -- 应该 = 0 (已剔除)
FROM mapping.年金客户;

-- 验证被剔除的数据
SELECT company_id, 客户名称, 年金客户类型
FROM legacy.mapping.年金客户
WHERE company_id LIKE 'IN%'
LIMIT 10;  -- 查看被剔除的样本数据
```

#### 策略 B: 分阶段迁移 (base_info → business_info → biz_label → 年金客户)

**关键挑战**: Postgres 对 6 个字段进行了类型规范化，迁移时必须进行数据清洗

**SQL 伪代码**:
```sql
INSERT INTO enterprise.business_info (
    -- Legacy → Postgres 字段映射
    company_id,
    registered_date,
    registered_capital,
    registered_status,
    legal_person_name,
    address,
    codename,
    company_name,
    company_en_name,
    currency,
    credit_code,
    register_code,
    organization_code,
    company_type,
    industry_name,
    registration_organ_name,
    start_date,
    end_date,
    start_end,
    business_scope,
    telephone,
    email_address,
    website,
    colleagues_num,  -- 注意: Legacy 是 collegues_num
    company_former_name,
    control_id,
    control_name,
    bene_id,
    bene_name,
    legal_person_id,  -- Legacy: legalPersonId
    province,
    logo_url,  -- Legacy: logoUrl
    type_code,  -- Legacy: typeCode
    department,
    update_time,  -- Legacy: updateTime
    actual_capital,  -- Legacy: actualCapi
    registered_capital_currency,  -- Legacy: registeredCapitalCurrency
    full_register_type_desc,  -- Legacy: fullRegisterTypeDesc
    industry_code,  -- Legacy: industryCode

    -- Postgres 新增字段 (设置默认值)
    created_at,
    updated_at
)
SELECT
    company_id,
    -- 数据清洗: VARCHAR → DATE
    CASE
        WHEN registered_date ~ '^\d{4}-\d{2}-\d{2}$' THEN registered_date::DATE
        ELSE NULL  -- 无法解析的日期设为 NULL
    END as registered_date,

    -- 数据清洗: VARCHAR "80000.00万元" → NUMERIC(20,2) 800000000.00
    CASE
        WHEN registerCaptial ~ '^\d+(\.\d+)?万元?$' THEN
            (substring(registerCaptial from '^\d+(\.\d+)?')::NUMERIC(20,2)) * 10000
        ELSE NULL
    END as registered_capital,

    registered_status,
    legal_person_name,
    address,
    codename,
    company_name,
    company_en_name,
    currency,
    credit_code,
    register_code,
    organization_code,
    company_type,
    industry_name,
    registration_organ_name,

    -- 数据清洗: VARCHAR → DATE
    CASE
        WHEN start_date ~ '^\d{4}-\d{2}-\d{2}$' THEN start_date::DATE
        ELSE NULL
    END as start_date,

    -- 数据清洗: VARCHAR → DATE ("长期" → NULL)
    CASE
        WHEN end_date = '长期' THEN NULL
        WHEN end_date ~ '^\d{4}-\d{2}-\d{2}$' THEN end_date::DATE
        ELSE NULL
    END as end_date,

    start_end,
    business_scope,
    telephone,
    email_address,
    website,

    -- 数据清洗: VARCHAR → INTEGER (修正拼写)
    CASE
        WHEN collegues_num ~ '^\d+$' THEN collegues_num::INTEGER
        ELSE NULL
    END as colleagues_num,

    company_former_name,
    control_id,
    control_name,
    bene_id,
    bene_name,
    legalPersonId as legal_person_id,  -- 重命名
    province,
    logoUrl as logo_url,  -- 重命名
    typeCode as type_code,  -- 重命名
    department,
    updateTime as update_time,  -- 重命名

    -- 数据清洗: VARCHAR "50000.00万元" → NUMERIC(20,2)
    CASE
        WHEN actualCapi ~ '^\d+(\.\d+)?万元?$' THEN
            (substring(actualCapi from '^\d+(\.\d+)?')::NUMERIC(20,2)) * 10000
        ELSE NULL
    END as actual_capital,

    registeredCapitalCurrency as registered_capital_currency,  -- 重命名
    fullRegisterTypeDesc as full_register_type_desc,  -- 重命名
    industryCode as industry_code,  -- 重命名

    -- Postgres 新增字段
    NOW() as created_at,
    NOW() as updated_at
FROM legacy.enterprise.business_info
ON CONFLICT (company_id) DO NOTHING;  -- 注意: 这里使用 company_id 而非 id
```

**⚠️ 关键注意事项**:
1. **主键变更**: Postgres 主键是 `id`，但 `ON CONFLICT` 应使用 `company_id` (需添加 UNIQUE 约束)
2. **数据清洗**: 6 个字段需要正则表达式解析和类型转换
3. **字段映射**: 9 个 camelCase 字段需要映射到 snake_case
4. **拼写修正**: `collegues_num` (Legacy) → `colleagues_num` (Postgres)
5. **外键约束**: 确保 `company_id` 在 `base_info` 表中存在

#### 策略 B: 分阶段迁移 (清洗 + 迁移)

如果数据清洗逻辑复杂，建议分两步执行：

**Phase 1: 中间表暂存**
```sql
-- 创建中间表 (与 Legacy 结构一致)
CREATE TEMPORARY TABLE business_info_staging AS
SELECT * FROM legacy.enterprise.business_info;
```

**Phase 2: 清洗并迁移**
```sql
-- 使用 Python/ETL 脚本读取中间表，执行清洗后插入 Postgres
-- 参考: Story 6.2-P9 (数据清洗规则)
```

#### 策略 C: biz_label 迁移 (字段映射 + NULL 过滤)

**关键挑战**:
1. 主键变更: `_id` → `id` (SERIAL)
2. 字段映射: 5 个 camelCase → snake_case
3. NOT NULL 约束: `company_id` 从可空变为非空
4. FK 约束: 必须关联到有效的 `base_info.company_id`

**SQL 伪代码**:
```sql
INSERT INTO enterprise.biz_label (
    -- Legacy → Postgres 字段映射
    company_id,  -- Legacy: companyId (camelCase)
    type,
    lv1_name,    -- Legacy: lv1Name (camelCase)
    lv2_name,    -- Legacy: lv2Name (camelCase)
    lv3_name,    -- Legacy: lv3Name (camelCase)
    lv4_name,    -- Legacy: lv4Name (camelCase)

    -- Postgres 新增字段
    created_at,
    updated_at
)
SELECT
    companyId as company_id,  -- 字段重命名
    type,
    lv1Name as lv1_name,      -- 字段重命名
    lv2Name as lv2_name,      -- 字段重命名
    lv3Name as lv3_name,      -- 字段重命名
    lv4Name as lv4_name,      -- 字段重命名

    -- Postgres 新增字段
    NOW() as created_at,
    NOW() as updated_at
FROM legacy.enterprise.biz_label
WHERE companyId IS NOT NULL  -- ⚠️ 关键: 过滤 NULL，满足 NOT NULL 约束
  AND EXISTS (              -- ⚠️ 关键: 确保 FK 约束有效
      SELECT 1 FROM enterprise.base_info
      WHERE base_info.company_id = biz_label.companyId
  )
ON CONFLICT (id) DO NOTHING;  -- 使用自增 id，几乎不会冲突
```

**⚠️ 关键注意事项**:
1. **NULL 过滤**: Legacy 中 `companyId` 可能为 NULL，必须使用 `WHERE companyId IS NOT NULL` 过滤
2. **FK 验证**: 必须使用 `WHERE EXISTS` 确保 `company_id` 在 `base_info` 中存在
3. **字段映射**: 5 个 camelCase 字段需要映射到 snake_case
4. **主键变更**: Legacy 的 `_id` 不需要保留，使用 Postgres 自增 `id`
5. **数据丢失风险**: 过滤 NULL 和无效 FK 可能导致部分 Legacy 数据丢失，需要记录日志

### 4.3 必须保留的 Postgres 对象

**禁止删除/修改**:

**business_info**:
- ❌ 字段: `id` (SERIAL), `created_at`, `updated_at`, `_cleansing_status`
- ❌ 字段名称: 9 个 snake_case 字段 (不得回退为 camelCase)
- ❌ 字段类型: 6 个规范化字段 (DATE, NUMERIC, INTEGER)
- ❌ 索引: `idx_business_info_company_id`
- ❌ 约束: `fk_business_info_company_id` (FK → base_info)

**biz_label**:
- ❌ 字段: `id` (SERIAL), `created_at`, `updated_at`
- ❌ 字段名称: 5 个 snake_case 字段 (不得回退为 camelCase)
- ❌ 索引: `idx_biz_label_company_id`, `idx_biz_label_hierarchy`
- ❌ 约束: `fk_biz_label_company_id` (FK → base_info)

**验证方法**:
```sql
-- === business_info 验证 ===
-- 迁移前验证
SELECT count(*) FROM enterprise.business_info;  -- 记录现有行数

-- 迁移后验证
SELECT
    count(*) as total_rows,
    count(id) as has_id,  -- 应该 = total_rows
    count(company_id) as has_company_id,  -- 应该 = total_rows
    count(registered_date) as has_registered_date,  -- DATE 类型
    count(registered_capital) as has_registered_capital,  -- NUMERIC 类型
    count(colleagues_num) as has_colleagues_num  -- INTEGER 类型 (注意拼写)
FROM enterprise.business_info;

-- 验证 FK 约束存在
SELECT
    conname as constraint_name,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint
WHERE conrelid = 'enterprise.business_info'::regclass
AND contype = 'f';

-- === biz_label 验证 ===
-- 迁移前验证
SELECT
    count(*) as total_legacy_rows,
    count(companyId) as has_company_id,
    count(*) - count(companyId) as null_company_id_count  -- 统计 NULL 数量
FROM legacy.enterprise.biz_label;

-- 迁移后验证
SELECT
    count(*) as total_rows,
    count(id) as has_id,
    count(company_id) as has_company_id,  -- 应该 = total_rows (NOT NULL 约束)
    count(type) as has_type,
    count(lv1_name) as has_lv1_name
FROM enterprise.biz_label;

-- 验证 FK 约束存在
SELECT
    conname as constraint_name,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint
WHERE conrelid = 'enterprise.biz_label'::regclass
AND contype = 'f';

-- 验证索引存在
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'enterprise' AND tablename = 'biz_label';
-- 应该看到: biz_label_pkey1, idx_biz_label_company_id, idx_biz_label_hierarchy
```

### 4.4 数据完整性验证

**验证清单**:

**base_info**:
- [ ] Legacy 行数 = 28,576
- [ ] Postgres 迁移后行数 ≥ Legacy 行数
- [ ] 所有 company_id 无丢失
- [ ] 新增 JSONB 字段允许 NULL
- [ ] 新增索引全部存在
- [ ] 查询性能测试 (unite_code, search_key_word, api_fetched_at)

**business_info**:
- [ ] Legacy 行数 = 11,542
- [ ] Postgres 迁移后行数 ≥ Legacy 行数
- [ ] 所有 company_id 无丢失
- [ ] `company_id` 唯一性约束存在 (防止重复)
- [ ] DATE 类型字段包含有效日期 (非 NULL 且格式正确)
- [ ] NUMERIC 类型字段已成功转换 (非 NULL 且数值合理)
- [ ] INTEGER 类型字段已成功转换 (`colleagues_num` 拼写正确)
- [ ] FK 约束有效 (所有 `company_id` 在 `base_info` 中存在)
- [ ] 新增索引全部存在
- [ ] 查询性能测试 (company_id JOIN 查询)

**biz_label**:
- [ ] Legacy 行数 = 126,332
- [ ] Legacy 中 NULL `companyId` 统计 (预计数据丢失量)
- [ ] Postgres 迁移后行数 ≤ Legacy 行数 (已过滤 NULL 和无效 FK)
- [ ] 所有 `company_id` 非空 (NOT NULL 约束)
- [ ] 所有 `company_id` 在 `base_info` 中存在 (FK 约束)
- [ ] 5 个 snake_case 字段正确映射
- [ ] 新增索引全部存在 (包括复合索引)
- [ ] 查询性能测试 (标签层级查询)

**年金客户**:
- [ ] Legacy 行数 = 10,997
- [ ] Legacy 中 `company_id LIKE 'IN%'` 统计 (应该 = 793)
- [ ] Postgres 迁移后行数 = 10,204 (已过滤 IN% 类型)
- [ ] Postgres 中 `company_id LIKE 'IN%'` 行数 = 0 (已成功剔除)
- [ ] 所有 27 个字段无需映射 (结构完全一致)
- [ ] WHERE 过滤条件正确执行

---

## 5. enterprise.company_types_classification

### 5.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | enterprise | enterprise | - |
| **表名** | company_types_classification | company_types_classification | - |
| **行数** | 104 | 104 | **完全一致** |
| **字段数** | 8 | 8 | **完全一致** |
| **主键** | typeCode | typeCode | - |
| **索引数** | 1 | 1 | - |

### 5.2 字段对比

| 字段名 | Legacy 类型 | Postgres 类型 | Nullable | 差异 |
|--------|------------|---------------|----------|------|
| typeCode | VARCHAR | VARCHAR | **NO** | ✅ 一致 (主键) |
| company_type | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 公司类型/组织类型 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 分类 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 子分类 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 是否上市 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 法人类型 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 说明 | VARCHAR | VARCHAR | YES | ✅ 一致 |

**关键发现**:
- ✅ **8 个字段完全一致** (无新增、无删除、无重命名)
- ✅ **主键相同**: typeCode (NOT NULL)
- ✅ **数据类型完全一致**: 全部 VARCHAR
- ✅ **行数完全一致**: 104 行
- 🟢 **最简单的 P0 迁移表之一** (与年金客户并列最简单)

### 5.3 索引对比

| 索引名 | 字段 | 类型 | 差异 |
|--------|------|------|------|
| company_types_classification_pkey | typeCode | btree (UNIQUE) | ✅ 一致 |

**关键发现**:
- ✅ 索引完全一致 (仅 PK 索引)

### 5.4 迁移策略

#### 策略: 直接迁移 (无任何转换)

**关键挑战**: **无** (结构完全一致)

**SQL 迁移脚本**:
```sql
INSERT INTO enterprise.company_types_classification (
    typeCode,
    company_type,
    "公司类型/组织类型",
    分类,
    子分类,
    是否上市,
    法人类型,
    说明
)
SELECT
    typeCode,
    company_type,
    "公司类型/组织类型",
    分类,
    子分类,
    是否上市,
    法人类型,
    说明
FROM legacy.enterprise.company_types_classification
ON CONFLICT (typeCode) DO NOTHING;
```

**关键注意事项**:
- ✅ **无需字段映射** (所有字段名完全一致)
- ✅ **无需数据清洗** (所有数据类型一致)
- ✅ **无需 WHERE 过滤** (无数据剔除)
- ✅ **无需担心主键冲突** (Postgres 当前 104 行与 Legacy 完全相同)
- 🟢 **最安全的迁移表** (零风险)

### 5.5 数据完整性验证

**验证清单**:
- [ ] Legacy 行数 = 104
- [ ] Postgres 迁移前行数 = 104 (可能已同步)
- [ ] Postgres 迁移后行数 = 104 (无数据丢失)
- [ ] 所有 typeCode 无丢失 (PK 完整性)
- [ ] 所有 8 个字段数据完整性验证
- [ ] 索引存在性验证

**验证 SQL**:
```sql
-- 迁移前验证
SELECT count(*) as legacy_rows FROM legacy.enterprise.company_types_classification;
SELECT count(*) as postgres_rows FROM enterprise.company_types_classification;
-- 应该都 = 104

-- 迁移后验证
SELECT
    count(*) as total_rows,
    count(typeCode) as has_typecode,  -- 应该 = total_rows
    count(company_type) as has_company_type,
    count("公司类型/组织类型") as has_chinese_name,
    count(分类) as has_分类,
    count(子分类) as has_子分类,
    count(是否上市) as has_是否上市,
    count(法人类型) as has_法人类型,
    count(说明) as has_说明
FROM enterprise.company_types_classification;
-- 所有 count 应该 = 104

-- 验证索引存在
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'enterprise' AND tablename = 'company_types_classification';
-- 应该看到: company_types_classification_pkey
```

---

## 6. enterprise.industrial_classification

### 6.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | enterprise | enterprise | - |
| **表名** | industrial_classification | industrial_classification | - |
| **行数** | 1,183 | 1,183 | **完全一致** |
| **字段数** | 10 | 10 | **完全一致** |
| **主键** | 类别代码 | 类别代码 | - |
| **索引数** | 1 | 1 | - |

### 6.2 字段对比

| 字段名 | Legacy 类型 | Postgres 类型 | Nullable | 差异 |
|--------|------------|---------------|----------|------|
| 类别代码 | VARCHAR | VARCHAR | **NO** | ✅ 一致 (主键) |
| 门类代码 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 大类代码 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 中类顺序码 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 小类顺序码 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 门类名称 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 大类名称 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 中类名称 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 类别名称 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 说明 | VARCHAR | VARCHAR | YES | ✅ 一致 |

**关键发现**:
- ✅ **10 个字段完全一致** (无新增、无删除、无重命名)
- ✅ **主键相同**: 类别代码 (NOT NULL)
- ✅ **数据类型完全一致**: 全部 VARCHAR
- ✅ **行数完全一致**: 1,183 行
- 🟢 **最简单的 P0 迁移表之一** (与 company_types_classification、年金客户并列最简单)

### 6.3 索引对比

| 索引名 | 字段 | 类型 | 差异 |
|--------|------|------|------|
| industrial_classification_pkey | 类别代码 | btree (UNIQUE) | ✅ 一致 |

**关键发现**:
- ✅ 索引完全一致 (仅 PK 索引)

### 6.4 迁移策略

#### 策略: 直接迁移 (无任何转换)

**关键挑战**: **无** (结构完全一致)

**SQL 迁移脚本**:
```sql
INSERT INTO enterprise.industrial_classification (
    类别代码,
    门类代码,
    大类代码,
    中类顺序码,
    小类顺序码,
    门类名称,
    大类名称,
    中类名称,
    类别名称,
    说明
)
SELECT
    类别代码,
    门类代码,
    大类代码,
    中类顺序码,
    小类顺序码,
    门类名称,
    大类名称,
    中类名称,
    类别名称,
    说明
FROM legacy.enterprise.industrial_classification
ON CONFLICT (类别代码) DO NOTHING;
```

**关键注意事项**:
- ✅ **无需字段映射** (所有字段名完全一致)
- ✅ **无需数据清洗** (所有数据类型一致)
- ✅ **无需 WHERE 过滤** (无数据剔除)
- ✅ **无需担心主键冲突** (Postgres 当前 1,183 行与 Legacy 完全相同)
- 🟢 **最安全的迁移表** (零风险)

### 6.5 数据完整性验证

**验证清单**:
- [ ] Legacy 行数 = 1,183
- [ ] Postgres 迁移前行数 = 1,183 (可能已同步)
- [ ] Postgres 迁移后行数 = 1,183 (无数据丢失)
- [ ] 所有 类别代码 无丢失 (PK 完整性)
- [ ] 所有 10 个字段数据完整性验证
- [ ] 索引存在性验证

**验证 SQL**:
```sql
-- 迁移前验证
SELECT count(*) as legacy_rows FROM legacy.enterprise.industrial_classification;
SELECT count(*) as postgres_rows FROM enterprise.industrial_classification;
-- 应该都 = 1183

-- 迁移后验证
SELECT
    count(*) as total_rows,
    count(类别代码) as has_类别代码,  -- 应该 = total_rows
    count(门类代码) as has_门类代码,
    count(大类代码) as has_大类代码,
    count(中类顺序码) as has_中类顺序码,
    count(小类顺序码) as has_小类顺序码,
    count(门类名称) as has_门类名称,
    count(大类名称) as has_大类名称,
    count(中类名称) as has_中类名称,
    count(类别名称) as has_类别名称,
    count(说明) as has_说明
FROM enterprise.industrial_classification;
-- 所有 count 应该 = 1183

-- 验证索引存在
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'enterprise' AND tablename = 'industrial_classification';
-- 应该看到: industrial_classification_pkey
```

---

## 7. mapping.产品线

### 7.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | mapping | mapping | - |
| **表名** | 产品线 | 产品线 | - |
| **行数** | 12 | 14 | **⚠️ Postgres +2 行** |
| **字段数** | 6 | 6 | **完全一致** |
| **主键** | 产品线代码 | 产品线代码 | - |
| **索引数** | 1 | 1 | - |

### 7.2 字段对比

| 字段名 | Legacy 类型 | Postgres 类型 | Nullable | 差异 |
|--------|------------|---------------|----------|------|
| 产品线代码 | VARCHAR | VARCHAR | **NO** | ✅ 一致 (主键) |
| 产品线 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 产品类别 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 业务大类 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| NO_产品线 | INTEGER | INTEGER | YES | ✅ 一致 |
| NO_产品类别 | INTEGER | INTEGER | YES | ✅ 一致 |

**关键发现**:
- ✅ **6 个字段完全一致** (无新增、无删除、无重命名)
- ✅ **主键相同**: 产品线代码 (NOT NULL)
- ✅ **数据类型完全一致**: VARCHAR + INTEGER
- ⚠️ **行数不一致**: Legacy 12 行 vs Postgres 14 行 (**Postgres 多 2 行**)
- 🟡 **数据量差异**: Postgres 已有额外种子数据

### 7.3 索引对比

| 索引名 | 字段 | 类型 | 差异 |
|--------|------|------|------|
| 产品线_pkey | 产品线代码 | btree (UNIQUE) | ✅ 一致 |

**关键发现**:
- ✅ 索引完全一致 (仅 PK 索引)

### 7.4 迁移策略

#### 策略: 增量迁移 (仅迁移缺失数据)

**关键挑战**: Postgres 已有 14 行，Legacy 只有 12 行，说明 Postgres 有额外的种子数据

**SQL 迁移脚本**:
```sql
-- 仅迁移 Legacy 中存在但 Postgres 中不存在的行
INSERT INTO mapping.产品线 (
    产品线代码,
    产品线,
    产品类别,
    业务大类,
    NO_产品线,
    NO_产品类别
)
SELECT
    产品线代码,
    产品线,
    产品类别,
    业务大类,
    NO_产品线,
    NO_产品类别
FROM legacy.mapping.产品线
WHERE NOT EXISTS (
    SELECT 1 FROM mapping.产品线
    WHERE 产品线.产品线代码 = legacy_mapping.产品线.产品线代码
)
ON CONFLICT (产品线代码) DO NOTHING;
```

**关键注意事项**:
- ✅ **无需字段映射** (所有字段名完全一致)
- ✅ **无需数据清洗** (所有数据类型一致)
- ⚠️ **使用 WHERE NOT EXISTS**: 仅迁移 Postgres 中不存在的行
- ⚠️ **数据量差异**: Postgres (14 行) > Legacy (12 行)，需要保留 Postgres 额外的 2 行
- 🟡 **低风险迁移** (结构简单，但需注意数据差异)

### 7.5 数据完整性验证

**验证清单**:
- [ ] Legacy 行数 = 12
- [ ] Postgres 迁移前行数 = 14 (已有额外数据)
- [ ] Postgres 迁移后行数 ≥ 14 (保留现有数据 + 新增 Legacy 唯一数据)
- [ ] 所有 产品线代码 无丢失 (PK 完整性)
- [ ] 所有 6 个字段数据完整性验证
- [ ] Postgres 额外的 2 行数据合理性确认
- [ ] 索引存在性验证

**验证 SQL**:
```sql
-- 迁移前验证
SELECT count(*) as legacy_rows FROM legacy.mapping.产品线;
-- 应该 = 12

SELECT count(*) as postgres_rows_before FROM mapping.产品线;
-- 应该 = 14

-- 迁移后验证
SELECT count(*) as postgres_rows_after FROM mapping.产品线;
-- 应该 ≥ 14 (保留现有 14 行 + 可能新增的 Legacy 唯一数据)

SELECT
    count(*) as total_rows,
    count(产品线代码) as has_产品线代码,  -- 应该 = total_rows
    count(产品线) as has_产品线,
    count(产品类别) as has_产品类别,
    count(业务大类) as has_业务大类,
    count(NO_产品线) as has_NO_产品线,
    count(NO_产品类别) as has_NO_产品类别
FROM mapping.产品线;

-- 验证 Postgres 额外的 2 行数据
SELECT * FROM mapping.产品线
WHERE 产品线代码 NOT IN (SELECT 产品线代码 FROM legacy.mapping.产品线);
-- 检查这 2 行数据的合理性

-- 验证索引存在
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'mapping' AND tablename = '产品线';
-- 应该看到: 产品线_pkey
```

---

## 8. mapping.组织架构

### 8.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | mapping | mapping | - |
| **表名** | 组织架构 | 组织架构 | - |
| **行数** | 38 | 41 | **⚠️ Postgres +3 行** |
| **字段数** | 9 | 9 | **完全一致** |
| **主键** | 机构代码 | 机构代码 | - |
| **索引数** | 1 | 1 | - |

### 8.2 字段对比

| 字段名 | Legacy 类型 | Postgres 类型 | Nullable | 差异 |
|--------|------------|---------------|----------|------|
| 机构代码 | VARCHAR | VARCHAR | **NO** | ✅ 一致 (主键) |
| 机构 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 年金中心 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 战区 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| NO_机构 | INTEGER | INTEGER | YES | ✅ 一致 |
| NO_年金中心 | INTEGER | INTEGER | YES | ✅ 一致 |
| NO_区域 | INTEGER | INTEGER | YES | ✅ 一致 |
| 新架构 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| 行政域 | VARCHAR | VARCHAR | YES | ✅ 一致 |

**关键发现**:
- ✅ **9 个字段完全一致** (无新增、无删除、无重命名)
- ✅ **主键相同**: 机构代码 (NOT NULL)
- ✅ **数据类型完全一致**: VARCHAR + INTEGER
- ⚠️ **行数不一致**: Legacy 38 行 vs Postgres 41 行 (**Postgres 多 3 行**)
- 🟡 **数据量差异**: Postgres 已有额外种子数据

### 8.3 索引对比

| 索引名 | 字段 | 类型 | 差异 |
|--------|------|------|------|
| 组织架构_pkey | 机构代码 | btree (UNIQUE) | ✅ 一致 |

**关键发现**:
- ✅ 索引完全一致 (仅 PK 索引)

### 8.4 迁移策略

#### 策略: 增量迁移 (仅迁移缺失数据)

**关键挑战**: Postgres 已有 41 行，Legacy 只有 38 行，说明 Postgres 有额外的种子数据

**SQL 迁移脚本**:
```sql
-- 仅迁移 Legacy 中存在但 Postgres 中不存在的行
INSERT INTO mapping.组织架构 (
    机构代码,
    机构,
    年金中心,
    战区,
    NO_机构,
    NO_年金中心,
    NO_区域,
    新架构,
    行政域
)
SELECT
    机构代码,
    机构,
    年金中心,
    战区,
    NO_机构,
    NO_年金中心,
    NO_区域,
    新架构,
    行政域
FROM legacy.mapping.组织架构
WHERE NOT EXISTS (
    SELECT 1 FROM mapping.组织架构
    WHERE 组织架构.机构代码 = legacy_mapping.组织架构.机构代码
)
ON CONFLICT (机构代码) DO NOTHING;
```

**关键注意事项**:
- ✅ **无需字段映射** (所有字段名完全一致)
- ✅ **无需数据清洗** (所有数据类型一致)
- ⚠️ **使用 WHERE NOT EXISTS**: 仅迁移 Postgres 中不存在的行
- ⚠️ **数据量差异**: Postgres (41 行) > Legacy (38 行)，需要保留 Postgres 额外的 3 行
- 🟡 **低风险迁移** (结构简单，但需注意数据差异)

### 8.5 数据完整性验证

**验证清单**:
- [ ] Legacy 行数 = 38
- [ ] Postgres 迁移前行数 = 41 (已有额外数据)
- [ ] Postgres 迁移后行数 ≥ 41 (保留现有数据 + 新增 Legacy 唯一数据)
- [ ] 所有 机构代码 无丢失 (PK 完整性)
- [ ] 所有 9 个字段数据完整性验证
- [ ] Postgres 额外的 3 行数据合理性确认
- [ ] 索引存在性验证

**验证 SQL**:
```sql
-- 迁移前验证
SELECT count(*) as legacy_rows FROM legacy.mapping.组织架构;
-- 应该 = 38

SELECT count(*) as postgres_rows_before FROM mapping.组织架构;
-- 应该 = 41

-- 迁移后验证
SELECT count(*) as postgres_rows_after FROM mapping.组织架构;
-- 应该 ≥ 41 (保留现有 41 行 + 可能新增的 Legacy 唯一数据)

SELECT
    count(*) as total_rows,
    count(机构代码) as has_机构代码,  -- 应该 = total_rows
    count(机构) as has_机构,
    count(年金中心) as has_年金中心,
    count(战区) as has_战区,
    count(NO_机构) as has_NO_机构,
    count(NO_年金中心) as has_NO_年金中心,
    count(NO_区域) as has_NO_区域,
    count(新架构) as has_新架构,
    count(行政域) as has_行政域
FROM mapping.组织架构;

-- 验证 Postgres 额外的 3 行数据
SELECT * FROM mapping.组织架构
WHERE 机构代码 NOT IN (SELECT 机构代码 FROM legacy.mapping.组织架构);
-- 检查这 3 行数据的合理性

-- 验证索引存在
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'mapping' AND tablename = '组织架构';
-- 应该看到: 组织架构_pkey
```

---

## 9. mapping.计划层规模

### 9.1 基本信息

| 属性 | Legacy MySQL | Postgres | 差异 |
|------|-------------|----------|------|
| **Schema** | mapping | mapping | - |
| **表名** | 计划层规模 | 计划层规模 | - |
| **行数** | 7 | 7 | **完全一致** |
| **字段数** | 5 | 5 | **完全一致** |
| **主键** | 规模分类代码 | 规模分类代码 | - |
| **索引数** | 1 | 1 | - |

### 9.2 字段对比

| 字段名 | Legacy 类型 | Postgres 类型 | Nullable | 差异 |
|--------|------------|---------------|----------|------|
| 规模分类代码 | VARCHAR | VARCHAR | **NO** | ✅ 一致 (主键) |
| 规模分类 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| NO_规模分类 | INTEGER | INTEGER | YES | ✅ 一致 |
| 规模大类 | VARCHAR | VARCHAR | YES | ✅ 一致 |
| NO_规模大类 | INTEGER | INTEGER | YES | ✅ 一致 |

**关键发现**:
- ✅ **5 个字段完全一致** (无新增、无删除、无重命名)
- ✅ **主键相同**: 规模分类代码 (NOT NULL)
- ✅ **数据类型完全一致**: VARCHAR + INTEGER
- ✅ **行数完全一致**: 7 行
- 🟢 **最简单的 P0 迁移表之一** (与 company_types、industrial、年金客户并列最简单)

### 9.3 索引对比

| 索引名 | 字段 | 类型 | 差异 |
|--------|------|------|------|
| 计划层规模_pkey | 规模分类代码 | btree (UNIQUE) | ✅ 一致 |

**关键发现**:
- ✅ 索引完全一致 (仅 PK 索引)

### 9.4 迁移策略

#### 策略: 直接迁移 (无任何转换)

**关键挑战**: **无** (结构完全一致)

**SQL 迁移脚本**:
```sql
INSERT INTO mapping.计划层规模 (
    规模分类代码,
    规模分类,
    NO_规模分类,
    规模大类,
    NO_规模大类
)
SELECT
    规模分类代码,
    规模分类,
    NO_规模分类,
    规模大类,
    NO_规模大类
FROM legacy.mapping.计划层规模
ON CONFLICT (规模分类代码) DO NOTHING;
```

**关键注意事项**:
- ✅ **无需字段映射** (所有字段名完全一致)
- ✅ **无需数据清洗** (所有数据类型一致)
- ✅ **无需 WHERE 过滤** (无数据剔除)
- ✅ **无需担心主键冲突** (Postgres 当前 7 行与 Legacy 完全相同)
- 🟢 **最安全的迁移表** (零风险，最小表)

### 9.5 数据完整性验证

**验证清单**:
- [ ] Legacy 行数 = 7
- [ ] Postgres 迁移前行数 = 7 (可能已同步)
- [ ] Postgres 迁移后行数 = 7 (无数据丢失)
- [ ] 所有 规模分类代码 无丢失 (PK 完整性)
- [ ] 所有 5 个字段数据完整性验证
- [ ] 索引存在性验证

**验证 SQL**:
```sql
-- 迁移前验证
SELECT count(*) as legacy_rows FROM legacy.mapping.计划层规模;
SELECT count(*) as postgres_rows FROM mapping.计划层规模;
-- 应该都 = 7

-- 迁移后验证
SELECT
    count(*) as total_rows,
    count(规模分类代码) as has_规模分类代码,  -- 应该 = total_rows
    count(规模分类) as has_规模分类,
    count(NO_规模分类) as has_NO_规模分类,
    count(规模大类) as has_规模大类,
    count(NO_规模大类) as has_NO_规模大类
FROM mapping.计划层规模;
-- 所有 count 应该 = 7

-- 验证索引存在
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'mapping' AND tablename = '计划层规模';
-- 应该看到: 计划层规模_pkey
```

---

## 10. 迁移风险与缓解措施

### 10.1 九表风险对比

> **说明**: "主键变更"不是迁移脚本的风险（由Alembic管理），本表仅关注迁移脚本需要处理的数据转换

| 风险类型 | base_info | business_info | biz_label | 年金客户 | company_types | industrial | 产品线 | 组织架构 | 计划层 | 风险等级 |
|---------|-----------|---------------|-----------|----------|---------------|------------|----------|----------|----------|----------|
| **数据清洗** | ✅ 无需清洗 | 🔴 6字段转换 | ✅ 无需清洗 | ✅ 无需清洗 | ✅ 无需清洗 | ✅ 无需清洗 | ✅ 无需清洗 | ✅ 无需清洗 | ✅ 无需清洗 | **高** |
| **字段映射** | ✅ 无需映射 | 🟡 9个字段 | 🟡 5个字段 | ✅ 无需映射 | ✅ 无需映射 | ✅ 无需映射 | ✅ 无需映射 | ✅ 无需映射 | ✅ 无需映射 | **中** |
| **NOT NULL 约束** | ✅ 无变更 | ✅ 无变更 | 🔴 可空→NOT NULL | ✅ 无变更 | ✅ 无变更 | ✅ 无变更 | ✅ 无变更 | ✅ 无变更 | ✅ 无变更 | **高** |
| **WHERE 过滤** | ✅ 无需过滤 | ✅ 无需过滤 | ✅ 无需过滤 | 🔴 过滤793行 | ✅ 无需过滤 | ✅ 无需过滤 | ⚠️ 数据量差异 | ⚠️ 数据量差异 | ✅ 无需过滤 | **中** |
| **外键约束** | ✅ 无FK | 🟡 新增FK | 🟡 新增FK | ✅ 无FK | ✅ 无FK | ✅ 无FK | ✅ 无FK | ✅ 无FK | ✅ 无FK | **中** |
| **数据丢失风险** | 🟢 低 | 🟡 中 | 🟠 中高 | 🟡 低(过滤) | 🟢 零风险 | 🟢 零风险 | 🟡 低(+2行) | 🟡 低(+3行) | 🟢 零风险 | **中高** |
| **数据量** | 28,576行 | 11,542行 | 126,332行 | 10,997行 | 104行 | 1,183行 | 12/14行 | 38/41行 | 7行 | - |

**结论**:
- `company_types_classification`、`industrial_classification`、`计划层规模` 和 `年金客户` 是**最简单**的 P0 迁移表 (结构完全一致，无需任何转换)
- `产品线` 和 `组织架构` 结构简单但存在数据量差异 (需使用 WHERE NOT EXISTS 增量迁移)
- `business_info` 需要复杂的数据清洗 (6字段类型转换) 和字段映射 (9字段重命名)
- `biz_label` 需要 NOT NULL 过滤 + 字段映射 + 外键验证，数据量最大 (126k行)
- `base_info` 几乎无需转换 (仅4个新增字段允许NULL)
- 九表迁移难度：**biz_label > business_info > 产品线 ≈ 组织架构 > base_info > 年金客户 ≈ company_types ≈ industrial ≈ 计划层**

### 9.2 缓解措施

**通用措施**:
1. **预清洗验证**: 在 Legacy 上运行清洗逻辑，统计失败率
2. **回滚计划**: 保留 Legacy 数据直到 Postgres 数据完全验证通过
3. **分批迁移**: 按 company_id 分批迁移，逐步验证
4. **双写验证**: 迁移后短期双写，对比数据一致性

**biz_label 专属措施**:
1. **NULL 统计**: 在迁移前统计 Legacy 中 NULL `companyId` 的数量，评估数据丢失风险
2. **孤儿数据记录**: 将无法迁移的记录（NULL 或无效 FK）导出到日志文件，供后续人工审查
3. **性能优化**: 由于数据量大 (126,332 行)，考虑使用 `COPY` 命令而非 `INSERT` 提升性能
4. **分批提交**: 每批 10,000 行提交一次，避免事务过大导致锁表

**年金客户 专属措施**:
1. **被过滤数据审查**: 导出被剔除的 793 行数据 (`company_id LIKE 'IN%'`)，审查是否真的应该过滤
2. **过滤条件验证**: 在迁移前验证 `WHERE company_id NOT LIKE 'IN%'` 是否正确匹配预期数据
3. **数据完整性**: 确保过滤后的 10,204 行包含所有有效业务数据

---

## 11. P0 表结构差异分析状态汇总

| 序号 | Schema | 表名 | 行数 | 风险等级 | 状态 | 章节 |
|------|--------|------|------|---------|------|------|
| 1 | public | pipeline_executions | - | 🟡 中 | ⬜ 待分析 | - |
| 2 | public | data_quality_metrics | - | 🟡 中 | ⬜ 待分析 | - |
| 3 | enterprise | base_info | 28,576 | 🔴 高 | ✅ 已完成 | [§1](#1-enterprisebase_info) |
| 4 | enterprise | business_info | 11,542 | 🔴 高 | ✅ 已完成 | [§2](#2-enterprisebusiness_info) |
| 5 | enterprise | biz_label | 126,332 | 🔴 高 | ✅ 已完成 | [§3](#3-enterprisebiz_label) |
| 6 | enterprise | company_types_classification | 104 | 🟡 中 | ✅ 已完成 | [§5](#5-enterprisecompany_types_classification) |
| 7 | enterprise | industrial_classification | 1,183 | 🟡 中 | ✅ 已完成 | [§6](#6-enterpriseindustrial_classification) |
| 8 | business | 规模明细 | 625,126 | 🟡 中 | ⬜ 待分析 | - |
| 9 | business | 收入明细 | 158,480 | 🟡 中 | ⬜ 待分析 | - |
| 10 | mapping | 年金客户 | 10,204 | 🔴 高 | ✅ 已完成 | [§4](#4-mapping年金客户) |
| 11 | mapping | 组合计划 | 1,338 | 🟡 中 | ⬜ 待分析 | - |
| 12 | mapping | 年金计划 | 1,159 | 🟡 中 | ⬜ 待分析 | - |
| 13 | mapping | 组织架构 | 38 | 🟡 中 | ✅ 已完成 | [§8](#8-mapping组织架构) |
| 14 | mapping | 产品线 | 12 | 🟡 中 | ✅ 已完成 | [§7](#7-mapping产品线) |
| 15 | mapping | 计划层规模 | 7 | 🟡 中 | ✅ 已完成 | [§9](#9-mapping计划层规模) |
| 16 | mapping | 产品明细 | 18 | 🟡 中 | ⬜ 待分析 | - |
| 17 | mapping | 利润指标 | 12 | 🟡 中 | ⬜ 待分析 | - |
| 18 | system | sync_state | - | 🟡 中 | ⬜ 待分析 | - |

**统计**:
- ✅ **已完成**: 9/18 (50%)
  - enterprise: 5/5 (100%) ✅
  - mapping: 4/8 (50%)
  - business: 0/2 (0%)
  - public: 0/2 (0%)
  - system: 0/1 (0%)
- ⬜ **待分析**: 9/18 (50%)

---

## 12. 变更历史

| 日期 | 变更内容 | 作者 |
|------|---------|------|
| 2025-12-27 | 完成 enterprise.base_info 表结构差异分析 | Link, Claude (Barry) |
| 2025-12-27 | 完成 enterprise.business_info 表结构差异分析 (40→43字段, 主键变更, 6字段类型规范化) | Link, Claude (Barry) |
| 2025-12-27 | 完成 enterprise.biz_label 表结构差异分析 (7→9字段, 主键变更, 5字段重命名, NOT NULL约束, 复合索引) | Link, Claude (Barry) |
| 2025-12-27 | 完成 mapping.年金客户 表结构差异分析 (27字段完全一致, WHERE过滤793行, 最简单的P0表) | Link, Claude (Barry) |
| 2025-12-27 | 完成 enterprise.company_types_classification 表结构差异分析 (8字段完全一致, 104行, 零风险参考数据表) | Link, Claude (Barry) |
| 2025-12-27 | 完成 enterprise.industrial_classification 表结构差异分析 (10字段完全一致, 1,183行, 零风险参考数据表) | Link, Claude (Barry) |
| 2025-12-27 | 完成 mapping.产品线 表结构差异分析 (6字段完全一致, 12→14行数据量差异, 增量迁移策略) | Link, Claude (Barry) |
| 2025-12-27 | 完成 mapping.组织架构 表结构差异分析 (9字段完全一致, 38→41行数据量差异, 增量迁移策略) | Link, Claude (Barry) |
| 2025-12-27 | 完成 mapping.计划层规模 表结构差异分析 (5字段完全一致, 7行, 零风险参考数据表, 最简单的P0迁移表之一) | Link, Claude (Barry) |
| 2025-12-28 | 更新 P0 表清单概览 - 添加完整的18张表清单，明确标记9/50%完成状态，添加章节链接 | Link, Claude (Barry) |
| 2025-12-28 | **重要概念澄清**: 明确迁移脚本职责范围，"主键变更"是表结构差异（由Alembic管理），不是迁移脚本需要处理的转换。更新风险评估表格，移除"主键变更"行，重新评估迁移难度 | Link, Claude (Barry) |

---

## 总结

本文档完成了对 **18 张 P0 迁移表** 中 **9 张表 (50%)** 的结构差异分析：

### ✅ 已完成分析 (9/18)

1. **enterprise** (5/5 - 100%): base_info, business_info, biz_label, company_types_classification, industrial_classification
2. **mapping** (4/8 - 50%): 年金客户, 产品线, 组织架构, 计划层规模

### ⬜ 待分析 (9/18)

1. **business** (2/2 - 0%): 规模明细 (625,126行), 收入明细 (158,480行)
2. **mapping** (4/8 - 50%): 组合计划 (1,338行), 年金计划 (1,159行), 产品明细 (18行), 利润指标 (12行)
3. **public** (2/2 - 0%): pipeline_executions, data_quality_metrics
4. **system** (1/1 - 0%): sync_state

### 📊 分析成果

- ✅ 所有 enterprise 核心表已完成分析
- ✅ mapping 参考数据表大部分已完成分析
- 📋 为每张表提供了详细的字段对比、迁移策略和验证SQL
- 🎯 识别了4种迁移模式：直接迁移、数据清洗、字段映射、增量迁移
- ⚠️ **重要澄清**: "主键变更"是表结构差异，由Alembic管理，不是迁移脚本的责任

### 🎯 迁移脚本核心原则

**迁移脚本职责** (仅负责数据迁移):
- ✅ `INSERT INTO target_table SELECT ... FROM source_table`
- ✅ 数据类型转换、字段映射、数据清洗
- ✅ WHERE 过滤、外键验证

**不迁移脚本职责** (由Alembic管理):
- ❌ CREATE TABLE、ALTER TABLE、DROP CONSTRAINT
- ❌ 修改主键、索引、约束等DDL操作

### 🎯 下一步

建议优先分析剩余的 **9 张表**，特别是：
- business schema 的 2 张大表 (规模明细、收入明细)
- mapping schema 的 4 张待分析表
- public 和 system 的基础设施表

