"""
Pydantic 集成适配器

提供清洗框架与 Pydantic 模型的无缝集成，
让开发者可以用声明式的方式替换现有的重复 field_validators。
"""

import logging
from typing import Any, Dict, List, Optional, Set, Union, get_type_hints
from functools import wraps

from pydantic import field_validator, ValidationInfo
from pydantic._internal._model_construction import complete_model_class

from ..registry import registry, CleansingRule
from ..rules.numeric_rules import comprehensive_decimal_cleaning

logger = logging.getLogger(__name__)


def cleansing_field_validator(*field_names: str, rules: Optional[List[str]] = None, mode: str = "before"):
    """
    清洗框架增强的 field_validator 装饰器
    
    自动查找和应用适用的清洗规则，替代手动编写重复的 field_validator 逻辑
    
    Args:
        field_names: 字段名列表
        rules: 明确指定要应用的清洗规则名称列表
        mode: Pydantic 验证模式
        
    Example:
        @cleansing_field_validator("期初资产规模", "期末资产规模", rules=["comprehensive_decimal_cleaning"])
        @classmethod
        def clean_financial_fields(cls, v, info):
            # 自动应用清洗规则，无需手动实现
            pass
    """
    def decorator(func):
        @field_validator(*field_names, mode=mode)
        @classmethod
        @wraps(func)
        def wrapper(cls, v, info: ValidationInfo):
            field_name = info.field_name or ""
            
            # 如果明确指定了规则，使用指定的规则
            if rules:
                applied_rules = []
                for rule_name in rules:
                    rule = registry.find_by_name(rule_name)
                    if rule:
                        applied_rules.append(rule)
                    else:
                        logger.warning(f"Rule '{rule_name}' not found in registry")
            else:
                # 自动发现适用的清洗规则
                applied_rules = registry.find_by_field_pattern(field_name)
            
            # 应用清洗规则
            cleaned_value = v
            for rule in applied_rules:
                try:
                    # 根据规则函数签名调用
                    if rule.name == "comprehensive_decimal_cleaning":
                        cleaned_value = rule.func(cleaned_value, field_name=field_name)
                    else:
                        cleaned_value = rule.func(cleaned_value)
                    
                    logger.debug(f"Applied rule '{rule.name}' to field '{field_name}'")
                except Exception as e:
                    logger.error(f"Rule '{rule.name}' failed for field '{field_name}': {e}")
                    raise
            
            # 如果原函数有额外逻辑，也执行
            if func.__name__ != 'wrapper':  # 避免无限递归
                try:
                    result = func(cleaned_value, info)
                    return result if result is not None else cleaned_value
                except Exception:
                    # 如果原函数执行失败，返回清洗后的值
                    return cleaned_value
            
            return cleaned_value
        
        return wrapper
    return decorator


def auto_cleansing_model(precision_config: Optional[Dict[str, int]] = None):
    """
    自动清洗模型装饰器
    
    为模型自动添加清洗逻辑，基于字段名和类型自动匹配清洗规则
    
    Args:
        precision_config: 数值字段精度配置
        
    Example:
        @auto_cleansing_model(precision_config={"当期收益率": 6})
        class AnnuityPerformanceOut(BaseModel):
            期初资产规模: Optional[Decimal] = None
            当期收益率: Optional[Decimal] = None
    """
    def decorator(cls):
        # 获取模型字段类型信息
        try:
            type_hints = get_type_hints(cls)
        except Exception:
            type_hints = {}
        
        # 为每个字段自动添加适当的清洗逻辑
        for field_name, field_type in type_hints.items():
            if field_name.startswith('_'):  # 跳过私有字段
                continue
            
            # 查找适用的清洗规则
            applicable_rules = registry.find_by_field_pattern(field_name)
            
            if applicable_rules:
                # 创建清洗函数
                cleansing_func = _create_field_cleansing_func(
                    field_name, applicable_rules, precision_config
                )
                
                # 动态添加到类中
                setattr(cls, f"_clean_{field_name}", cleansing_func)
        
        return cls
    
    return decorator


def _create_field_cleansing_func(field_name: str, rules: List[CleansingRule], precision_config: Optional[Dict[str, int]]):
    """为特定字段创建清洗函数"""
    @field_validator(field_name, mode="before")
    @classmethod
    def cleansing_func(cls, v, info: ValidationInfo):
        cleaned_value = v
        
        # 应用所有适用的规则
        for rule in rules:
            try:
                if rule.name == "comprehensive_decimal_cleaning":
                    cleaned_value = rule.func(
                        cleaned_value, 
                        field_name=field_name,
                        precision_config=precision_config
                    )
                else:
                    cleaned_value = rule.func(cleaned_value)
            except Exception as e:
                logger.error(f"Rule '{rule.name}' failed for field '{field_name}': {e}")
                raise
        
        return cleaned_value
    
    return cleansing_func


# 便捷装饰器 - 用于快速替换现有的重复实现
def decimal_fields_cleaner(
    *field_names: str, 
    precision_config: Optional[Dict[str, int]] = None
):
    """
    专门用于数值字段清洗的便捷装饰器
    
    直接替换现有的 clean_decimal_fields 实现
    
    Example:
        # 替换原来的重复实现
        @decimal_fields_cleaner(
            "期初资产规模", "期末资产规模", "供款", "当期收益率",
            precision_config={"当期收益率": 6}
        )
        class AnnuityPerformanceOut(BaseModel):
            # 字段定义...
            pass
    """
    def decorator(cls):
        # 获取原有的字段定义
        original_init = cls.__init__
        
        def __init__(self, **data):
            # 预处理指定的字段
            for field_name in field_names:
                if field_name in data:
                    data[field_name] = comprehensive_decimal_cleaning(
                        value=data[field_name],
                        field_name=field_name,
                        precision_config=precision_config
                    )
            
            # 调用原始的初始化方法
            original_init(self, **data)
        
        # 替换初始化方法
        cls.__init__ = __init__
        
        return cls
    
    return decorator


# 导入时自动加载清洗规则
def _load_cleansing_rules():
    """导入时自动加载所有清洗规则"""
    try:
        # 这会触发 @rule 装饰器的执行，自动注册规则
        from ..rules import numeric_rules
        logger.info(f"Loaded {len(registry.list_all_rules())} cleansing rules")
    except ImportError as e:
        logger.warning(f"Failed to load cleansing rules: {e}")


# 自动加载规则
_load_cleansing_rules()