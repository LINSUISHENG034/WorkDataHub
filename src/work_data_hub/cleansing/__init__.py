"""
WorkDataHub 统一数据清洗框架主入口

这个框架解决了数据清洗逻辑重复实现的问题，
提供高复用、可扩展、声明式的数据清洗解决方案。

主要特性:
- 清洗规则自动注册和发现
- 装饰器驱动的声明式清洗
- 与现有 Pydantic 模型无缝集成
- 完全消除重复清洗代码

Usage:
    # 1. 使用便捷装饰器替换重复的 field_validator
    from work_data_hub.cleansing import decimal_fields_cleaner
    
    @decimal_fields_cleaner("期初资产规模", "期末资产规模")
    class MyModel(BaseModel):
        期初资产规模: Optional[Decimal] = None
        期末资产规模: Optional[Decimal] = None
    
    # 2. 使用清洗规则注册表
    from work_data_hub.cleansing import registry
    
    rules = registry.find_by_field_pattern("资产规模")
    
    # 3. 创建自定义清洗规则
    from work_data_hub.cleansing import rule, RuleCategory
    
    @rule(
        name="my_custom_rule",
        category=RuleCategory.STRING,
        description="自定义清洗规则"
    )
    def my_cleaner(value):
        return value.strip().upper()
"""

# 导出主要的公共 API
from .registry import (
    registry,
    rule, 
    RuleCategory,
    CleansingRule,
    CleansingRegistry
)

from .integrations.pydantic_adapter import (
    cleansing_field_validator,
    auto_cleansing_model,
    decimal_fields_cleaner
)

from .rules.numeric_rules import (
    comprehensive_decimal_cleaning,
    remove_currency_symbols,
    handle_percentage_conversion,
    standardize_null_values,
    decimal_quantization,
    annuity_decimal_cleaner,
    trustee_decimal_cleaner
)

# 版本信息
__version__ = "1.0.0"
__author__ = "WorkDataHub Team"

# 公共API
__all__ = [
    # 核心组件
    "registry",
    "rule",
    "RuleCategory", 
    "CleansingRule",
    "CleansingRegistry",
    
    # Pydantic 集成
    "cleansing_field_validator",
    "auto_cleansing_model", 
    "decimal_fields_cleaner",
    
    # 常用清洗规则
    "comprehensive_decimal_cleaning",
    "remove_currency_symbols",
    "handle_percentage_conversion",
    "standardize_null_values",
    "decimal_quantization",
    
    # 预配置清洗器
    "annuity_decimal_cleaner",
    "trustee_decimal_cleaner",
]


def get_framework_info():
    """获取框架信息和统计数据"""
    stats = registry.get_statistics()
    
    return {
        "version": __version__,
        "author": __author__,
        "total_rules": stats["total_rules"],
        "rules_by_category": stats["rules_by_category"],
        "available_categories": [cat.value for cat in RuleCategory],
        "description": "统一数据清洗框架 - 消除重复实现，提高代码复用性"
    }


def list_available_rules():
    """列出所有可用的清洗规则"""
    rules = registry.list_all_rules()
    
    result = []
    for rule_obj in rules:
        result.append({
            "name": rule_obj.name,
            "category": rule_obj.category.value,
            "description": rule_obj.description,
            "field_patterns": rule_obj.field_patterns,
            "applicable_types": [t.__name__ for t in rule_obj.applicable_types],
            "version": rule_obj.version
        })
    
    return result


def find_rules_for_field(field_name: str):
    """查找适用于特定字段的清洗规则"""
    rules = registry.find_by_field_pattern(field_name)
    
    return [
        {
            "name": rule.name,
            "category": rule.category.value,
            "description": rule.description
        }
        for rule in rules
    ]