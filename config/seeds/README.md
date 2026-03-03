# 种子数据说明文档

> **用途**: 说明 `config/seeds/` 目录下种子数据的来源、处理规则和导出命令
> **创建日期**: 2025-12-28
> **更新日期**: 2026-03-03
> **数据来源**:
>
> - Legacy PostgreSQL: `postgresql://postgres:***@localhost:5432/legacy` (1-10)
> - Postgres: `postgresql://postgres:***@localhost:5432/postgres` (11-12)
>
> **支持格式**: CSV (`.csv`)

---

## 1. 数据源概述

- **表 1-10**: 从 Legacy PostgreSQL 数据库导出，使用 `\COPY` 命令
- **表 11 (base_info)**: 从 Postgres 数据库导出，使用 psycopg v3 COPY 协议
- **表 12 (enrichment_index)**: 从 Postgres 数据库导出，数据源于迁移脚本

**连接信息**: 见 `.wdh_env` (root dir)

### 1.1 版本管理机制

种子数据采用版本化管理，CSV 格式，每个文件独立解析到最高版本：

```
config/seeds/
├── 001/                              # 版本 1 (初始数据)
│   ├── enrichment_index.csv
│   ├── 客户明细.csv
│   └── ...
├── 002/                              # 版本 2 (客户明细更新)
│   └── 客户明细.csv
├── 003/                              # 版本 3 (base_info/enrichment_index CSV化)
│   ├── base_info.csv
│   └── enrichment_index.csv
└── README.md
```

**当前版本状态**:
| 文件 | v001 | v002 | v003 | 使用版本 | 格式 |
|------|------|------|------|----------|------|
| base_info | - | - | 27,689 行 | v003 | csv |
| enrichment_index | 32,052 行 | - | 45,105 行 | v003 | csv |
| 客户明细 | 9,822 行 | 10,306 行 | - | v002 | csv |

> **Note:** v002 目录中仍有旧 `.dump` 文件 (base_info.dump, enrichment_index.dump)，
> 它们不会被加载，因为 v003 CSV 文件优先级更高。业务数据备份已移至 `data/backups/`。

---

## 2. 种子数据清单

| #   | 文件名                             | Schema     | 表名                         | 行数      | 格式 | 数据类型     | 敏感级别 |
| --- | ---------------------------------- | ---------- | ---------------------------- | --------- | ---- | ------------ | -------- |
| 1   | `company_types_classification.csv` | enterprise | company_types_classification | 104       | csv  | 参考数据     | 🟢 低    |
| 2   | `industrial_classification.csv`    | enterprise | industrial_classification    | 1,183     | csv  | 参考数据     | 🟢 低    |
| 3   | `产品线.csv`                       | mapping    | 产品线                       | 12        | csv  | 参考数据     | 🟢 低    |
| 4   | `组织架构.csv`                     | mapping    | 组织架构                     | 38        | csv  | 参考数据     | 🟢 低    |
| 5   | `计划层规模.csv`                   | mapping    | 计划层规模                   | 7         | csv  | 参考数据     | 🟢 低    |
| 6   | `产品明细.csv`                     | mapping    | 产品明细                     | 18        | csv  | 参考数据     | 🟢 低    |
| 7   | `利润指标.csv`                     | mapping    | 利润指标                     | 12        | csv  | 参考数据     | 🟢 低    |
| 8   | `客户明细.csv`                     | customer   | 客户明细                       | 10,306    | csv  | **业务数据** | 🔴 高    |
| 9   | `年金计划.csv`                     | mapping    | 年金计划                     | 1,128     | csv  | **业务数据** | 🟡 中    |
| 10  | `组合计划.csv`                     | mapping    | 组合计划                     | 1,315     | csv  | **业务数据** | 🟡 中    |
| 11  | `base_info.csv`                    | enterprise | base_info                    | 27,689    | csv  | **业务数据** | 🔴 高    |
| 12  | `enrichment_index.csv`             | enterprise | enrichment_index             | 45,105    | csv  | **聚合数据** | 🟡 中    |

---

## 3. 处理规则

### 3.1 无过滤规则 (直接导出)

以下表格直接全量导出，无过滤条件：

| 文件名                             | 导出命令                                                               |
| ---------------------------------- | ---------------------------------------------------------------------- |
| `company_types_classification.csv` | `\COPY enterprise.company_types_classification TO ... WITH CSV HEADER` |
| `industrial_classification.csv`    | `\COPY enterprise.industrial_classification TO ... WITH CSV HEADER`    |
| `产品线.csv`                       | `\COPY mapping.产品线 TO ... WITH CSV HEADER`                          |
| `组织架构.csv`                     | `\COPY mapping.组织架构 TO ... WITH CSV HEADER`                        |
| `计划层规模.csv`                   | `\COPY mapping.计划层规模 TO ... WITH CSV HEADER`                      |
| `产品明细.csv`                     | `\COPY mapping.产品明细 TO ... WITH CSV HEADER`                        |
| `利润指标.csv`                     | `\COPY mapping.利润指标 TO ... WITH CSV HEADER`                        |

### 3.2 版本 003 数据导出 (2026-03-03)

**v003 使用纯 Python CSV 导出**，消除 pg_dump/pg_restore 外部工具依赖：

**导出脚本**: `scripts/seed_data/export_seed_csv.py`

```bash
PYTHONPATH=src uv run --env-file .wdh_env python scripts/seed_data/export_seed_csv.py
```

导出的表：
| 文件 | 大小 | 说明 |
|------|------|------|
| `base_info.csv` | ~757 MB | 含 `raw_data`, `raw_business_info`, `raw_biz_label` JSON 字段 |
| `enrichment_index.csv` | ~8 MB | 聚合索引数据 |

### 3.3 特殊数据源 (v001 enrichment_index)

**enrichment_index** 数据来源于现有 **Postgres 数据库**，而非 Legacy 数据库。

- **数据来源**: 迁移脚本 `scripts/migrations/enrichment_index/`
- **包含脚本**:
  - `migrate_customer_name_mapping.py` - 客户名称映射
  - `migrate_account_name_mapping.py` - 账户名称映射
  - `migrate_account_number_mapping.py` - 账户号码映射
  - `migrate_plan_mapping.py` - 计划映射
- **备份/恢复**: `restore_enrichment_index.py`

```sql
-- 从 Postgres 数据库导出 (非 legacy)
\COPY enterprise.enrichment_index TO 'enrichment_index.csv' WITH CSV HEADER ENCODING 'UTF8'
```

### 3.4 基础过滤规则 (年金计划)

**年金计划** 是级联过滤的基础表：

```sql
-- 过滤条件: 排除 company_id 以 'IN' 开头的记录
SELECT * FROM mapping.年金计划
WHERE company_id NOT LIKE 'IN%' OR company_id IS NULL
```

**原因**: `IN%` 开头的 company_id 为测试/无效数据

### 3.5 级联过滤规则 (客户明细)

**客户明细** 依赖 **年金计划** 的过滤结果：

```sql
-- 级联过滤: 关键年金计划 必须存在于已过滤的年金计划中
SELECT * FROM customer."客户明细" c
WHERE c.关键年金计划 IN (
    SELECT 年金计划号 FROM mapping.年金计划
    WHERE company_id NOT LIKE 'IN%' OR company_id IS NULL
)
AND (c.company_id NOT LIKE 'IN%' OR c.company_id IS NULL)
```

### 3.6 级联过滤规则 (组合计划)

**组合计划** 依赖 **年金计划** 的过滤结果：

```sql
-- 级联过滤: 年金计划号 必须存在于已过滤的年金计划中
SELECT * FROM mapping.组合计划 p
WHERE p.年金计划号 IN (
    SELECT 年金计划号 FROM mapping.年金计划
    WHERE company_id NOT LIKE 'IN%' OR company_id IS NULL
)
```

### 3.7 客户标签字段约定 (客户明细)

`customer."客户明细"` 仅保留 `tags` JSONB 标签数组作为客户标签来源。
历史字段 `年金客户标签` 已弃用并移除，所有标签已合并到 `tags`。

---

## 5. 导出顺序

由于存在级联依赖关系，导出顺序为：

1. **无依赖表** (可并行): 1-7, 11-12
2. **基础表**: 年金计划 (9)
3. **依赖表**: 客户明细 (8), 组合计划 (10)

---

## 6. 安全注意事项

- 🔴 **高敏感**: `客户明细.csv`, `base_info.csv` 包含客户信息
- 🟡 **中敏感**: `年金计划.csv`, `组合计划.csv`, `enrichment_index.csv` 包含业务数据
- ⚠️ **不得提交 Git**: `.gitignore` 已配置阻止 `config/seeds/` 目录
- 📁 **业务备份**: 旧业务数据备份 (`.dump` 格式) 已移至 `data/backups/`

---

## 7. 审核确认

请确认以上规则是否正确，审核通过后我将按此规则生成种子数据。

- [ ] 过滤规则确认
- [ ] 导出顺序确认
- [ ] 敏感级别分类确认
