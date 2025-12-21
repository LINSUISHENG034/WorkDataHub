# Enrichment Index Migration Scripts

将 Legacy 数据库中的映射数据迁移到 `enterprise.enrichment_index` 表。

## 脚本列表

| 脚本 | 数据源 | 目标 lookup_type |
|------|--------|------------------|
| `migrate_customer_name_mapping.py` | enterprise.company_id_mapping, enterprise.eqc_search_result | customer_name |
| `migrate_plan_mapping.py` | mapping.年金计划 | plan_code |
| `migrate_account_number_mapping.py` | enterprise.annuity_account_mapping | account_number |
| `migrate_account_name_mapping.py` | business.规模明细 | account_name |
| `restore_enrichment_index.py` | (统一恢复脚本) | 全部 |
| `cleanup_enrichment_index.py` | (数据清理脚本) | - |

## 使用方法

### 完整恢复

```bash
# Dry run 测试
PYTHONPATH=src uv run python scripts/migrations/enrichment_index/restore_enrichment_index.py --dry-run

# 执行恢复
PYTHONPATH=src uv run python scripts/migrations/enrichment_index/restore_enrichment_index.py

# 仅验证当前状态
PYTHONPATH=src uv run python scripts/migrations/enrichment_index/restore_enrichment_index.py --verify-only
```

### 单独迁移

```bash
PYTHONPATH=src uv run python scripts/migrations/enrichment_index/migrate_<type>_mapping.py [--dry-run] [--verify]
```

### 数据清理

恢复后需要执行数据清理，移除无效数据：

```bash
# 分析（查看将被清理的数据）
PYTHONPATH=src uv run python scripts/migrations/enrichment_index/cleanup_enrichment_index.py --analyze

# 执行清理
PYTHONPATH=src uv run python scripts/migrations/enrichment_index/cleanup_enrichment_index.py
```

## 数据清理规则

| 规则 | 说明 |
|------|------|
| Rule 1 | 剔除 `company_id = 'N'` 或 `company_id LIKE 'IN%'` 的记录（无效 company_id） |
| Rule 2 | 剔除 `lookup_key = company_id` 的记录（自引用无意义） |
| Rule 3 | 当 `lookup_key` 同时存在 `account_name` 和 `customer_name` 时，仅保留 `account_name` |

## 数据库配置

脚本从 `.wdh_env` 读取配置：
- `WDH_DATABASE__URI` - 目标数据库 (postgres)
- `LEGACY_DATABASE__URI` - 源数据库 (legacy)

