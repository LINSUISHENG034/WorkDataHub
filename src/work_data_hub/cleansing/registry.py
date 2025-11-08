"""
数据清洗框架核心注册表和发现机制。

提供清洗规则的统一注册、发现和管理功能，
确保清洗规则可以在整个系统中高效复用。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class RuleCategory(Enum):
    """清洗规则分类枚举"""

    DATE = "date"
    NUMERIC = "numeric"
    STRING = "string"
    MAPPING = "mapping"
    VALIDATION = "validation"
    BUSINESS = "business"


@dataclass
class CleansingRule:
    """清洗规则元数据 - 简化版本，遵循KISS原则"""

    name: str
    category: RuleCategory
    func: Callable
    description: str

    def __post_init__(self):
        """验证规则的有效性"""
        if not callable(self.func):
            raise ValueError(f"Rule {self.name} must have a callable function")


class CleansingRegistry:
    """
    清洗规则注册表 - 简化版本

    负责管理所有清洗规则的注册和基本查找功能。
    遵循KISS原则，移除过度工程化的索引系统。
    """

    _instance = None
    _rules: Dict[str, CleansingRule] = {}

    def __new__(cls):
        """实现单例模式，确保全局唯一的注册表"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, rule: CleansingRule) -> None:
        """
        注册清洗规则到全局注册表

        Args:
            rule: 要注册的清洗规则
        """
        if rule.name in self._rules:
            logger.warning(f"Overriding existing rule: {rule.name}")

        self._rules[rule.name] = rule
        logger.debug(f"Registered cleansing rule: {rule.name} ({rule.category.value})")

    def get_rule(self, name: str) -> Optional[CleansingRule]:
        """根据名称获取清洗规则"""
        return self._rules.get(name)

    def find_by_category(self, category: RuleCategory) -> List[CleansingRule]:
        """根据分类查找清洗规则"""
        return [rule for rule in self._rules.values() if rule.category == category]

    def list_all_rules(self) -> List[CleansingRule]:
        """获取所有已注册的清洗规则"""
        return list(self._rules.values())

    def get_statistics(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        rules_by_category: Dict[str, int] = {}

        # 计算每个分类的规则数量
        for category in RuleCategory:
            count = len([r for r in self._rules.values() if r.category == category])
            rules_by_category[category.value] = count

        stats = {
            "total_rules": len(self._rules),
            "rules_by_category": rules_by_category
        }
        return stats


# 全局注册表实例
registry = CleansingRegistry()


def rule(name: str, category: RuleCategory, description: str):
    """
    清洗规则注册装饰器 - 简化版本

    遵循KISS原则，专注于核心功能：将函数注册为可复用的清洗规则。

    Args:
        name: 规则名称
        category: 规则分类
        description: 规则描述

    Example:
        @rule(
            name="decimal_quantization",
            category=RuleCategory.NUMERIC,
            description="数值字段精度量化处理"
        )
        def quantize_decimal(value, precision=4):
            # 清洗逻辑
            return processed_value
    """

    def decorator(func: Callable) -> Callable:
        # 创建清洗规则对象
        rule_obj = CleansingRule(name=name, category=category, func=func, description=description)

        # 注册到全局注册表
        registry.register(rule_obj)

        # 为函数添加元数据
        func._cleansing_rule = rule_obj  # type: ignore[attr-defined]

        return func

    return decorator
