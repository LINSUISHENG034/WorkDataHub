"""
Pydantic 集成适配器 - 简化版本

提供清洗框架与 Pydantic 模型的简化集成，遵循KISS原则。
"""

import logging
from typing import Any, Dict, Optional

from pydantic import ValidationInfo, field_validator

from work_data_hub.infrastructure.cleansing.registry import registry
from work_data_hub.infrastructure.cleansing.rules.numeric_rules import (
    comprehensive_decimal_cleaning,
)

logger = logging.getLogger(__name__)


def decimal_fields_cleaner(
    *field_names: str, precision_config: Optional[Dict[str, int]] = None
) -> Any:
    """
    专门用于数值字段清洗的简化装饰器

    直接使用 comprehensive_decimal_cleaning 函数，替换重复的实现。

    Args:
        field_names: 需要清洗的字段名
        precision_config: 字段精度配置字典

    Example:
        @decimal_fields_cleaner(
            "期初资产规模", "期末资产规模", "当期收益率",
            precision_config={"当期收益率": 6, "期初资产规模": 4}
        )
        class AnnuityPerformanceOut(BaseModel):
            期初资产规模: Optional[Decimal] = None
            当期收益率: Optional[Decimal] = None
    """

    def decorator(cls: Any) -> Any:
        # 创建验证器函数
        def validator_func(v: Any, info: ValidationInfo) -> Any:
            return comprehensive_decimal_cleaning(
                value=v, field_name=info.field_name, precision_config=precision_config
            )

        # 为每个字段动态添加验证器
        for field_name in field_names:
            # 创建字段验证器装饰器
            field_val = field_validator(field_name, mode="before")(
                classmethod(validator_func)
            )

            # 添加到类的注释中，以便Pydantic能够发现它
            validator_name = (
                f"validate_{field_name.replace('/', '_').replace(' ', '_')}"
            )
            setattr(cls, validator_name, field_val)

        # 重建模型以应用新的验证器
        try:
            cls.model_rebuild()
        except Exception:
            pass  # 在某些情况下可能不需要rebuild

        return cls

    return decorator


def simple_field_validator(
    *field_names: str, rule_name: str = "comprehensive_decimal_cleaning"
) -> Any:
    """
    简化的字段验证器装饰器

    Args:
        field_names: 字段名列表
        rule_name: 使用的清洗规则名称
    """

    def decorator(func: Any) -> Any:
        @field_validator(*field_names, mode="before")
        @classmethod
        def wrapper(cls: Any, v: Any, info: ValidationInfo) -> Any:
            # 直接使用综合清洗函数
            if rule_name == "comprehensive_decimal_cleaning":
                return comprehensive_decimal_cleaning(v, field_name=info.field_name)
            else:
                rule = registry.get_rule(rule_name)
                if rule:
                    return rule.func(v)
                else:
                    logger.warning(
                        f"Rule '{rule_name}' not found, using original function"
                    )
                    return func(v, info)

        return wrapper

    return decorator
