# 计划代码和组合代码处理一致性分析

**分析日期**: 2026-01-02
**分析范围**: `annuity_performance` 和 `annuity_income` 域
**问题类型**: 代码重复、违反 DRY 原则、未完全实现单点真实来源（SSOT）

---

## 执行摘要

`annuity_performance` 和 `annuity_income` 两个域对于计划代码（计划代码）和组合代码（组合代码）的处理存在**部分一致性**问题：

- ✅ **组合代码常量**：已提升到 infrastructure 层，两个域共享
- ⚠️ **组合代码处理函数**：两个域各自实现，逻辑相同但代码重复
- ❌ **计划代码常量**：两个域存在重复定义，未提升到 infrastructure 层
- ❌ **计划代码处理函数**：两个域存在完全相同的重复实现

---

## 1. 组合代码（组合代码）处理

### 1.1 常量定义 - ✅ 已提升到 infrastructure 层

| 常量名称 | 值 | 位置 |
|---------|---|------|
| `DEFAULT_PORTFOLIO_CODE_MAPPING` | `{"集合计划": "QTAN001", "单一计划": "QTAN002", "职业年金": "QTAN003"}` | infrastructure/mappings/shared.py:33-37 |
| `PORTFOLIO_QTAN003_BUSINESS_TYPES` | `("职年受托", "职年投资")` | infrastructure/mappings/shared.py:41 |

**引用方式**：
```python
# annuity_performance/constants.py:9
from work_data_hub.infrastructure.mappings import DEFAULT_PORTFOLIO_CODE_MAPPING

# annuity_income/constants.py:9
from work_data_hub.infrastructure.mappings import DEFAULT_PORTFOLIO_CODE_MAPPING
```

**状态**: ✅ **符合 SSOT 原则**

### 1.2 处理函数 - ⚠️ 代码重复

| 域 | 函数 | 位置 | 代码行数 |
|---|------|------|---------|
| annuity_performance | `_apply_portfolio_code_defaults()` | pipeline_builder.py:61-96 | 36 行 |
| annuity_income | `_apply_portfolio_code_defaults()` | pipeline_builder.py:130-165 | 36 行 |

**实现对比**：

**annuity_performance** (pipeline_builder.py:61-96):
- 使用 `_clean_portfolio_code()` 辅助函数清理每个值
- 处理逻辑：
  1. 保留数值类型（如 12345）
  2. 字符串：去空格、移除 'F'/'f' 前缀
  3. 职年受托/职年投资 → QTAN003
  4. 其他：按计划类型默认值

**annuity_income** (pipeline_builder.py:130-165):
- 使用 pandas 链式操作 `str.replace('^f', '', regex=True).str.upper()`
- 处理逻辑：
  1. 正则替换 '^F' 前缀（大小写不敏感）
  2. 职年受托/职年投资 → QTAN003
  3. 其他：按计划类型默认值

**一致性评估**: ⚠️ **业务逻辑一致，实现方式略有差异**

---

## 2. 计划代码（计划代码）处理

### 2.1 常量定义 - ❌ 重复定义

| 常量名称 | 值 | annuity_performance | annuity_income |
|---------|---|-------------------|----------------|
| `PLAN_CODE_CORRECTIONS` | `{"1P0290": "P0290", "1P0807": "P0807"}` | constants.py:43 | constants.py:30 |
| `PLAN_CODE_DEFAULTS` | `{"集合计划": "AN001", "单一计划": "AN002"}` | constants.py:44 | constants.py:33 |

**问题**：
- 两个域的 constants.py 中都定义了相同的值
- 违反 DRY（Don't Repeat Yourself）原则
- 未实现单点真实来源（SSOT）

### 2.2 处理函数 - ❌ 完全重复

| 域 | 函数 | 位置 | 代码行数 |
|---|------|------|---------|
| annuity_performance | `_apply_plan_code_defaults()` | pipeline_builder.py:41-58 | 18 行 |
| annuity_income | `_apply_plan_code_defaults()` | pipeline_builder.py:108-127 | 20 行 |

**实现对比**：

两个域的实现**完全相同**（Story 7.3-6 注释确认 annuity_income 是从 annuity_performance 复制的）：

```python
def _apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
    """Apply default plan codes based on plan type (legacy parity)."""
    if "计划代码" not in df.columns:
        return pd.Series([None] * len(df), index=df.index)

    result = df["计划代码"].copy()

    if "计划类型" in df.columns:
        empty_mask = result.isna() | (result == "")
        collective_mask = empty_mask & (df["计划类型"] == "集合计划")
        single_mask = empty_mask & (df["计划类型"] == "单一计划")

        result = result.mask(collective_mask, "AN001")
        result = result.mask(single_mask, "AN002")

    return result
```

**一致性评估**: ❌ **代码完全重复，应提升到 infrastructure 层**

---

## 3. Pipeline 应用对比

### 3.1 组合代码处理步骤

| 域 | Pipeline 步骤 | 位置 |
|---|-------------|------|
| annuity_performance | Step 8: CalculationStep | pipeline_builder.py:270-275 |
| annuity_income | Step 7: CalculationStep | pipeline_builder.py:322-327 |

### 3.2 计划代码处理步骤

| 域 | Pipeline 步骤 | 位置 |
|---|-------------|------|
| annuity_performance | Step 3: ReplacementStep<br>Step 4: CalculationStep | pipeline_builder.py:236<br>pipeline_builder.py:238-242 |
| annuity_income | Step 2.5: ReplacementStep<br>Step 2.6: CalculationStep | pipeline_builder.py:275<br>pipeline_builder.py:277 |

---

## 4. 影响分析

### 4.1 维护成本

- **常量重复**：如果需要添加新的计划代码修正（如 `PLAN_CODE_CORRECTIONS`），需要同时修改两个域的 constants.py
- **函数重复**：如果计划代码默认值逻辑变更，需要同时修改两个域的 pipeline_builder.py
- **测试成本**：相同的逻辑需要在两个域中分别测试

### 4.2 一致性风险

- 历史记录显示，annuity_income 在 Story 7.3-6 时从 annuity_performance 复制了代码
- 如果未来只修改一个域，会导致两个域的行为不一致
- 新增域时需要重复实现相同逻辑

### 4.3 代码量统计

| 组件 | 重复代码量 | 潜在节省 |
|-----|----------|---------|
| `PLAN_CODE_CORRECTIONS` 常量 | 2 行定义 × 2 域 | ~50% |
| `PLAN_CODE_DEFAULTS` 常量 | 2 行定义 × 2 域 | ~50% |
| `_apply_plan_code_defaults()` | 18-20 行 × 2 域 | ~50% |
| `_apply_portfolio_code_defaults()` | 36 行 × 2 域 | ~50% |

**总计**：约 120-140 行重复代码可被消除

---

## 5. 改进建议

### 5.1 短期方案（Story 7.3-2 或后续 Story）

**目标**：将计划代码相关常量和函数提升到 infrastructure 层

**实施步骤**：

1. **在 `infrastructure/mappings/shared.py` 中添加常量**：
   ```python
   # Plan code corrections (typo fixes)
   PLAN_CODE_CORRECTIONS: Dict[str, str] = {
       "1P0290": "P0290",
       "1P0807": "P0807",
   }

   # Plan code defaults based on plan type
   PLAN_CODE_DEFAULTS: Dict[str, str] = {
       "集合计划": "AN001",
       "单一计划": "AN002",
   }
   ```

2. **在 `infrastructure/transforms/` 中创建共享函数**：
   ```python
   # infrastructure/transforms/plan_portfolio_helpers.py
   def apply_plan_code_defaults(df: pd.DataFrame) -> pd.Series:
       """Apply default plan codes based on plan type."""
       # ... 实现逻辑 ...

   def apply_portfolio_code_defaults(df: pd.DataFrame) -> pd.Series:
       """Apply default portfolio codes based on business type and plan type."""
       # ... 实现逻辑 ...
   ```

3. **更新两个域的导入**：
   ```python
   # annuity_performance/constants.py
   from work_data_hub.infrastructure.mappings import (
       PLAN_CODE_CORRECTIONS,
       PLAN_CODE_DEFAULTS,
   )

   # annuity_income/constants.py
   from work_data_hub.infrastructure.mappings import (
       PLAN_CODE_CORRECTIONS,
       PLAN_CODE_DEFAULTS,
   )
   ```

4. **删除重复定义**：
   - annuity_performance/constants.py:43-44
   - annuity_income/constants.py:30-33

5. **更新 pipeline_builder.py**：
   - 导入共享函数
   - 删除本地 `_apply_plan_code_defaults()` 和 `_apply_portfolio_code_defaults()` 函数

### 5.2 长期方案

**考虑创建 `DomainCodeNormalizer` 类**：

```python
# infrastructure/enrichment/domain_code_normalizer.py
class DomainCodeNormalizer:
    """Centralized code normalization for plan and portfolio codes."""

    @staticmethod
    def normalize_plan_codes(df: pd.DataFrame) -> pd.DataFrame:
        """Apply corrections and defaults to plan codes."""
        # Step 1: Apply corrections
        # Step 2: Apply defaults based on plan type
        return df

    @staticmethod
    def normalize_portfolio_codes(df: pd.DataFrame) -> pd.DataFrame:
        """Apply cleaning and defaults to portfolio codes."""
        # Step 1: Clean codes (remove prefix, handle numeric)
        # Step 2: Apply defaults based on business type and plan type
        return df
```

**优势**：
- 更高的抽象层次
- 统一的代码规范化接口
- 便于添加新的规范化规则

---

## 6. 对齐 Multi-Domain Checklist

根据 `docs/specific/multi-domain/new-domain-checklist.md`，本分析发现的问题对应以下检查项：

- [ ] **验证器共享**: 计划代码和组合代码的处理逻辑应共享
- [x] **常量提取**: 组合代码常量已提取到 infrastructure 层
- [ ] **常量提取**: 计划代码常量未提取到 infrastructure 层
- [ ] **函数复用**: 计划代码处理函数未复用
- [ ] **函数复用**: 组合代码处理函数未复用

---

## 7. 相关 Stories

- **Story 5.5.4**: 组合代码常量提升到 infrastructure 层（已完成）
- **Story 7.3-2**: 提取共享验证器到 infrastructure 层（部分完成）
- **Story 7.3-6**: annuity_income 与 annuity_performance 对齐（添加了计划代码处理）

**建议新增 Story**：
- **Story 7.3-X**: 消除计划代码和组合代码处理的重复代码
  - 将 `PLAN_CODE_CORRECTIONS` 和 `PLAN_CODE_DEFAULTS` 提升到 infrastructure 层
  - 创建共享的代码规范化函数
  - 更新两个域以使用共享实现

---

## 8. 附录：代码位置索引

### 8.1 组合代码相关

| 组件 | 文件路径 | 行号 |
|-----|---------|-----|
| `DEFAULT_PORTFOLIO_CODE_MAPPING` | infrastructure/mappings/shared.py | 33-37 |
| `PORTFOLIO_QTAN003_BUSINESS_TYPES` | infrastructure/mappings/shared.py | 41 |
| annuity_performance 导入 | domain/annuity_performance/constants.py | 9 |
| annuity_income 导入 | domain/annuity_income/constants.py | 9 |
| annuity_performance 函数 | domain/annuity_performance/pipeline_builder.py | 61-96 |
| annuity_income 函数 | domain/annuity_income/pipeline_builder.py | 130-165 |

### 8.2 计划代码相关

| 组件 | 文件路径 | 行号 |
|-----|---------|-----|
| annuity_performance PLAN_CODE_CORRECTIONS | domain/annuity_performance/constants.py | 43 |
| annuity_performance PLAN_CODE_DEFAULTS | domain/annuity_performance/constants.py | 44 |
| annuity_income PLAN_CODE_CORRECTIONS | domain/annuity_income/constants.py | 30 |
| annuity_income PLAN_CODE_DEFAULTS | domain/annuity_income/constants.py | 33 |
| annuity_performance 函数 | domain/annuity_performance/pipeline_builder.py | 41-58 |
| annuity_income 函数 | domain/annuity_income/pipeline_builder.py | 108-127 |

---

**文档状态**: 🟡 待处理
**优先级**: P1（影响代码可维护性）
**建议 Story**: Story 7.3-X（多域一致性改进）
