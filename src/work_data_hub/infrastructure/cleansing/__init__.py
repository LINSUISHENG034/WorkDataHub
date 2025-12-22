"""
WorkDataHub 统一数据清洗框架主入口 - 简化版本

这个框架解决了数据清洗逻辑重复实现的问题，
提供高复用、可扩展、声明式的数据清洗解决方案。

遵循KISS原则，专注于核心功能：
- 清洗规则注册和基本查找
- 与 Pydantic 模型的简化集成
- 消除重复的 clean_decimal_fields 代码

Usage:
    # 1. 使用便捷装饰器替换重复的 field_validator
    from work_data_hub.infrastructure.cleansing import decimal_fields_cleaner

    @decimal_fields_cleaner("期初资产规模", "期末资产规模")
    class MyModel(BaseModel):
        期初资产规模: Optional[Decimal] = None
        期末资产规模: Optional[Decimal] = None

    # 2. 使用清洗规则注册表
    from work_data_hub.infrastructure.cleansing import registry

    rules = registry.find_by_category(RuleCategory.NUMERIC)

    # 3. 创建自定义清洗规则
    from work_data_hub.infrastructure.cleansing import rule, RuleCategory

    @rule(
        name="my_custom_rule",
        category=RuleCategory.STRING,
        description="自定义清洗规则"
    )
    def my_cleaner(value):
        return value.strip().upper()
"""

from typing import Any, Dict

# 导出主要的公共 API
from work_data_hub.infrastructure.cleansing.integrations.pydantic_adapter import (
    decimal_fields_cleaner,
    simple_field_validator,
)
from work_data_hub.infrastructure.cleansing.registry import (
    CleansingRegistry,
    CleansingRule,
    RuleCategory,
    get_cleansing_registry,
    registry,
    rule,
)
from work_data_hub.infrastructure.cleansing.rules.date_rules import (
    parse_chinese_date_value,
)
from work_data_hub.infrastructure.cleansing.rules.numeric_rules import (
    annuity_decimal_cleaner,
    comprehensive_decimal_cleaning,
    convert_chinese_amount_units,
    decimal_quantization,
    handle_percentage_conversion,
    remove_currency_symbols,
    standardize_null_values,
    trustee_decimal_cleaner,
)
from work_data_hub.infrastructure.cleansing.rules.string_rules import (
    normalize_company_name,
    trim_whitespace,
)

# 版本信息
__version__ = "1.1.0"
__author__ = "WorkDataHub Team"

# 公共API
__all__: list[str] = [
    # 核心组件
    "registry",
    "rule",
    "RuleCategory",
    "CleansingRule",
    "CleansingRegistry",
    "get_cleansing_registry",
    # Pydantic 集成
    "decimal_fields_cleaner",
    "simple_field_validator",
    # 常用清洗规则
    "comprehensive_decimal_cleaning",
    "remove_currency_symbols",
    "handle_percentage_conversion",
    "standardize_null_values",
    "decimal_quantization",
    "convert_chinese_amount_units",
    "trim_whitespace",
    "normalize_company_name",
    "parse_chinese_date_value",
    # 预配置清洗器
    "annuity_decimal_cleaner",
    "trustee_decimal_cleaner",
]


def get_framework_info() -> Dict[str, Any]:
    """获取简化框架信息和统计数据"""
    stats = registry.get_statistics()

    return {
        "version": __version__,
        "author": __author__,
        "total_rules": stats["total_rules"],
        "rules_by_category": stats["rules_by_category"],
        "available_categories": [cat.value for cat in RuleCategory],
        "description": "简化统一数据清洗框架 - 消除重复实现，提高代码复用性",
    }


def list_available_rules() -> Dict[str, Any]:
    """列出所有可用的清洗规则"""
    rules = registry.list_all_rules()

    result = []
    for rule_obj in rules:
        result.append(
            {
                "name": rule_obj.name,
                "category": rule_obj.category.value,
                "description": rule_obj.description,
            }
        )

    return result
