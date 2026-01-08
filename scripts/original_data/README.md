# Original Data Generation Guide

> **目标**: 从Legacy数据库导出原始数据并清洗，为New Pipeline生成Bronze层输入。

> **⚠️ 重要**: 如使用2026-01-08之前的版本导出的数据，请重新运行脚本以获取完整数据（见下文"已知问题"）。

---

## 📋 概述

本目录包含从Legacy PostgreSQL导出原始数据并清洗的脚本，清洗后的数据将通过New Pipeline ETL生成标准化种子数据。

### 可用脚本

| 脚本 | 源表 | 目标域 | 说明 |
|------|------|--------|------|
| `generate_annuity_performance_original_data.py` | `business.规模明细` | `annuity_performance` | 年金绩效数据 |
| `generate_annuity_income_original_data.py` | `business.收入明细` | `annuity_income` | 年金收入数据 |

### 核心理念

**为什么需要构建种子数据？**

Legacy数据已经过Legacy系统的清洗和处理，而New Pipeline有更先进的处理模块（如升级的`customer_name_normalize`）。为了保证种子数据与未来新数据使用**相同的处理口径**，我们需要：

1. **导出原始数据** - 从Legacy MySQL获取源数据
2. **清洗数据** - 移除Legacy处理痕迹，准备让New Pipeline重新处理
3. **执行New Pipeline ETL** - 使用统一的标准化流程生成种子数据

### 数据流程

```
Legacy PostgreSQL (business.规模明细 / business.收入明细)
    ↓ [导出]
Raw CSV - 保留所有原始Legacy数据
    ↓ [清洗]
Cleaned CSV - Bronze层输入
    ↓ [New Pipeline ETL]
Standardized Data - Silver/Gold种子数据
```

---

## 🚀 快速开始

### Annuity Performance (规模明细)

```bash
# 完整流程（导出+清洗）
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_performance_original_data.py

# 指定输出路径
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_performance_original_data.py \
    -o data/seed_data/annuity_performance.csv

# 测试模式（限制行数）
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_performance_original_data.py --limit 10000
```

### Annuity Income (收入明细)

```bash
# 完整流程（导出+清洗）
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_income_original_data.py

# 指定输出路径
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_income_original_data.py \
    -o data/seed_data/annuity_income.csv

# 测试模式（限制行数）
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_income_original_data.py --limit 10000
```

---

## 📖 命令行参数

两个脚本使用相同的参数结构：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-o, --output` | 清洗后数据输出路径（raw文件自动生成`_raw`后缀） | `data/seed_data/<domain>_<timestamp>.csv` |
| `-i, --input` | 输入CSV路径（`--clean-only`模式必需） | - |
| `--export-only` | 仅导出数据，跳过清洗 | - |
| `--clean-only` | 仅清洗数据，跳过导出 | - |
| `-b, --batch-size` | 每批导出行数 | 50000 |
| `-l, --limit` | 最大导出行数 | 全部 |

### 输出文件命名规则

当指定 `-o data/seed_data/my_output.csv` 时：
- **Cleaned文件**: `data/seed_data/my_output.csv`
- **Raw文件**: `data/seed_data/my_output_raw.csv`（自动生成）

---

## 🔍 数据清洗规则

### Annuity Performance (规模明细) 清洗步骤

| 步骤 | 操作 | 说明 |
|------|------|------|
| Step 0 | 清空"GM"开头的`年金账户号` | Legacy自定义清洗数据，New Pipeline已移除此逻辑 |
| Step 1 | 填充缺失的`年金账户名` | 使用`客户名称`填充空值 |
| Step 2 | 用`年金账户名`替换`客户名称` | 保留最原始的客户名称数据 |
| Step 3 | 删除`年金账户名`列 | 数据已合并到`客户名称` |
| Step 4 | 删除`company_id`和`产品线代码` | New Pipeline重新判定 |
| Step 5 | `年金账户号` → `集团企业客户号` | 字段重命名 |
| Step 6 | 重置`G00`机构代码为NULL | New Pipeline重新判定 |
| Step 7 | `流失(含待遇支付)` → `流失_含待遇支付` | 统一字段名格式 |

### Annuity Income (收入明细) 清洗步骤

| 步骤 | 操作 | 说明 |
|------|------|------|
| Step 1 | 填充缺失的`年金账户名` | 使用`客户名称`填充空值 |
| Step 2 | 用`年金账户名`替换`客户名称` | 保留最原始的客户名称数据 |
| Step 3 | 删除`年金账户名`列 | 数据已合并到`客户名称` |
| Step 4 | 删除`company_id`和`产品线代码` | New Pipeline重新判定 |
| Step 5 | 重置`G00`机构代码为NULL | New Pipeline重新判定 |

> **注意**: `收入明细`表没有`年金账户号`字段，因此不需要GM清洗和字段重命名步骤。

---

## 🔧 环境配置

### 数据库连接

脚本从`.wdh_env`文件读取Legacy数据库配置：

```bash
# .wdh_env 文件中的配置
LEGACY_DATABASE__URI=postgres://user:password@host:port/database
```

优先级：
1. 环境变量 `LEGACY_DATABASE__URI`
2. `.wdh_env` 文件
3. `work_data_hub.config.settings` 模块

---

## 🎯 下一步：执行New Pipeline ETL

清洗完成后，将清洗后的CSV作为Bronze层输入，执行New Pipeline ETL：

```bash
# Annuity Performance
mv data/seed_data/annuity_performance.csv data/bronze/annuity_performance/
uv run work-data-hub etl execute annuity_performance

# Annuity Income
mv data/seed_data/annuity_income.csv data/bronze/annuity_income/
uv run work-data-hub etl execute annuity_income
```

---

## ⚠️ 已知问题

### 数据导出不完整（已修复）

**问题描述**: 2026-01-08版本的导出脚本存在bug，导致早期数据（如2022年）导出不完整。

**根本原因**: 导出脚本在批量读取数据时未使用`ORDER BY id`，PostgreSQL按物理存储顺序返回数据，跳过了ID较小的早期记录。

**影响范围**:
- `generate_annuity_performance_original_data.py`: 2022年数据只导出了65条（实际3,517条）
- `generate_annuity_income_original_data.py`: 同样问题

**解决方案**: 已在batch query中添加`ORDER BY id`子句，确保按ID顺序完整导出所有数据。

**修复版本**: 2026-01-08 v1.3

**数据重新导出**: 如使用旧版本导出的数据，请重新运行脚本：

```bash
# 重新导出 annuity_performance
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_performance_original_data.py \
    -o "tests/fixtures/real_data/Legacy Database Data/"

# 重新导出 annuity_income
uv run --env-file .wdh_env python scripts/original_data/generate_annuity_income_original_data.py \
    -o "tests/fixtures/real_data/Legacy Database Data/"
```

**验证方法**: 检查导出的raw文件，确认各年份数据完整性：

```python
import pandas as pd

df = pd.read_csv('annuity_performance_raw.csv')
df['年'] = pd.to_datetime(df['月度']).dt.year
print(df['年'].value_counts().sort_index())
```

预期2022年应有3,517条记录。

---

## 📝 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-01-08 | 1.0 | 初始版本，创建annuity_performance脚本 |
| 2026-01-08 | 1.1 | 简化参数，添加GM清洗步骤 |
| 2026-01-08 | 1.2 | 添加annuity_income脚本，更新README |
| 2026-01-08 | 1.3 | **[Bug修复]** 添加`ORDER BY id`确保数据完整性 |

---

**创建时间**: 2026-01-08
**维护者**: Seed Data Generator
