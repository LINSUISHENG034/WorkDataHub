# Domain架构重构设计文档

**文档版本：** 1.0
**日期：** 2025-12-01
**作者：** Winston (Architecture Agent)
**状态：** 设计阶段

---

## 1. 执行摘要

WorkDataHub项目的`annuity_performance`域经过Story 4.7-4.10的优化后，代码仍然高达3,446行，严重阻碍后续域的开发。本文档提出一个全新的**轻量级域架构模式**，将域代码精简至1,000行以内，同时保持功能完整性和扩展性。

### 关键变更
- 将通用功能抽离到基础设施层
- 采用声明式配置替代硬编码
- 实现批量处理取代行级操作
- 为Epic5的company_id扩展预留接口

---

## 2. 背景与问题分析

### 2.1 现状分析

#### 代码分布（总计3,446行）
```
models.py            648行 (19%) - Pydantic模型，含复杂验证器
schemas.py           606行 (18%) - Pandera DataFrame验证（冗余）
processing_helpers.py 852行 (25%) - 行级处理和转换逻辑（核心问题）
pipeline_steps.py    444行 (13%) - Pipeline步骤定义
service.py           387行 (11%) - 服务编排
其他文件            509行 (14%) - 配置、常量、CSV导出等
```

### 2.2 核心问题

1. **验证层冗余**
   - Pydantic和Pandera双重验证
   - 相同的验证逻辑重复实现
   - 维护成本高，易出现不一致

2. **行级处理困境**
   - 852行代码用于逐行处理
   - 违背DataFrame向量化原则
   - 性能瓶颈明显

3. **职责不清晰**
   ```python
   # 现有域承担了过多职责
   - 数据验证（应由Pipeline负责）
   - 行级转换（应由批处理服务负责）
   - 富化调用（应由富化服务负责）
   - CSV导出（应由导出服务负责）
   - 业务逻辑（域的真正职责）✓
   ```

4. **缺乏标准化**
   - 每个新域都需要重新实现相似功能
   - 没有统一的域开发模板
   - 代码复用率低（约20%）

### 2.3 Legacy系统对比

Legacy系统`data_cleaner.py`仅785行就完成了相似功能：
- 使用简单的类继承模式
- 直接的DataFrame操作
- 清晰的职责划分

这证明了精简架构的可行性。

---

## 3. Domain职能重新定位

### 3.1 核心原则

**域应该只负责业务逻辑，而非技术实现细节。**

### 3.2 职责边界

#### Domain保留的职责（核心）
1. **业务规则定义** - 特定于该域的业务逻辑
2. **领域模型** - 业务实体和值对象
3. **业务转换** - 特定于业务的数据转换
4. **业务验证** - 超出数据类型的业务规则验证

#### Domain移除的职责（非核心）
1. **通用数据验证** → Pipeline验证层
2. **行级处理** → 批量处理服务
3. **富化服务调用** → 独立富化服务
4. **数据导出** → 通用导出服务
5. **错误收集** → 统一错误处理器

### 3.3 域的标准接口

```python
class DomainInterface(Protocol):
    """所有域必须实现的标准接口"""

    def process(self, data: pd.DataFrame) -> ProcessingResult:
        """处理数据的唯一入口"""
        pass

    def get_config(self) -> DomainConfig:
        """返回域配置"""
        pass

    def validate_business_rules(self, data: pd.DataFrame) -> ValidationResult:
        """验证业务规则（非数据类型验证）"""
        pass
```

---

## 4. 新架构设计

### 4.1 整体架构

```
work_data_hub/
├── domain/                           # 域层（业务逻辑）
│   ├── annuity_performance/         # 年金业绩域
│   │   ├── models.py               # 业务模型（~200行）
│   │   ├── rules.py                # 业务规则配置（~100行）
│   │   ├── transformers.py         # 业务转换器（~300行）
│   │   ├── service.py              # 服务编排（~200行）
│   │   └── __init__.py             # 接口暴露
│   │
│   └── _templates/                  # 域模板
│       └── cookiecutter/            # 域生成器
│
├── infrastructure/                   # 基础设施层（技术实现）
│   ├── validation/
│   │   ├── dataframe_validator.py  # DataFrame级验证
│   │   ├── batch_model_validator.py # 批量Pydantic验证
│   │   └── validation_rules.py     # 通用验证规则
│   │
│   ├── processing/
│   │   ├── batch_processor.py      # 批量处理框架
│   │   ├── vectorized_ops.py       # 向量化操作库
│   │   └── parallel_executor.py    # 并行执行器
│   │
│   ├── enrichment/
│   │   ├── batch_enrichment_service.py  # 批量富化
│   │   ├── enrichment_cache.py          # 富化缓存
│   │   └── company_id_resolver.py       # company_id解析器（Epic5）
│   │
│   └── export/
│       ├── universal_exporter.py    # 通用导出服务
│       └── export_formats.py        # 导出格式定义
│
└── shared/                          # 共享层
    ├── constants/                   # 全局常量
    ├── mappings/                    # 全局映射表
    └── types/                       # 共享类型定义
```

### 4.2 轻量级域实现示例

#### 4.2.1 业务规则配置（rules.py）
```python
# domain/annuity_performance/rules.py
from typing import Dict, Any

DOMAIN_CONFIG = {
    "name": "annuity_performance",
    "version": "2.0",
    "description": "年金业绩数据处理域",

    # 声明式字段映射
    "field_mappings": {
        "机构": "机构名称",
        "计划号": "计划代码",
        "流失（含待遇支付）": "流失(含待遇支付)"
    },

    # 数据验证规则（声明式）
    "validations": {
        "计划代码": {
            "type": "string",
            "pattern": r"^[PA]\d{4}$",
            "required": True,
            "normalize": "uppercase"
        },
        "月度": {
            "type": "date",
            "format": "%Y-%m-%d",
            "required": True
        },
        "机构代码": {
            "type": "string",
            "enum": ["G00", "G01", "G02", ...],  # 引用全局常量
            "default": "G00"
        }
    },

    # 业务转换规则
    "transformations": [
        {
            "name": "normalize_plan_code",
            "type": "replacement",
            "config": {
                "field": "计划代码",
                "replacements": {
                    "1P0290": "P0290",
                    "1P0807": "P0807"
                }
            }
        },
        {
            "name": "resolve_company_id",
            "type": "multi_level_fallback",
            "config": {
                "target": "company_id",
                "levels": [
                    {"source": "计划代码", "mapping": "COMPANY_ID_BY_PLAN"},
                    {"source": "集团企业客户号", "mapping": "COMPANY_ID_BY_GROUP"},
                    {"source": "客户名称", "mapping": "COMPANY_ID_BY_NAME"},
                    {"default": "600866980"}
                ]
            }
        }
    ],

    # 业务规则（超出数据验证的逻辑）
    "business_rules": [
        {
            "name": "集合计划默认代码",
            "condition": "计划代码.isna() & 计划类型 == '集合计划'",
            "action": {"set": {"计划代码": "AN001"}}
        },
        {
            "name": "单一计划默认代码",
            "condition": "计划代码.isna() & 计划类型 == '单一计划'",
            "action": {"set": {"计划代码": "AN002"}}
        }
    ],

    # Epic5扩展点：company_id增强配置
    "extensions": {
        "company_id": {
            "resolver": "infrastructure.enrichment.company_id_resolver",
            "cache_enabled": True,
            "batch_size": 1000,
            "fallback_strategy": "hierarchical"
        }
    }
}
```

#### 4.2.2 业务模型（models.py）
```python
# domain/annuity_performance/models.py
from decimal import Decimal
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, validator

class AnnuityPerformanceRecord(BaseModel):
    """年金业绩记录模型 - 仅包含业务属性"""

    # 基础标识
    机构代码: str = Field(..., description="机构代码")
    机构名称: str = Field(..., description="机构名称")
    月度: date = Field(..., description="数据月度")

    # 计划信息
    计划代码: str = Field(..., description="年金计划代码")
    计划类型: str = Field(..., description="计划类型：集合/单一")
    组合代码: Optional[str] = Field(None, description="投资组合代码")

    # 客户信息
    客户名称: str = Field(..., description="清洗后的客户名称")
    年金账户名: Optional[str] = Field(None, description="原始年金账户名")
    company_id: str = Field(..., description="统一客户标识")

    # 业务指标
    规模: Decimal = Field(default=Decimal("0"), description="资产规模")
    流入: Decimal = Field(default=Decimal("0"), description="资金流入")
    流出含待遇支付: Decimal = Field(default=Decimal("0"), description="流出(含待遇支付)")

    # 业务分类
    业务类型: str = Field(..., description="业务类型")
    产品线代码: str = Field(..., description="产品线代码")

    class Config:
        # 使用中文字段名
        allow_population_by_field_name = True
        # 优化性能
        validate_assignment = False

    @validator("计划代码")
    def validate_plan_code(cls, v):
        """业务规则：计划代码格式验证"""
        if v and not v.startswith(("P", "A", "AN")):
            raise ValueError(f"无效的计划代码格式: {v}")
        return v
```

#### 4.2.3 业务转换器（transformers.py）
```python
# domain/annuity_performance/transformers.py
import pandas as pd
from typing import Dict, Any

class AnnuityBusinessTransformer:
    """年金业务特定转换器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def apply_portfolio_defaults(self, df: pd.DataFrame) -> pd.DataFrame:
        """应用组合代码默认值业务规则"""
        # 职年业务特殊处理
        mask_zhinian = df['业务类型'].isin(['职年受托', '职年投资'])
        df.loc[mask_zhinian & df['组合代码'].isna(), '组合代码'] = 'QTAN003'

        # 其他业务类型默认值
        portfolio_defaults = {
            '集合计划': 'QTAN001',
            '单一计划': 'QTAN002'
        }

        for plan_type, default_code in portfolio_defaults.items():
            mask = (df['计划类型'] == plan_type) & df['组合代码'].isna()
            df.loc[mask, '组合代码'] = default_code

        return df

    def normalize_institution_codes(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化机构代码"""
        # 替换特殊值
        df['机构代码'] = df['机构代码'].replace(['null', '', None], 'G00')
        df['机构代码'] = df['机构代码'].fillna('G00')

        return df

    def clean_customer_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗客户名称 - 业务规则"""
        # 保存原始名称
        df['年金账户名'] = df['客户名称'].copy()

        # 应用业务清洗规则（向量化）
        df['客户名称'] = df['客户名称'].str.replace(r'[（(].*?[)）]', '', regex=True)
        df['客户名称'] = df['客户名称'].str.strip()

        return df
```

#### 4.2.4 服务编排（service.py）
```python
# domain/annuity_performance/service.py
from typing import Optional
import pandas as pd

from infrastructure.validation import DataFrameValidator
from infrastructure.processing import BatchProcessor
from infrastructure.enrichment import CompanyIdResolver
from .models import AnnuityPerformanceRecord
from .transformers import AnnuityBusinessTransformer
from .rules import DOMAIN_CONFIG

class AnnuityPerformanceService:
    """年金业绩域服务 - 仅编排，不实现技术细节"""

    def __init__(self):
        # 注入基础设施服务
        self.validator = DataFrameValidator()
        self.processor = BatchProcessor()
        self.transformer = AnnuityBusinessTransformer(DOMAIN_CONFIG)
        self.company_resolver = CompanyIdResolver()

    def process(self, df: pd.DataFrame) -> ProcessingResult:
        """处理年金业绩数据"""

        # 1. 应用字段映射（基础设施层）
        df = self.processor.apply_field_mappings(
            df,
            DOMAIN_CONFIG["field_mappings"]
        )

        # 2. 数据验证（基础设施层）
        validation_result = self.validator.validate(
            df,
            DOMAIN_CONFIG["validations"]
        )

        if validation_result.has_critical_errors:
            return ProcessingResult.failure(validation_result.errors)

        # 3. 应用转换规则（基础设施层）
        df = self.processor.apply_transformations(
            df,
            DOMAIN_CONFIG["transformations"]
        )

        # 4. 业务特定转换（域层）
        df = self.transformer.apply_portfolio_defaults(df)
        df = self.transformer.normalize_institution_codes(df)
        df = self.transformer.clean_customer_names(df)

        # 5. company_id解析（基础设施层，Epic5扩展点）
        df = self.company_resolver.resolve_batch(
            df,
            strategy=DOMAIN_CONFIG["extensions"]["company_id"]
        )

        # 6. 批量模型验证（基础设施层）
        models_result = self.processor.to_models(
            df,
            AnnuityPerformanceRecord,
            chunk_size=1000
        )

        return ProcessingResult(
            success=True,
            data=df,
            models=models_result.models,
            errors=validation_result.errors + models_result.errors,
            stats={
                "total_records": len(df),
                "valid_records": len(models_result.models),
                "error_records": len(models_result.errors)
            }
        )

    def get_config(self) -> Dict[str, Any]:
        """返回域配置，供外部系统使用"""
        return DOMAIN_CONFIG
```

### 4.3 基础设施层关键组件

#### 4.3.1 批量处理器
```python
# infrastructure/processing/batch_processor.py
from typing import List, Type, Dict, Any
import pandas as pd
import numpy as np
from pydantic import BaseModel, ValidationError

class BatchProcessor:
    """批量处理框架 - 避免行级操作"""

    def to_models(
        self,
        df: pd.DataFrame,
        model_class: Type[BaseModel],
        chunk_size: int = 1000
    ) -> BatchModelResult:
        """批量转换DataFrame到Pydantic模型"""

        models = []
        errors = []

        # 使用numpy分块，避免逐行处理
        chunks = np.array_split(df, max(1, len(df) // chunk_size))

        for chunk_idx, chunk in enumerate(chunks):
            # 批量转换为字典
            records = chunk.to_dict('records')

            # 使用列表推导式批量创建模型
            chunk_models = []
            chunk_errors = []

            for idx, record in enumerate(records):
                try:
                    model = model_class(**record)
                    chunk_models.append(model)
                except ValidationError as e:
                    error_detail = {
                        'row': chunk_idx * chunk_size + idx,
                        'errors': e.errors(),
                        'data': record
                    }
                    chunk_errors.append(error_detail)

            models.extend(chunk_models)
            errors.extend(chunk_errors)

        return BatchModelResult(models=models, errors=errors)

    def apply_transformations(
        self,
        df: pd.DataFrame,
        transformations: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """应用声明式转换规则"""

        for transform in transformations:
            transform_type = transform["type"]

            if transform_type == "replacement":
                # 向量化替换
                field = transform["config"]["field"]
                replacements = transform["config"]["replacements"]
                df[field] = df[field].replace(replacements)

            elif transform_type == "multi_level_fallback":
                # 多级回退（向量化）
                df = self._apply_fallback_vectorized(df, transform["config"])

        return df

    def _apply_fallback_vectorized(
        self,
        df: pd.DataFrame,
        config: Dict[str, Any]
    ) -> pd.DataFrame:
        """向量化的多级回退实现"""
        target = config["target"]
        df[target] = None

        for level in config["levels"]:
            if "source" in level:
                # 使用向量化映射
                source = level["source"]
                mapping = self._get_mapping(level["mapping"])

                # 仅更新尚未赋值的行
                mask = df[target].isna()
                df.loc[mask, target] = df.loc[mask, source].map(mapping)

            elif "default" in level:
                # 应用默认值
                mask = df[target].isna()
                df.loc[mask, target] = level["default"]

        return df
```

#### 4.3.2 Company ID解析器（Epic5扩展点）
```python
# infrastructure/enrichment/company_id_resolver.py
from typing import Dict, Optional, List
import pandas as pd
from functools import lru_cache

class CompanyIdResolver:
    """Company ID解析器 - Epic5的扩展基础"""

    def __init__(self):
        self.cache = {}
        self.resolution_stats = {
            "total": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "fallbacks": 0
        }

    def resolve_batch(
        self,
        df: pd.DataFrame,
        strategy: Dict[str, Any]
    ) -> pd.DataFrame:
        """批量解析company_id"""

        if strategy.get("cache_enabled"):
            # 预加载缓存
            self._preload_cache(df)

        # 分层解析策略
        if strategy["fallback_strategy"] == "hierarchical":
            df = self._hierarchical_resolution(df, strategy)
        else:
            df = self._simple_resolution(df, strategy)

        return df

    def _hierarchical_resolution(
        self,
        df: pd.DataFrame,
        strategy: Dict[str, Any]
    ) -> pd.DataFrame:
        """分层解析 - 支持Epic5的复杂场景"""

        # Level 1: 计划代码映射（最可靠）
        df['company_id'] = df['计划代码'].map(self._get_plan_mapping())

        # Level 2: 集团客户号映射
        mask = df['company_id'].isna()
        if mask.any():
            df.loc[mask, 'company_id'] = df.loc[mask, '集团企业客户号'].map(
                self._get_group_mapping()
            )

        # Level 3: 客户名称映射
        mask = df['company_id'].isna()
        if mask.any():
            # 批量查询API
            unique_names = df.loc[mask, '客户名称'].unique()
            name_mapping = self._batch_query_by_name(unique_names)
            df.loc[mask, 'company_id'] = df.loc[mask, '客户名称'].map(name_mapping)

        # Level 4: 富化服务（Epic5新增）
        mask = df['company_id'].isna()
        if mask.any() and strategy.get("enrichment_enabled"):
            df = self._enrich_from_external_service(df, mask)

        # Level 5: 默认值
        df['company_id'] = df['company_id'].fillna("600866980")

        return df

    @lru_cache(maxsize=10000)
    def _get_plan_mapping(self) -> Dict[str, str]:
        """获取计划代码映射（带缓存）"""
        # 从配置或数据库加载
        return {
            "P0001": "100000001",
            "P0002": "100000002",
            # ...
        }

    def _batch_query_by_name(
        self,
        names: List[str],
        batch_size: int = 100
    ) -> Dict[str, str]:
        """批量查询客户名称映射"""
        result = {}

        # 分批查询，避免单次查询过大
        for i in range(0, len(names), batch_size):
            batch = names[i:i + batch_size]
            # 模拟API调用
            batch_result = self._call_enrichment_api(batch)
            result.update(batch_result)

        return result
```

---

## 5. 实施计划

### 5.1 阶段划分

#### Phase 1: 基础设施构建（3天）
- Day 1: 创建基础设施层框架
  - 批量处理器
  - DataFrame验证器
  - 通用导出服务

- Day 2: 实现核心组件
  - 向量化操作库
  - 配置解析器
  - 错误处理器

- Day 3: Company ID解析器（Epic5准备）
  - 可扩展的解析框架
  - 缓存机制
  - 批量查询接口

#### Phase 2: annuity_performance重构（2天）
- Day 4: 域结构重组
  - 归档现有代码
  - 创建新的域结构
  - 迁移业务规则

- Day 5: 集成测试
  - 对比测试（新旧版本）
  - 性能测试
  - 回归测试

#### Phase 3: 标准化与模板化（1天）
- Day 6:
  - 创建域开发模板
  - 编写开发指南
  - 建立代码规范

### 5.2 迁移策略

1. **保持数据兼容性**
   - 输入/输出格式不变
   - API接口保持一致
   - 错误格式兼容

2. **渐进式切换**
   ```python
   # 过渡期配置
   MIGRATION_CONFIG = {
       "use_new_architecture": True,
       "fallback_to_legacy": True,
       "comparison_mode": True  # 对比新旧结果
   }
   ```

3. **监控与回滚**
   - 详细的性能指标
   - 结果差异监控
   - 快速回滚机制

---

## 6. 预期成果

### 6.1 量化指标

| 指标 | 现状 | 目标 | 改进 |
|------|------|------|------|
| 域代码总量 | 3,446行 | <1,000行 | -71% |
| 行级处理代码 | 852行 | 0行 | -100% |
| 新域开发时间 | 5-7天 | 1-2天 | -75% |
| 代码复用率 | ~20% | >80% | +300% |
| 测试覆盖率 | 65% | >90% | +38% |
| 处理性能 | 基准 | 3-5x | +400% |

### 6.2 质量提升

1. **可维护性**
   - 清晰的职责边界
   - 声明式配置
   - 标准化接口

2. **可扩展性**
   - Epic5 company_id扩展预留
   - 插件式架构
   - 配置驱动

3. **可测试性**
   - 单元测试友好
   - 模拟数据简单
   - 隔离的业务逻辑

### 6.3 开发效率

新域开发只需：
1. 定义业务模型（~200行）
2. 配置业务规则（~100行）
3. 实现特定转换（~300行）
4. 编排服务（~200行）

总计：<1,000行代码

---

## 7. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 基础设施bug影响所有域 | 高 | 中 | 充分的单元测试；渐进式推广 |
| 性能不如预期 | 中 | 低 | 性能基准测试；优化热点路径 |
| 学习成本 | 中 | 中 | 详细文档；培训；模板 |
| Epic5需求变更 | 中 | 高 | 预留扩展点；插件式设计 |

---

## 8. 结论

本架构重构将彻底解决当前域开发的痛点，通过清晰的职责划分和基础设施复用，将域开发的复杂度降低75%以上。同时为Epic5的company_id扩展预留了清晰的接口，确保架构的长期演进能力。

建议立即启动Phase 1的基础设施建设，为后续的域开发奠定坚实基础。

---

## 附录

### A. 迁移检查清单
- [ ] 基础设施层单元测试覆盖率>95%
- [ ] annuity_performance新旧版本对比测试通过
- [ ] 性能提升验证（>3x）
- [ ] 文档完整性检查
- [ ] 代码评审通过

### B. 参考资料
- Domain-Driven Design, Eric Evans
- Clean Architecture, Robert C. Martin
- Enterprise Integration Patterns, Gregor Hohpe

### C. 术语表
- **域（Domain）**：业务逻辑的封装单元
- **基础设施（Infrastructure）**：技术实现细节
- **向量化（Vectorization）**：DataFrame级别的批量操作
- **声明式（Declarative）**：通过配置而非代码表达逻辑