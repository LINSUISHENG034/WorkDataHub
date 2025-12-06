"""
Legacy-compatible company name normalization for temporary ID generation.

This module provides name normalization functions that ensure consistent
temporary ID generation across different name variants. The normalization
logic is based on the legacy clean_company_name implementation.

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- Legacy Analysis: docs/supplement/03_clean_company_name_logic.md

CRITICAL: Name normalization MUST be applied before hashing to ensure
the same customer receives the same temporary ID regardless of:
- Trailing/leading whitespace
- Bracket variations (Chinese vs English)
- Status markers (已转出, 待转出, etc.)
- Full-width vs half-width characters
"""

import base64
import hashlib
import hmac
import re
from typing import List

# Status markers from legacy (29 patterns) + additional patterns from edge cases
# These indicate company status changes and should be stripped for ID generation
CORE_REPLACE_STRING: List[str] = [
    # Original 29 patterns
    "已转出",
    "待转出",
    "终止",
    "转出",
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
    # Additional patterns from edge case testing
    "已作废",
    "作废",
    "存量",
    "原",  # Prefix marker like (原)
]

# Sort by length descending for greedy matching
CORE_REPLACE_STRING_SORTED = sorted(CORE_REPLACE_STRING, key=len, reverse=True)


def normalize_for_temp_id(company_name: str) -> str:
    """
    Normalize company name for temporary ID generation.

    Based on: legacy/annuity_hub/common_utils/common_utils.py::clean_company_name

    Operations (in order):
    1. Remove all whitespace
    2. Remove business patterns (及下属子企业, -养老, etc.)
    3. Remove status markers (已转出, 待转出, etc.)
    4. Remove trailing punctuation
    5. Full-width → Half-width conversion
    6. Normalize brackets to Chinese
    7. Lowercase (NEW - for hash stability)

    Args:
        company_name: Raw company name to normalize.

    Returns:
        Normalized company name suitable for hashing.

    Examples:
        >>> normalize_for_temp_id("中国平安 ")
        '中国平安'
        >>> normalize_for_temp_id("中国平安-已转出")
        '中国平安'
        >>> normalize_for_temp_id("中国平安(集团)")
        '中国平安（集团）'
    """
    if not company_name:
        return ""

    name = company_name

    # 1. Remove all whitespace
    name = re.sub(r"\s+", "", name)

    # 2. Remove business-specific patterns and suffixes
    name = re.sub(r"及下属子企业", "", name)
    # Remove patterns like: (团托), -ChinaHolding, -BSU280, -养老, -福利, -Dsservice
    # Also handles mixed alphanumeric codes like -SupportChinaMiniMalls
    name = re.sub(
        r"(?:\(团托\)|（团托）|-[A-Za-z][A-Za-z0-9]*|-\d+|-养老|-福利)$", "", name
    )

    # 3. Remove status markers
    for core_str in CORE_REPLACE_STRING_SORTED:
        # Pattern for status at start (with optional brackets and separator)
        # e.g., "已转出-中国平安" -> "中国平安"
        pattern_start = rf"^[\(\（]?{re.escape(core_str)}[\)\）]?[\-]?"
        name = re.sub(pattern_start, "", name)

        # Pattern for status at end (with optional separators and brackets)
        # e.g., "中国平安-已转出" -> "中国平安"
        pattern_end = rf"[\-\(\（]{re.escape(core_str)}[\)\）]?$"
        name = re.sub(pattern_end, "", name)

        # Pattern for status in brackets at end
        # e.g., "中国平安（已转出）" -> "中国平安"
        pattern_bracket = rf"[\(\（]{re.escape(core_str)}[\)\）]$"
        name = re.sub(pattern_bracket, "", name)

    # 4. Full-width → Half-width conversion (before bracket normalization)
    name = "".join(
        [
            chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
            for char in name
        ]
    )

    # 5. Normalize brackets to Chinese
    name = name.replace("(", "（").replace(")", "）")

    # 6. Remove trailing punctuation and empty brackets (after bracket normalization)
    name = re.sub(r"[\-\.。]+$", "", name)  # Remove trailing dash, period (EN/CN)
    name = re.sub(r"（）$", "", name)  # Remove empty Chinese brackets at end

    # 7. Lowercase for hash stability (NEW - not in legacy)
    name = name.lower()

    return name


def generate_temp_company_id(customer_name: str, salt: str) -> str:
    """
    Generate stable temporary company ID with legacy-compatible normalization.

    Format: IN_<16-char-Base32>
    Algorithm: HMAC-SHA1

    The customer name is normalized before hashing to ensure consistent
    ID generation across name variants.

    Args:
        customer_name: Customer name to generate ID for.
        salt: Salt for HMAC (from WDH_ALIAS_SALT environment variable).

    Returns:
        Temporary ID in format "IN_<16-char-Base32>".

    Examples:
        >>> generate_temp_company_id("中国平安", "test_salt")
        'IN_...'  # 19 characters total
        >>> # Same input produces same output
        >>> id1 = generate_temp_company_id("中国平安", "salt")
        >>> id2 = generate_temp_company_id("中国平安", "salt")
        >>> id1 == id2
        True
    """
    # CRITICAL: Normalize before hashing!
    normalized = normalize_for_temp_id(customer_name)

    # Handle empty normalized name
    if not normalized:
        normalized = "__empty__"

    digest = hmac.new(
        salt.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha1,
    ).digest()

    # Take first 10 bytes and encode as Base32 (produces 16 characters)
    encoded = base64.b32encode(digest[:10]).decode("ascii")

    return f"IN_{encoded}"
