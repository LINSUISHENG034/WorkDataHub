# 客户名称清洗函数统一重构

> **日期**: 2026-01-05  
> **状态**: ✅ 技术验证通过 - 待实施  
> **决策**: 使用 UPPERCASE 大写转换 + 数据质量同步提升

## 问题背景

### 发现的问题

在 `enrichment_index` 种子数据重构过程中，发现项目中存在 **3 个功能相似但实现不一致** 的客户名称清洗函数：

| 函数                     | 位置                                                | 调用场景                                 |
| ------------------------ | --------------------------------------------------- | ---------------------------------------- |
| `normalize_for_temp_id`  | `infrastructure/enrichment/normalizer.py`           | DB cache 匹配、TempID 生成、种子数据生成 |
| `normalize_company_name` | `infrastructure/cleansing/rules/string_rules.py`    | ETL 管道 CleansingStep（`客户名称`字段） |
| `clean_company_name`     | `domain/pipelines/steps/customer_name_cleansing.py` | 旧版 Row-based 管道                      |

### 函数实现差异对比

| 特性                  | normalize_for_temp_id | normalize_company_name | clean_company_name |
| --------------------- | --------------------- | ---------------------- | ------------------ |
| **后缀模板数量**      | 29+ 个                | 16 个                  | 14 个              |
| **空格处理**          | 完全移除              | 压缩为单空格           | 完全移除           |
| **全/半角转换**       | 全角 ASCII→ 半角      | 全角 ASCII→ 半角       | 无                 |
| **括号规范化**        | 半角 → 全角           | 半角 → 全角            | 无                 |
| **开头/结尾括号清理** | 仅清理状态标记括号    | 清理任意括号内容       | 无                 |
| **装饰字符清理**      | 无                    | 「」『』" 等           | 无                 |
| **小写转换**          | 是                    | 否                     | 否                 |
| **无效占位符处理**    | 是 (null, N/A 等)     | 否                     | 否                 |

---

## 具体冲突分析

### 测试用例对比结果

**统计**: 17 个测试用例中，一致 6 个 (35%)，冲突 11 个 (65%)

| 输入                   | temp_id            | company_name     | clean                  | 一致 |
| ---------------------- | ------------------ | ---------------- | ---------------------- | ---- |
| `'中国平安'`           | `'中国平安'`       | `'中国平安'`     | `'中国平安'`           | ✓    |
| `'中国平安-已转出'`    | `'中国平安'`       | `'中国平安'`     | `'中国平安-'`          | ✗    |
| `'中国平安（已转出）'` | `'中国平安'`       | `'中国平安'`     | `'中国平安（已转出）'` | ✗    |
| `'（原）深圳出版集团'` | `'深圳出版集团'`   | `'深圳出版集团'` | `'（原）深圳出版集团'` | ✗    |
| `'CHINA LIFE'`         | `'chinalife'`      | `'CHINA LIFE'`   | `'CHINALIFE'`          | ✗    |
| `'  ABC  公司  '`      | `'abc公司'`        | `'ABC 公司'`     | `'ABC公司'`            | ✗    |
| `'某公司(集团)'`       | `'某公司（集团）'` | `'某公司'`       | `'某公司(集团)'`       | ✗    |
| `'null'`               | `''`               | `'null'`         | `'null'`               | ✗    |

### 关键冲突点

#### 1. 状态标记处理不完整

- `clean_company_name` 仅移除末尾标记，不处理带分隔符或括号的情况
- 影响：`'中国平安-已转出'` → `'中国平安-'`（遗留破折号）

#### 2. 大小写处理不一致

- `normalize_for_temp_id` 转小写；其他保持原样
- 影响：英文名称 `'CHINA LIFE'` 三者输出完全不同

#### 3. 空格处理差异

- `normalize_company_name` 保留单空格；其他完全移除
- 影响：`'ABC 公司'` vs `'ABC公司'`

#### 4. 括号规范化差异

- 三者对括号处理完全不同
- 影响：`'某公司(集团)'` 输出三种结果

#### 5. 无效占位符处理

- 仅 `normalize_for_temp_id` 识别 `'null'` 为空
- 影响：脏数据进入 DB cache

### 导致的业务问题

1. **DB cache 匹配失败**：种子数据使用 `normalize_for_temp_id` 生成 `lookup_key`，但 ETL 管道清洗 `客户名称` 使用 `normalize_company_name`，两者输出不一致导致无法匹配。

2. **代码重复**：三个函数实现逻辑高度重叠，违反 DRY 原则。

3. **维护困难**：新增清洗规则需要在多处修改，容易遗漏。

---

## 重构目标

### 核心目标

**创建一个统一的、功能更强的客户名称清洗函数**，供所有场景调用：

1. **函数命名通用化**：使用 `normalize_customer_name` 作为统一名称
2. **功能综合化**：合并三个函数的所有清洗能力
3. **位置合理化**：放置在 `infrastructure/cleansing/` 下，作为基础设施层
4. **不保留别名**：全部替换为新函数名，确保代码清晰

---

## 冲突处理决策

针对 5 个关键冲突点，需确定统一行为：

### 1. 空格处理

| 选项 | 行为         | 推荐   |
| ---- | ------------ | ------ |
| A    | 完全移除     | ✓ 推荐 |
| B    | 压缩为单空格 | -      |

**决策**: 完全移除空格，确保匹配稳定性。`"ABC 公司"` → `"abc公司"`

### 2. 大小写处理

| 选项 | 行为     | 推荐    |
| ---- | -------- | ------- |
| A    | 转大写   | ✅ 确认 |
| B    | 转小写   | -       |
| C    | 保持原样 | -       |

**决策**: ✅ 统一转大写。更符合企业名称正式表示，在数据迁移过程中同步提升数据质量。`"china life"` → `"CHINALIFE"`

### 3. 括号处理

| 选项 | 行为                  | 推荐   |
| ---- | --------------------- | ------ |
| A    | 半角 → 全角，保留内容 | ✓ 推荐 |
| B    | 删除结尾括号内容      | -      |

**决策**: 规范化为全角括号，保留有意义的括号内容（如"集团"）。仅删除包含状态标记的括号。

### 4. 装饰字符处理

| 选项 | 行为           | 推荐   |
| ---- | -------------- | ------ |
| A    | 移除 「」『』" | ✓ 推荐 |
| B    | 保留           | -      |

**决策**: 移除装饰字符，这些不是公司名称的有效组成部分。

### 5. 无效占位符处理

| 选项 | 行为         | 推荐   |
| ---- | ------------ | ------ |
| A    | 识别并返回空 | ✓ 推荐 |
| B    | 保持原样     | -      |

**决策**: 识别 `null`, `N/A`, `空白` 等占位符，返回空字符串。

---

## 调用方迁移

> [!IMPORTANT] > **不保留别名**，全部替换为新函数名 `normalize_customer_name`

| 原函数                     | 迁移方式                                     |
| -------------------------- | -------------------------------------------- |
| `normalize_for_temp_id()`  | 删除，调用处改为 `normalize_customer_name()` |
| `normalize_company_name()` | 删除，调用处改为 `normalize_customer_name()` |
| `clean_company_name()`     | 删除，调用处改为 `normalize_customer_name()` |

### 需修改的文件 (2026-01-05 验证更新)

```
# normalize_for_temp_id 调用处 (14 files)
infrastructure/enrichment/normalizer.py           # 定义处
infrastructure/enrichment/__init__.py             # re-export
infrastructure/enrichment/types.py
infrastructure/enrichment/resolver/db_strategy.py
infrastructure/enrichment/resolver/eqc_strategy.py
infrastructure/enrichment/resolver/cache_warming.py
infrastructure/enrichment/resolver/backflow.py
infrastructure/enrichment/repository/core.py
infrastructure/enrichment/eqc_provider.py
infrastructure/enrichment/domain_learning_service.py
infrastructure/enrichment/company_id_resolver.py
domain/company_enrichment/lookup_queue.py
gui/eqc_query/controller.py
migrations/migrate_legacy_to_enrichment_index.py

# normalize_company_name 调用处 (8 files)
infrastructure/cleansing/rules/string_rules.py   # 定义处
infrastructure/cleansing/__init__.py             # re-export
infrastructure/cleansing/validators.py
infrastructure/cleansing/settings/cleansing_rules.yml
infrastructure/transforms/cleansing_step.py
infrastructure/enrichment/resolver/eqc_strategy.py
infrastructure/enrichment/resolver/backflow.py
infrastructure/enrichment/company_id_resolver.py

# clean_company_name 调用处 (4 files)
domain/pipelines/steps/customer_name_cleansing.py # 定义处
domain/pipelines/steps/__init__.py
infrastructure/enrichment/normalizer.py           # docstring reference
infrastructure/cleansing/rules/string_rules.py    # docstring reference
```

---

## 技术方案

### 新函数位置

```
src/work_data_hub/infrastructure/cleansing/
├── normalizers/
│   ├── __init__.py
│   └── customer_name.py    # 新建：统一客户名称清洗
```

或直接在现有位置扩展：

```
src/work_data_hub/infrastructure/cleansing/
├── rules/
│   └── string_rules.py     # 扩展：添加综合清洗函数
```

### 兼容性

- 保持所有现有函数签名不变
- 现有函数改为调用新函数的包装器
- 单元测试应全部通过

---

## 验证标准

```python
# 三个函数输出必须完全一致
test_cases = [
    "中国平安",
    "中国平安 ",
    "中国平安-已转出",
    "（原）深圳出版集团有限公司",
    "某公司及下属子企业",
    "  ABC  公司  ",
]

for case in test_cases:
    result = normalize_customer_name(case)
    print(f"{case!r} → {result!r}")
```

---

## 数据库迁移策略

> [!CAUTION] > **必须执行的迁移步骤**  
> `enrichment_index.lookup_key` 列当前使用 `normalize_for_temp_id` 生成（小写）。  
> 统一函数改为大写输出后，现有数据将无法匹配，**必须执行数据迁移**。

### 迁移脚本需求

```python
# migrations/migrate_lookup_key_to_uppercase.py
"""
Re-normalize all lookup_key values in enrichment_index to UPPERCASE.

This migration is required due to the change from lowercase to uppercase
normalization in the unified normalize_customer_name() function.
"""

def migrate_lookup_keys(session):
    """
    Steps:
    1. Query all distinct (customer_name, lookup_key) pairs
    2. Apply new normalize_customer_name() to customer_name
    3. Update lookup_key with new normalized value
    4. Log changes for audit
    """
    pass
```

### 迁移验证

- [ ] 迁移前后记录数一致
- [ ] 随机抽样 100 条验证新旧 lookup_key 映射正确
- [ ] ETL 重新执行后 DB cache 匹配率 ≥ 原有水平
