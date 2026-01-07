"""Unified customer name normalization module.

This module provides a single, comprehensive customer name normalization function
that consolidates the logic from three legacy functions:
- normalize_for_temp_id (enrichment/normalizer.py)
- normalize_company_name (cleansing/rules/string_rules.py)
- clean_company_name (pipelines/steps/customer_name_cleansing.py)

Architecture Reference:
- docs/specific/customer/customer-name-normalization-refactor.md

Usage:
    from work_data_hub.infrastructure.cleansing.normalizers import (
        normalize_customer_name,
    )

    normalized = normalize_customer_name("中国平安-已转出")
    # Returns: "中国平安"
"""

from __future__ import annotations

import re
from typing import List

from work_data_hub.infrastructure.cleansing.constants import (
    FULLWIDTH_CHAR_END,
    FULLWIDTH_CHAR_START,
    FULLWIDTH_TO_HALFWIDTH_OFFSET,
)

# =============================================================================
# Status Markers (33 patterns) - merged from all three functions
# =============================================================================
# These indicate company status changes and should be stripped for normalization
STATUS_MARKERS: List[str] = [
    # From normalize_for_temp_id (29+ patterns)
    "已转出",
    "待转出",
    "待转移",
    "终止",
    "转出",
    "转移",
    "保留",
    "暂停",
    "注销",
    "清算",
    "解散",
    "吊销",
    "撤销",
    "停业",
    "歇业",
    "关闭",
    "迁出",
    "迁入",
    "变更",
    "合并",
    "分立",
    "破产",
    "重整",
    "托管",
    "接管",
    "整顿",
    "清盘",
    "退出",
    "终结",
    "结束",
    "完结",
    "已作废",
    "作废",
    "存量",
    "原",
    # Additional from normalize_company_name
    "转移终止",
    "已终止",
    "保留账户",
    "已转移终止",
    "本部",
    "未使用",
    "集合",
    # Additional patterns from user feedback (2026-01-05)
    "企业年金计划",  # e.g., "XX公司（企业年金计划）"
]

# Sort by length descending for greedy matching
_STATUS_MARKERS_SORTED = sorted(STATUS_MARKERS, key=len, reverse=True)

# =============================================================================
# Enterprise Types to PRESERVE (legal entity structure indicators)
# =============================================================================
# These indicate legal entity structure and should NOT be removed
ENTERPRISE_TYPES: List[str] = [
    "特殊普通合伙",  # Special General Partnership
    "普通合伙",  # General Partnership
    "有限合伙",  # Limited Partnership
    "有限公司",  # Limited Liability Company (in parentheses)
    "个人独资",  # Sole Proprietorship
    "全民所有制",  # Wholly State-owned
    "集体所有制",  # Collective-owned
    "股份合作",  # Shareholding Cooperative
    "个体工商户",  # Individual Business
]

# Sort by length descending for greedy matching
_ENTERPRISE_TYPES_SORTED = sorted(ENTERPRISE_TYPES, key=len, reverse=True)

# Decorative characters to remove (from normalize_company_name)
_DECORATIVE_CHARS = '「」『』"'

# Invalid placeholder values that should be treated as empty
# These are data entry placeholders, not real company names
INVALID_PLACEHOLDERS: List[str] = [
    "null",
    "NULL",
    "空白",
    "无",
    "N/A",
    "n/a",
    "-",
    "--",
    "—",
    "——",
]

# =============================================================================
# Protected Names (whitelist) - skip cleaning entirely, only apply UPPERCASE
# =============================================================================
# These exact names are protected from any cleaning transformations.
# Use for special entity names that would otherwise be incorrectly modified.
PROTECTED_NAMES: List[str] = [
    "保留账户管理",  # Would be incorrectly stripped to "管理" due to STATUS_MARKERS
]

# Create a set for O(1) lookup, normalized to uppercase for matching
_PROTECTED_NAMES_SET = {name.upper() for name in PROTECTED_NAMES}


def _clean_trailing_parenthesis(name: str) -> str:
    """Remove trailing parenthesized suffixes unless they contain enterprise types.

    Simplified logic (2026-01-07):
    - KEEP: Only if content matches an ENTERPRISE_TYPE (普通合伙, 有限合伙, etc.)
    - REMOVE: Everything else (aliases, status, group indicators, etc.)

    This provides better generalization than trying to enumerate all removal patterns.

    Args:
        name: Company name to clean.

    Returns:
        Cleaned name with trailing parenthesis removed unless it's an enterprise type.

    Examples:
        >>> _clean_trailing_parenthesis("公司（集团）")
        '公司'
        >>> _clean_trailing_parenthesis("公司（普通合伙）")
        '公司（普通合伙）'
        >>> _clean_trailing_parenthesis("公司（平安）")
        '公司'
        >>> _clean_trailing_parenthesis("中心（另一个名字）")
        '中心'
    """
    # Match trailing parenthesized content: （...） or (...)
    match = re.search(r"[（\(]([^）\)]+)[）\)]$", name)
    if not match:
        return name

    content = match.group(1)

    # ONLY preserve if content matches an enterprise type
    for etype in _ENTERPRISE_TYPES_SORTED:
        if etype in content:
            return name  # Preserve enterprise type

    # Remove all other trailing parenthesis content
    return name[: match.start()]


def normalize_customer_name(name: str | None) -> str:
    """Unified customer name normalization for all use cases.

    This function consolidates the logic from three legacy functions to provide
    consistent normalization across the entire codebase.

    Operations (in order):
    1. Handle None/invalid placeholders
    2. Remove all whitespace
    3. Remove decorative characters (「」『』")
    4. Remove leading/trailing bracket content with status markers
    5. Remove business patterns (及下属子企业, -养老, etc.)
    6. Remove status markers from start/end (33 patterns)
    7. Full-width → Half-width ASCII conversion
    8. Normalize brackets to Chinese full-width
    9. Remove trailing punctuation and empty brackets
    10. **UPPERCASE conversion**

    Args:
        name: Raw customer/company name to normalize.

    Returns:
        Normalized customer name suitable for matching, hashing, and display.
        Returns empty string for None or invalid placeholder inputs.

    Examples:
        >>> normalize_customer_name("中国平安")
        '中国平安'
        >>> normalize_customer_name("中国平安-已转出")
        '中国平安'
        >>> normalize_customer_name("  ABC  公司  ")
        'ABC公司'
        >>> normalize_customer_name("CHINA LIFE")
        'CHINALIFE'
        >>> normalize_customer_name("null")
        ''
    """
    if name is None:
        return ""

    if not isinstance(name, str):
        return ""

    # 0. Check for protected names - skip all cleaning, only apply UPPERCASE
    # This allows exact matches to bypass all transformations
    name_upper = name.strip().upper()
    if name_upper in _PROTECTED_NAMES_SET:
        return name_upper

    # 1. Check for invalid placeholders (before any processing)
    if name.strip() in INVALID_PLACEHOLDERS:
        return ""

    result = name

    # 2. Remove all whitespace (including full-width spaces)
    result = result.replace("\u3000", " ")  # Full-width space → half-width
    result = re.sub(r"\s+", "", result)

    # 3. Remove decorative characters
    for char in _DECORATIVE_CHARS:
        result = result.replace(char, "")

    # 4. Remove leading bracket content (may contain status markers)
    # e.g., "(原)中国平安" → "中国平安"
    result = re.sub(r"^[（\(][^）\)]*[）\)]", "", result)

    # 5. Remove business-specific patterns and suffixes
    result = re.sub(r"及下属子企业", "", result)
    # Remove patterns like: (团托), -ChinaHolding, -BSU280, -养老, -福利
    result = re.sub(
        r"(?:\(团托\)|（团托）|-[A-Za-z][A-Za-z0-9]*|-\d+|-养老|-福利)$", "", result
    )

    # 6. Remove status markers from start and end
    for marker in _STATUS_MARKERS_SORTED:
        # Pattern for status at start (with optional brackets and separator)
        # e.g., "已转出-中国平安" → "中国平安"
        pattern_start = rf"^[\(\（]?{re.escape(marker)}[\)\）]?[\-]?"
        result = re.sub(pattern_start, "", result)

        # Pattern for status at end (with optional separators and brackets)
        # e.g., "中国平安-已转出" → "中国平安"
        # Also handle em-dash: "中国平安——待转出" → "中国平安"
        pattern_end = rf"[—\-\(\（]{re.escape(marker)}[\)\）]?$"
        result = re.sub(pattern_end, "", result)

        # Pattern for status in brackets at end
        # e.g., "中国平安（已转出）" → "中国平安"
        pattern_bracket = rf"[\(\（]{re.escape(marker)}[\)\）]$"
        result = re.sub(pattern_bracket, "", result)

    # 6.5 Clean trailing parenthesized suffixes but preserve enterprise types
    # e.g., "公司（集团）" → "公司" but "公司（普通合伙）" stays
    result = _clean_trailing_parenthesis(result)

    # 7. Full-width ASCII → Half-width conversion
    result = "".join(
        [
            chr(ord(char) - FULLWIDTH_TO_HALFWIDTH_OFFSET)
            if FULLWIDTH_CHAR_START <= ord(char) <= FULLWIDTH_CHAR_END
            else char
            for char in result
        ]
    )

    # 8. Normalize brackets to Chinese full-width
    result = result.replace("(", "（").replace(")", "）")

    # 9. Remove trailing punctuation and empty brackets
    result = re.sub(r"[—\-\.。]+$", "", result)  # Remove trailing dash, em-dash, period
    result = re.sub(r"（）$", "", result)  # Remove empty Chinese brackets
    # Only remove orphaned/unmatched trailing brackets, not paired ones with content
    # e.g., "公司）" → "公司" but "公司（集团）" stays as is
    result = re.sub(
        r"[—\-]+$", "", result
    )  # Remove trailing dashes (regular and em-dash)

    # 10. UPPERCASE conversion (decision: 2026-01-05)
    result = result.upper()

    return result


__all__ = [
    "normalize_customer_name",
    "STATUS_MARKERS",
    "INVALID_PLACEHOLDERS",
    "ENTERPRISE_TYPES",
    "PROTECTED_NAMES",
]
