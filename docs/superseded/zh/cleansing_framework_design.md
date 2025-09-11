"""
统一数据清洗框架架构设计文档

此框架旨在解决WorkDataHub中数据清洗逻辑重复实现的问题，
提供高复用、可扩展、声明式的数据清洗解决方案。

## 框架目录结构

src/work_data_hub/cleansing/
├── __init__.py                 # 框架入口，导出主要API
├── registry.py                 # 清洗规则注册表和发现机制
├── pipeline.py                 # 清洗管道编排引擎
├── decorators.py               # 清洗装饰器（@cleanse, @rule等）
├── tracker.py                  # 清洗过程追踪和审计
├── exceptions.py               # 清洗相关异常定义
├── rules/                      # 清洗规则库
│   ├── __init__.py
│   ├── base.py                 # 清洗规则基类
│   ├── date_rules.py           # 日期清洗规则
│   ├── numeric_rules.py        # 数值清洗规则  
│   ├── string_rules.py         # 字符串清洗规则
│   ├── mapping_rules.py        # 映射填充规则
│   ├── validation_rules.py     # 验证规则
│   └── business_rules.py       # 业务逻辑规则
├── config/                     # 清洗配置
│   ├── __init__.py
│   ├── domain_rules.yml        # 按域的清洗配置
│   ├── field_mappings.yml      # 字段映射配置
│   └── business_mappings.yml   # 业务映射字典
└── integrations/               # 与现有系统的集成
    ├── __init__.py
    ├── pydantic_adapter.py     # Pydantic集成适配器
    └── dagster_adapter.py      # Dagster集成适配器

## 核心特性

### 1. 声明式清洗规则
通过装饰器和配置文件声明清洗需求，而非硬编码清洗逻辑

### 2. 规则注册和自动发现
所有清洗规则自动注册到全局注册表，支持按类型、字段名、业务规则查找

### 3. 管道式组合
多个清洗步骤可以组合成清洗管道，支持条件执行和错误处理

### 4. 完整的追踪机制
记录每个字段的清洗历史，包括应用的规则、前后值变化、时间戳等

### 5. 高度复用性
相同的清洗规则可在多个域、多个字段中复用，避免重复实现

## 使用示例

### 装饰器方式
```python
from work_data_hub.cleansing import cleanse, decimal_rule, date_rule

@cleanse([
    decimal_rule(precision=4, handle_percentage=True),
    currency_symbol_removal(),
    null_value_handler(["", "-", "N/A"])
])
class AssetScale(BaseModel):
    期初资产规模: Optional[Decimal] = None
    期末资产规模: Optional[Decimal] = None
```

### 配置文件方式
```yaml
# domain_rules.yml
annuity_performance:
  financial_fields:
    - 期初资产规模
    - 期末资产规模
  rules:
    - decimal_cleansing:
        precision: 4
        handle_percentage: true
    - currency_symbol_removal
    - null_value_standardization
```

### 管道方式
```python
pipeline = CleansingPipeline([
    "remove_currency_symbols",
    "handle_percentage_conversion", 
    "decimal_quantization",
    "null_value_standardization"
])

cleaned_data = pipeline.process(raw_data, field_config)
```

## 迁移策略

1. **渐进式迁移**: 现有代码可逐步迁移到新框架
2. **向后兼容**: 现有Pydantic validators可无缝集成
3. **性能优化**: 框架设计考虑高性能处理大数据集
4. **测试支持**: 内置测试工具验证清洗规则正确性

这个框架将彻底解决数据清洗重复实现问题，并为未来扩展提供强有力的基础。
"""