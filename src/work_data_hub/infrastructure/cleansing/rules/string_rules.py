"""字符串清洗规则集合（Story 2.3）。

.. deprecated:: 2026-01-05
    The normalize_company_name function now delegates to normalize_customer_name
    from infrastructure.cleansing.normalizers for unified behavior.
"""

from __future__ import annotations

import warnings
from typing import Any

from work_data_hub.infrastructure.cleansing.normalizers import (
    normalize_customer_name,
)
from work_data_hub.infrastructure.cleansing.registry import RuleCategory, rule


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
    description="公司名称规范化：使用统一的 normalize_customer_name 函数",
)
def normalize_company_name(value: Any) -> Any:
    """
    公司名称规范化。

    .. deprecated:: 2026-01-05
        This function now delegates to normalize_customer_name from
        infrastructure.cleansing.normalizers for unified behavior.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    warnings.warn(
        "normalize_company_name is deprecated. "
        "Use normalize_customer_name from infrastructure.cleansing.normalizers instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return normalize_customer_name(value)


__all__ = ["trim_whitespace", "normalize_company_name"]
