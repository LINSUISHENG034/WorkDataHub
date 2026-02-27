# 实施计划: 全量重建数据库 + Alembic 迁移脚本整合

> **来源**: `customer-schema-rename-implementation-plan.md` (代码层已实施完毕)
> **日期**: 2026-02-26
> **目标**: 整合冗余迁移脚本, 全量重建数据库以验证 Alembic 链的正确性
> **数据库**: `postgres://localhost:5432/postgres` (schema: `customer`)

---

## 现状分析

### 代码 vs 数据库 差异对照

| # | 代码期望名称 | 数据库当前名称 | 类型 |
|---|-------------|--------------|------|
| T1 | `客户年金计划` | `customer_plan_contract` | 表 |
| T2 | `客户业务月度快照` | `fct_customer_product_line_monthly` | 表 |
| T3 | `客户计划月度快照` | `fct_customer_plan_monthly` | 表 |
| T4 | `中标客户明细` | `当年中标` | 表 |
| T5 | `流失客户明细` | `当年流失` | 表 |
| T6 | `客户明细` | `年金关联公司` | 表 |

### 当前 Alembic 迁移链 (13 个文件)

```
001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009 → 010 → 011 → 012 → 013
```

- **Alembic 版本**: `20260205_000012` (migration 013 尚未应用到数据库)
- **007** (`add_customer_tags_jsonb`): 给 `客户明细` 加 `tags JSONB` 列 + GIN 索引 + 数据迁移
- **012** (`fix_contract_unique_constraint`): 修复 `客户年金计划` 唯一约束 (valid_to → valid_from)

这两个迁移属于对前序迁移的"补丁", 在全量重建场景下可直接整合到源头。

---

## Step 1: 整合迁移脚本

### 1.1 整合 007 → 001 + 003

**007 做了 4 件事:**

1. 给 `客户明细` 加 `tags JSONB DEFAULT '[]'` 列
2. 从 `年金客户标签` 迁移数据到 `tags`
3. 创建 GIN 索引 `idx_customer_detail_tags_gin`
4. 给旧列加 DEPRECATED 注释

**整合方案:**

| 原 007 内容 | 整合目标 | 原因 |
|------------|---------|------|
| `tags JSONB` 列定义 | → **001** CREATE TABLE | 列应从建表时就存在 |
| GIN 索引 | → **001** CREATE TABLE 后 | 索引随表创建 |
| 数据迁移 (年金客户标签→tags) | → **003** seed 之后 | 必须在 CSV 数据导入后执行 |
| DEPRECATED 注释 | → **003** seed 之后 | 随数据迁移一起 |

#### 修改 001: 在 `客户明细` CREATE TABLE 中加入 tags 列

在 `001_initial_infrastructure.py` 第 617 行 (`sa.Column("其他开拓机构"...)`) 之后, `sa.Column("计划状态"...)` 之前, 添加:

```python
sa.Column("tags", sa.JSON(), nullable=True, server_default=sa.text("'[]'::jsonb")),
```

并在 CREATE TABLE 之后 (约第 636 行后) 添加 GIN 索引:

```python
# GIN index for tags JSONB queries
conn.execute(sa.text('''
    CREATE INDEX IF NOT EXISTS idx_customer_detail_tags_gin
    ON customer."客户明细" USING GIN (tags)
'''))
```

#### 修改 003: 在 seed `客户明细` 之后添加数据迁移

在 `003_seed_static_data.py` 第 380 行 (`print(f"Seeded {count} rows into customer.客户明细")`) 之后添加:

```python
# Migrate 年金客户标签 → tags JSONB (consolidated from 007)
conn.execute(sa.text("""
    UPDATE customer."客户明细"
    SET tags = CASE
        WHEN "年金客户标签" IS NULL OR "年金客户标签" = '' THEN '[]'::jsonb
        ELSE jsonb_build_array("年金客户标签")
    END
"""))
conn.execute(sa.text("""
    COMMENT ON COLUMN customer."客户明细"."年金客户标签"
    IS 'DEPRECATED: Use tags JSONB column instead'
"""))
print("  Migrated 年金客户标签 → tags JSONB")
```

### 1.2 整合 012 → 008

**012 做了 3 件事:**

1. 删除旧约束 `uq_active_contract`
2. 去重 (按 valid_from 分区, 保留最新 valid_to)
3. 创建新约束 `uq_contract_version (company_id, plan_code, product_line_code, valid_from)`

**整合方案:** 直接修改 008 的 CREATE TABLE, 将约束从 `valid_to` 改为 `valid_from`, 同时更新约束名称。

#### 修改 008: 替换唯一约束定义

在 `008_create_customer_plan_contract.py` 第 73-75 行, 将:

```sql
CONSTRAINT uq_active_contract UNIQUE (
    company_id, plan_code, product_line_code, valid_to
)
```

替换为:

```sql
CONSTRAINT uq_contract_version UNIQUE (
    company_id, plan_code, product_line_code, valid_from
)
```

> **注意**: 012 中的去重逻辑 (DELETE ... ROW_NUMBER) 在全量重建场景下不需要, 因为表是空的。

---

## Step 2: 文件重编号 + 修订链修复

删除 007 和 012 后, 将后续文件重新编号为连续序列 001-011。

### 2.1 文件重命名映射

| 原文件名 | 新文件名 | 变更 |
|---------|---------|------|
| `001_initial_infrastructure.py` | 不变 | 内容修改 (加 tags 列) |
| `002_initial_domains.py` | 不变 | — |
| `003_seed_static_data.py` | 不变 | 内容修改 (加数据迁移) |
| `004_create_annual_award.py` | 不变 | — |
| `005_create_annual_loss.py` | 不变 | — |
| `006_create_business_type_view.py` | 不变 | — |
| ~~`007_add_customer_tags_jsonb.py`~~ | **删除** | 已整合到 001+003 |
| `008_create_customer_plan_contract.py` | → `007_create_customer_plan_contract.py` | 内容修改 (约束 + revision) |
| `009_create_fct_customer_monthly_status.py` | → `008_create_fct_customer_monthly_status.py` | revision 修改 |
| `010_create_bi_star_schema.py` | → `009_create_bi_star_schema.py` | revision 修改 |
| `011_create_sync_product_line_trigger.py` | → `010_create_sync_product_line_trigger.py` | revision 修改 |
| ~~`012_fix_contract_unique_constraint.py`~~ | **删除** | 已整合到 007(原008) |
| `013_create_fct_customer_plan_monthly.py` | → `011_create_fct_customer_plan_monthly.py` | revision 修改 |

### 2.2 修订链更新

整合后的链: `001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009 → 010 → 011`

需要修改 `revision` / `down_revision` 的文件:

| 新文件 | revision | down_revision | 变更说明 |
|--------|----------|---------------|---------|
| 007 (原008) | `20260118_000007` | `20260115_000006` | revision 编号改 007, down 跳过已删除的 007 指向 006 |
| 008 (原009) | `20260121_000008` | `20260118_000007` | 编号改 008, down 指向新 007 |
| 009 (原010) | `20260129_000009` | `20260121_000008` | 编号改 009, down 指向新 008 |
| 010 (原011) | `20260129_000010` | `20260129_000009` | 编号改 010, down 指向新 009 |
| 011 (原013) | `20260209_000011` | `20260129_000010` | 编号改 011, down 跳过已删除的 012 指向新 010 |

---

## Step 3: 全量重建数据库

### 3.1 前置条件

- [ ] Step 1 的代码修改已完成 (001, 003, 008 内容整合)
- [ ] Step 2 的文件重命名已完成 (007/012 删除, 后续文件重编号)
- [ ] 修订链 `alembic check` 通过
- [ ] 确认本地数据库无需保留的业务数据

### 3.2 清理现有 Schema

```sql
-- 连接到 postgres 数据库
-- ⚠️ 这会删除 customer 和 bi schema 下的所有数据

DROP SCHEMA IF EXISTS customer CASCADE;
DROP SCHEMA IF EXISTS bi CASCADE;

-- 清理 alembic 版本记录
DELETE FROM public.alembic_version;
```

### 3.3 执行全量迁移

```bash
cd E:/Projects/WorkDataHub
PYTHONPATH=src uv run alembic upgrade head
```

预期输出: 11 个迁移依次执行, 无报错。

---

## Step 4: 验证

### 4.1 Alembic 版本验证

```sql
SELECT * FROM public.alembic_version;
-- 预期: version_num = '20260209_000011'
```

### 4.2 表名验证

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'customer'
ORDER BY table_name;
```

预期结果 (6 张表):

| table_name |
|------------|
| 中标客户明细 |
| 客户业务月度快照 |
| 客户年金计划 |
| 客户明细 |
| 客户计划月度快照 |
| 流失客户明细 |

### 4.3 整合项验证

```sql
-- 验证 tags 列存在且有 GIN 索引
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema = 'customer'
  AND table_name = '客户明细'
  AND column_name = 'tags';
-- 预期: tags | jsonb | '[]'::jsonb

-- 验证 GIN 索引
SELECT indexname FROM pg_indexes
WHERE schemaname = 'customer'
  AND tablename = '客户明细'
  AND indexname = 'idx_customer_detail_tags_gin';
-- 预期: 1 行

-- 验证 客户年金计划 唯一约束 (valid_from, 非 valid_to)
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'customer."客户年金计划"'::regclass
  AND contype = 'u';
-- 预期: uq_contract_version | UNIQUE (company_id, plan_code, product_line_code, valid_from)
```

### 4.4 触发器验证

```sql
SELECT trigger_name, event_object_table, action_timing, event_manipulation
FROM information_schema.triggers
WHERE trigger_schema = 'customer'
ORDER BY event_object_table, trigger_name;
```

预期: 应包含以下触发器 (共 7 个 customer schema 触发器):

| trigger_name | event_object_table |
|-------------|-------------------|
| trg_sync_contract_customer_name | 客户明细 |
| update_annual_award_timestamp | 中标客户明细 |
| update_annual_loss_timestamp | 流失客户明细 |
| update_customer_plan_contract_timestamp | 客户年金计划 |
| update_fct_customer_monthly_status_timestamp | 客户业务月度快照 |
| update_fct_customer_plan_monthly_timestamp | 客户计划月度快照 |
| sync_product_line_name_to_snapshots | 客户业务月度快照 |

### 4.5 Seed 数据验证

```sql
-- 验证关键表的行数
SELECT '客户明细' AS table_name, COUNT(*) FROM customer."客户明细"
UNION ALL
SELECT '产品线', COUNT(*) FROM mapping."产品线"
UNION ALL
SELECT '年金计划', COUNT(*) FROM mapping."年金计划"
UNION ALL
SELECT '组合计划', COUNT(*) FROM mapping."组合计划";
```

预期:

| table_name | count |
|-----------|-------|
| 客户明细 | ~985 |
| 产品线 | 12 |
| 年金计划 | ~1,128 |
| 组合计划 | ~1,315 |

```sql
-- 验证 tags 数据迁移
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE tags != '[]'::jsonb) AS has_tags
FROM customer."客户明细";
-- 预期: has_tags > 0 (原 年金客户标签 非空的行)
```

---

## Step 5: 修复现有测试断言

整合迁移脚本后, 以下现有测试会因硬编码值失效, 必须同步修复。

### 5.1 修复 `test_migrations.py:26` — alembic_version 断言过时

**文件**: `tests/io/schema/test_migrations.py`

当前断言:

```python
assert revision == "20251228_000003"  # 003_seed_static_data (head of new chain)
```

fixture `postgres_db_with_migrations` 调用 `migration_runner.upgrade()` 升级到 HEAD,
但断言仍停留在 003。整合后 HEAD 为 `20260209_000011`。

**修复**: 将 `"20251228_000003"` 替换为 `"20260209_000011"`。

### 5.2 修复 `test_enterprise_schema_migration.py:372` — 客户明细列数 27→28

**文件**: `tests/integration/migrations/test_enterprise_schema_migration.py`

整合后 001 的 `客户明细` CREATE TABLE 新增 `tags JSONB` 列, 总列数从 27 变为 28。

**修复 (2 处)**:

1. 第 354 行注释: `# Expected 27 columns` → `# Expected 28 columns`
2. 第 372 行断言: `len(columns) == 27` → `len(columns) == 28`
3. 第 355-371 行 `expected_columns` 集合中加入 `"tags"`

---

## Step 6: 补充测试覆盖缺口

现有测试套件存在 3 个与整合计划直接相关的覆盖缺口, 需要新增测试用例。

### 6.1 缺口: `客户年金计划` 唯一约束验证

**问题**: 整个 `tests/` 目录中无任何测试引用 `uq_contract_version` 或 `uq_active_contract`。
这是 SCD Type 2 的核心约束, 整合计划 Step 1.2 将其从 `valid_to` 改为 `valid_from`。

**文件**: `tests/integration/migrations/test_enterprise_schema_migration.py`

**新增测试**:

```python
def test_客户年金计划_unique_constraint(self, migrated_db: Engine):
    """Verify uq_contract_version uses valid_from (not valid_to) for SCD Type 2."""
    inspector = inspect(migrated_db)
    constraints = inspector.get_unique_constraints(
        "客户年金计划", schema="customer"
    )
    uq = {c["name"]: c["column_names"] for c in constraints}
    assert "uq_contract_version" in uq, (
        "uq_contract_version constraint should exist"
    )
    assert uq["uq_contract_version"] == [
        "company_id", "plan_code", "product_line_code", "valid_from"
    ], "SCD Type 2 constraint should use valid_from, not valid_to"
```

### 6.2 缺口: `客户明细` tags GIN 索引验证

**问题**: 整合后 GIN 索引 `idx_customer_detail_tags_gin` 在 001 中创建, 但无测试验证。

**文件**: `tests/integration/migrations/test_enterprise_schema_migration.py`

**修改**: 在现有 `test_客户明细_table_exists` 末尾追加索引检查:

```python
# Verify GIN index for tags JSONB (consolidated from 007)
indexes = inspector.get_indexes("客户明细", schema="customer")
index_names = [idx["name"] for idx in indexes]
assert "idx_customer_detail_tags_gin" in index_names, (
    "idx_customer_detail_tags_gin GIN index should exist"
)
```

### 6.3 缺口: tags 数据迁移验证

**问题**: 整合后 003 执行 `年金客户标签 → tags JSONB` 数据迁移, 但现有 seed 测试只检查行数, 不检查列值。

**文件**: `tests/integration/migrations/test_enterprise_schema_migration.py`

**新增测试**:

```python
def test_客户明细_tags_data_migration(self, migrated_db: Engine):
    """Verify 年金客户标签 → tags JSONB migration in 003 (consolidated from 007)."""
    with migrated_db.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FILTER (WHERE tags != '[]'::jsonb) AS has_tags,
                   COUNT(*) FILTER (WHERE tags = '[]'::jsonb) AS empty_tags
            FROM customer."客户明细"
        """))
        row = result.one()
        # Seed data with non-empty 年金客户标签 should have been migrated
        assert row.has_tags > 0, (
            "tags migration should populate from 年金客户标签"
        )
```

---

## Step 7: 运行测试套件

完成 Step 1-6 的所有代码修改后, 运行完整测试套件验证。

```bash
cd E:/Projects/WorkDataHub
PYTHONPATH=src uv run pytest tests/ -v --tb=short
```

重点关注以下测试文件:

| 测试文件 | 验证内容 |
|---------|---------|
| `tests/io/schema/test_migrations.py` | alembic_version = 新 HEAD |
| `tests/integration/migrations/test_enterprise_schema_migration.py` | 客户明细 28 列 + tags + GIN 索引 + 约束 |
| `tests/integration/customer_mdm/test_e2e_pipeline.py` | 全链路: contract sync → snapshot → BI view |
| `tests/integration/customer_mdm/test_trigger_sync.py` | 触发器传播 |
| `tests/integration/customer_mdm/test_status_fields.py` | SCD Type 2 版本控制 |
| `tests/unit/test_enterprise_schema_migration_static.py` | 001 静态分析 (不受影响) |
