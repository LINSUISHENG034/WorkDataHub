# Table Structure Reference

> **数据来源**: PostgreSQL (postgres MCP) + Legacy (legacy-mysql MCP)
> **提取日期**: 2024-12-24
> **用途**: 新迁移脚本编写参考

---

## 1. Schema: public (迁移管理)

### 1.1 pipeline_executions ✅

**来源**: 现有迁移 `20251113_000001`

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| execution_id | uuid | NO | - | PK |
| pipeline_name | varchar | NO | - | |
| status | varchar | NO | - | |
| started_at | timestamptz | NO | - | |
| completed_at | timestamptz | YES | - | |
| input_file | text | YES | - | |
| row_counts | jsonb | YES | - | |
| error_details | text | YES | - | |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

**Indexes**:
- `pipeline_executions_pkey` (execution_id) - PK
- `ix_pipeline_executions_pipeline_name` (pipeline_name)
- `ix_pipeline_executions_started_at` (started_at)

---

### 1.2 data_quality_metrics ✅

**来源**: 现有迁移 `20251113_000001`

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| metric_id | uuid | NO | - | PK |
| execution_id | uuid | NO | - | FK → pipeline_executions |
| pipeline_name | varchar | NO | - | |
| metric_type | varchar | NO | - | |
| metric_value | numeric | YES | - | |
| recorded_at | timestamptz | NO | - | |
| metadata | jsonb | YES | - | |

**Indexes**:
- `data_quality_metrics_pkey` (metric_id) - PK
- `ix_data_quality_metrics_pipeline_name` (pipeline_name)
- `ix_data_quality_metrics_metric_type` (metric_type)

**Foreign Keys**:
- `data_quality_metrics_execution_id_fkey` → pipeline_executions(execution_id) ON DELETE CASCADE

---

## 2. Schema: enterprise

### 2.1 base_info ✅

**来源**: 现有迁移 `20251206_000001`，实际表有 41 列

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| company_id | varchar(255) | NO | - | PK |
| search_key_word | varchar(255) | YES | - | |
| name | varchar(255) | YES | - | Legacy |
| name_display | varchar(255) | YES | - | Legacy |
| symbol | varchar(255) | YES | - | Legacy |
| rank_score | double precision | YES | - | Legacy |
| country | varchar(255) | YES | - | Legacy |
| company_en_name | varchar(255) | YES | - | Legacy |
| smdb_code | varchar(255) | YES | - | Legacy |
| is_hk | integer | YES | - | Legacy |
| coname | varchar(255) | YES | - | Legacy |
| is_list | integer | YES | - | Legacy |
| company_nature | varchar(255) | YES | - | Legacy |
| _score | double precision | YES | - | Legacy |
| type | varchar(255) | YES | - | Legacy |
| registeredStatus | varchar(255) | YES | - | Legacy (camelCase) |
| organization_code | varchar(255) | YES | - | Legacy |
| le_rep | text | YES | - | Legacy |
| reg_cap | double precision | YES | - | Legacy |
| is_pa_relatedparty | integer | YES | - | Legacy |
| province | varchar(255) | YES | - | Legacy |
| companyFullName | varchar(255) | YES | - | Canonical (quoted) |
| est_date | varchar(255) | YES | - | Legacy (raw string) |
| company_short_name | varchar(255) | YES | - | Legacy |
| id | varchar(255) | YES | - | Legacy |
| is_debt | integer | YES | - | Legacy |
| unite_code | varchar(255) | YES | - | Canonical credit code |
| registered_status | varchar(255) | YES | - | Canonical status |
| cocode | varchar(255) | YES | - | Legacy |
| default_score | double precision | YES | - | Legacy |
| company_former_name | varchar(255) | YES | - | Legacy |
| is_rank_list | integer | YES | - | Legacy |
| trade_register_code | varchar(255) | YES | - | Legacy |
| companyId | varchar(255) | YES | - | Legacy (camelCase) |
| is_normal | integer | YES | - | Legacy |
| company_full_name | varchar(255) | YES | - | Legacy (compatibility) |
| raw_data | jsonb | YES | - | API response |
| raw_business_info | jsonb | YES | - | findDepart response |
| raw_biz_label | jsonb | YES | - | findLabels response |
| api_fetched_at | timestamptz | YES | - | |
| updated_at | timestamptz | NO | now() | |

**Indexes**:
- `base_info_pkey1` (company_id) - PK
- `idx_base_info_unite_code` (unite_code)
- `idx_base_info_search_key` (search_key_word)
- `idx_base_info_api_fetched` (api_fetched_at)

---

### 2.2 business_info ✅

**来源**: 现有迁移 `20251206_000001`，实际表有 43 列

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | nextval() | PK, auto-increment |
| company_id | varchar(255) | NO | - | FK → base_info |
| registered_date | date | YES | - | Normalized |
| registered_capital | numeric(20,2) | YES | - | Normalized |
| start_date | date | YES | - | |
| end_date | date | YES | - | |
| colleagues_num | integer | YES | - | 员工数 |
| actual_capital | numeric(20,2) | YES | - | |
| registered_status | varchar(100) | YES | - | |
| legal_person_name | varchar(255) | YES | - | |
| address | text | YES | - | |
| codename | varchar(100) | YES | - | |
| company_name | varchar(255) | YES | - | |
| company_en_name | text | YES | - | |
| currency | varchar(50) | YES | - | |
| credit_code | varchar(50) | YES | - | 统一社会信用代码 |
| register_code | varchar(50) | YES | - | |
| organization_code | varchar(50) | YES | - | |
| company_type | varchar(100) | YES | - | |
| industry_name | varchar(255) | YES | - | |
| registration_organ_name | varchar(255) | YES | - | |
| start_end | varchar(100) | YES | - | |
| business_scope | text | YES | - | |
| telephone | varchar(100) | YES | - | |
| email_address | varchar(255) | YES | - | |
| website | varchar(500) | YES | - | |
| company_former_name | text | YES | - | |
| control_id | varchar(100) | YES | - | |
| control_name | varchar(255) | YES | - | |
| bene_id | varchar(100) | YES | - | |
| bene_name | varchar(255) | YES | - | |
| province | varchar(100) | YES | - | |
| department | varchar(255) | YES | - | |
| legal_person_id | varchar(100) | YES | - | |
| logo_url | text | YES | - | |
| type_code | varchar(50) | YES | - | |
| update_time | date | YES | - | EQC update time |
| registered_capital_currency | varchar(50) | YES | - | |
| full_register_type_desc | varchar(255) | YES | - | |
| industry_code | varchar(50) | YES | - | |
| _cleansing_status | jsonb | YES | - | Cleansing tracking |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

**Indexes**:
- `business_info_pkey1` (id) - PK
- `idx_business_info_company_id` (company_id)

**Foreign Keys**:
- `fk_business_info_company_id` → base_info(company_id)

---

### 2.3 biz_label ✅

**来源**: 现有迁移 `20251206_000001`

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | nextval() | PK |
| company_id | varchar(255) | NO | - | FK → base_info |
| type | varchar(100) | YES | - | Label type |
| lv1_name | varchar(255) | YES | - | Level 1 |
| lv2_name | varchar(255) | YES | - | Level 2 |
| lv3_name | varchar(255) | YES | - | Level 3 |
| lv4_name | varchar(255) | YES | - | Level 4 |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

**Indexes**:
- `biz_label_pkey1` (id) - PK
- `idx_biz_label_company_id` (company_id)
- `idx_biz_label_hierarchy` (company_id, type, lv1_name, lv2_name)

**Foreign Keys**:
- `fk_biz_label_company_id` → base_info(company_id)

---

### 2.4 enrichment_requests ✅

**来源**: 现有迁移 `20251206_000001` + `20251207_000001`

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | nextval() | PK |
| raw_name | varchar(255) | NO | - | 原始名称 |
| normalized_name | varchar(255) | NO | - | 规范化名称 |
| temp_id | varchar(50) | YES | - | IN_xxx 格式 |
| status | varchar(20) | NO | 'pending' | pending/processing/done/failed |
| attempts | integer | NO | 0 | |
| last_error | text | YES | - | |
| resolved_company_id | varchar(100) | YES | - | |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

**Indexes**:
- `enrichment_requests_pkey` (id) - PK
- `idx_enrichment_requests_status` (status, created_at)
- `idx_enrichment_requests_normalized` UNIQUE PARTIAL (normalized_name) WHERE status IN ('pending', 'processing')

**注意**: 迁移 `20251207_000001` 添加 `next_retry_at` 列，但当前数据库未执行该迁移

---

### 2.5 enrichment_index ✅

**来源**: 现有迁移 `20251208_000001`

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | nextval() | PK |
| lookup_key | varchar(255) | NO | - | |
| lookup_type | varchar(20) | NO | - | plan_code/account_name/account_number/customer_name/plan_customer |
| company_id | varchar(100) | NO | - | |
| confidence | numeric(3,2) | NO | 1.00 | 0.00-1.00 |
| source | varchar(50) | NO | - | yaml/eqc_api/manual/backflow/domain_learning/legacy_migration |
| source_domain | varchar(50) | YES | - | |
| source_table | varchar(100) | YES | - | |
| hit_count | integer | NO | 0 | |
| last_hit_at | timestamptz | YES | - | |
| created_at | timestamptz | NO | now() | |
| updated_at | timestamptz | NO | now() | |

**Indexes**:
- `enrichment_index_pkey` (id) - PK
- `uq_enrichment_index_key_type` UNIQUE (lookup_key, lookup_type)
- `ix_enrichment_index_type_key` (lookup_type, lookup_key)
- `ix_enrichment_index_source` (source)
- `ix_enrichment_index_source_domain` (source_domain)

**Check Constraints**:
- `chk_enrichment_index_lookup_type` - lookup_type IN (...)
- `chk_enrichment_index_source` - source IN (...)
- `chk_enrichment_index_confidence` - confidence >= 0.00 AND confidence <= 1.00

---

### 2.6 company_types_classification ✅ (非迁移)

**来源**: 直接从 postgres 数据库提取

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| company_type | varchar | YES | NULL | |
| typeCode | varchar | NO | - | PK |
| 公司类型/组织类型 | varchar | YES | NULL | |
| 分类 | varchar | YES | NULL | |
| 子分类 | varchar | YES | NULL | |
| 是否上市 | varchar | YES | NULL | |
| 法人类型 | varchar | YES | NULL | |
| 说明 | varchar | YES | NULL | |

**Indexes**:
- `company_types_classification_pkey` (typeCode) - PK

**数据量**: 104 行 (适合作为种子数据)

---

### 2.7 industrial_classification ✅ (非迁移)

**来源**: 直接从 postgres 数据库提取

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| 门类名称 | varchar | YES | NULL | |
| 大类名称 | varchar | YES | NULL | |
| 中类名称 | varchar | YES | NULL | |
| 类别名称 | varchar | YES | NULL | |
| 类别代码 | varchar | NO | - | PK |
| 门类代码 | varchar | YES | NULL | |
| 大类代码 | varchar | YES | NULL | |
| 中类顺序码 | varchar | YES | NULL | |
| 小类顺序码 | varchar | YES | NULL | |
| 说明 | varchar | YES | NULL | |

**Indexes**:
- `industrial_classification_pkey` (类别代码) - PK

**数据量**: 1,183 行 (国标行业分类，适合作为种子数据)

---

### 2.8 validation_results ✅ (非迁移)

**来源**: 直接从 postgres 数据库提取

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | nextval() | PK |
| validated_at | timestamptz | YES | now() | |
| archive_company_id | varchar | NO | - | |
| search_key_word | varchar | YES | - | |
| archive_company_name | varchar | YES | - | |
| archive_unite_code | varchar | YES | - | |
| api_success | boolean | YES | - | |
| api_company_id | varchar | YES | - | |
| api_company_name | varchar | YES | - | |
| api_unite_code | varchar | YES | - | |
| api_results_count | integer | YES | - | |
| company_id_match | boolean | YES | - | |
| company_name_match | boolean | YES | - | |
| unite_code_match | boolean | YES | - | |
| error_message | text | YES | - | |

**Indexes**:
- `validation_results_pkey` (id) - PK

---

## 3. Schema: business

### 3.1 规模明细 ✅ (非迁移)

**来源**: postgres 数据库 (ETL 产出)

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | - | PK |
| 月度 | date | NO | - | |
| 业务类型 | varchar | YES | - | |
| 计划类型 | varchar | YES | - | |
| 计划代码 | varchar | NO | - | |
| 计划名称 | varchar | YES | - | |
| 组合类型 | varchar | YES | - | |
| 组合代码 | varchar | YES | - | |
| 组合名称 | varchar | YES | - | |
| 客户名称 | varchar | YES | - | |
| 期初资产规模 | double precision | YES | - | |
| 期末资产规模 | double precision | YES | - | |
| 供款 | double precision | YES | - | |
| 流失_含待遇支付 | double precision | YES | - | |
| 流失 | double precision | YES | - | |
| 待遇支付 | double precision | YES | - | |
| 投资收益 | double precision | YES | - | |
| 当期收益率 | double precision | YES | - | |
| 机构代码 | varchar | YES | - | |
| 机构名称 | varchar | YES | - | |
| 产品线代码 | varchar | YES | - | |
| 年金账户号 | varchar | YES | - | |
| 年金账户名 | varchar | YES | - | |
| company_id | varchar | NO | - | |
| created_at | timestamptz | YES | CURRENT_TIMESTAMP | |
| updated_at | timestamptz | YES | CURRENT_TIMESTAMP | |

**Indexes** (10个):
- `规模明细_pkey` (id) - PK
- `idx_规模明细_月度` (月度)
- `idx_规模明细_计划代码` (计划代码)
- `idx_规模明细_company_id` (company_id)
- `idx_规模明细_机构代码` (机构代码)
- `idx_规模明细_产品线代码` (产品线代码)
- `idx_规模明细_年金账户号` (年金账户号)
- `idx_规模明细_月度_计划代码` (月度, 计划代码)
- `idx_规模明细_月度_company_id` (月度, company_id)
- `idx_规模明细_月度_计划代码_company_id` (月度, 计划代码, company_id)

**数据量**: 625,126 行

---

### 3.2 收入明细 (需创建)

**来源**: legacy 数据库结构参考

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | - | PK |
| 月度 | date | YES | - | |
| 业务类型 | varchar | YES | NULL | |
| 计划类型 | varchar | YES | NULL | |
| 计划号 | varchar | YES | NULL | ⚠️ legacy 用 "计划号" |
| 计划名称 | varchar | YES | NULL | |
| 组合类型 | varchar | YES | NULL | |
| 组合代码 | varchar | YES | NULL | |
| 组合名称 | varchar | YES | NULL | |
| 客户名称 | varchar | YES | NULL | |
| company_id | varchar | YES | NULL | |
| 固费 | double precision | YES | - | |
| 浮费 | double precision | YES | - | |
| 回补 | double precision | YES | - | |
| 税 | double precision | YES | - | |
| 机构代码 | varchar | YES | NULL | |
| 机构名称 | varchar | YES | NULL | |
| 产品线代码 | varchar | YES | NULL | |
| 年金账户名 | varchar | YES | NULL | |

**建议调整**:
- 添加 `created_at`, `updated_at` 审计字段
- 添加索引（参考规模明细）
- 统一字段名：`计划号` → `计划代码`（与规模明细一致）

---

## 4. Schema: mapping

### 4.1 年金计划 ✅ (非迁移)

**来源**: postgres 数据库

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | - | |
| 年金计划号 | varchar | NO | - | PK |
| 计划简称 | varchar | YES | NULL | |
| 计划全称 | varchar | YES | NULL | |
| 主拓代码 | varchar | YES | NULL | |
| 计划类型 | varchar | YES | NULL | |
| 客户名称 | varchar | YES | NULL | |
| company_id | varchar | YES | NULL | |
| 管理资格 | varchar | YES | NULL | |
| 计划状态 | varchar | YES | NULL | |
| 主拓机构 | varchar | YES | NULL | |
| 组合数 | integer | YES | - | |
| 北京统括 | smallint | YES | 0 | |
| 备注 | text | YES | - | |

**Indexes**:
- `年金计划_pkey` (年金计划号) - PK

**数据量**: 1,159 行

---

### 4.2 组合计划 ✅ (非迁移)

**来源**: postgres 数据库

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | - | |
| 年金计划号 | varchar | YES | NULL | FK → 年金计划 |
| 组合代码 | varchar | NO | - | PK |
| 组合名称 | varchar | YES | NULL | |
| 组合简称 | varchar | YES | NULL | |
| 组合状态 | varchar | YES | NULL | |
| 运作开始日 | date | YES | - | |
| 组合类型 | varchar | YES | NULL | |
| 子分类 | varchar | YES | NULL | |
| 受托人 | varchar | YES | NULL | |
| 是否存款组合 | smallint | YES | - | |
| 是否外部组合 | smallint | YES | - | |
| 是否PK组合 | smallint | YES | - | |
| 投资管理人 | varchar | YES | NULL | |
| 受托管理人 | varchar | YES | NULL | |
| 投资组合代码 | varchar | YES | NULL | |
| 投资组合名称 | varchar | YES | NULL | |
| 备注 | text | YES | - | |

**Indexes**:
- `组合计划_pkey` (组合代码) - PK

**Foreign Keys**:
- `FK_年金计划_组合计划` → 年金计划(年金计划号)

**数据量**: 1,338 行

---

### 4.3 产品线 ✅ (非迁移)

**来源**: postgres 数据库

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| 产品线 | varchar | YES | NULL | |
| 产品类别 | varchar | YES | NULL | |
| 业务大类 | varchar | YES | NULL | |
| 产品线代码 | varchar | NO | - | PK |
| NO_产品线 | integer | YES | - | |
| NO_产品类别 | integer | YES | - | |

**Indexes**:
- `产品线_pkey` (产品线代码) - PK

**数据量**: 12 行

---

### 4.4 组织架构 ✅ (非迁移)

**来源**: postgres 数据库

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| 机构 | varchar | YES | NULL | |
| 年金中心 | varchar | YES | NULL | |
| 战区 | varchar | YES | NULL | |
| 机构代码 | varchar | NO | - | PK |
| NO_机构 | integer | YES | - | |
| NO_年金中心 | integer | YES | - | |
| NO_区域 | integer | YES | - | |
| 新架构 | varchar | YES | NULL | |
| 行政域 | varchar | YES | NULL | |

**Indexes**:
- `组织架构_pkey` (机构代码) - PK

**数据量**: 38 行

---

### 4.5 年金客户 ✅ (非迁移)

**来源**: postgres 数据库

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| id | integer | NO | - | |
| company_id | varchar | NO | - | PK |
| 客户名称 | varchar | YES | NULL | |
| 年金客户标签 | varchar | YES | NULL | |
| 年金客户类型 | varchar | YES | NULL | |
| 年金计划类型 | varchar | YES | NULL | |
| 关键年金计划 | varchar | YES | NULL | |
| 主拓机构代码 | varchar | YES | NULL | |
| 主拓机构 | varchar | YES | NULL | |
| 其他年金计划 | varchar | YES | NULL | |
| 客户简称 | varchar | YES | NULL | |
| 更新时间 | date | YES | - | |
| 最新受托规模 | double precision | YES | - | |
| 最新投管规模 | double precision | YES | - | |
| 管理资格 | varchar | YES | NULL | |
| 规模区间 | varchar | YES | NULL | |
| 计划层规模 | double precision | YES | - | |
| 年缴费规模 | double precision | YES | - | |
| 外部受托规模 | double precision | YES | - | |
| 上报受托规模 | double precision | YES | - | |
| 上报投管规模 | double precision | YES | - | |
| 关联机构数 | integer | YES | - | |
| 其他开拓机构 | varchar | YES | NULL | |
| 计划状态 | varchar | YES | NULL | |
| 关联计划数 | integer | YES | - | |
| 备注 | text | YES | - | |

**Indexes**:
- `年金客户_pkey` (company_id) - PK

**数据量**: 10,997 行

---

### 4.6 计划层规模 ✅ (非迁移)

**来源**: postgres 数据库

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| 规模分类代码 | varchar | NO | - | PK |
| 规模分类 | varchar | YES | NULL | |
| NO_规模分类 | integer | YES | - | |
| 规模大类 | varchar | YES | NULL | |
| NO_规模大类 | integer | YES | - | |

**Indexes**:
- `计划层规模_pkey` (规模分类代码) - PK

**数据量**: 7 行

---

## 5. Schema: system

### 5.1 sync_state (需创建)

**来源**: 现有迁移 `20251214_000001` (未执行)

| Column | Type | Nullable | Default | 备注 |
|--------|------|----------|---------|------|
| job_name | varchar(255) | NO | - | PK (composite) |
| table_name | varchar(255) | NO | - | PK (composite) |
| last_synced_at | timestamptz | NO | - | High-water mark |
| updated_at | timestamptz | NO | CURRENT_TIMESTAMP | |

**Indexes**:
- PK (job_name, table_name) - Composite PK
- `ix_sync_state_updated_at` (updated_at)

---

## 6. 价值评估汇总

### 6.1 可直接复用的迁移定义

| 表名 | 来源 | 复用价值 | 备注 |
|------|------|---------|------|
| pipeline_executions | 20251113_000001 | ✅ 高 | 直接复用 |
| data_quality_metrics | 20251113_000001 | ✅ 高 | 直接复用 |
| base_info | 20251206_000001 | ✅ 高 | 41列完整定义 |
| business_info | 20251206_000001 | ✅ 高 | 43列完整定义 |
| biz_label | 20251206_000001 | ✅ 高 | 直接复用 |
| enrichment_requests | 20251206_000001 | ⚠️ 中 | 需合并 next_retry_at |
| enrichment_index | 20251208_000001 | ✅ 高 | 直接复用 |
| sync_state | 20251214_000001 | ✅ 高 | 直接复用 |

### 6.2 需从数据库提取的表结构

| 表名 | Schema | 复用价值 | 备注 |
|------|--------|---------|------|
| company_types_classification | enterprise | ✅ 高 | 种子数据表 |
| industrial_classification | enterprise | ✅ 高 | 种子数据表 |
| validation_results | enterprise | ⚠️ 中 | 验证辅助表 |
| 规模明细 | business | ✅ 高 | 主业务表，完善索引 |
| 年金计划 | mapping | ✅ 高 | 参考表 |
| 组合计划 | mapping | ✅ 高 | 参考表，有 FK |
| 产品线 | mapping | ✅ 高 | 参考表 |
| 组织架构 | mapping | ✅ 高 | 参考表 |
| 年金客户 | mapping | ✅ 高 | 参考表 |
| 计划层规模 | mapping | ✅ 高 | 参考表 |

### 6.3 需要新建的表

| 表名 | Schema | 参考来源 | 备注 |
|------|--------|---------|------|
| 收入明细 | business | legacy 结构 + 规模明细约定 | 统一审计字段、索引 |

---

## 7. 差异点与建议

### 7.1 字段命名不一致

| 表 | legacy 字段 | postgres 字段 | 建议 |
|----|-----------|--------------|------|
| 收入明细 | 计划号 | - | 改为 `计划代码`（与规模明细一致） |
| 规模明细 | 流失(含待遇支付) | 流失_含待遇支付 | 保持 postgres 版本（无括号） |

### 7.2 缺失的审计字段

以下表建议添加 `created_at`, `updated_at`:
- 收入明细 (新建时添加)
- mapping.* 表 (可选，参考数据变更频率低)

### 7.3 缺失的索引

收入明细建议添加索引（参考规模明细）:
- `idx_收入明细_月度`
- `idx_收入明细_计划代码`
- `idx_收入明细_company_id`
- 组合索引

---

*文档完成，可作为新迁移脚本编写参考*
