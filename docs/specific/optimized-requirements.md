# Optimization Requirements

本文档记录 WorkDataHub 项目的优化需求，便于后续迭代实施。

---

## OPT-001: Dry Run 模式失败记录导出功能

### 需求概述

在 Pipeline Dry Run 模式下，导出验证失败的记录到 CSV 文件，便于用户发现和修复数据异常。

### 背景信息

**发现时间：** 2025-12-06 (Epic 5.5 MVP 验证阶段)

**发现场景：**
在执行 `docs/runbooks/mvp-validation-end-to-end.md` Phase 3 (Pipeline Processing Dry Run) 时，发现：
- `annuity_performance` domain: 输入 33,615 行，输出 33,613 行，**2 行失败**
- `annuity_income` domain: 输入 2,631 行，输出 2,631 行，0 行失败

当前系统只记录失败日志（debug 级别），不提供失败记录的详细信息导出，用户无法快速定位数据问题。

### 当前代码分析

**相关文件：**
- `src/work_data_hub/domain/annuity_performance/helpers.py`
- `src/work_data_hub/domain/annuity_income/helpers.py`

**当前行为 (`convert_dataframe_to_models` 函数)：**

```python
def convert_dataframe_to_models(df: pd.DataFrame) -> Tuple[List[Model], List[str]]:
    records = []
    unknown_names = []

    for idx, row in df.iterrows():
        try:
            # 静默跳过缺少必填字段的记录
            if not row_dict.get("计划代码") or row_dict.get("月度") is None:
                continue  # <-- 问题1: 无记录

            record = Model(**row_dict)
            records.append(record)
        except ValidationError as exc:
            # 只记录日志，不保存失败信息
            event_logger.debug("Row validation failed", row_index=idx, error=str(exc))
            # <-- 问题2: 失败记录丢失

    return records, unknown_names
```

**问题总结：**
1. 缺少必填字段的记录被静默跳过，无任何记录
2. ValidationError 只记录到 debug 日志，不返回失败详情
3. 用户无法获取失败记录的原始数据和失败原因

### 功能需求

#### 核心需求

1. **失败记录收集**
   - 收集所有验证失败的记录
   - 记录失败原因（缺少必填字段、类型错误、验证规则失败等）
   - 保留原始行数据便于排查

2. **CSV 导出**
   - 导出失败记录到 CSV 文件
   - 文件命名格式：`failed_records_{domain}_{timestamp}.csv`
   - 导出目录：`logs/` (与 unknown_names CSV 一致)

3. **导出内容**
   - 原始行索引 (`row_index`)
   - 失败原因分类 (`failure_type`: `missing_required_field`, `validation_error`, `unexpected_error`)
   - 详细错误信息 (`error_message`)
   - 原始行数据（关键字段）

#### 可选增强

- 支持配置是否启用导出 (`export_failed_records: bool`)
- 支持配置导出字段列表
- 在 `ProcessingResultWithEnrichment` 中添加 `failed_records_csv` 字段

### 建议实现方案

#### 1. 定义失败记录数据结构

```python
@dataclass
class FailedRecord:
    row_index: int
    failure_type: str  # "missing_required_field" | "validation_error" | "unexpected_error"
    error_message: str
    original_data: Dict[str, Any]  # 关键字段快照
```

#### 2. 修改 `convert_dataframe_to_models` 返回值

```python
def convert_dataframe_to_models(
    df: pd.DataFrame,
) -> Tuple[List[Model], List[str], List[FailedRecord]]:
    records = []
    unknown_names = []
    failed_records = []  # 新增

    for idx, row in df.iterrows():
        try:
            row_dict = {...}
            if not row_dict.get("计划代码") or row_dict.get("月度") is None:
                failed_records.append(FailedRecord(
                    row_index=idx,
                    failure_type="missing_required_field",
                    error_message="缺少必填字段: 计划代码 或 月度",
                    original_data={"计划代码": row_dict.get("计划代码"), "月度": row_dict.get("月度"), "客户名称": row_dict.get("客户名称")},
                ))
                continue

            record = Model(**row_dict)
            records.append(record)
        except ValidationError as exc:
            failed_records.append(FailedRecord(
                row_index=idx,
                failure_type="validation_error",
                error_message=str(exc),
                original_data={"计划代码": row_dict.get("计划代码"), "客户名称": row_dict.get("客户名称")},
            ))

    return records, unknown_names, failed_records
```

#### 3. 添加导出函数

```python
def export_failed_records_csv(
    failed_records: List[FailedRecord],
    data_source: str,
    *,
    export_enabled: bool = True,
) -> Optional[str]:
    if not export_enabled or not failed_records:
        return None

    df = pd.DataFrame([
        {
            "row_index": r.row_index,
            "failure_type": r.failure_type,
            "error_message": r.error_message,
            **r.original_data,
        }
        for r in failed_records
    ])

    csv_path = export_error_csv(
        df,
        filename_prefix=f"failed_records_{data_source}",
        output_dir=Path("logs"),
    )
    return str(csv_path)
```

### 影响范围

**需要修改的文件：**
- `src/work_data_hub/domain/annuity_performance/helpers.py`
- `src/work_data_hub/domain/annuity_performance/service.py`
- `src/work_data_hub/domain/annuity_performance/models.py`
- `src/work_data_hub/domain/annuity_income/helpers.py`
- `src/work_data_hub/domain/annuity_income/service.py`
- `src/work_data_hub/domain/annuity_income/models.py`

**测试覆盖：**
- 单元测试：验证失败记录收集逻辑
- 集成测试：验证 CSV 导出功能
- E2E 测试：验证 Dry Run 模式下的完整流程

### 优先级与排期

- **优先级：** Medium
- **建议排期：** Epic 6 或独立 Story
- **预估工作量：** 2-3 小时

### 验收标准

1. Dry Run 模式执行后，如有失败记录，自动导出到 `logs/failed_records_*.csv`
2. CSV 包含行索引、失败类型、错误信息、原始数据关键字段
3. `ProcessingResultWithEnrichment` 返回 `failed_records_csv` 路径
4. 日志记录导出的失败记录数量和文件路径
5. 单元测试覆盖率 > 80%

---

## OPT-002: normalize_company_name 括号处理 Bug 修复

### 需求概述

`normalize_company_name` 清洗规则在处理包含 `(集团)` 或 `（集团）` 后缀的公司名称时，错误地移除了右括号。

### 背景信息

**发现时间：** 2025-12-06

**发现场景：**
在数据清洗过程中发现公司名称规范化存在 bug。

### 问题复现

| 输入 | 期望输出 | 实际输出 | 问题 |
|------|----------|----------|------|
| 中国机械科学研究总院集团有限公司(集团) | 中国机械科学研究总院集团有限公司（集团） | 中国机械科学研究总院集团有限公司（集团 | ❌ 右括号丢失 |
| 平安银行(集团) | 平安银行（集团） | 平安银行（集团 | ❌ 右括号丢失 |

### 根本原因分析

**相关文件：**
- `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py`

**问题代码位置：** 第 28 行 & 第 77-82 行

**原因：**

1. `_COMPANY_NAME_SUFFIXES_TO_REMOVE` (第 28 行) 包含 `"集合"` 作为需要移除的后缀标记

2. `normalize_company_name` 函数中的正则表达式 (第 77-82 行)：
   ```python
   pattern_end = rf'(?<![\\u4e00-\\u9fff])([\\-\\(\\（]?){re.escape(core_str)}([\\)\\）]?)[\\-\\(\\（\\)\\）]*$'
   ```

3. 处理流程：
   - 输入: `"中国机械科学研究总院集团有限公司(集团)"`
   - 半角括号转全角后: `"中国机械科学研究总院集团有限公司（集团）"`
   - 当遍历到 `core_str = "集合"` 时，正则 `pattern_end` 尝试匹配
   - lookbehind `(?<![\\u4e00-\\u9fff])` 检查前一个字符是否为汉字
   - `（集团）` 中，`（` 不是汉字，所以 lookbehind 通过
   - 正则匹配到 `（集` + 后续内容，错误地移除了 `）`

4. 核心问题：`"集合"` 的 `"集"` 字与 `"（集团）"` 的 `"集"` 字重叠，导致误匹配

### 影响范围

**需要修改的文件：**
- `src/work_data_hub/infrastructure/cleansing/rules/string_rules.py`

**测试覆盖：**
- 添加单元测试用例覆盖 `(集团)` 和 `（集团）` 场景
- 回归测试确保现有清洗逻辑不受影响

### 优先级与排期

- **优先级：** High（数据质量问题）
- **建议排期：** 下一个 Sprint 或 Hotfix
- **预估工作量：** 1-2 小时

### 验收标准

1. `normalize_company_name("中国机械科学研究总院集团有限公司(集团)")` 返回 `"中国机械科学研究总院集团有限公司（集团）"`
2. `normalize_company_name("平安银行(集团)")` 返回 `"平安银行（集团）"`
3. 如果保留 `"集合"` 移除功能，确保 `normalize_company_name("某公司(集合)")` 正确移除 `(集合)`
4. 所有现有单元测试通过
5. 新增测试用例覆盖边界场景

---

## OPT-003: Domain 配置支持 Upsert Keys 设置

### 需求概述

在 Domain 配置文件中支持设置 `upsert_keys`，实现基于组合字段的覆盖写入功能，对齐 Legacy 架构的 `update_based_on_field` 能力。

### 背景信息

**发现时间：** 2025-12-06

**发现场景：**
Legacy 架构通过 `config.annuity_mapping` 表的 `update_based_on_field` 字段（如 `"月度+业务类型"`）支持按组合字段覆盖写入。新 Pipeline 的 `WarehouseLoader` 已支持 `upsert_keys` 参数实现相同功能，但缺少配置层支持。

### 功能对比

| 特性 | Legacy (MySQL) | 新 Pipeline (PostgreSQL) |
|------|----------------|--------------------------|
| 覆盖写入 | ✅ 先删后插 | ✅ `ON CONFLICT DO UPDATE` |
| 组合键支持 | ✅ `"月度+业务类型"` | ✅ `upsert_keys=["月度", "业务类型"]` |
| 原子性 | ❌ 两步操作 | ✅ 单条 SQL |
| 配置方式 | 数据库表 | ⚠️ 需在 Domain 配置中设置 |

### 功能需求

#### 核心需求

1. **Domain 配置文件支持 `upsert_keys`**
   - 每个 Domain 的更新字段相对固定，直接在 Domain 配置文件中设置
   - 使用注释清晰说明用途和字段含义

2. **配置示例**
   ```python
   # src/work_data_hub/domain/annuity_performance/config.py

   # Upsert Keys: 用于覆盖写入的组合字段
   # 当新数据与数据库中已有记录的这些字段值完全匹配时，执行更新而非插入
   # 等同于 Legacy 架构的 update_based_on_field 配置
   UPSERT_KEYS: List[str] = ["月度", "计划代码"]
   ```

3. **Service 层集成**
   - 在 `service.py` 的 `load_to_warehouse` 方法中读取配置并传递给 `WarehouseLoader`

### 数据库约束要求

PostgreSQL 的 `ON CONFLICT` 要求目标表有对应的 **UNIQUE 约束或主键**：

```sql
-- 示例：为 annuity_performance 表添加唯一约束
ALTER TABLE annuity.annuity_performance
ADD CONSTRAINT uq_annuity_performance_month_plan
UNIQUE (月度, 计划代码);
```

### 影响范围

**需要修改的文件：**
- `src/work_data_hub/domain/annuity_performance/config.py` (新增或修改)
- `src/work_data_hub/domain/annuity_performance/service.py`
- `src/work_data_hub/domain/annuity_income/config.py` (新增或修改)
- `src/work_data_hub/domain/annuity_income/service.py`
- 数据库 DDL（添加 UNIQUE 约束）

### 优先级与排期

- **优先级：** Medium
- **建议排期：** Epic 6 或独立 Story
- **预估工作量：** 2-3 小时

### 验收标准

1. 每个 Domain 配置文件包含 `UPSERT_KEYS` 配置项，带清晰注释
2. `WarehouseLoader.load_dataframe()` 正确接收并使用 `upsert_keys`
3. 重复执行 Pipeline 时，相同组合键的记录被更新而非重复插入
4. 数据库表有对应的 UNIQUE 约束
5. 单元测试覆盖 upsert 场景

---

## OPT-004: 新增 Domain 开发指引文档

### 需求概述

总结 Epic 5.5 的实施经验，编写新增 Domain 开发的常规指引文档，为后续 Domain 开发提供标准化流程和最佳实践。

### 背景信息

**发现时间：** 2025-12-06

**发现场景：**
Epic 5.5 完成了 `annuity_performance` 和 `annuity_income` 两个 Domain 的开发，积累了大量实践经验。需要将这些经验文档化，降低后续 Domain 开发的学习成本和出错概率。

### 功能需求

#### 文档内容大纲

1. **Domain 目录结构规范**
   ```
   src/work_data_hub/domain/{domain_name}/
   ├── __init__.py
   ├── config.py          # Domain 配置（含 UPSERT_KEYS）
   ├── models.py          # Pydantic 数据模型
   ├── schemas.py         # Pandera DataFrame Schema
   ├── helpers.py         # 数据转换辅助函数
   ├── service.py         # 业务服务层
   └── assets/            # Dagster Assets 定义
       └── __init__.py
   ```

2. **开发流程 Checklist**
   - [ ] 分析 Legacy 数据源和清洗逻辑
   - [ ] 定义 Pydantic 模型 (`models.py`)
   - [ ] 定义 Pandera Schema (`schemas.py`)
   - [ ] 实现数据转换 (`helpers.py`)
   - [ ] 实现服务层 (`service.py`)
   - [ ] 配置 Upsert Keys (`config.py`)
   - [ ] 定义 Dagster Assets (`assets/`)
   - [ ] 编写单元测试
   - [ ] Legacy Parity 验证
   - [ ] 数据库 DDL（表结构 + UNIQUE 约束）

3. **关键配置说明**
   - `UPSERT_KEYS`: 覆盖写入的组合字段配置
   - Schema 验证规则设计原则
   - 清洗规则复用指南

4. **常见问题与解决方案**
   - 括号处理 Bug（参考 OPT-002）
   - 验证失败记录追踪（参考 OPT-001）
   - Legacy Parity 验证方法

5. **测试策略**
   - 单元测试覆盖要求
   - 集成测试场景
   - E2E 验证流程

### 建议文档位置

```
docs/
├── guides/
│   └── domain-development-guide.md    # 新增 Domain 开发指引
└── specific/
    └── optimized-requirements.md      # 本文档
```

### 优先级与排期

- **优先级：** Medium
- **建议排期：** Epic 5.5 收尾阶段或 Epic 6 启动前
- **预估工作量：** 3-4 小时

### 验收标准

1. 文档覆盖 Domain 开发的完整生命周期
2. 包含可直接复用的代码模板和配置示例
3. 包含 Epic 5.5 的经验教训和最佳实践
4. 新开发者可依据文档独立完成 Domain 开发
5. 文档经过团队 Review 并合入主分支

---

## OPT-005: (预留)

---

**文档版本：** 1.2
**创建日期：** 2025-12-06
**最后更新：** 2025-12-06
