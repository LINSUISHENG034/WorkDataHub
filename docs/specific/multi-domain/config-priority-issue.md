# 配置优先级问题分析

> **日期:** 2025-12-29  
> **状态:** ✅ 已修复 (Story 7.3-5)  
> **发现场景:** Multi-domain 测试过程中执行 Alembic 迁移

---

## 问题描述

执行 `uv run --env-file .wdh_env alembic upgrade head` 时，Alembic 连接到错误的数据库 (`wdh_migration_test`)，而非 `.wdh_env` 中配置的 `postgres` 数据库。

### 根因

PowerShell 会话中存在环境变量 `$env:WDH_DATABASE__URI = wdh_migration_test`，**环境变量优先级高于 `.wdh_env` 文件配置**。

---

## 技术分析

### pydantic-settings 默认优先级

1. **系统环境变量** ← 最高优先级
2. **`.env` 文件** (`.wdh_env`)
3. **代码默认值**

### 当前配置 (`settings.py`)

```python
model_config = SettingsConfigDict(
    env_prefix="WDH_",
    env_file=str(SETTINGS_ENV_FILE),  # 指向 .wdh_env
    env_file_encoding="utf-8",
    case_sensitive=False,
    env_nested_delimiter="__",
    extra="ignore",
)
```

### 设计预期

`.wdh_env` 应作为**唯一配置来源**，避免系统环境变量意外覆盖。

---

## 影响范围

| 组件         | 受影响 | 说明             |
| ------------ | ------ | ---------------- |
| Alembic 迁移 | ✅     | 连接错误数据库   |
| ETL CLI      | ✅     | 数据写入错误位置 |
| 单元测试     | ⚠️     | 可能使用错误配置 |

---

## 修复方案

### 方案 A: 修改 `get_database_connection_string()`

强制从 `.wdh_env` 文件读取，忽略环境变量：

```python
def get_database_connection_string(self) -> str:
    """只从 .wdh_env 文件读取数据库 URI。"""
    if SETTINGS_ENV_FILE.exists():
        for line in SETTINGS_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("WDH_DATABASE__URI="):
                uri = line.split("=", 1)[1].strip()
                if uri.startswith("postgres://"):
                    uri = uri.replace("postgres://", "postgresql://", 1)
                return uri
    # fallback to current logic
    return self._get_database_connection_string_legacy()
```

### 方案 B: 文档化环境变量行为

保持当前行为，在 `.wdh_env` 和开发文档中明确说明环境变量优先级。

---

## 推荐

**方案 A** - 确保配置单一来源，避免运行时意外。

---

## 修复后验证步骤

### Step 1: 重建数据库表

修复配置优先级问题后，使用 Alembic 迁移脚本重建 `规模明细` 和 `收入明细` 表：

```bash
# 1. 确保 .wdh_env 配置正确
cat .wdh_env | grep WDH_DATABASE__URI

# 2. 删除现有表（如需完全重建）
# 在 postgres 中手动执行：
# DROP TABLE IF EXISTS business.收入明细 CASCADE;
# DROP TABLE IF EXISTS business.规模明细 CASCADE;

# 3. 运行 Alembic 迁移
uv run --env-file .wdh_env alembic downgrade base
uv run --env-file .wdh_env alembic upgrade head
```

### Step 2: 使用 postgres MCP 验证字段

连接 postgres 数据库，验证表结构是否符合 `domain-field-gap-summary.md` 规划：

**预期字段验证清单：**

| 表名       | Schema   | 预期列数 | Story 7.3-4 新增字段                                                                           |
| ---------- | -------- | -------- | ---------------------------------------------------------------------------------------------- |
| `收入明细` | business | 21       | 计划名称, 组合类型, 组合名称, 机构名称                                                         |
| `规模明细` | business | 27       | 计划名称, 组合类型, 组合名称, 机构名称, 子企业号, 子企业名称, 集团企业客户号, 集团企业客户名称 |

**验证 SQL 语句：**

```sql
-- 验证 收入明细 表结构
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='business' AND table_name='收入明细'
ORDER BY ordinal_position;

-- 验证 规模明细 表结构
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='business' AND table_name='规模明细'
ORDER BY ordinal_position;

-- 确认 Story 7.3-4 新增字段存在
SELECT column_name FROM information_schema.columns
WHERE table_schema='business'
  AND table_name='收入明细'
  AND column_name IN ('计划名称', '组合类型', '组合名称', '机构名称');
```

### Step 3: 验证成功标准

- [ ] `收入明细` 表包含 21 列
- [ ] `规模明细` 表包含 27 列
- [ ] Story 7.3-4 新增的 4 个字段全部存在于 `收入明细`
- [ ] 所有新增字段类型为 `character varying`，nullable = YES

---

## 参考

- `src/work_data_hub/config/settings.py` 第 352-379 行
- pydantic-settings 文档: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
