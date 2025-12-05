# Legacy Parity Validation Guide

> **Epic 5 Retrospective** - 验证新架构与 Legacy 系统输出一致性的标准流程

## 概述

在迁移或重构数据处理 Domain 时，确保新架构与 Legacy 系统产生相同的输出是关键验收标准。本指南提供了一套标准化的验证流程和工具。

## Quick Reference

| Domain | 验证脚本 | Legacy 基线 |
|--------|----------|-------------|
| **AnnuityPerformance** | `scripts/tools/parity/validate_annuity_performance_parity.py` | `scripts/tools/run_legacy_annuity_performance_cleaner.py` |
| **AnnuityIncome** | `scripts/tools/parity/validate_annuity_income_parity.py` | `scripts/tools/run_legacy_annuity_income_cleaner.py` |

| Item | Value |
|------|-------|
| **结果目录** | `tests/fixtures/validation_results/` |
| **比较方法** | Set-based 行签名比较 |

## AnnuityIncome Parity Quickstart（Story 5.5.3）
- 前置：5.5-2 域已实现；真实 收入明细 Excel 位于 `tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集/`; legacy mappings 可用；环境 Python 3.12（pandas/pandera/pydantic）。
- 命令：`uv run python scripts/tools/parity/validate_annuity_income_parity.py`
- 成功门槛：除 company_id intentional 差异外 100% 行/列/值匹配；company_id 差异（ID5 去除、plan override 改进）统一延期至 Epic-6 处理，仅记录。
- 产物：legacy/pipeline parquet、json 报告、xlsx 对比 → `tests/fixtures/validation_results/`.
- 若失败：先比对数据源一致性 → 列/映射配置 → 清洗规则 → company_id 解析。

### IO Contract（AnnuityIncome）
- 输入：Excel `收入明细` sheet；必备列 月度, 机构, 机构名称, 计划号, 客户名称, 业务类型, 计划类型, 组合代码, 收入金额（及 cleaner 使用的元数据列）；类型：月度=string date，计划号/组合代码=string，收入金额=numeric。
- 输出：比较列同上；新增 产品线代码、company_id、年金账户名、`_source`、`_source_file`（后两者不比较；company_id 仅做意图差异统计）。
- 配置护栏：`config/data_sources.yml` 中 annuity_income（sheet=收入明细，pattern=`*年金终稿*.xlsx`，version strategy=highest_number）；`src/work_data_hub/infrastructure/cleansing/settings/cleansing_rules.yml` 包含 annuity_income 规则。
- 错误处理：禁止静默丢行；形状/类型不符需显式失败；允许差异（company_id ID5 去除等）须在报告记录。

## 验证脚本架构

### 核心组件

```
scripts/tools/parity/
├── validate_annuity_performance_parity.py   # parity（annuity_performance）
├── validate_annuity_income_parity.py        # parity（annuity_income）
└── common.py                                # shared compare/report utilities

scripts/tools/
├── run_legacy_annuity_performance_cleaner.py # legacy 提取（performance）
└── run_legacy_annuity_income_cleaner.py     # legacy 提取（income）

tests/fixtures/
├── real_data/202412/               # 真实测试数据
├── sample_legacy_mappings.json     # Legacy 映射配置
└── validation_results/             # 验证结果输出
    ├── legacy_output_*.parquet
    ├── pipeline_output_*.parquet
    ├── comparison_report_*.json
    └── comparison_*.xlsx
```

### 验证流程

```
┌─────────────────┐     ┌─────────────────┐
│   Real Data     │     │   Real Data     │
│   (Excel)       │     │   (Excel)       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Legacy Cleaner  │     │  New Pipeline   │
│ (Extracted)     │     │  (Domain)       │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Legacy Output   │     │ Pipeline Output │
│ (DataFrame)     │     │ (DataFrame)     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
            ┌─────────────────┐
            │ Set-based       │
            │ Comparison      │
            └────────┬────────┘
                     ▼
            ┌─────────────────┐
            │ Parity Report   │
            │ (JSON/Excel)    │
            └─────────────────┘
```

## 使用方法

### 1. 运行验证

```bash
cd E:\Projects\WorkDataHub
uv run python scripts/tools/parity/validate_annuity_performance_parity.py
```

### 2. 查看结果

验证完成后，结果保存在 `tests/fixtures/validation_results/`：

- **Parquet 文件**: 用于程序化分析
- **JSON 报告**: 详细的差异统计
- **Excel 文件**: 便于人工审查（含 Legacy、Pipeline、Differences 三个 sheet）

### 3. 解读报告

```json
{
  "summary": {
    "row_count_match": true,
    "column_match": true,
    "data_match": true,
    "overall_parity": true,
    "match_rate": "100.00%",
    "common_rows": 33318,
    "legacy_only_rows": 0,
    "pipeline_only_rows": 0
  }
}
```

| 指标 | 含义 | 目标值 |
|------|------|--------|
| `row_count_match` | 行数是否一致 | `true` |
| `column_match` | 列是否一致（考虑重命名） | `true` |
| `data_match` | 数据内容是否一致 | `true` |
| `overall_parity` | 整体是否达到 parity | `true` |
| `match_rate` | 匹配率 | `100.00%` |

## 为新 Domain 创建验证脚本

### Step 1: 提取 Legacy 清洗逻辑

创建 `scripts/tools/run_legacy_{domain}_cleaner.py`：

```python
"""
Legacy {Domain} Cleaner - 提取自原系统用于 parity 验证
"""
from typing import Any, Dict, List
import pandas as pd

class ExtractedLegacyCleaner:
    """从 legacy 系统提取的清洗逻辑（保持原样）。"""

    def __init__(self, mappings: Dict[str, Any]) -> None:
        self.mappings = mappings

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """执行 legacy 清洗逻辑。"""
        # 复制 legacy 系统的清洗代码
        # 保持原有逻辑，不做优化
        ...
        return df


def canonicalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """标准化 DataFrame 用于比较。"""
    # 排序列名
    df = df.reindex(sorted(df.columns), axis=1)
    # 重置索引
    df = df.reset_index(drop=True)
    return df


def load_mapping_fixture(path: str) -> Dict[str, Any]:
    """加载映射配置。"""
    import json
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

### Step 2: 创建验证脚本

创建 `scripts/tools/validate_{domain}_parity.py`：

```python
#!/usr/bin/env python3
"""
{Domain} Parity Validation Script

验证新 Pipeline 与 Legacy 系统输出一致性。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

# 配置
REAL_DATA_PATH = Path("tests/fixtures/real_data/{period}/{file}.xlsx")
MAPPING_FIXTURE_PATH = Path("tests/fixtures/sample_legacy_mappings.json")
OUTPUT_DIR = Path("tests/fixtures/validation_results")
SHEET_NAME = "数据Sheet名"

# 必要列与比较设置（示例）
REQUIRED_COLUMNS = ["月度", "机构", "机构名称", "计划号", "客户名称", "业务类型", "计划类型", "组合代码", "收入金额"]
EXCLUDED_COLS = ("_source", "_source_file", "company_id")

def load_input() -> pd.DataFrame:
    df = pd.read_excel(REAL_DATA_PATH, sheet_name=SHEET_NAME)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    return df


def compare_dataframes(
    legacy_df: pd.DataFrame,
    pipeline_df: pd.DataFrame
) -> Dict[str, Any]:
    """使用 set-based 方法比较两个 DataFrame。"""

    # 1. 列比较（考虑重命名）
    column_renames = {
        "legacy_col_name": "pipeline_col_name",
    }

    # 2. 排除不参与比较的列
    excluded_cols = EXCLUDED_COLS

    # 3. 创建行签名用于 set 比较
    comparison_cols = [
        col for col in legacy_df.columns
        if col not in excluded_cols
    ]

    # 4. 标准化数据类型
    legacy_norm = legacy_df[comparison_cols].copy()
    pipeline_norm = pipeline_df[comparison_cols].copy()

    for col in comparison_cols:
        legacy_norm[col] = legacy_norm[col].fillna("__NULL__").astype(str)
        pipeline_norm[col] = pipeline_norm[col].fillna("__NULL__").astype(str)

    # 5. 生成行签名
    legacy_norm["_row_sig"] = legacy_norm.apply(
        lambda row: "|".join(row.values), axis=1
    )
    pipeline_norm["_row_sig"] = pipeline_norm.apply(
        lambda row: "|".join(row.values), axis=1
    )

    # 6. Set 比较
    legacy_sigs = set(legacy_norm["_row_sig"].tolist())
    pipeline_sigs = set(pipeline_norm["_row_sig"].tolist())

    common_rows = legacy_sigs.intersection(pipeline_sigs)
    legacy_only = legacy_sigs - pipeline_sigs
    pipeline_only = pipeline_sigs - legacy_sigs

    # 7. 生成报告
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "row_count_match": len(legacy_df) == len(pipeline_df),
            "data_match": len(legacy_only) == 0 and len(pipeline_only) == 0,
            "overall_parity": len(legacy_only) == 0 and len(pipeline_only) == 0,
            "match_rate": f"{len(common_rows) / max(len(legacy_sigs), 1) * 100:.2f}%",
            "common_rows": len(common_rows),
            "legacy_only_rows": len(legacy_only),
            "pipeline_only_rows": len(pipeline_only),
        },
    }
```

### Step 3: 准备测试数据

1. **真实数据**: 放置在 `tests/fixtures/real_data/{period}/`
2. **映射配置**: 创建 `tests/fixtures/sample_legacy_mappings.json`
3. **确保 `.gitignore`**: 排除敏感的真实数据文件

## 常见差异及解决方案

### 1. 日期格式差异

**问题**: Legacy 输出 `2024-12-01 00:00:00`，Pipeline 输出 `2024-12-01`

**解决**: 在比较时标准化日期格式

```python
def normalize_date_value(val: Any) -> str:
    if pd.isna(val):
        return "NaN"
    s = str(val)
    if " 00:00:00" in s:
        s = s.replace(" 00:00:00", "")
    return s
```

### 2. 列名重命名

**问题**: Legacy 使用 `流失(含待遇支付)`，Pipeline 使用 `流失_含待遇支付`

**解决**: 在比较配置中声明等价映射

```python
column_renames = {
    "流失(含待遇支付)": "流失_含待遇支付",
}
```

### 3. 空值处理差异

**问题**: Legacy 保留 `NaN`，Pipeline 生成临时 ID

**解决**: 将该列排除在比较之外（如果是设计改进）

```python
excluded_cols = ("company_id",)  # 设计改进，不参与 parity 比较
```

### 4. 数值类型转换

**问题**: Legacy 对数值列执行字符串操作返回 `NaN`

**解决**: 在 Pipeline 中复现相同行为

```python
# Legacy behavior: str.replace on numeric values converts them to NaN
result = result.apply(
    lambda x: None if (isinstance(x, (int, float)) and not pd.isna(x))
    else x
)
```

### 5. 递归后缀移除

**问题**: Legacy 递归移除多个后缀，Pipeline 只移除一次

**解决**: 使用 while 循环实现递归移除

```python
changed = True
while changed:
    changed = False
    for suffix in SUFFIXES_TO_REMOVE:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            changed = True
            break
```

### 6. Annuity Income Domain 决策

**问题**: Legacy 系统在 `annuity_income` domain 中有 `COMPANY_ID5_MAPPING` fallback 逻辑，但新架构中决定移除。

**解决**: 这是一个架构决策（Architecture Decision），不视为 Parity 失败，而是预期的行为差异。

- **Legacy**: 尝试 ID1 -> ID2 -> ID3 -> ID4 -> **ID5** -> NULL
- **Pipeline**: 尝试 ID1 -> ID2 -> ID3 -> ID4 -> NULL
- **验证**: 在比较时，排除 `company_id` 列的差异，并在报告中单独统计因缺少 ID5 fallback 导致的 NULL 增加数量。

```python
# 在比较脚本中记录差异原因
print(f"Intentionally missing ID5 resolutions: {count_legacy_id5_resolved}")
```

## 验证检查清单

### Pre-Validation

- [ ] Legacy 清洗逻辑已完整提取
- [ ] 真实测试数据已准备
- [ ] 映射配置文件已创建
- [ ] 输出目录已创建

### During Validation

- [ ] 行数匹配
- [ ] 列名匹配（考虑重命名）
- [ ] 数据内容匹配
- [ ] 无 Legacy-only 行
- [ ] 无 Pipeline-only 行

### Post-Validation

- [ ] 100% match rate 达成
- [ ] 差异已记录并解释
- [ ] 设计改进已文档化
- [ ] 验证结果已保存

## 最佳实践

1. **保持 Legacy 代码原样**: 提取时不要优化或重构 Legacy 代码
2. **使用 Set-based 比较**: 避免行顺序敏感的比较方法
3. **记录设计改进**: 明确区分 bug 修复和设计改进
4. **保存验证结果**: 便于后续审计和回归测试
5. **迭代修复**: 从最大差异开始，逐步达到 100% parity

## 相关文档

- [Annuity Performance Runbook](./annuity_performance.md)
- [Pipeline Integration Guide](../architecture-patterns/pipeline-integration-guide.md)
- [Domain Refactoring Design](../specific/domain-design/domain-refactoring-design.md)
