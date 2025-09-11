"""
数据清洗框架核心注册表和发现机制。

提供清洗规则的统一注册、发现和管理功能，
确保清洗规则可以在整个系统中高效复用。
"""

import logging
import inspect
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

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
    """清洗规则元数据"""
    name: str
    category: RuleCategory
    func: Callable
    description: str
    applicable_types: Set[type]
    field_patterns: List[str]
    version: str = "1.0.0"
    author: str = "WorkDataHub"
    
    def __post_init__(self):
        """验证规则的有效性"""
        if not callable(self.func):
            raise ValueError(f"Rule {self.name} must have a callable function")
        
        # 检查函数签名
        sig = inspect.signature(self.func)
        if len(sig.parameters) < 1:
            raise ValueError(f"Rule {self.name} function must accept at least one parameter")


class CleansingRegistry:
    """
    清洗规则注册表 - 核心组件
    
    负责管理所有清洗规则的注册、发现和查找。
    这是解决重复实现问题的关键组件。
    """
    
    _instance = None
    _rules: Dict[str, CleansingRule] = {}
    _category_index: Dict[RuleCategory, List[str]] = {}
    _type_index: Dict[type, List[str]] = {}
    _pattern_index: Dict[str, List[str]] = {}
    
    def __new__(cls):
        """实现单例模式，确保全局唯一的注册表"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._initialize_indexes()
        return cls._instance
    
    @classmethod
    def _initialize_indexes(cls):
        """初始化索引结构"""
        cls._category_index = {category: [] for category in RuleCategory}
        cls._type_index = {}
        cls._pattern_index = {}
    
    def register(self, rule: CleansingRule) -> None:
        """
        注册清洗规则到全局注册表
        
        Args:
            rule: 要注册的清洗规则
        """
        if rule.name in self._rules:
            logger.warning(f"Overriding existing rule: {rule.name}")
        
        self._rules[rule.name] = rule
        
        # 更新分类索引
        if rule.name not in self._category_index[rule.category]:
            self._category_index[rule.category].append(rule.name)
        
        # 更新类型索引
        for applicable_type in rule.applicable_types:
            if applicable_type not in self._type_index:
                self._type_index[applicable_type] = []
            if rule.name not in self._type_index[applicable_type]:
                self._type_index[applicable_type].append(rule.name)
        
        # 更新模式索引
        for pattern in rule.field_patterns:
            if pattern not in self._pattern_index:
                self._pattern_index[pattern] = []
            if rule.name not in self._pattern_index[pattern]:
                self._pattern_index[pattern].append(rule.name)
        
        logger.debug(f"Registered cleansing rule: {rule.name} ({rule.category.value})")
    
    def find_by_name(self, name: str) -> Optional[CleansingRule]:
        """根据名称查找清洗规则"""
        return self._rules.get(name)
    
    def find_by_category(self, category: RuleCategory) -> List[CleansingRule]:
        """根据分类查找清洗规则"""
        rule_names = self._category_index.get(category, [])
        return [self._rules[name] for name in rule_names]
    
    def find_by_type(self, data_type: type) -> List[CleansingRule]:
        """根据数据类型查找适用的清洗规则"""
        rule_names = self._type_index.get(data_type, [])
        return [self._rules[name] for name in rule_names]
    
    def find_by_field_pattern(self, field_name: str) -> List[CleansingRule]:
        """
        根据字段名模式查找适用的清洗规则
        
        支持精确匹配和模式匹配（*通配符）
        """
        matching_rules = []
        
        # 精确匹配
        if field_name in self._pattern_index:
            rule_names = self._pattern_index[field_name]
            matching_rules.extend([self._rules[name] for name in rule_names])
        
        # 模式匹配
        for pattern in self._pattern_index:
            if self._match_pattern(field_name, pattern) and pattern != field_name:
                rule_names = self._pattern_index[pattern]
                matching_rules.extend([self._rules[name] for name in rule_names])
        
        # 去重
        seen = set()
        unique_rules = []
        for rule in matching_rules:
            if rule.name not in seen:
                seen.add(rule.name)
                unique_rules.append(rule)
        
        return unique_rules
    
    def _match_pattern(self, field_name: str, pattern: str) -> bool:
        """
        简单的模式匹配实现
        
        支持 * 通配符，例如：
        - "*金额" 匹配所有以"金额"结尾的字段
        - "资产*" 匹配所有以"资产"开头的字段
        """
        if "*" not in pattern:
            return field_name == pattern
        
        if pattern.startswith("*") and pattern.endswith("*"):
            # *xxx* 模式
            middle = pattern[1:-1]
            return middle in field_name
        elif pattern.startswith("*"):
            # *xxx 模式
            suffix = pattern[1:]
            return field_name.endswith(suffix)
        elif pattern.endswith("*"):
            # xxx* 模式
            prefix = pattern[:-1]
            return field_name.startswith(prefix)
        
        return False
    
    def list_all_rules(self) -> List[CleansingRule]:
        """获取所有已注册的清洗规则"""
        return list(self._rules.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        return {
            "total_rules": len(self._rules),
            "rules_by_category": {
                category.value: len(rule_names) 
                for category, rule_names in self._category_index.items()
            },
            "rules_by_type": {
                str(data_type): len(rule_names)
                for data_type, rule_names in self._type_index.items()
            }
        }


# 全局注册表实例
registry = CleansingRegistry()


def rule(
    name: str,
    category: RuleCategory,
    description: str,
    applicable_types: Optional[Set[type]] = None,
    field_patterns: Optional[List[str]] = None,
    version: str = "1.0.0"
):
    """
    清洗规则注册装饰器
    
    这是框架的核心装饰器，用于将函数注册为可复用的清洗规则。
    
    Args:
        name: 规则名称
        category: 规则分类
        description: 规则描述
        applicable_types: 适用的数据类型
        field_patterns: 适用的字段名模式
        version: 规则版本
    
    Example:
        @rule(
            name="decimal_quantization",
            category=RuleCategory.NUMERIC,
            description="数值字段精度量化处理",
            applicable_types={float, int, str},
            field_patterns=["*金额", "*规模", "*收益"]
        )
        def quantize_decimal(value, precision=4):
            # 清洗逻辑
            return processed_value
    """
    def decorator(func: Callable) -> Callable:
        # 创建清洗规则对象
        rule_obj = CleansingRule(
            name=name,
            category=category,
            func=func,
            description=description,
            applicable_types=applicable_types or set(),
            field_patterns=field_patterns or [],
            version=version
        )
        
        # 注册到全局注册表
        registry.register(rule_obj)
        
        # 为函数添加元数据
        func._cleansing_rule = rule_obj
        
        return func
    
    return decorator