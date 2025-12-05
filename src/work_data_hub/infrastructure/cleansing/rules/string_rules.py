"""字符串清洗规则集合（Story 2.3）。"""

from __future__ import annotations

from typing import Any

import re

from work_data_hub.infrastructure.cleansing.registry import RuleCategory, rule

_DECORATIVE_CHARS = "「」『』\"""《》"

# Legacy parity: suffixes / markers to remove from company names
_COMPANY_NAME_SUFFIXES_TO_REMOVE = (
    "已转出",
    "待转出",
    "终止",
    "转出",
    "转移终止",
    "已作废",
    "已终止",
    "保留",
    "保留账户",
    "存量",
    "已转移终止",
    "本部",
    "未使用",
    "集合",
    "原",
)

# Legacy parity: marker set used by legacy common_utils.clean_company_name
_CORE_REPLACE_STRING = set(_COMPANY_NAME_SUFFIXES_TO_REMOVE)


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
    description="公司名称规范化：去装饰字符、压缩多余空格、半角括号转全角、移除特定后缀",
)
def normalize_company_name(value: Any) -> Any:
    """
    Legacy-compatible公司名称规范化（对齐 legacy/annuity_hub/common_utils.clean_company_name）。
    """
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    # Remove all whitespace (legacy behavior) and decorative chars
    normalized = re.sub(r"\s+", "", value.replace("\u3000", " "))
    for char in _DECORATIVE_CHARS:
        normalized = normalized.replace(char, "")

    # Remove specific patterns from legacy cleaner
    normalized = re.sub(r"及下属子企业", "", normalized)
    normalized = re.sub(r"(?:\(团托\)|-[A-Za-z]+|-\d+|-养老|-福利)$", "", normalized)

    # Remove core status markers from start/end (sorted desc by length)
    sorted_core = sorted(_CORE_REPLACE_STRING, key=lambda s: -len(s))
    for core_str in sorted_core:
        pattern_start = rf'^([\(\（]?){re.escape(core_str)}([\)\）]?)(?=[^\u4e00-\u9fff]|$)'
        normalized = re.sub(pattern_start, "", normalized)

        pattern_end = rf'(?<![\u4e00-\u9fff])([\-\(\（]?){re.escape(core_str)}([\)\）]?)[\-\(\（\)\）]*$'
        normalized = re.sub(pattern_end, "", normalized)

    # Trim trailing hyphens/brackets
    normalized = re.sub(r"[\-\(\（\)\）]+$", "", normalized)

    # Convert full-width ASCII to half-width (legacy default to_fullwidth=False)
    normalized = "".join(
        [chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char for char in normalized]
    )

    # Normalize parentheses to full-width (Chinese standard)
    normalized = normalized.replace("(", "（").replace(")", "）")

    return normalized


__all__ = ["trim_whitespace", "normalize_company_name"]
