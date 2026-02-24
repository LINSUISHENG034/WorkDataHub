# enrichment_index 表优化分析报告

> **日期**: 2026-01-04
> **状态**: 调查中
> **相关表**: `enterprise.enrichment_index`

## 1. 背景

`enterprise.enrichment_index` 表用于 company_id 在 DB cache 层匹配。表的冗余程度直接影响 DB cache 层的性能。

### 1.1 待验证问题

1. **主键设计**: 是否需要将 `lookup_key` 设置为主键？
2. **数据清洗**: `lookup_key` 中是否存在未清洗的客户名称？

---

## 2. 当前表结构

### 2.1 列定义

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK, IDENTITY | 自增主键 |
| lookup_key | VARCHAR(255) | NOT NULL | 查找键 |
| lookup_type | VARCHAR(20) | NOT NULL | 类型: plan_code/account_name/account_number/customer_name/former_name |
| company_id | VARCHAR(100) | NOT NULL | 匹配到的公司ID |
| confidence | NUMERIC(3,2) | NOT NULL, DEFAULT 1.00 | 置信度 0.00-1.00 |
| source | VARCHAR(50) | NOT NULL | 来源: yaml/eqc_api/manual/backflow/domain_learning/legacy_migration |
| source_domain | VARCHAR(50) | NULL | 来源域 |
| source_table | VARCHAR(100) | NULL | 来源表 |
| hit_count | INTEGER | NOT NULL, DEFAULT 0 | 命中次数 |
| last_hit_at | TIMESTAMP | NULL | 最后命中时间 |
| created_at | TIMESTAMP | NOT NULL | 创建时间 |
| updated_at | TIMESTAMP | NOT NULL | 更新时间 |

### 2.2 索引和约束

```sql
-- 主键
enrichment_index_pkey: PRIMARY KEY (id)

-- 唯一约束
uq_enrichment_index_key_type: UNIQUE (lookup_key, lookup_type)

-- 索引
ix_enrichment_index_type_key: INDEX (lookup_type, lookup_key)
ix_enrichment_index_source: INDEX (source)
ix_enrichment_index_source_domain: INDEX (source_domain)
```

### 2.3 数据分布

| lookup_type | 总记录数 | 唯一 lookup_key | 重复数 |
|-------------|----------|-----------------|--------|
| customer_name | 15,322 | 15,322 | 0 |
| account_name | 10,945 | 10,945 | 0 |
| account_number | 10,265 | 10,265 | 0 |
| former_name | 3,620 | 3,620 | 0 |
| plan_code | 1,104 | 1,104 | 0 |

---

## 3. 问题1分析: 主键设计

### 3.1 初步结论

当前唯一约束 `(lookup_key, lookup_type)` 已确保数据唯一性，无重复数据。

### 3.2 第一性原理分析

#### 3.2.1 核心问题

当前设计使用 `(lookup_key, lookup_type)` 组合作为唯一约束。这个设计的**隐含假设**是：

> 同一个 `lookup_key` 在不同 `lookup_type` 下可能映射到**不同的** `company_id`

#### 3.2.2 数据验证

**跨类型冲突统计**：

| 指标 | 数值 |
|------|------|
| 总记录数 | 41,256 |
| 同一 lookup_key 映射到不同 company_id | 22 |
| 冲突率 | 0.05% |

**冲突来源分析**：

| 来源组合 | 冲突数 | 占比 |
|----------|--------|------|
| eqc_api vs legacy_migration | 26 | 96% |
| eqc_api vs eqc_api | 1 | 4% |

#### 3.2.3 真实业务场景验证

唯一的 eqc_api 内部冲突案例：

```
lookup_key: 峨眉山市殡葬服务中心
├── customer_name → company_id: 696725805 (当前公司名称)
└── former_name   → company_id: 695643619 (曾用名)
```

**业务解释**：
- 公司A（695643619）**曾经**叫"峨眉山市殡葬服务中心"
- 公司B（696725805）**现在**叫"峨眉山市殡葬服务中心"
- 这是**公司改名**的真实业务场景

#### 3.2.4 结论

**✅ 当前设计合理**

`lookup_type` 字段是必要的，因为：
1. 同一名称可能是不同公司的"当前名称"和"曾用名"
2. 不同类型的标识符（plan_code vs customer_name）语义不同
3. 96% 的冲突是数据质量问题，可通过清理 legacy_migration 数据解决

**❌ 不建议将 lookup_key 单独设为主键**

原因：会丢失 lookup_type 维度的区分能力，导致公司改名场景无法正确处理

---

## 4. 问题2分析: 数据清洗

### 4.1 调查结果

**确认存在问题**: 1,449 条 `customer_name` 类型记录包含未清洗数据。

| 来源 | 未清洗记录数 |
|------|--------------|
| eqc_api | 817 |
| legacy_migration | 632 |
| **总计** | **1,449** |

### 4.2 问题示例

```
数据库存储值: 《农村金融时报》社
ETL 查询标准化后: 农村金融时报社
结果: 匹配失败
```

### 4.3 根本原因

- 代码中 `insert_enrichment_index_batch` 会调用 `_normalize_lookup_key` 标准化
- 但早期数据（legacy_migration）和部分 EQC API 数据绕过了标准化
- 导致数据库中存储了未标准化的原始值

---

## 5. 修复方案

### 5.1 问题1：主键设计

**结论：无需修改**

当前设计 `(lookup_key, lookup_type)` 唯一约束是合理的。

### 5.2 问题2：数据清洗

**需要修复**：1,449 条未清洗的 customer_name 记录。

### 5.3 新发现：跨类型数据冗余

#### 5.3.1 问题描述

在进行 `customer_name` 匹配时，**不会**引用到 `account_name` 类型的记录。

原因：
- 查询按 `(lookup_type, lookup_key)` 组合进行
- `customer_name` 和 `account_name` 使用不同的源字段

#### 5.3.2 数据冗余统计

| 指标 | 数值 |
|------|------|
| customer_name 与 account_name 重叠记录 | 3,873 |
| 映射到相同 company_id | 3,856 (99.6%) |
| 映射到不同 company_id | 17 (0.4%) |

#### 5.3.3 冲突来源分析

所有17条不同映射都是 `eqc_api` vs `legacy_migration` 的冲突，属于**数据质量问题**。

#### 5.3.4 优化建议

**方案A：保持现状**
- 优点：无风险
- 缺点：3,856 条冗余记录占用空间

**方案B：清理 legacy_migration 冲突数据**
- 删除17条 legacy_migration 来源的冲突记录
- 保留 eqc_api 来源的记录（数据质量更高）

**方案C1：删除冗余 account_name 记录**
- 删除3,856条与 customer_name 重复且映射相同 company_id 的 account_name 记录
- 风险：中等，需验证 ETL 查询不受影响

**方案C2：合并类型（不推荐）**
- 将 customer_name 和 account_name 合并为统一类型
- 风险：高，需修改3个代码文件，且7,072条独立 account_name 无法合并

### 5.4 方案详细分析

#### 5.4.1 方案B详情

**问题**：17条记录中，同一 lookup_key 在不同类型下映射到不同 company_id。

**冲突模式**：全部是 eqc_api (customer_name) vs legacy_migration (account_name)

**实施步骤**：
```sql
-- Step 1: 备份
CREATE TABLE enterprise.enrichment_index_conflict_backup AS
SELECT e2.* FROM enterprise.enrichment_index e1
JOIN enterprise.enrichment_index e2 ON e1.lookup_key = e2.lookup_key
WHERE e1.lookup_type = 'customer_name'
AND e2.lookup_type = 'account_name'
AND e1.company_id != e2.company_id
AND e2.source = 'legacy_migration';

-- Step 2: 删除
DELETE FROM enterprise.enrichment_index
WHERE id IN (SELECT id FROM enterprise.enrichment_index_conflict_backup);
```

#### 5.4.2 方案C1详情

**问题**：3,856条记录同时存在于 customer_name 和 account_name，且映射相同 company_id。

**冗余来源**：99.97% 是 eqc_api (customer_name) + legacy_migration (account_name)

**安全性验证**：
- 删除的记录都有 customer_name 对应且映射相同
- 剩余7,055条独立 account_name 不受影响

**实施步骤**：
```sql
-- Step 1: 备份
CREATE TABLE enterprise.enrichment_index_redundant_backup AS
SELECT e2.* FROM enterprise.enrichment_index e1
JOIN enterprise.enrichment_index e2 ON e1.lookup_key = e2.lookup_key
WHERE e1.lookup_type = 'customer_name'
AND e2.lookup_type = 'account_name'
AND e1.company_id = e2.company_id;

-- Step 2: 删除
DELETE FROM enterprise.enrichment_index
WHERE id IN (SELECT id FROM enterprise.enrichment_index_redundant_backup);
```

### 5.5 推荐方案

**组合方案：B + C1**

| Phase | 操作 | 清理记录数 |
|-------|------|-----------|
| 1 | 方案B：删除冲突 | 17 |
| 2 | 方案C1：删除冗余 | 3,856 |
| **总计** | | **3,873** |

### 5.6 多优先级匹配风险评估

#### 5.6.1 风险场景

DB cache 匹配按优先级顺序进行：
```
DB-P2: account_name (年金账户名)  ← 优先于
DB-P4: customer_name (客户名称)
```

ETL 数据中 `客户名称` 和 `年金账户名` 是**两个独立字段**，可能存在：
- 只有年金账户名，没有客户名称
- 两个字段值不同

#### 5.6.2 业务数据分析

| 字段状态 | 数量 | 占比 |
|----------|------|------|
| 客户名称 = 年金账户名 | 17,302 | 96.5% |
| 客户名称 ≠ 年金账户名 | 628 | 3.5% |

#### 5.6.3 风险验证

对于628条"不同"记录中的297个唯一年金账户名：

| 检查项 | 结果 |
|--------|------|
| 在 enrichment_index 有 account_name 记录 | 297 |
| 同时在 customer_name 类型中存在 | **0** |
| 会被方案C1删除 | **0** |

#### 5.6.4 结论

**方案C1安全**，因为：
1. 只删除"与 customer_name 重复"的 account_name 记录
2. 关键的297个独立 account_name 记录**不会被删除**
3. ETL 匹配不受影响

#### Phase 1: 数据备份

```sql
-- 创建备份表
CREATE TABLE enterprise.enrichment_index_backup_20260104 AS
SELECT * FROM enterprise.enrichment_index;

-- 验证备份
SELECT COUNT(*) FROM enterprise.enrichment_index_backup_20260104;
```

#### Phase 2: 数据清洗脚本

创建 `scripts/migration/normalize_enrichment_index.py`：

1. 读取所有 customer_name/former_name 类型记录
2. 对 lookup_key 应用 `normalize_for_temp_id()` 标准化
3. 处理标准化后的重复：保留 confidence 最高的记录
4. 更新数据库

#### Phase 3: 修改 Alembic 迁移脚本

修改 `001_initial_infrastructure.py`，在表创建后添加注释说明 lookup_key 应存储标准化值。

#### Phase 4: 验证

```sql
-- 验证清洗后无未标准化数据
SELECT COUNT(*) FROM enterprise.enrichment_index
WHERE lookup_type IN ('customer_name', 'former_name')
AND (
    lookup_key ~ '[（）\(\)【】\[\]《》<>「」『』]'
    OR lookup_key ~ '[\s　]'
);
-- 预期: 0
```

---

## 6. 问题3分析: 单边括号记录

### 6.1 问题描述

`enrichment_index` 表的 `lookup_key` 字段中存在客户名称只包含单边括号的不规范记录，例如：
- `深业中心发展（深圳有限公司` (缺少右括号)
- `绍兴茶机厂）` (只有右括号)

这些记录会导致：
1. **匹配失败**: ETL 查询使用标准化后的名称，无法匹配到这些不规范记录
2. **数据冗余**: 同一公司可能同时存在规范和不规范的记录

### 6.2 调查结果

#### 6.2.1 数据统计

| 指标 | 数值 |
|------|------|
| 单边括号记录总数 | 878 条 |
| 来自 search_key_word 表 | 837 条 (95.3%) |
| 不在 search_key_word 表 | 41 条 (4.7%) |

#### 6.2.2 来源分析

**search_key_word 表中的单边括号记录分布**:

| 来源 | 数量 | 占比 |
|------|------|------|
| name | 1,642 | 89% |
| search_key_word | 147 | 8% |
| 规模明细 | 54 | 3% |
| **总计** | **1,843** | 100% |

#### 6.2.3 根本原因

**结论：脚本不是问题根源**

用户怀疑的两个脚本：
- `scripts/validation/EQC/process_unfound_keywords.py`
- `scripts/validation/EQC/verify_eqc_enrichment_writeback.py`

经代码追踪验证，这些脚本的数据流为：
1. 从 `search_key_word` 表读取关键词
2. 调用 `EqcProvider.lookup(keyword)` 查询 EQC API
3. `_cache_result()` 方法使用 `normalize_for_temp_id(company_name)` 标准化后写入

**根本原因是 `search_key_word` 表中的源数据本身就有单边括号问题**（1,843 条），脚本只是将这些有问题的数据传递到了 `enrichment_index` 表。

### 6.3 清理执行

#### 6.3.1 备份

```sql
CREATE TABLE enterprise.enrichment_index_single_bracket_backup AS
SELECT * FROM enterprise.enrichment_index
WHERE (lookup_key LIKE '%（%' AND lookup_key NOT LIKE '%）%')
   OR (lookup_key LIKE '%）%' AND lookup_key NOT LIKE '%（%');
-- 备份记录数: 878
```

#### 6.3.2 删除

```sql
DELETE FROM enterprise.enrichment_index
WHERE (lookup_key LIKE '%（%' AND lookup_key NOT LIKE '%）%')
   OR (lookup_key LIKE '%）%' AND lookup_key NOT LIKE '%（%');
```

#### 6.3.3 清理结果

| 指标 | 数值 |
|------|------|
| 已删除记录 | 878 条 |
| 剩余单边括号记录 | 0 条 |
| 当前总记录数 | 36,432 条 |

### 6.4 后续建议

1. **清理 search_key_word 表**: 修复 1,843 条单边括号记录
2. **数据入口校验**: 在写入 `search_key_word` 表时添加括号配对校验
3. **normalize_for_temp_id 增强**: 考虑添加括号配对修复逻辑

---

## 7. 参考文件

- `src/work_data_hub/infrastructure/enrichment/repository/enrichment_index_ops.py`
- `src/work_data_hub/infrastructure/enrichment/repository/core.py`
- `src/work_data_hub/infrastructure/enrichment/normalizer.py`
- `io/schema/migrations/versions/001_initial_infrastructure.py`
