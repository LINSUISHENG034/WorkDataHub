# Database Schema Panorama (数据库全景图)

**Created:** 2025-12-23
**Last Updated:** 2026-01-16
**Version:** 2.1
**Maintainer:** Development Team
**Verified Against:** PostgreSQL production database (2025-12-23)

---

## Quick Navigation

| Section | Description |
|---------|-------------|
| [1. Overview](#1-overview) | Architecture summary and design principles |
| [2. Schema: enterprise](#2-schema-enterprise) | Company enrichment & EQC data (12 tables) |
| [3. Schema: business](#3-schema-business) | Domain transaction data (1 table) |
| [4. Schema: mapping](#4-schema-mapping) | Reference/master data (6 tables) |
| [5. Schema: public](#5-schema-public) | Pipeline infrastructure (3 tables) |
| [6. Schema: customer](#6-schema-customer) | Customer lifecycle tracking (2 tables, 1 view) |
| [7. Empty Schemas](#7-empty-schemas) | Reserved schemas |
| [8. Entity Relationships](#8-entity-relationships) | Visual table relationships |
| [9. Data Flow Architecture](#9-data-flow-architecture) | How data moves through the system |
| [Appendix](#appendix) | Configuration, glossary, deprecated tables |

---

## 1. Overview

### 1.1 Database Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL - work_data_hub                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  enterprise  │  │   business   │  │   mapping    │  │    public    │ │
│  │  (12 tables) │  │  (1 table)   │  │  (6 tables)  │  │  (3 tables)  │ │
│  │              │  │              │  │              │  │              │ │
│  │ • EQC Data   │  │ • 规模明细   │  │ • 年金计划   │  │ • Pipeline   │ │
│  │ • Enrichment │  │              │  │ • 组合计划   │  │   Execution  │ │
│  │ • Archive    │  │              │  │ • 年金客户   │  │ • Metrics    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   customer   │  │   finance    │  │    system    │  │   wdh_dev    │ │
│  │  (3 objects) │  │   (empty)    │  │   (empty)    │  │   (empty)    │ │
│  │ • 当年中标   │  │  [Reserved]  │  │  [Reserved]  │  │  [Reserved]  │ │
│  │ • 当年流失   │  │              │  │              │  │              │ │
│  │ • Agg View   │  │              │  │              │  │              │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Schema Summary

| Schema | Tables | Purpose | Status |
|--------|--------|---------|--------|
| `enterprise` | 12 | Company enrichment, EQC data, mapping cache | ✅ Active |
| `business` | 1 | Domain transaction data (annuity performance) | ✅ Active |
| `mapping` | 6 | Reference/master data (plans, portfolios, customers) | ✅ Active |
| `public` | 3 | Pipeline infrastructure (executions, metrics, migrations) | ✅ Active |
| `customer` | 3 | Customer lifecycle tracking (awards, losses, views) | ✅ Active |
| `finance` | 0 | Reserved for future financial data | 🔲 Empty |
| `system` | 0 | Reserved for system operations | 🔲 Empty |
| `wdh_dev` | 0 | Development/testing sandbox | 🔲 Empty |

### 1.3 Legacy Database (Reference Only)

> ⚠️ **重要提示:** Legacy MySQL 数据库已全部迁移至 PostgreSQL 数据库。
>
> - **连接地址:** `postgresql://localhost:5432/legacy`
> - **用途:** 参考数据同步 (Reference Sync) 的只读数据源
> - **配置位置:** `config/reference_sync.yml`, 环境变量 `WDH_LEGACY_PG_*`

#### Legacy Database Schema Summary (58 tables)

| Schema | Tables | Purpose |
|--------|--------|---------|
| `enterprise` | 9 | Company master data, EQC search results, classifications |
| `business` | 9 | Domain transaction data (规模明细, 收入明细, 组合业绩, etc.) |
| `mapping` | 11 | Reference/master data (年金计划, 组合计划, 年金客户, etc.) |
| `customer` | 20 | Customer lifecycle tracking (中标, 已客, 战客, 流失, etc.) |
| `finance` | 7 | Financial data (减值计提, 历史浮费, 考核收入, etc.) |
| `config` | 1 | Configuration (data_sources) |
| `legacy` | 0 | Empty (reserved) |

#### Key Tables in Legacy Database

**enterprise schema:**
- `base_info`, `business_info`, `biz_label` - EQC company data (source for sync)
- `company_id_mapping`, `annuity_account_mapping` - Historical mappings
- `company_types_classification`, `industrial_classification` - Reference codes

**business schema:**
- `规模明细` - Annuity performance (synced to work_data_hub)
- `收入明细` - Annuity income
- `组合业绩` - Portfolio performance
- `企康缴费`, `团养缴费` - Payment records

**mapping schema:**
- `年金计划`, `组合计划`, `年金客户` - Master data (synced to work_data_hub)
- `产品线`, `组织架构`, `计划层规模` - Reference data (synced to work_data_hub)

### 1.4 Design Principles

| Principle | Description |
|-----------|-------------|
| **Single Source of Truth** | Domain Registry defines all schema metadata |
| **Zero Legacy** | No deprecated tables or backward-compatible wrappers |
| **Async Enrichment** | Multi-layer cache + queue for company ID resolution |
| **Audit Trail** | All tables have `created_at`/`updated_at` timestamps |

---

## 2. Schema: enterprise

**Purpose:** Company enrichment, EQC API data storage, and mapping cache.

### 2.1 Table Summary

| Table | Rows | Purpose | Status |
|-------|------|---------|--------|
| `base_info` | ~125 | Master company data (EQC primary) | ✅ Active |
| `business_info` | ~125 | Company business details (cleansed) | ✅ Active |
| `biz_label` | ~500 | Business classifications (4-level hierarchy) | ✅ Active |
| `enrichment_index` | ~300 | Layer 2 lookup cache (5 types) | ✅ Active |
| `enrichment_requests` | ~50 | Async enrichment queue | ✅ Active |
| `company_mapping` | ~200 | Priority-based mapping | ❌ **DEPRECATED** |
| `archive_base_info` | ~125 | Legacy backup (from MySQL) | 📦 Archive |
| `archive_business_info` | ~125 | Legacy backup | 📦 Archive |
| `archive_biz_label` | ~500 | Legacy backup | 📦 Archive |
| `company_types_classification` | ~100 | Company type reference | 📖 Reference |
| `industrial_classification` | ~1500 | Industry codes (GB/T 4754) | 📖 Reference |
| `validation_results` | ~200 | EQC validation audit | 📊 Audit |

---

### 2.2 base_info (Master Company Data)

**Purpose:** Primary company information from EQC API.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `company_id` | VARCHAR | **NO** | **PK** - EQC company identifier |
| `search_key_word` | VARCHAR | YES | Original search keyword |
| `name` | VARCHAR | YES | Company name |
| `name_display` | VARCHAR | YES | Display name |
| `symbol` | VARCHAR | YES | Stock symbol |
| `rank_score` | DOUBLE | YES | EQC ranking score |
| `country` | VARCHAR | YES | Country code |
| `company_en_name` | VARCHAR | YES | English name |
| `smdb_code` | VARCHAR | YES | SMDB identifier |
| `is_hk` | INTEGER | YES | Hong Kong company flag (0/1) |
| `coname` | VARCHAR | YES | Legacy company name |
| `is_list` | INTEGER | YES | Listed company flag (0/1) |
| `company_nature` | VARCHAR | YES | Company nature/type |
| `_score` | DOUBLE | YES | EQC match score |
| `type` | VARCHAR | YES | Match type (全称精确匹配/模糊匹配/拼音) |
| `registeredStatus` | VARCHAR | YES | Registration status (legacy) |
| `organization_code` | VARCHAR | YES | Organization code |
| `le_rep` | TEXT | YES | Legal representative |
| `reg_cap` | DOUBLE | YES | Registered capital |
| `is_pa_relatedparty` | INTEGER | YES | PA related party flag |
| `province` | VARCHAR | YES | Province/region |
| `companyFullName` | VARCHAR | YES | Full legal name |
| `est_date` | VARCHAR | YES | Establishment date |
| `company_short_name` | VARCHAR | YES | Short name |
| `id` | VARCHAR | YES | EQC internal ID |
| `is_debt` | INTEGER | YES | Debt flag |
| `unite_code` | VARCHAR | YES | Unified social credit code |
| `registered_status` | VARCHAR | YES | Current registration status |
| `cocode` | VARCHAR | YES | Company code |
| `default_score` | DOUBLE | YES | Default score |
| `company_former_name` | VARCHAR | YES | Former name |
| `is_rank_list` | INTEGER | YES | Rank list flag |
| `trade_register_code` | VARCHAR | YES | Trade registration code |
| `companyId` | VARCHAR | YES | Alternative company ID |
| `is_normal` | INTEGER | YES | Normal status flag |
| `company_full_name` | VARCHAR | YES | Full name (normalized) |
| `raw_data` | JSONB | YES | Raw EQC searchCompany response |
| `raw_business_info` | JSONB | YES | Raw EQC findDepart response |
| `raw_biz_label` | JSONB | YES | Raw EQC findLabels response |
| `api_fetched_at` | TIMESTAMPTZ | YES | Last API fetch time |
| `updated_at` | TIMESTAMPTZ | **NO** | Last update (default: now()) |

**Indexes:**
- `base_info_pkey1` - PRIMARY KEY on `company_id`
- `idx_base_info_unite_code` - Credit code lookup
- `idx_base_info_search_key` - Search keyword lookup
- `idx_base_info_api_fetched` - API refresh scheduling

---

### 2.3 business_info (Company Business Details)

**Purpose:** Normalized business information from EQC findDepart API.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | **PK** - Auto-increment |
| `company_id` | VARCHAR | **NO** | **FK** → base_info.company_id |
| `registered_date` | DATE | YES | Registration date |
| `registered_capital` | NUMERIC | YES | Registered capital amount |
| `start_date` | DATE | YES | Business start date |
| `end_date` | DATE | YES | Business end date |
| `colleagues_num` | INTEGER | YES | Employee count |
| `actual_capital` | NUMERIC | YES | Actual capital |
| `registered_status` | VARCHAR | YES | Registration status |
| `legal_person_name` | VARCHAR | YES | Legal representative |
| `address` | TEXT | YES | Registered address |
| `codename` | VARCHAR | YES | Code name |
| `company_name` | VARCHAR | YES | Company name |
| `company_en_name` | TEXT | YES | English name |
| `currency` | VARCHAR | YES | Currency code |
| `credit_code` | VARCHAR | YES | Unified credit code |
| `register_code` | VARCHAR | YES | Registration code |
| `organization_code` | VARCHAR | YES | Organization code |
| `company_type` | VARCHAR | YES | Company type |
| `industry_name` | VARCHAR | YES | Industry name |
| `registration_organ_name` | VARCHAR | YES | Registration authority |
| `start_end` | VARCHAR | YES | Operating period |
| `business_scope` | TEXT | YES | Business scope |
| `telephone` | VARCHAR | YES | Contact phone |
| `email_address` | VARCHAR | YES | Contact email |
| `website` | VARCHAR | YES | Website URL |
| `company_former_name` | TEXT | YES | Former names |
| `control_id` | VARCHAR | YES | Actual controller ID |
| `control_name` | VARCHAR | YES | Actual controller name |
| `bene_id` | VARCHAR | YES | Beneficiary owner ID |
| `bene_name` | VARCHAR | YES | Beneficiary owner name |
| `province` | VARCHAR | YES | Province |
| `department` | VARCHAR | YES | Department |
| `legal_person_id` | VARCHAR | YES | Legal person ID |
| `logo_url` | TEXT | YES | Company logo URL |
| `type_code` | VARCHAR | YES | Type code |
| `update_time` | DATE | YES | EQC update time |
| `registered_capital_currency` | VARCHAR | YES | Capital currency |
| `full_register_type_desc` | VARCHAR | YES | Full registration type |
| `industry_code` | VARCHAR | YES | Industry code |
| `_cleansing_status` | JSONB | YES | Cleansing metadata |
| `created_at` | TIMESTAMPTZ | **NO** | Record creation |
| `updated_at` | TIMESTAMPTZ | **NO** | Last update |

**Constraints:**
- `fk_business_info_company_id` → `base_info.company_id`

---

### 2.4 biz_label (Business Classifications)

**Purpose:** 4-level hierarchical business classifications from EQC findLabels API.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | **PK** - Auto-increment |
| `company_id` | VARCHAR | **NO** | **FK** → base_info.company_id |
| `type` | VARCHAR | YES | Label type |
| `lv1_name` | VARCHAR | YES | Level 1 classification |
| `lv2_name` | VARCHAR | YES | Level 2 classification |
| `lv3_name` | VARCHAR | YES | Level 3 classification |
| `lv4_name` | VARCHAR | YES | Level 4 classification |
| `created_at` | TIMESTAMPTZ | **NO** | Record creation |
| `updated_at` | TIMESTAMPTZ | **NO** | Last update |

**Indexes:**
- `idx_biz_label_company_id` - Company lookup
- `idx_biz_label_hierarchy` - Hierarchy search (company_id, type, lv1, lv2)

---

### 2.5 enrichment_index (Layer 2 Lookup Cache)

**Purpose:** Multi-type database cache for company ID resolution.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | **PK** - Auto-increment |
| `lookup_key` | VARCHAR | **NO** | Search key value |
| `lookup_type` | VARCHAR | **NO** | Type: plan_code, account_name, account_number, customer_name, plan_customer |
| `company_id` | VARCHAR | **NO** | Resolved company ID |
| `confidence` | NUMERIC | **NO** | Match confidence (0.00-1.00), default: 1.00 |
| `source` | VARCHAR | **NO** | Data source: yaml, eqc_api, manual, backflow, domain_learning, legacy_migration |
| `source_domain` | VARCHAR | YES | Learning origin domain |
| `source_table` | VARCHAR | YES | Learning origin table |
| `hit_count` | INTEGER | **NO** | Cache hit count, default: 0 |
| `last_hit_at` | TIMESTAMPTZ | YES | Last cache hit time |
| `created_at` | TIMESTAMPTZ | **NO** | Record creation |
| `updated_at` | TIMESTAMPTZ | **NO** | Last update |

**Constraints:**
- `uq_enrichment_index_key_type` - UNIQUE(lookup_key, lookup_type)
- `chk_enrichment_index_lookup_type` - CHECK(lookup_type IN (...))
- `chk_enrichment_index_source` - CHECK(source IN (...))
- `chk_enrichment_index_confidence` - CHECK(confidence >= 0 AND confidence <= 1)

**Indexes:**
- `ix_enrichment_index_type_key` - Primary lookup (lookup_type, lookup_key)
- `ix_enrichment_index_source` - Source filtering
- `ix_enrichment_index_source_domain` - Domain learning tracking

---

### 2.6 enrichment_requests (Async Queue)

**Purpose:** Queue for asynchronous company enrichment.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | **PK** - Auto-increment |
| `raw_name` | VARCHAR | **NO** | Original company name |
| `normalized_name` | VARCHAR | **NO** | Normalized name for matching |
| `temp_id` | VARCHAR | YES | Temporary ID (INxxx format) |
| `status` | VARCHAR | **NO** | Status: pending, processing, done, failed (default: pending) |
| `attempts` | INTEGER | **NO** | Processing attempt count (default: 0) |
| `last_error` | TEXT | YES | Error message if failed |
| `resolved_company_id` | VARCHAR | YES | Result after enrichment |
| `created_at` | TIMESTAMPTZ | **NO** | Record creation |
| `updated_at` | TIMESTAMPTZ | **NO** | Last update |

**Indexes:**
- `idx_enrichment_requests_status` - Status + created_at for queue processing
- `idx_enrichment_requests_normalized` - UNIQUE partial index on normalized_name WHERE status IN (pending, processing)

---

### 2.7 company_mapping (DEPRECATED)

**⚠️ Status: DEPRECATED - To be removed in Epic 7.1-4**

**Replacement:** Use `enrichment_index` instead.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | **PK** - Auto-increment |
| `alias_name` | VARCHAR | **NO** | Source identifier |
| `canonical_id` | VARCHAR | **NO** | Resolved company_id |
| `match_type` | VARCHAR | **NO** | Type: plan, account, hardcode, name, account_name |
| `priority` | INTEGER | **NO** | Resolution priority (1-5) |
| `source` | VARCHAR | **NO** | Data source (default: internal) |
| `created_at` | TIMESTAMPTZ | **NO** | Record creation |
| `updated_at` | TIMESTAMPTZ | **NO** | Last update |

---

### 2.8 company_types_classification (Reference)

**Purpose:** Company type code reference table.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `company_type` | VARCHAR | YES | Company type name |
| `typeCode` | VARCHAR | **NO** | **PK** - Type code |
| `公司类型/组织类型` | VARCHAR | YES | Type in Chinese |
| `分类` | VARCHAR | YES | Classification |
| `子分类` | VARCHAR | YES | Sub-classification |
| `是否上市` | VARCHAR | YES | Listed status |
| `法人类型` | VARCHAR | YES | Legal entity type |
| `说明` | VARCHAR | YES | Description |

---

### 2.9 industrial_classification (Reference)

**Purpose:** National industry classification codes (GB/T 4754).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `门类名称` | VARCHAR | YES | Category name (A-T) |
| `大类名称` | VARCHAR | YES | Major category name |
| `中类名称` | VARCHAR | YES | Medium category name |
| `类别名称` | VARCHAR | YES | Sub-category name |
| `类别代码` | VARCHAR | **NO** | **PK** - Category code |
| `门类代码` | VARCHAR | YES | Category code (A-T) |
| `大类代码` | VARCHAR | YES | Major category code |
| `中类顺序码` | VARCHAR | YES | Medium category sequence |
| `小类顺序码` | VARCHAR | YES | Sub-category sequence |
| `说明` | VARCHAR | YES | Description |

---

### 2.10 validation_results (Audit)

**Purpose:** EQC validation audit trail.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | **PK** - Auto-increment |
| `validated_at` | TIMESTAMPTZ | YES | Validation timestamp (default: now()) |
| `archive_company_id` | VARCHAR | **NO** | Archive company ID |
| `search_key_word` | VARCHAR | YES | Search keyword |
| `archive_company_name` | VARCHAR | YES | Archive company name |
| `archive_unite_code` | VARCHAR | YES | Archive credit code |
| `api_success` | BOOLEAN | YES | API call success |
| `api_company_id` | VARCHAR | YES | API returned company ID |
| `api_company_name` | VARCHAR | YES | API returned name |
| `api_unite_code` | VARCHAR | YES | API returned credit code |
| `api_results_count` | INTEGER | YES | Number of API results |
| `company_id_match` | BOOLEAN | YES | ID match flag |
| `company_name_match` | BOOLEAN | YES | Name match flag |
| `unite_code_match` | BOOLEAN | YES | Credit code match flag |
| `error_message` | TEXT | YES | Error message |

---

### 2.11 archive_base_info (Legacy Archive)

**Purpose:** Backup of original MySQL base_info data.

*Structure similar to base_info with 38 columns, including legacy field `for_check` (BOOLEAN).*

---

## 3. Schema: business

**Purpose:** Domain transaction data for annuity business.

### 3.1 规模明细 (Annuity Performance)

**Purpose:** Monthly asset scale and performance metrics.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | **PK** - Record ID |
| `月度` | DATE | **NO** | Reporting month |
| `业务类型` | VARCHAR | YES | Business type |
| `计划类型` | VARCHAR | YES | Plan type |
| `计划代码` | VARCHAR | **NO** | Plan code |
| `计划名称` | VARCHAR | YES | Plan name |
| `组合类型` | VARCHAR | YES | Portfolio type |
| `组合代码` | VARCHAR | YES | Portfolio code |
| `组合名称` | VARCHAR | YES | Portfolio name |
| `客户名称` | VARCHAR | YES | Customer name |
| `期初资产规模` | DOUBLE | YES | Starting assets |
| `期末资产规模` | DOUBLE | YES | Ending assets |
| `供款` | DOUBLE | YES | Contribution |
| `流失_含待遇支付` | DOUBLE | YES | Loss including benefits |
| `流失` | DOUBLE | YES | Loss |
| `待遇支付` | DOUBLE | YES | Benefit payment |
| `投资收益` | DOUBLE | YES | Investment return |
| `当期收益率` | DOUBLE | YES | Current period return rate |
| `机构代码` | VARCHAR | YES | Institution code |
| `机构名称` | VARCHAR | YES | Institution name |
| `产品线代码` | VARCHAR | YES | Product line code |
| `年金账户号` | VARCHAR | YES | Pension account number |
| `年金账户名` | VARCHAR | YES | Pension account name |
| `company_id` | VARCHAR | **NO** | Enriched company ID |
| `created_at` | TIMESTAMPTZ | YES | Record creation (default: CURRENT_TIMESTAMP) |
| `updated_at` | TIMESTAMPTZ | YES | Last update (default: CURRENT_TIMESTAMP) |

**Keys:**
- **Primary Key:** `id`
- **Composite Key (Business):** (月度, 计划代码, 组合代码, company_id)
- **Delete Scope Key:** (月度, 计划代码, company_id)

**Indexes:**
- `idx_规模明细_月度` - Temporal queries
- `idx_规模明细_计划代码` - Plan lookups
- `idx_规模明细_company_id` - Company filtering
- `idx_规模明细_机构代码` - Institution filtering
- `idx_规模明细_产品线代码` - Product line filtering
- `idx_规模明细_年金账户号` - Account number lookup
- `idx_规模明细_月度_计划代码` - Composite temporal + plan
- `idx_规模明细_月度_company_id` - Composite temporal + company
- `idx_规模明细_月度_计划代码_company_id` - Full composite key

---

## 4. Schema: mapping

**Purpose:** Reference and master data for annuity business.

### 4.1 Table Summary

| Table | Rows | Purpose |
|-------|------|---------|
| `年金计划` | ~500 | Annuity plan master data |
| `组合计划` | ~2000 | Portfolio plan master data |
| `年金客户` | ~300 | Annuity customer master data |
| `产品线` | ~20 | Product line reference |
| `组织架构` | ~50 | Organization structure |
| `计划层规模` | ~10 | Plan scale classification |

---

### 4.2 年金计划 (Annuity Plans)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | Record ID |
| `年金计划号` | VARCHAR | **NO** | **PK** - Plan number |
| `计划简称` | VARCHAR | YES | Plan short name |
| `计划全称` | VARCHAR | YES | Plan full name |
| `主拓代码` | VARCHAR | YES | Primary development code |
| `计划类型` | VARCHAR | YES | Plan type |
| `客户名称` | VARCHAR | YES | Customer name |
| `company_id` | VARCHAR | YES | Company ID |
| `管理资格` | VARCHAR | YES | Management qualification |
| `计划状态` | VARCHAR | YES | Plan status |
| `主拓机构` | VARCHAR | YES | Primary institution |
| `组合数` | INTEGER | YES | Portfolio count |
| `北京统括` | SMALLINT | YES | Beijing unified flag (default: 0) |
| `备注` | TEXT | YES | Notes |

---

### 4.3 组合计划 (Portfolio Plans)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | Record ID |
| `年金计划号` | VARCHAR | YES | **FK** → 年金计划.年金计划号 |
| `组合代码` | VARCHAR | **NO** | **PK** - Portfolio code |
| `组合名称` | VARCHAR | YES | Portfolio name |
| `组合简称` | VARCHAR | YES | Portfolio short name |
| `组合状态` | VARCHAR | YES | Portfolio status |
| `运作开始日` | DATE | YES | Operation start date |
| `组合类型` | VARCHAR | YES | Portfolio type |
| `子分类` | VARCHAR | YES | Sub-classification |
| `受托人` | VARCHAR | YES | Trustee |
| `是否存款组合` | SMALLINT | YES | Deposit portfolio flag |
| `是否外部组合` | SMALLINT | YES | External portfolio flag |
| `是否PK组合` | SMALLINT | YES | PK portfolio flag |
| `投资管理人` | VARCHAR | YES | Investment manager |
| `受托管理人` | VARCHAR | YES | Trust manager |
| `投资组合代码` | VARCHAR | YES | Investment portfolio code |
| `投资组合名称` | VARCHAR | YES | Investment portfolio name |
| `备注` | TEXT | YES | Notes |

**Constraints:**
- `FK_年金计划_组合计划` → `年金计划.年金计划号`

---

### 4.4 年金客户 (Annuity Customers)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | INTEGER | **NO** | Record ID |
| `company_id` | VARCHAR | **NO** | **PK** - Company ID |
| `客户名称` | VARCHAR | YES | Customer name |
| `年金客户标签` | VARCHAR | YES | **DEPRECATED** - Use `tags` column instead |
| `tags` | JSONB | YES | Customer tags array (default: `[]`). GIN indexed. |
| `年金客户类型` | VARCHAR | YES | Customer type |
| `年金计划类型` | VARCHAR | YES | Plan type |
| `关键年金计划` | VARCHAR | YES | Key plan |
| `主拓机构代码` | VARCHAR | YES | Primary institution code |
| `主拓机构` | VARCHAR | YES | Primary institution |
| `其他年金计划` | VARCHAR | YES | Other plans |
| `客户简称` | VARCHAR | YES | Customer short name |
| `更新时间` | DATE | YES | Update time |
| `最新受托规模` | DOUBLE | YES | Latest trustee scale |
| `最新投管规模` | DOUBLE | YES | Latest investment scale |
| `管理资格` | VARCHAR | YES | Management qualification |
| `规模区间` | VARCHAR | YES | Scale range |
| `计划层规模` | DOUBLE | YES | Plan-level scale |
| `年缴费规模` | DOUBLE | YES | Annual contribution |
| `外部受托规模` | DOUBLE | YES | External trustee scale |
| `上报受托规模` | DOUBLE | YES | Reported trustee scale |
| `上报投管规模` | DOUBLE | YES | Reported investment scale |
| `关联机构数` | INTEGER | YES | Related institutions count |
| `其他开拓机构` | VARCHAR | YES | Other development institutions |
| `计划状态` | VARCHAR | YES | Plan status |
| `关联计划数` | INTEGER | YES | Related plans count |
| `备注` | TEXT | YES | Notes |

---

### 4.5 产品线 (Product Lines)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `产品线` | VARCHAR | YES | Product line name |
| `产品类别` | VARCHAR | YES | Product category |
| `业务大类` | VARCHAR | YES | Business major category |
| `产品线代码` | VARCHAR | **NO** | **PK** - Product line code |
| `NO_产品线` | INTEGER | YES | Product line sequence |
| `NO_产品类别` | INTEGER | YES | Category sequence |

---

### 4.6 组织架构 (Organization Structure)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `机构` | VARCHAR | YES | Institution name |
| `年金中心` | VARCHAR | YES | Pension center |
| `战区` | VARCHAR | YES | Region/Zone |
| `机构代码` | VARCHAR | **NO** | **PK** - Institution code |
| `NO_机构` | INTEGER | YES | Institution sequence |
| `NO_年金中心` | INTEGER | YES | Center sequence |
| `NO_区域` | INTEGER | YES | Region sequence |
| `新架构` | VARCHAR | YES | New structure |
| `行政域` | VARCHAR | YES | Administrative domain |

---

### 4.7 计划层规模 (Plan Scale Classification)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `规模分类代码` | VARCHAR | **NO** | **PK** - Classification code |
| `规模分类` | VARCHAR | YES | Scale classification |
| `NO_规模分类` | INTEGER | YES | Classification sequence |
| `规模大类` | VARCHAR | YES | Scale major category |
| `NO_规模大类` | INTEGER | YES | Major category sequence |

---

## 5. Schema: public

**Purpose:** Pipeline infrastructure and migration tracking.

### 5.1 pipeline_executions

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `execution_id` | UUID | **NO** | **PK** - Execution identifier |
| `pipeline_name` | VARCHAR | **NO** | Pipeline name |
| `status` | VARCHAR | **NO** | Execution status |
| `started_at` | TIMESTAMPTZ | **NO** | Start time |
| `completed_at` | TIMESTAMPTZ | YES | Completion time |
| `input_file` | TEXT | YES | Input file path |
| `row_counts` | JSONB | YES | Row count statistics |
| `error_details` | TEXT | YES | Error information |
| `created_at` | TIMESTAMPTZ | **NO** | Record creation |
| `updated_at` | TIMESTAMPTZ | **NO** | Last update |

**Indexes:**
- `ix_pipeline_executions_pipeline_name` - Pipeline name lookup
- `ix_pipeline_executions_started_at` - Temporal queries

---

### 5.2 data_quality_metrics

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `metric_id` | UUID | **NO** | **PK** - Metric identifier |
| `execution_id` | UUID | **NO** | **FK** → pipeline_executions |
| `pipeline_name` | VARCHAR | **NO** | Pipeline name |
| `metric_type` | VARCHAR | **NO** | Metric type |
| `metric_value` | NUMERIC | YES | Metric value |
| `recorded_at` | TIMESTAMPTZ | **NO** | Recording time |
| `metadata` | JSONB | YES | Additional metadata |

**Constraints:**
- `data_quality_metrics_execution_id_fkey` → `pipeline_executions.execution_id`

---

### 5.3 alembic_version

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `version_num` | VARCHAR(32) | **NO** | **PK** - Migration version |

---

## 6. Schema: customer

**Purpose:** Customer lifecycle tracking - awards, losses, and aggregation views.

### 6.1 Table Summary

| Object | Type | Rows | Purpose |
|--------|------|------|---------|
| `当年中标` | Table | ~416 | Annual award records (23 months: 2024-02 to 2025-12) |
| `当年流失` | Table | ~241 | Annual loss records (23 months: 2024-02 to 2025-12) |
| `v_customer_business_monthly_status_by_type` | View | - | Pre-aggregated monthly status by business type |

---

### 6.2 v_customer_business_monthly_status_by_type (Aggregation View)

**Purpose:** Pre-aggregated view for BI analysis of award/loss patterns by business type.

**Source Tables:** `customer.当年中标`, `customer.当年流失`

| Column | Type | Description |
|--------|------|-------------|
| `上报月份` | DATE | Report month dimension |
| `业务类型` | VARCHAR | Business type (企年受托/企年投资) |
| `award_count` | BIGINT | Count of awards |
| `award_distinct_companies` | BIGINT | Distinct company_ids with awards (NULL excluded) |
| `loss_count` | BIGINT | Count of losses |
| `loss_distinct_companies` | BIGINT | Distinct company_ids with losses (NULL excluded) |
| `net_change` | BIGINT | award_count - loss_count |

**SQL Definition:**
```sql
CREATE VIEW customer.v_customer_business_monthly_status_by_type AS
WITH combined AS (
    SELECT "上报月份", "业务类型", company_id, 'award' AS record_type
    FROM customer."当年中标"
    UNION ALL
    SELECT "上报月份", "业务类型", company_id, 'loss' AS record_type
    FROM customer."当年流失"
)
SELECT
    "上报月份",
    "业务类型",
    COUNT(*) FILTER (WHERE record_type = 'award') AS award_count,
    COUNT(DISTINCT company_id) FILTER (WHERE record_type = 'award' AND company_id IS NOT NULL) AS award_distinct_companies,
    COUNT(*) FILTER (WHERE record_type = 'loss') AS loss_count,
    COUNT(DISTINCT company_id) FILTER (WHERE record_type = 'loss' AND company_id IS NOT NULL) AS loss_distinct_companies,
    COUNT(*) FILTER (WHERE record_type = 'award') - COUNT(*) FILTER (WHERE record_type = 'loss') AS net_change
FROM combined
GROUP BY "上报月份", "业务类型"
ORDER BY "上报月份" DESC, "业务类型";
```

**Usage Example:**
```sql
-- Get monthly status for all business types
SELECT * FROM customer.v_customer_business_monthly_status_by_type;

-- Filter by specific business type
SELECT * FROM customer.v_customer_business_monthly_status_by_type
WHERE "业务类型" = '企年受托';
```

---

## 7. Empty Schemas

| Schema | Purpose | Notes |
|--------|---------|-------|
| `finance` | Reserved for financial data | Future expansion |
| `system` | Reserved for system operations | Was planned for sync_state table |
| `wdh_dev` | Development/testing sandbox | Local development use |

---

## 8. Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ENTERPRISE SCHEMA                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────┐                                                 │
│  │     base_info       │ ←─────────────────────────────────────┐        │
│  │  PK: company_id     │                                        │        │
│  │  • EQC Master Data  │                                        │        │
│  │  • raw_data (JSONB) │                                        │        │
│  └──────────┬──────────┘                                        │        │
│             │ 1:N                                                │        │
│    ┌────────┴────────┐                                          │        │
│    │                 │                                          │        │
│    ▼                 ▼                                          │        │
│  ┌──────────────┐  ┌──────────────┐                             │        │
│  │business_info │  │  biz_label   │                             │        │
│  │FK:company_id │  │FK:company_id │                             │        │
│  │• 43 columns  │  │• 4-level     │                             │        │
│  │• Cleansed    │  │  hierarchy   │                             │        │
│  └──────────────┘  └──────────────┘                             │        │
│                                                                  │        │
│  ┌─────────────────────┐      ┌─────────────────────┐           │        │
│  │  enrichment_index   │      │enrichment_requests  │           │        │
│  │  (Layer 2 Cache)    │      │  (Async Queue)      │           │        │
│  │  • lookup_key       │      │  • raw_name         │           │        │
│  │  • lookup_type      │      │  • status           │           │        │
│  │  • company_id ──────┼──────┼──→ resolved_company_id          │        │
│  └─────────────────────┘      └─────────────────────┘           │        │
│                                                                  │        │
└──────────────────────────────────────────────────────────────────┘        │
                                                                             │
                                          Enriched company_id ───────────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          BUSINESS SCHEMA                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                          规模明细                                 │    │
│  │  PK: id                                                          │    │
│  │  • 月度 (NOT NULL)                                               │    │
│  │  • 计划代码 (NOT NULL)                                           │    │
│  │  • company_id (NOT NULL) ←── Enriched from enterprise.base_info  │    │
│  │  • Financial metrics (供款, 流失, 投资收益, etc.)                 │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          MAPPING SCHEMA                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐                   │
│  │      年金计划        │◄─────│      组合计划        │                   │
│  │  PK: 年金计划号      │ 1:N  │  PK: 组合代码        │                   │
│  │  • company_id       │      │  FK: 年金计划号      │                   │
│  │  • 客户名称          │      │  • 组合名称          │                   │
│  └─────────────────────┘      └─────────────────────┘                   │
│           │                                                               │
│           │ N:1                                                           │
│           ▼                                                               │
│  ┌─────────────────────┐      ┌─────────────────────┐                   │
│  │      年金客户        │      │      产品线          │                   │
│  │  PK: company_id     │      │  PK: 产品线代码      │                   │
│  │  • 客户名称          │      │  • 业务大类          │                   │
│  │  • 最新受托规模      │      └─────────────────────┘                   │
│  └─────────────────────┘                                                 │
│                                                                           │
│  ┌─────────────────────┐      ┌─────────────────────┐                   │
│  │      组织架构        │      │     计划层规模       │                   │
│  │  PK: 机构代码        │      │  PK: 规模分类代码    │                   │
│  │  • 年金中心          │      │  • 规模分类          │                   │
│  └─────────────────────┘      └─────────────────────┘                   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Data Flow Architecture

### 9.1 ETL Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ETL Pipeline Flow                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  [1. File Discovery]                                                      │
│       │                                                                   │
│       ▼                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│  │   BRONZE    │────▶│   SILVER    │────▶│    GOLD     │                │
│  │  (Raw Data) │     │ (Validated) │     │ (Enriched)  │                │
│  └─────────────┘     └─────────────┘     └─────────────┘                │
│       │                    │                    │                        │
│  • Read Excel         • Pydantic          • Company ID                   │
│  • Column mapping       validation          enrichment                   │
│  • Type coercion      • Business rules    • FK backfill                  │
│  • Null handling      • Cleansing         • Final validation             │
│                                                                           │
│                              │                                            │
│                              ▼                                            │
│                     ┌─────────────────┐                                  │
│                     │  PostgreSQL DB  │                                  │
│                     │ business.规模明细│                                  │
│                     └─────────────────┘                                  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Company Enrichment Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Company Enrichment Resolution (5 Layers)               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Input: 客户名称 / 计划代码 / 年金账户号                                  │
│       │                                                                   │
│       ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    LAYER 1: YAML Config                      │        │
│  │  config/company_mapping.yml (hardcoded mappings)             │        │
│  └─────────────────────────────────────────────────────────────┘        │
│       │ Miss                                                             │
│       ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    LAYER 2: DB Cache                         │        │
│  │  enterprise.enrichment_index (5 lookup types)                │        │
│  │  Priority: plan_code > account_name > account_number >       │        │
│  │            customer_name > plan_customer                     │        │
│  └─────────────────────────────────────────────────────────────┘        │
│       │ Miss                                                             │
│       ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    LAYER 3: Existing Column                  │        │
│  │  Check if company_id already present in source data          │        │
│  └─────────────────────────────────────────────────────────────┘        │
│       │ Miss                                                             │
│       ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    LAYER 4: EQC API                          │        │
│  │  Synchronous lookup with budget control                      │        │
│  │  → Stores result in enterprise.base_info                     │        │
│  │  → Caches in enterprise.enrichment_index                     │        │
│  └─────────────────────────────────────────────────────────────┘        │
│       │ Miss                                                             │
│       ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐        │
│  │                    LAYER 5: Temp ID                          │        │
│  │  Generate HMAC-based temporary ID (INxxx format)             │        │
│  │  → Queue for async enrichment                                │        │
│  └─────────────────────────────────────────────────────────────┘        │
│       │                                                                   │
│       ▼                                                                   │
│  Output: company_id (resolved or temporary)                              │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix

### A. Configuration Files

| File | Purpose |
|------|---------|
| `config/data_sources.yml` | Domain file discovery patterns |
| `config/foreign_keys.yml` | FK backfill configuration |
| `config/reference_sync.yml` | Reference data sync settings |
| `config/company_mapping.yml` | Layer 1 hardcoded mappings |

### B. Domain Registry

**Location:** `src/work_data_hub/infrastructure/schema/`

| Domain | Schema | Table | Primary Key |
|--------|--------|-------|-------------|
| `annuity_performance` | business | 规模明细 | id |

### C. Deprecated Tables (Zero Legacy)

| Table | Status | Replacement | Notes |
|-------|--------|-------------|-------|
| `enterprise.company_mapping` | ❌ DEPRECATED | `enterprise.enrichment_index` | Epic 7.1-4 删除任务 |

### D. Glossary

| Term | Definition |
|------|------------|
| **EQC** | Enterprise Query Client - External API for company data |
| **Bronze Layer** | Raw data with minimal validation |
| **Silver Layer** | Validated and cleansed data |
| **Gold Layer** | Enriched data ready for business use |
| **Enrichment** | Process of resolving company_id from customer names |
| **Backfill** | Auto-derivation of reference data from domain tables |

### E. Environment Configuration

数据库连接通过 `.wdh_env` 文件配置：

```bash
# .wdh_env 文件
# 主数据库 (postgres) - ETL 输出目标
DATABASE_URL=postgresql://postgres:Post.169828@localhost:5432/postgres

# Legacy 数据库 (只读) - 历史数据源
WDH_LEGACY_PG_HOST=localhost
WDH_LEGACY_PG_PORT=5432
WDH_LEGACY_PG_DATABASE=legacy
WDH_LEGACY_PG_USER=postgres
WDH_LEGACY_PG_PASSWORD=Post.169828
```

**使用方式：**
```bash
uv run --env-file .wdh_env python -m work_data_hub.cli.etl --check-db
```

---

**Document End**
