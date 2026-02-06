---
title: '年金客户表 Schema 迁移 (mapping → customer)'
slug: 'annuity-customer-schema-migration'
created: '2026-01-17'
status: 'implementation-complete'
stepsCompleted: [1, 2, 3, 4]
tech_stack:
  - Alembic
  - PostgreSQL
  - Python
files_to_modify:
  - io/schema/migrations/versions/001_initial_infrastructure.py
  - io/schema/migrations/versions/003_seed_static_data.py
  - io/schema/migrations/versions/007_add_customer_tags_jsonb.py
  - config/foreign_keys.yml
  - config/data_sources.yml
  - docs/project-planning-artifacts/sprint-change-proposal-2026-01-10.md
  - docs/database-schema-panorama.md
  - docs/specific/customer-mdm/customer-plan-contract-specification.md
  - docs/specific/customer-mdm/customer-monthly-snapshot-specification.md
files_created:
  - scripts/migrations/migrate_annuity_customer_to_customer_schema.sql
  - scripts/migrations/rollback_annuity_customer_migration.sql
code_patterns:
  - Idempotent migration (IF NOT EXISTS)
  - Schema-qualified table references
  - Raw SQL execution via conn.execute(sa.text(...))
test_patterns:
  - ETL integration test via CLI
adversarial_review:
  performed: true
  findings_resolved: [F1, F3, F5, F6, F7, F9, F10]
  findings_invalid: [F2, F4, F8]
---

# Tech-Spec: 年金客户表 Schema 迁移 (mapping → customer)

**Created:** 2026-01-17

## Overview

### Problem Statement

`年金客户` 表目前位于 `mapping` schema 中，但作为 Customer MDM（主数据管理）的核心客户维度表，应该归属于 `customer` schema 以保持架构一致性。当前 `customer` schema 已包含 `当年中标` 和 `当年流失` 表，它们都引用 `年金客户.company_id` 作为外键。

### Solution

1. 修改 Alembic 迁移脚本，将 `年金客户` 表创建在 `customer` schema
2. 更新 `config/foreign_keys.yml` 中的 FK 回填配置
3. 在 `mapping` schema 中创建指向 `customer."年金客户"` 的兼容性视图
4. 提供 SQL 脚本用于同步修改现有数据库

### Scope

**In Scope:**
- 修改 4 个 Alembic 迁移脚本和配置文件
- 创建 `mapping."年金客户"` 兼容性视图
- 提供现有数据库同步 SQL 脚本
- ETL 验证运行
- **更新相关技术文档** (4个文档，见 Task 5.5-5.7)

**Out of Scope:**
- 表结构变更（所有列定义保持不变）
- 新功能开发
- BI 层查询更新（兼容性视图已覆盖）

## Context for Development

### Codebase Patterns

- **Idempotent Migrations**: 使用 `IF NOT EXISTS` / `DO $$ BEGIN ... END $$` 模式
- **Schema-Qualified References**: 所有表引用使用 `schema."表名"` 格式
- **Raw SQL Execution**: `conn.execute(sa.text("..."))`
- **FK Backfill**: 使用 `target_schema` + `target_table` 直接写入目标表（不通过视图）

### Files to Reference

| File | Purpose | Search Pattern |
| ---- | ------- | -------------- |
| `001_initial_infrastructure.py` | 基础设施表定义 | 搜索 `# === 14. 年金客户` |
| `003_seed_static_data.py` | 种子数据加载 | 搜索 `年金客户` |
| `007_add_customer_tags_jsonb.py` | Tags JSONB 列 | 全文替换 `mapping` → `customer` |
| `004_create_annual_award.py` | `customer` schema 创建参考 | 搜索 `CREATE SCHEMA` |
| `config/foreign_keys.yml` | FK 回填配置 | 搜索 `fk_customer` |
| `sprint-change-proposal-2026-01-10.md` | Customer MDM 开发文档 | 搜索 `mapping.*年金客户` |

### Technical Decisions

1. **兼容性视图策略**: 在 `mapping` schema 创建只读视图，确保 BI 查询向后兼容
2. **无新增迁移脚本**: 直接修改现有迁移脚本以保持迁移链整洁
3. **SQL 同步脚本**: 提供独立 SQL 用于现有数据库迁移（包含事务保护）
4. **FK 回填验证**: 回填逻辑直接写入 `customer."年金客户"`，不受视图影响

---

## Implementation Plan

### Tasks

#### Task 1: 修改 001_initial_infrastructure.py - 表定义

**File:** `io/schema/migrations/versions/001_initial_infrastructure.py`

**Actions:**
- [ ] 1.1 在 `upgrade()` 函数中，**在 MAPPING SCHEMA 区域之前**添加 CUSTOMER SCHEMA 区域：
  ```python
  # ========================================================================
  # CUSTOMER SCHEMA (1 table: 年金客户)
  # ========================================================================
  conn.execute(sa.text("CREATE SCHEMA IF NOT EXISTS customer"))
  ```
- [ ] 1.2 将 `年金客户` 表创建代码移动到 CUSTOMER SCHEMA 区域
- [ ] 1.3 修改 `op.create_table()` 的 `schema="mapping"` → `schema="customer"`
- [ ] 1.4 修改主键约束名 `name="年金客户_pkey"` 保持不变（或改为 `customer_年金客户_pkey`）
- [ ] 1.5 在原 MAPPING SCHEMA 区域位置添加兼容性视图：
  ```python
  # === 14. 年金客户 兼容性视图 ===
  conn.execute(sa.text('''
      CREATE OR REPLACE VIEW mapping."年金客户" AS
      SELECT * FROM customer."年金客户"
  '''))
  ```
- [ ] 1.6 更新 `downgrade()` 函数：
  ```python
  # 先删除视图
  conn.execute(sa.text('DROP VIEW IF EXISTS mapping."年金客户"'))
  # 再删除表
  if _table_exists(conn, "年金客户", "customer"):
      op.drop_table("年金客户", schema="customer")
  ```

---

#### Task 2: 修改 003_seed_static_data.py - 种子数据加载

**File:** `io/schema/migrations/versions/003_seed_static_data.py`

**Actions:**
- [ ] 2.1 搜索 `年金客户` 并修改 `upgrade()` 中的引用：
  - `_table_exists(conn, "年金客户", "mapping")` → `"customer"`
  - `_load_csv_seed_data(..., "mapping")` → `"customer"`
  - print 语句中的 `mapping.年金客户` → `customer.年金客户`
- [ ] 2.2 搜索 `downgrade()` 中的 `("年金客户", "mapping")` 并修改为 `("年金客户", "customer")`

---

#### Task 3: 修改 007_add_customer_tags_jsonb.py - Tags 列迁移

**File:** `io/schema/migrations/versions/007_add_customer_tags_jsonb.py`

**Actions:**
- [ ] 3.1 全文替换（使用 replace_all）：
  - `mapping."年金客户"` → `customer."年金客户"`
  - `table_schema = 'mapping'` → `table_schema = 'customer'`
  - `mapping.idx_年金客户_tags_gin` → `customer.idx_年金客户_tags_gin`
- [ ] 3.2 更新 docstring 中的 schema 引用

---

#### Task 4: 修改 config/foreign_keys.yml - FK 回填配置

**File:** `config/foreign_keys.yml`

**Actions:**
- [ ] 4.1 搜索 `name: "fk_customer"` 并修改其下的 `target_schema`:
  - `annuity_performance` 域: `target_schema: "mapping"` → `target_schema: "customer"`
  - `annuity_income` 域: `target_schema: "mapping"` → `target_schema: "customer"`

---

#### Task 5: 更新 sprint-change-proposal 实施提案

**File:** `docs/project-planning-artifacts/sprint-change-proposal-2026-01-10.md`

> **重要说明**: 此文档是**未完成的实施提案**，必须同步更新以确保后续实施计划正常进行。

**Actions (14 处引用):**
- [ ] 5.1 Line 25: `mapping."年金客户"` → `customer."年金客户"` (Discovery Context)
- [ ] 5.2 Lines 145, 150, 153, 160: Story 7.4 SQL 示例中的 `mapping."年金客户"` → `customer."年金客户"`
- [ ] 5.3 Line 273: FK 约束 `REFERENCES mapping.年金客户` → `REFERENCES customer.年金客户`
- [ ] 5.4 Lines 450-455: Mermaid ERD 中 `mapping_年金客户` → `customer_年金客户`
- [ ] 5.5 Lines 504, 508: Mermaid 关系定义 `mapping_年金客户` → `customer_年金客户`
- [ ] 5.6 Lines 517, 520: 外键关系表中 `mapping."年金客户"` → `customer."年金客户"`
- [ ] 5.7 Lines 553, 562: 数据流图中 `mapping.年金客户` → `customer.年金客户`
- [ ] 5.8 Lines 593, 629: Success Criteria 和 Checklist 中的引用更新

---

#### Task 5.5: 更新 database-schema-panorama.md - 数据库全景图

**File:** `docs/database-schema-panorama.md`

**优先级**: **P0** - 必须更新，反映当前 schema 真相

**Actions:**
- [ ] 5.5.1 Line 63: Schema summary table 更新
  - `mapping` tables: 6 → 5 (1 view for compatibility)
  - `customer` objects: 3 → 4 (新增 `年金客户` 表)
- [ ] 5.5.2 Line 84: Section 1.3 Legacy Database 中的描述
  - `年金计划, 组合计划, 年金客户` → `年金计划, 组合计划`
  - 添加注释: `年金客户已迁移至 customer schema，mapping 保留兼容性视图`
- [ ] 5.5.3 Section 4.1 Table Summary (line 481)
  - 移除 `年金客户` from mapping schema tables
- [ ] 5.5.4 Section 4.4 年金客户 (lines 537-568)
  - **整个 section 移至 customer schema 部分** (作为新的 section 6.4)
- [ ] 5.5.5 Section 6 Schema: customer (line 662)
  - Table Summary 更新: 3 objects → 4 objects (新增 `年金客户` 表)
  - 添加新的 6.4 `年金客户` 表说明 (从 mapping schema 移入)
- [ ] 5.5.6 Section 8 Entity Relationships (line 737)
  - 更新 ERD 图，将 `年金客户` 归属到 customer schema

**参考变更**:
```markdown
### 6.4 年金客户 (Annuity Customers)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `company_id` | VARCHAR | **NO** | **PK** - Company ID |
| `客户名称` | VARCHAR | YES | Customer name |
| `tags` | JSONB | YES | Customer tags array (default: `[]`). GIN indexed. |
| ... (其余列保持不变)

**Note**: 原 `mapping."年金客户"` 表已迁移至此，mapping schema 保留兼容性视图。
```

---

#### Task 5.6: 更新 customer-plan-contract-specification.md - 合约表规格

**File:** `docs/specific/customer-mdm/customer-plan-contract-specification.md`

**优先级**: **P0** - 必须更新，FK 约束正确性

**Actions:**
- [ ] 5.6.1 Line 65: 数据分层架构图
  - `mapping."年金客户"` → `customer."年金客户"`
- [ ] 5.6.2 Line 112: DDL 中的 FK 约束
  - `REFERENCES mapping."年金客户"(company_id)` → `REFERENCES customer."年金客户"(company_id)`
- [ ] 5.6.3 Line 138: 数据来源表中的 `mapping."产品线"` **保持不变** (产品线仍在 mapping schema)
- [ ] 5.6.4 Line 173: 依赖表清单
  - `mapping."年金客户"` → `customer."年金客户"`
- [ ] 5.6.5 Line 188: 数据完整性规则
  - `mapping."年金客户"` → `customer."年金客户"`
- [ ] 5.6.6 Line 273: SQL 示例中的外键约束
  - `REFERENCES mapping."年金客户"` → `REFERENCES customer."年金客户"`
- [ ] 5.6.7 Line 315: 业务主键说明
  - `mapping."产品线"` **保持不变**

---

#### Task 5.7: 更新 customer-monthly-snapshot-specification.md - 快照表规格

**File:** `docs/specific/customer-mdm/customer-monthly-snapshot-specification.md`

**优先级**: **P0** - 必须更新，FK 约束正确性

**Actions:**
- [ ] 5.7.1 Line 103: DDL 中的 FK 约束
  - `REFERENCES mapping."年金客户"(company_id)` → `REFERENCES customer."年金客户"(company_id)`
- [ ] 5.7.2 Line 138: 数据来源中的 `mapping."产品线"` **保持不变**
- [ ] 5.7.3 Line 232: SQL 中的 `LEFT JOIN mapping."产品线"` **保持不变**

---

#### Task 6: 创建数据库同步 SQL 脚本

**Output:** `scripts/migrations/migrate_annuity_customer_to_customer_schema.sql`

**SQL Operations (含事务保护):**
```sql
-- ============================================================
-- 年金客户表 Schema 迁移脚本
-- From: mapping."年金客户" → To: customer."年金客户"
-- Date: 2026-01-17
-- ============================================================

-- 预检查：记录迁移前行数
DO $$
DECLARE
    row_count_before INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count_before FROM mapping."年金客户";
    RAISE NOTICE '迁移前行数: %', row_count_before;
END $$;

BEGIN;

-- Step 1: 确保 customer schema 存在
CREATE SCHEMA IF NOT EXISTS customer;

-- Step 2: 将表从 mapping 移动到 customer schema
ALTER TABLE mapping."年金客户" SET SCHEMA customer;

-- Step 3: 在 mapping schema 创建兼容性视图
CREATE OR REPLACE VIEW mapping."年金客户" AS
SELECT * FROM customer."年金客户";

COMMIT;

-- 后检查：验证迁移结果
DO $$
DECLARE
    row_count_after INTEGER;
    table_schema_result TEXT;
BEGIN
    -- 验证表位置
    SELECT schemaname INTO table_schema_result
    FROM pg_tables WHERE tablename = '年金客户' AND schemaname = 'customer';

    IF table_schema_result IS NULL THEN
        RAISE EXCEPTION '迁移失败: 表未在 customer schema 中找到';
    END IF;

    -- 验证行数
    SELECT COUNT(*) INTO row_count_after FROM customer."年金客户";
    RAISE NOTICE '迁移后行数: %', row_count_after;
    RAISE NOTICE '迁移成功！表现在位于 customer schema';
END $$;

-- 验证视图
SELECT schemaname, viewname FROM pg_views WHERE viewname = '年金客户';
```

**回滚脚本** (`scripts/migrations/rollback_annuity_customer_migration.sql`):
```sql
-- 回滚脚本
BEGIN;

-- 删除视图
DROP VIEW IF EXISTS mapping."年金客户";

-- 将表移回 mapping schema
ALTER TABLE customer."年金客户" SET SCHEMA mapping;

COMMIT;

-- 验证回滚
SELECT schemaname, tablename FROM pg_tables WHERE tablename = '年金客户';
```

---

#### Task 6: ETL 验证

**Command:**
```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains --period 202510 --file-selection newest --execute --no-enrichment
```

**Expected Result:** ETL 完成无错误，FK 回填数据写入 `customer."年金客户"`

**验证查询:**
```sql
-- 确认新数据写入 customer schema
SELECT COUNT(*) FROM customer."年金客户";

-- 确认视图可读
SELECT COUNT(*) FROM mapping."年金客户";

-- 确认两者一致
SELECT
    (SELECT COUNT(*) FROM customer."年金客户") =
    (SELECT COUNT(*) FROM mapping."年金客户") AS counts_match;
```

---

## Acceptance Criteria

- [ ] **AC-1**: Given 新环境执行 Alembic 迁移链，When `001_initial_infrastructure.py` upgrade() 执行完成，Then `年金客户` 表存在于 `customer` schema 且 `mapping."年金客户"` 视图正确指向它

- [ ] **AC-2**: Given 现有数据库执行同步 SQL 脚本，When 脚本执行完成，Then 迁移前后行数一致，表位于 `customer` schema

- [ ] **AC-3**: Given 修改后的 FK 配置，When 运行 annuity_performance ETL with FK backfill，Then 新客户数据正确写入 `customer."年金客户"`

- [ ] **AC-4**: Given 存在使用 `mapping."年金客户"` 的查询，When 执行 SELECT 查询，Then 视图透明返回 `customer."年金客户"` 数据

- [ ] **AC-5**: Given 完成所有修改，When 执行 `--all-domains` ETL 命令，Then 无错误完成

---

## Additional Context

### Dependencies

| Dependency | Required By | Notes |
|------------|-------------|-------|
| `customer` schema | Task 1 | **必须在 001 中显式创建**（解决 F1） |

### Migration Execution Order

新环境部署时 Alembic 迁移链顺序：
1. `001_initial_infrastructure.py` - **创建 `customer` schema** + 创建 `customer."年金客户"` 表 + `mapping."年金客户"` 视图
2. `002_initial_domains.py` - 业务表
3. `003_seed_static_data.py` - 种子数据加载到 `customer."年金客户"`
4. `004_create_annual_award.py` - 创建 `customer` schema（幂等，已存在）
5. `005_create_annual_loss.py`
6. `006_create_business_type_view.py`
7. `007_add_customer_tags_jsonb.py` - 为 `customer."年金客户"` 添加 tags 列

### Testing Strategy

1. **集成测试**: 运行完整 ETL 命令验证端到端流程
2. **回归测试**: 确保现有 FK 回填逻辑正常工作
3. **视图验证**: 执行 `SELECT * FROM mapping."年金客户" LIMIT 1` 确认视图工作
4. **回滚测试**: 执行回滚脚本并验证表恢复到 mapping schema

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| 生产数据库迁移失败 | SQL 脚本包含事务保护和行数验证；提供回滚脚本 |
| 迁移链顺序问题 | `customer` schema 在 `001` 中创建，早于所有依赖 |
| BI 查询中断 | 兼容性视图确保 `mapping."年金客户"` SELECT 查询继续工作 |
| 数据丢失 | 迁移前后行数校验 |

### Notes

- 现有生产数据库需要手动执行 Task 6 的 SQL 同步脚本
- 修改后的迁移脚本适用于新环境部署
- **兼容性视图是只读的**：所有 INSERT/UPDATE/DELETE 必须直接针对 `customer."年金客户"`
- **技术文档必须同步更新**：`sprint-change-proposal-2026-01-10.md` 是未完成的实施提案，必须更新以确保后续实施计划正常进行。其他技术规格文档（database-schema-panorama.md 等）也需同步更新以反映 schema 变更。

### Future Considerations (F10)

未来迁移脚本（如 `008_create_customer_plan_contract.py`、`009_create_fct_customer_monthly_status.py`）在实现时应直接引用 `customer."年金客户"`，而非 `mapping."年金客户"`。
