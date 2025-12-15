# 清洗规则迭代优化指引

**Document ID:** GUIDE-CLEANSE-ITER-001
**Version:** 1.1
**Created:** 2025-12-16
**Updated:** 2025-12-16
**Based on:** Sprint Change Proposal 2025-12-14 EQC API Full Coverage 验证经验

> [!TIP]
> 本指引提供 Bash (Linux/macOS) 和 PowerShell (Windows) 两种命令格式。PowerShell 命令以 `# [PS]` 标记。

---

## 概述

本指引描述了一套**正向迭代工作流**，用于持续优化 EQC 数据清洗规则。通过小批量采样验证，快速发现并修复清洗规则中的问题，确保数据质量。

### 核心原则

- **小批量采样**：每次选取 3-5 条记录，避免触碰 API 配额红线
- **端到端验证**：从 API 采集到清洗入库的完整链路验证
- **问题定位优先**：先定位问题字段，再分析规则缺陷
- **增量迭代**：每次修复一类问题，验证后再处理下一类

---

## 工作流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                     清洗规则迭代优化工作流                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Step 1   │───▶│ Step 2   │───▶│ Step 3   │───▶│ Step 4   │      │
│  │ 随机选取  │    │ 批量查询  │    │ 执行清洗  │    │ 检查结果  │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │                                               │             │
│       │                                               ▼             │
│       │                                        ┌──────────┐        │
│       │                                        │ Step 5   │        │
│       │                                        │ 问题定位  │        │
│       │                                        └──────────┘        │
│       │                                               │             │
│       │              ┌──────────┐                     │             │
│       └─────────────│ Step 6   │◀────────────────────┘             │
│                      │ 优化规则  │                                   │
│                      └──────────┘                                   │
│                           │                                         │
│                           ▼                                         │
│                    [返回 Step 1 验证]                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: 随机选取验证样本

### 目标
从 `archive_base_info` 中随机选取 3-5 条记录作为验证样本。

### 操作方法

**方法 A: 使用脚本（推荐）**

```bash
# [Bash]
PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_select_samples.py

# [PS] PowerShell
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_select_samples.py
```

**方法 B: SQL 随机选取并标记**

```sql
-- 清除之前的验证标记
UPDATE enterprise.archive_base_info SET for_check = false WHERE for_check = true;

-- 随机选取 5 条记录并标记
UPDATE enterprise.archive_base_info
SET for_check = true
WHERE company_id IN (
    SELECT company_id FROM enterprise.archive_base_info
    ORDER BY RANDOM()
    LIMIT 5
);

-- 查看选中的记录
SELECT company_id, search_key_word, "companyFullName"
FROM enterprise.archive_base_info
WHERE for_check = true;
```

**方法 C: 按特定条件选取（用于定向测试）**

```sql
-- 选取特定行业/地区的公司
UPDATE enterprise.archive_base_info
SET for_check = true
WHERE company_id IN (
    SELECT company_id FROM enterprise.archive_base_info
    WHERE province = '广东省'  -- 或其他筛选条件
    ORDER BY RANDOM()
    LIMIT 5
);
```

### 注意事项

- **样本数量控制在 3-5 条**，避免消耗过多 API 配额
- **清除旧标记**再选取新样本，保持验证环境干净
- **记录选取的 company_id**，便于后续问题追溯

---

## Step 2: 批量查询 EQC API

### 目标
使用选中记录的 `search_key_word` 调用 EQC API，获取完整数据（search + findDepart + findLabels）。

### 前置检查

```bash
# [Bash] 验证 Token 有效性
PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_check_token.py

# [PS] PowerShell
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_check_token.py

# 如果 Token 失效，重新获取
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.io.auth --capture --save
```

### 执行批量查询

```bash
# [Bash] 使用采集脚本（包含 3 个 API 调用）
PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_acquire.py --delay 1.5

# [PS] PowerShell
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_acquire.py --delay 1.5
```

### 验证采集结果

```sql
-- 检查 base_info 中的原始数据
SELECT
    company_id,
    search_key_word,
    raw_data IS NOT NULL AS has_search,
    raw_business_info IS NOT NULL AS has_biz_info,
    raw_biz_label IS NOT NULL AS has_labels,
    api_fetched_at
FROM enterprise.base_info
WHERE company_id IN (
    SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
);
```

**预期结果**：所有 `has_*` 字段应为 `true`

---

## Step 3: 执行批量清洗

### 目标
将 `base_info` 中的原始 JSONB 数据清洗转换到 `business_info` 和 `biz_label` 表。

### 执行清洗

```bash
# [Bash] 一次性清洗全部表
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
    --table all --batch-size 10

# [PS] PowerShell
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data --table all --batch-size 10

# 单独清洗某个表
# --table business_info 或 --table biz_label
```

### 重新清洗（修复规则后）

```bash
# 使用 --full-refresh 覆盖已有数据
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
    --table business_info --batch-size 10 --full-refresh
```

---

## Step 4: 检查清洗结果

### 目标
对比清洗后的数据与原始数据，识别数据质量问题。

### 使用脚本检查（推荐）

```bash
# [Bash]
PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_check_results.py

# [PS] PowerShell
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_check_results.py
```

脚本输出包含：字段完整性检查、数据类型验证、清洗状态分析。

### 4.1 字段完整性检查（SQL）

```sql
-- 检查关键字段的填充率
SELECT
    COUNT(*) AS total,
    COUNT(company_name) AS has_company_name,
    COUNT(registered_date) AS has_reg_date,
    COUNT(registered_capital) AS has_reg_capital,
    COUNT(legal_person_name) AS has_legal_person,
    COUNT(credit_code) AS has_credit_code,
    COUNT(industry_name) AS has_industry
FROM enterprise.business_info
WHERE company_id IN (
    SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
);
```

**预期结果**：关键字段填充率应接近 100%

### 4.2 数据类型验证

```sql
-- 检查日期和金额字段的转换结果
SELECT
    company_id,
    company_name,
    registered_date,           -- 应为 DATE 类型
    pg_typeof(registered_date) AS date_type,
    registered_capital,        -- 应为 NUMERIC（元）
    pg_typeof(registered_capital) AS capital_type,
    _cleansing_status         -- 查看清洗状态追踪
FROM enterprise.business_info
WHERE company_id IN (
    SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
);
```

### 4.3 清洗状态分析

```sql
-- 分析各字段的清洗状态
SELECT
    company_id,
    _cleansing_status->>'registered_date' AS date_status,
    _cleansing_status->>'registered_capital' AS capital_status,
    _cleansing_status->>'colleagues_num' AS colleagues_status
FROM enterprise.business_info
WHERE company_id IN (
    SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
);
```

**状态值说明**：
- `cleansed` - 成功清洗
- `null_input` - 原始数据为空（数据源问题，非规则问题）
- `parse_failed` - 解析失败（常见于 `colleagues_num` 字段，原始值可能为 "企业选择不公示"）
- `no_rules` - 无匹配规则
- `error:*` - 清洗过程出错

---

## Step 5: 问题定位与分析

### 目标
针对检查中发现的问题，定位具体的清洗规则缺陷。

### 5.1 常见问题类型

| 问题类型 | 症状 | 可能原因 |
|---------|------|---------|
| 字段全为 NULL | 某字段填充率为 0% | 字段名映射错误或嵌套路径错误 |
| 类型转换失败 | `parse_failed` 状态 | 规则链不完整或格式不匹配 |
| 数值异常 | 金额数量级错误 | 单位转换规则缺失（万元→元） |
| 日期格式错误 | 日期解析失败 | 中文日期格式未处理 |
| 非数值字符串 | `parse_failed` | 原始值为文本如 "企业选择不公示"（数据源问题）|

### 5.2 原始数据核对

```sql
-- 查看原始 JSONB 结构
SELECT
    company_id,
    jsonb_pretty(raw_business_info) AS raw_json
FROM enterprise.base_info
WHERE company_id = 'YOUR_PROBLEM_COMPANY_ID'
LIMIT 1;

-- 提取特定字段的原始值
SELECT
    company_id,
    raw_business_info->'businessInfodto'->>'registerCaptial' AS raw_capital,
    raw_business_info->'businessInfodto'->>'registered_date' AS raw_date,
    raw_business_info->'businessInfodto'->>'legal_person_name' AS raw_legal
FROM enterprise.base_info
WHERE company_id IN (
    SELECT company_id FROM enterprise.archive_base_info WHERE for_check = true
);
```

### 5.3 问题诊断脚本

```bash
# [Bash] 诊断单条记录的清洗过程
PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_diagnose.py --company-id YOUR_PROBLEM_COMPANY_ID

# [PS] PowerShell
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_diagnose.py --company-id YOUR_PROBLEM_COMPANY_ID

# 诊断所有 for_check=true 样本
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_diagnose.py --all-samples

# 仅查看原始数据（跳过清洗模拟）
$env:PYTHONPATH="src"; uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_diagnose.py --company-id XXX --raw-only
```

---

## Step 6: 优化清洗规则

### 目标
根据问题分析结果，修复清洗规则并验证。

### 6.1 清洗规则文件位置

```
src/work_data_hub/
├── infrastructure/
│   └── cleansing/
│       ├── business_info_cleanser.py    # 业务信息清洗器
│       ├── biz_label_parser.py          # 标签解析器
│       ├── registry.py                  # 规则注册中心
│       └── rules/
│           └── cleansing_rules.yml      # 规则配置文件
```

### 6.2 常见修复模式

**模式 A: 嵌套字段路径修复**

```python
# 修复前：直接从 raw 读取
raw_date = raw.get("registered_date")

# 修复后：从嵌套对象读取
data = raw.get("businessInfodto", raw)
raw_date = data.get("registered_date")
```

**模式 B: 字段名映射修复**

```python
# 支持多种字段名
raw_capital = data.get("registerCaptial") or data.get("registered_capital")
```

**模式 C: 单位转换规则**

```yaml
# cleansing_rules.yml
eqc_business_info:
  registerCaptial:
    - remove_currency_symbols        # 移除 "元"、"万元"
    - clean_comma_separated_number   # 移除千分位逗号
    - convert_chinese_amount_units   # 万元 → 元
```

**模式 D: 日期格式处理**

```yaml
eqc_business_info:
  registered_date:
    - trim_whitespace
    - parse_chinese_date_value       # 支持 "2015年01月15日" 格式
```

### 6.3 修复后验证

```bash
# 1. 重新清洗（覆盖模式）
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
    --table business_info --batch-size 10 --full-refresh

# 2. 检查清洗结果
# 返回 Step 4 执行检查
```

---

## 完整迭代示例

### 场景：发现 registered_capital 全为 NULL

**Step 1: 选取样本**
```sql
UPDATE enterprise.archive_base_info SET for_check = true
WHERE company_id IN (SELECT company_id FROM enterprise.archive_base_info ORDER BY RANDOM() LIMIT 3);
```

**Step 2: 批量采集**
```bash
PYTHONPATH=src uv run --env-file .wdh_env python scripts/validation/EQC/eqc_iter_acquire.py
```

**Step 3: 执行清洗**
```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data --table business_info
```

**Step 4: 检查结果**
```sql
SELECT company_id, company_name, registered_capital, _cleansing_status->>'registered_capital'
FROM enterprise.business_info WHERE company_id IN (...);
-- 结果：registered_capital 全为 NULL，状态为 "null_input"
```

**Step 5: 问题定位**
```sql
SELECT raw_business_info->'businessInfodto'->>'registerCaptial' AS raw_capital
FROM enterprise.base_info WHERE company_id = '...';
-- 结果：原始值为 "500.00万元"，说明字段读取路径错误
```

**Step 6: 修复规则**
```python
# business_info_cleanser.py
# 修复前
raw_capital = raw.get("registerCaptial")

# 修复后
data = raw.get("businessInfodto", raw)
raw_capital = data.get("registerCaptial") or data.get("registered_capital")
```

**验证修复**
```bash
PYTHONPATH=src uv run --env-file .wdh_env python -m work_data_hub.cli.cleanse_data \
    --table business_info --full-refresh
```

---

## 附录

### A. 验证脚本清单

| 脚本 | 用途 | 指引步骤 |
|------|------|----------|
| `eqc_iter_check_token.py` | 验证 API Token 有效性 | Step 2 前置 |
| `eqc_iter_select_samples.py` | 随机选取验证样本 | Step 1 |
| `eqc_iter_acquire.py` | 批量采集 EQC 数据 | Step 2 |
| `eqc_iter_check_results.py` | 检查清洗结果（完整性+状态） | Step 4 |
| `eqc_iter_diagnose.py` | 诊断单条/全部记录清洗问题 | Step 5 |
| `eqc_iter_validate.py` | API 数据与归档比对验证 | 独立功能 |
| `work_data_hub.cli.cleanse_data` | CLI 清洗工具 | Step 3 |

### B. 清洗状态码参考

| 状态码 | 含义 | 处理建议 |
|--------|------|---------|
| `cleansed` | 成功清洗 | 无需处理 |
| `null_input` | 原始数据为空 | 检查字段路径映射 |
| `parse_failed` | 解析失败 | 检查规则链配置 |
| `no_rules` | 无匹配规则 | 添加新规则 |
| `error:TypeError` | 类型错误 | 检查数据类型转换 |
| `error:KeyError` | 键值错误 | 检查 JSON 结构 |

### C. 相关文档

- [手动验证指南](validation-guides/manual-validation-guide-eqc-api-full-coverage.md)
- [清洗规则配置](../../src/work_data_hub/infrastructure/cleansing/rules/cleansing_rules.yml)
- [API 响应结构文档](api-response-structures.md)

---

*Generated with Claude Code*
