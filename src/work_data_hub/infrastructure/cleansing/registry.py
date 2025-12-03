"""
数据清洗框架核心注册表和发现机制。

提供清洗规则的统一注册、发现和管理功能，
确保清洗规则可以在整个系统中高效复用。
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

import yaml

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


RuleSpec = Union[str, Dict[str, Any]]


class CleansingRegistry:
    """
    清洗规则注册表 - 简化版本

    负责管理所有清洗规则的注册和基本查找功能。
    遵循KISS原则，移除过度工程化的索引系统。
    """

    _instance: Optional["CleansingRegistry"] = None
    _rules: Dict[str, CleansingRule] = {}
    _rule_signatures: Dict[str, inspect.Signature] = {}

    def __new__(cls):
        """实现单例模式，确保全局唯一的注册表"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._config_lock = RLock()
        config_dir = Path(__file__).resolve().parent / "settings"
        self._config_path = config_dir / "cleansing_rules.yml"
        self._config_mtime: Optional[float] = None
        self._domain_config: Dict[str, Any] = {
            "domains": {},
            "default_rules": [],
        }
        self._initialized = True

    # --- Rule registration -----------------------------------------------------
    def register(self, rule: CleansingRule) -> None:
        """
        注册清洗规则到全局注册表

        Args:
            rule: 要注册的清洗规则
        """
        if rule.name in self._rules:
            logger.warning(f"Overriding existing rule: {rule.name}")

        self._rules[rule.name] = rule
        try:
            self._rule_signatures[rule.name] = inspect.signature(rule.func)
        except (TypeError, ValueError):  # pragma: no cover - extremely rare
            self._rule_signatures.pop(rule.name, None)
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
            "rules_by_category": rules_by_category,
        }
        return stats

    # --- Rule execution helpers -------------------------------------------------
    def apply_rule(self, value: Any, rule_name: str, **kwargs: Any) -> Any:
        """执行单个清洗规则"""
        rule = self.get_rule(rule_name)
        if not rule:
            available = sorted(self._rules.keys())
            raise ValueError(
                f"Cleansing rule '{rule_name}' not registered. "
                f"Available: {available}"
            )

        try:
            filtered_kwargs = self._filter_kwargs(rule_name, kwargs)
            return rule.func(value, **filtered_kwargs)
        except Exception as exc:  # pragma: no cover - 防御性
            raise ValueError(
                f"Cleansing rule '{rule_name}' failed for value '{value}': {exc}"
            ) from exc

    def apply_rules(
        self,
        value: Any,
        rule_specs: Sequence[RuleSpec],
        **common_kwargs: Any,
    ) -> Any:
        """
        顺序执行一系列清洗规则

        Args:
            value: 输入值
            rule_specs: 规则名称或带参数的配置
            common_kwargs: 注入到每个规则的共享关键字参数
        """

        result = value
        if not rule_specs:
            return result

        for spec in rule_specs:
            if isinstance(spec, str):
                rule_name = spec
                rule_kwargs: Dict[str, Any] = {}
            elif isinstance(spec, dict):
                rule_name = spec.get("name")
                rule_kwargs = spec.get("kwargs", {})
                if not rule_name:
                    raise ValueError("Rule specification missing 'name'")
            else:
                raise ValueError(
                    f"Invalid rule specification {spec!r}. Expected string or mapping."
                )

            merged_kwargs = {**rule_kwargs, **common_kwargs}
            result = self.apply_rule(result, rule_name, **merged_kwargs)

        return result
    def _filter_kwargs(self, rule_name: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if not kwargs:
            return {}

        signature = self._rule_signatures.get(rule_name)
        if signature is None:
            try:
                signature = inspect.signature(self._rules[rule_name].func)
                self._rule_signatures[rule_name] = signature
            except (TypeError, ValueError):
                return {}

        accepts_var_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )
        if accepts_var_kwargs:
            return kwargs

        return {k: v for k, v in kwargs.items() if k in signature.parameters}

    # --- Domain-level configuration -------------------------------------------
    def get_domain_rules(self, domain: str, field: str) -> List[RuleSpec]:
        """返回指定 domain + field 的规则列表"""

        self._ensure_config_loaded()
        domains: Dict[str, Any] = self._domain_config.get("domains", {})
        if domain in domains:
            field_rules = domains[domain].get(field, [])
            return list(field_rules)

        # 未配置 domain 时返回默认规则
        return list(self._domain_config.get("default_rules", []))

    def reload_domain_config(self) -> None:
        """强制重新加载 YAML 配置（测试或热加载场景使用）"""
        with self._config_lock:
            self._config_mtime = None
        self._ensure_config_loaded()

    def _ensure_config_loaded(self) -> None:
        """按需加载配置文件"""
        with self._config_lock:
            path = self._config_path
            current_mtime = path.stat().st_mtime if path.exists() else None
            if self._config_mtime is not None and current_mtime == self._config_mtime:
                return

            if not path.exists():
                logger.debug("Cleansing config not found at %s", path)
                self._domain_config = {"domains": {}, "default_rules": []}
                self._config_mtime = None
                return

            with path.open("r", encoding="utf-8") as handle:
                parsed = yaml.safe_load(handle) or {}

            domains = parsed.get("domains") or {}
            if not isinstance(domains, dict):
                raise ValueError(
                    "'domains' section in cleansing_rules.yml must be a mapping"
                )

            default_rules: Iterable[RuleSpec] = parsed.get("default_rules") or []
            # 兼容旧格式: domains.default
            if "default" in domains and not default_rules:
                default_rules = domains.get("default") or []
                domains = {k: v for k, v in domains.items() if k != "default"}

            self._validate_domain_config(domains, default_rules)
            self._domain_config = {
                "domains": domains,
                "default_rules": list(default_rules),
            }
            self._config_mtime = current_mtime

    def _validate_domain_config(
        self,
        domains: Dict[str, Dict[str, Sequence[RuleSpec]]],
        default_rules: Iterable[RuleSpec],
    ) -> None:
        """验证配置中引用的规则在注册表中存在"""

        for domain, field_rules in domains.items():
            if not isinstance(field_rules, dict):
                raise ValueError(f"Domain '{domain}' configuration must be a mapping")
            for field_name, rules in field_rules.items():
                self._validate_rule_specs(rules, f"{domain}.{field_name}")

        self._validate_rule_specs(default_rules, "default_rules")

    def _validate_rule_specs(self, specs: Iterable[RuleSpec], label: str) -> None:
        for spec in specs:
            if isinstance(spec, str):
                rule_name = spec
            elif isinstance(spec, dict):
                rule_name = spec.get("name")
                if not rule_name:
                    raise ValueError(f"Rule spec in '{label}' missing name field")
            else:
                raise ValueError(
                    f"Invalid rule specification in '{label}'. Expected string or mapping, got {type(spec)}"
                )

            if rule_name not in self._rules:
                raise ValueError(
                    f"Rule '{rule_name}' referenced in '{label}' is not registered"
                )


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
        rule_obj = CleansingRule(
            name=name, category=category, func=func, description=description
        )

        # 注册到全局注册表
        registry.register(rule_obj)

        # 为函数添加元数据
        func._cleansing_rule = rule_obj  # type: ignore[attr-defined]

        return func

    return decorator


def get_cleansing_registry() -> CleansingRegistry:
    """便于依赖注入的辅助函数"""
    return registry
