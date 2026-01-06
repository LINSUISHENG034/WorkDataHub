# Domain Comparison Config Implementation Guide

本指南说明如何为验证脚本 `cleaner_compare.py` 添加新的域配置，以完整还原 Legacy 系统行为。

## Architecture Overview

```
scripts/validation/CLI/configs/
├── __init__.py                 # 注册域配置
├── base.py                     # 抽象基类 DomainComparisonConfig
├── annuity_performance.py      # ✅ 正确实现（参考模板）
└── annuity_income.py           # ✅ 已修复（2026-01-06）
```

---

## Correct Implementation Pattern (`annuity_performance`)

### Key Design: Direct Legacy Import

```python
# annuity_performance.py (行 77-86)
def get_legacy_cleaner(self) -> Type:
    """直接导入原始 Legacy Cleaner，连接实时 MySQL"""
    from annuity_hub.data_handler.data_cleaner import AnnuityPerformanceCleaner
    return AnnuityPerformanceCleaner
```

**优势**：
- 使用 MySQL `mapping.组织架构` 表的完整 38 条机构映射
- 完整复现 Legacy 系统的所有映射逻辑

### Required Abstract Methods

| 方法 | 说明 |
|------|------|
| `domain_name` | 域唯一标识符 |
| `sheet_name` | 默认 Excel 工作表名 |
| `numeric_fields` | 零容差数值字段列表 |
| `derived_fields` | 派生字段列表（映射/转换） |
| `get_legacy_cleaner()` | 返回 Legacy Cleaner 类 |
| `build_new_pipeline()` | 构建并执行 New Pipeline |

---

## Legacy Cleaner Dependencies

### MySQL Database Connection

```
mysql+pymysql://root:169828@127.0.0.1:3306/{database}
```

**必需数据库**：
- `mapping` - 包含组织架构、产品线等映射表
- `enterprise` - 包含 company_id 映射表

### Key Mappings (from `legacy/annuity_hub/data_handler/mappings.py`)

| 映射名称 | 数据源 | 用途 |
|---------|-------|------|
| `COMPANY_BRANCH_MAPPING` | `mapping.组织架构` | 机构名称 → 机构代码 |
| `BUSINESS_TYPE_CODE_MAPPING` | `mapping.产品线` | 业务类型 → 产品线代码 |
| `COMPANY_ID1_MAPPING` | `mapping.年金计划` | 计划号 → company_id |
| `COMPANY_ID2_MAPPING` | `enterprise.annuity_account_mapping` | 账户号 → company_id |
| `COMPANY_ID3_MAPPING` | 硬编码 | 特殊计划代码映射 |
| `COMPANY_ID4_MAPPING` | `enterprise.company_id_mapping` | 客户名称 → company_id |
| `COMPANY_ID5_MAPPING` | `business.规模明细` | 年金账户名 → company_id |

---

## Adding New Domain Config

### Step 1: Create Config File

```python
# configs/new_domain.py
from .base import DomainComparisonConfig

class NewDomainConfig(DomainComparisonConfig):
    @property
    def domain_name(self) -> str:
        return "new_domain"
    
    @property
    def sheet_name(self) -> str:
        return "sheet_name"
    
    @property
    def numeric_fields(self) -> List[str]:
        return ["field1", "field2"]
    
    @property
    def derived_fields(self) -> List[str]:
        return ["月度", "机构代码"]
    
    def get_legacy_cleaner(self) -> Type:
        # ✅ 直接导入 Legacy Cleaner
        from annuity_hub.data_handler.data_cleaner import NewDomainCleaner
        return NewDomainCleaner
    
    def build_new_pipeline(self, ...):
        # 参考 annuity_performance 实现
        ...

def _register():
    from . import DOMAIN_CONFIGS
    DOMAIN_CONFIGS["new_domain"] = NewDomainConfig

_register()
```

### Step 2: Register in `__init__.py`

```python
# configs/__init__.py
from .new_domain import NewDomainConfig  # 触发 _register()
```

---

## Anti-Pattern: Fixture-Based Approach

```python
# ❌ 不推荐：使用静态 fixture 文件
MAPPING_FIXTURE_PATH = project_root / "tests/fixtures/sample_legacy_mappings.json"
mappings = load_mapping_fixture(MAPPING_FIXTURE_PATH)
```

**问题**：
- Fixture 数据不完整（仅 9 条 vs MySQL 38 条）
- 无法反映实时数据库状态
- 导致验证结果不准确

---

## Verification Command

```bash
uv run --env-file .wdh_env python scripts/validation/CLI/cleaner_compare.py \
    --domain {domain_name} --month 202412 --file-selection newest --limit 100
```

---

## Troubleshooting Guide

### Issue 1: Legacy Cleaner 不接受 `sheet_name` 参数

**症状**：
```
TypeError: AbstractCleaner.__init__() got an unexpected keyword argument 'sheet_name'
```

**原因**：部分 Legacy Cleaner（如 `AnnuityIncomeCleaner`）不接受 `sheet_name` 参数，验证框架统一传递了该参数。

**解决方案**：创建适配器类包装原始 Cleaner：

```python
def get_legacy_cleaner(self) -> Type:
    from annuity_hub.data_handler.data_cleaner import AnnuityIncomeCleaner

    class AnnuityIncomeCleanerAdapter(AnnuityIncomeCleaner):
        def __init__(self, path, sheet_name: str = "收入明细"):
            super().__init__(path)  # 忽略 sheet_name

    return AnnuityIncomeCleanerAdapter
```

---

### Issue 2: Excel 列名与 Legacy Cleaner 期望不匹配

**症状**：
```
Error: 'company_id'
Legacy cleaner returned empty DataFrame - internal error
```

**诊断步骤**：
1. 检查 Excel 实际列名：
   ```python
   df = pd.read_excel(path, sheet_name='xxx', nrows=5)
   print(list(df.columns))
   ```
2. 对比 Legacy Cleaner 期望的列名

**案例**：`annuity_income` 域
- Excel 使用：`计划代码`
- Legacy 期望：`计划号`

**解决方案**：修改 Legacy Cleaner 添加列名重命名逻辑：

```python
# legacy/annuity_hub/data_handler/data_cleaner.py
df.rename(columns={
    "计划号": "计划代码",  # 兼容两种格式
}, inplace=True)

# 使用统一的列名
df = self._update_company_id(df, plan_code_col="计划代码", ...)
```

---

### Issue 3: 机构代码大量为 "G00"

**症状**：派生字段 `机构代码` 比较结果大量差异，Legacy 输出为 `G00`。

**原因**：
1. 使用了静态 fixture 文件（`sample_legacy_mappings.json`）
2. Fixture 仅包含 9 条映射，而 MySQL 有 38 条

**诊断**：
```bash
uv run python -c "
import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', 
                       password='169828', database='mapping')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM 组织架构')
print('MySQL 记录数:', cursor.fetchone()[0])
"
```

**解决方案**：改用直接导入 Legacy Cleaner（连接实时 MySQL）。

---

### Issue 4: 缺少 Legacy 依赖

**症状**：
```
ModuleNotFoundError: No module named 'pypac'
```

**解决方案**：
```bash
uv pip install pypac
```

**注意**：Legacy 系统可能依赖特定包，首次运行时需按需安装。
