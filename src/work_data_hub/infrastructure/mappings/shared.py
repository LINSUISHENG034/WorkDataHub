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
# CRITICAL: Complete mapping including:
# 1. All 38 mappings from legacy.mapping."组织架构" database table
# 2. 6 legacy overrides (内蒙, 战略, 中国, 济南, 北京其他, 北分) from Story 5.5-1
# 3. 2 new mappings (深圳分公司, 广州) added in pipeline
# Total: 46 mappings (complete parity with Legacy system)
# Used by: annuity_performance, annuity_income
COMPANY_BRANCH_MAPPING: Dict[str, str] = {
    # Standard mappings (shared across all domains)
    # From legacy.mapping."组织架构" database table
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
    "内蒙古": "G31",
    "青岛": "G11",
    "大连": "G07",
    "广西": "G14",
    "河北": "G24",
    "河南": "G32",
    "黑龙江": "G19",
    "湖北": "G09",
    "湖南": "G20",
    "吉林": "G08",
    "辽宁": "G06",
    "宁夏": "G28",
    "青海": "G27",
    "山西": "G33",
    "陕西": "G17",
    "四川": "G26",
    "天津": "G03",
    "西藏": "G36",
    "云南": "G16",
    "厦门": "G30",
    "北总": "G37",
    # New mappings added in pipeline
    "深圳分公司": "G05",
    "广州": "G04",
    # Legacy overrides (from annuity_income - Story 5.5-1 gap analysis)
    "内蒙": "G31",  # Duplicate of "内蒙古": "G31" but kept for legacy compatibility
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
