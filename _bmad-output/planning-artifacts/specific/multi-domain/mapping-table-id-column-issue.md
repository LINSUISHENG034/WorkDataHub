# Mapping 表 ID 列设计问题分析与修复方案

> **文档类型:** 问题分析与修复方案
> **创建日期:** 2025-12-31
> **问题发现:** ETL FK Backfill 执行失败
> **影响范围:** `mapping.年金客户`、`mapping.年金计划`、`mapping.组合计划`

---

## 1. 问题现象

ETL 执行时 FK backfill 向 `mapping.年金客户` 表插入新记录失败：

```
psycopg2.errors.NotNullViolation: null value in column "id" of relation "年金客户" violates not-null constraint
DETAIL: 失败, 行包含(null, IN7KZNPWPCVQXJ6AY7, null, ...)
```

---

## 2. 问题根因

### 2.1 表结构不一致

mapping schema 中 3 张表的 `id` 列设计不一致：

| 表名 | 当前主键 | id 列 | is_identity | 创建来源 | 问题 |
|------|----------|-------|-------------|----------|------|
| `年金客户` | `company_id` | `NOT NULL` | NO | `001_initial_infrastructure.py` | id 不是 IDENTITY，无法自动生成 |
| `年金计划` | `id` | `NOT NULL` | YES (ALWAYS) | `002_initial_domains.py` | 主键应该是 `年金计划号` |
| `组合计划` | `id` | `NOT NULL` | YES (ALWAYS) | `002_initial_domains.py` | 主键应该是 `组合代码` |

### 2.2 主键设计错误

从业务角度分析：

- **`年金客户`**: 主键应为 `company_id`（企业唯一标识）✅ 当前正确
- **`年金计划`**: 主键应为 `年金计划号`（计划唯一标识）❌ 当前错误使用 `id`
- **`组合计划`**: 主键应为 `组合代码`（组合唯一标识）❌ 当前错误使用 `id`

### 2.3 id 列定义问题

- `年金客户.id`: 定义为 `INTEGER NOT NULL` 但无 IDENTITY，FK backfill 插入时无法提供值
- `年金计划.id` 和 `组合计划.id`: 使用 IDENTITY 但作为主键，与业务语义不符

---

## 3. 影响分析

### 3.1 直接影响

1. **ETL 失败**: FK backfill 无法向 `年金客户` 表插入新客户记录
2. **数据完整性**: 新发现的客户无法被记录到参考表

### 3.2 潜在影响

1. **FK backfill 配置**: `年金计划` 和 `组合计划` 的 FK 配置使用业务键（年金计划号、组合代码），与当前主键（id）不一致
2. **ON CONFLICT 语义**: INSERT ON CONFLICT DO NOTHING 依赖主键，主键错误会导致重复插入或冲突检测失败

---

## 4. 修复方案

### 4.1 设计原则

1. **id 列统一为 IDENTITY**: 所有 id 列使用 `GENERATED ALWAYS AS IDENTITY`，自动生成
2. **主键使用业务键**: 主键应为业务唯一标识符，而非技术 id
3. **直接修改迁移脚本**: 迁移脚本面向从零开始的场景，直接修改而非增量迁移

### 4.2 修改清单

#### 4.2.1 迁移脚本修改

**文件:** `io/schema/migrations/versions/001_initial_infrastructure.py`

| 表名 | 修改内容 |
|------|----------|
| `年金客户` | `id` 列改为 `GENERATED ALWAYS AS IDENTITY`，主键保持 `company_id` |

**文件:** `io/schema/migrations/versions/003_seed_static_data.py`

| 修改内容 |
|----------|
| 将 `年金客户` 加入 id 列排除列表（与 `年金计划`、`组合计划` 一致）|

#### 4.2.2 Domain Registry 修改

**文件:** `src/work_data_hub/infrastructure/schema/definitions/annuity_plans.py`

| 属性 | 当前值 | 修改为 |
|------|--------|--------|
| `primary_key` | `"id"` | `"年金计划号"` |

**文件:** `src/work_data_hub/infrastructure/schema/definitions/portfolio_plans.py`

| 属性 | 当前值 | 修改为 |
|------|--------|--------|
| `primary_key` | `"id"` | `"组合代码"` |

### 4.3 修复后预期状态

| 表名 | 主键 | id 列 | is_identity |
|------|------|-------|-------------|
| `年金客户` | `company_id` | `INTEGER` | YES (ALWAYS) |
| `年金计划` | `年金计划号` | `INTEGER` | YES (ALWAYS) |
| `组合计划` | `组合代码` | `INTEGER` | YES (ALWAYS) |

---

## 5. 验证步骤

### 5.1 迁移验证

```bash
# 1. 重置数据库到基础状态
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic downgrade base

# 2. 重新执行所有迁移
WDH_ENV_FILE=.wdh_env PYTHONPATH=src uv run alembic upgrade head

# 3. 验证表结构
psql -c "SELECT table_name, column_name, is_identity, identity_generation
         FROM information_schema.columns
         WHERE table_schema = 'mapping' AND column_name = 'id';"
```

### 5.2 ETL 验证

```bash
# 执行 ETL 测试
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --all-domains --period 202510 --file-selection newest \
  --execute --no-enrichment
```

---

## 6. 验证结果 (2025-12-31)

### 6.1 迁移执行成功

```
Running upgrade  -> 20251228_000001, Initial infrastructure tables
Running upgrade 20251228_000001 -> 20251228_000002, Initial domain tables
Running upgrade 20251228_000002 -> 20251228_000003, Seed static reference data
Seeded 9813 rows into mapping.年金客户
Seeded 1142 rows into mapping.年金计划
Seeded 1324 rows into mapping.组合计划
```

### 6.2 表结构验证

| 表名 | 主键列 | id 列 IDENTITY |
|------|--------|----------------|
| `年金客户` | `company_id` ✅ | YES (ALWAYS) ✅ |
| `年金计划` | `年金计划号` ✅ | YES (ALWAYS) ✅ |
| `组合计划` | `组合代码` ✅ | YES (ALWAYS) ✅ |

### 6.3 ETL 执行验证

| Domain | 状态 | 记录数 |
|--------|------|--------|
| `annuity_performance` | ✅ SUCCESS | 37,121 rows |
| `annuity_income` | ✅ SUCCESS | 13,639 rows |

**结论：** FK backfill `NotNullViolation` 错误已解决。

---

## 7. 参考文档

- [multi-domain-check-list.md](./multi-domain-check-list.md) - 问题清单
- [fk-backfill-gap-analysis.md](./fk-backfill-gap-analysis.md) - FK 回填分析
- `io/schema/migrations/versions/001_initial_infrastructure.py` - 基础设施迁移
- `io/schema/migrations/versions/002_initial_domains.py` - 域表迁移
- `io/schema/migrations/versions/003_seed_static_data.py` - Seed 数据迁移
