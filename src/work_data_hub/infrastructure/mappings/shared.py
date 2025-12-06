"""Shared mapping constants used across multiple domains.

Extracted from domain-specific constants as part of Story 5.5.4 to reduce
code duplication and establish a single source of truth for cross-domain mappings.

Usage:
    from work_data_hub.infrastructure.mappings import BUSINESS_TYPE_CODE_MAPPING
"""

from __future__ import annotations

from typing import Dict, Sequence

# Business type to product line code mapping
# Used by: annuity_performance, annuity_income
BUSINESS_TYPE_CODE_MAPPING: Dict[str, str] = {
    "企年投资": "PL201",
    "企年受托": "PL202",
    "职年投资": "PL203",
    "职年受托": "PL204",
    "自有险资": "PL205",
    "直投": "PL206",
    "三方": "PL207",
    "团养": "PL208",
    "企康": "PL209",
    "企业年金": "PL210",
    "职业年金": "PL211",
    "其他": "PL301",
}

# Default portfolio code mapping based on plan type
# Used by: annuity_performance, annuity_income
DEFAULT_PORTFOLIO_CODE_MAPPING: Dict[str, str] = {
    "集合计划": "QTAN001",
    "单一计划": "QTAN002",
    "职业年金": "QTAN003",
}

# Business types that map to QTAN003 portfolio code
# Used by: annuity_performance, annuity_income
PORTFOLIO_QTAN003_BUSINESS_TYPES: Sequence[str] = ("职年受托", "职年投资")

# Company branch name to institution code mapping
# CRITICAL: This is the canonical superset including legacy overrides from
# annuity_income
# The 6 legacy overrides (内蒙, 战略, 中国, 济南, 北京其他, 北分) were identified in
# Story 5.5-1
# Used by: annuity_performance, annuity_income
COMPANY_BRANCH_MAPPING: Dict[str, str] = {
    # Standard mappings (shared across all domains)
    "总部": "G00",
    "北京": "G01",
    "上海": "G02",
    "深圳": "G05",
    "广东": "G04",
    "江苏": "G10",
    "浙江": "G12",
    "福建": "G13",
    "海南": "G15",
    "重庆": "G18",
    "山东": "G21",
    "江西": "G22",
    "新疆": "G23",
    "安徽": "G25",
    "宁波": "G29",
    "甘肃": "G34",
    "贵州": "G35",
    "深圳分公司": "G05",
    "广州": "G04",
    "青岛": "G11",
    # Legacy overrides (from annuity_income - Story 5.5-1 gap analysis)
    "内蒙": "G31",
    "战略": "G37",
    "中国": "G37",
    "济南": "G21",  # Different key from '山东': 'G21'
    "北京其他": "G37",
    "北分": "G37",
}

__all__ = [
    "BUSINESS_TYPE_CODE_MAPPING",
    "COMPANY_BRANCH_MAPPING",
    "DEFAULT_PORTFOLIO_CODE_MAPPING",
    "PORTFOLIO_QTAN003_BUSINESS_TYPES",
]
