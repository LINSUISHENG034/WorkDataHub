"""字符串清洗规则集合（Story 2.3）。"""

from __future__ import annotations

from typing import Any

from work_data_hub.infrastructure.cleansing.registry import RuleCategory, rule

_DECORATIVE_CHARS = "「」『』\"""《》"


@rule(
    name="trim_whitespace",
    category=RuleCategory.STRING,
    description="移除首尾空白并将全角空格转换为半角",
)
def trim_whitespace(value: Any) -> Any:
    """标准化首尾空白字符，兼容全角空格。"""
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    normalized = value.replace("\u3000", " ")  # 全角空格 -> 半角
    return normalized.strip()


@rule(
    name="normalize_company_name",
    category=RuleCategory.STRING,
    description="公司名称规范化：去装饰字符、压缩多余空格",
)
def normalize_company_name(value: Any) -> Any:
    """根据 AC2 要求规范化公司名称。"""
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    normalized = value.replace("\u3000", " ")

    for char in _DECORATIVE_CHARS:
        normalized = normalized.replace(char, "")

    # Collapse excessive whitespace between characters
    normalized = " ".join(normalized.split())

    return normalized


__all__ = ["trim_whitespace", "normalize_company_name"]
