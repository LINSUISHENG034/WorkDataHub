from __future__ import annotations

from typing import Dict, Sequence

# TODO(5.5.4): Extract to infrastructure/mappings/shared.py
# Duplicated from: annuity_performance/constants.py
# Reuse potential: HIGH (used by 2+ domains)
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

# TODO(5.5.4): Extract to infrastructure/mappings/shared.py
# Duplicated from: annuity_performance/constants.py
# Reuse potential: HIGH (used by 2+ domains)
DEFAULT_PORTFOLIO_CODE_MAPPING: Dict[str, str] = {
    "集合计划": "QTAN001",
    "单一计划": "QTAN002",
    "职业年金": "QTAN003",
}

# TODO(5.5.4): Extract to infrastructure/mappings/shared.py
# Duplicated from: annuity_performance/constants.py
# Reuse potential: HIGH (used by 2+ domains)
PORTFOLIO_QTAN003_BUSINESS_TYPES: Sequence[str] = ("职年受托", "职年投资")

# TODO(5.5.4): Extract to infrastructure/mappings/shared.py
# Duplicated from: annuity_performance/constants.py
# Reuse potential: HIGH (used by 2+ domains)
# CRITICAL: Includes 6 legacy overrides missing from annuity_performance (Story 5.5-1 finding)
COMPANY_BRANCH_MAPPING: Dict[str, str] = {
    # Standard mappings (shared with annuity_performance)
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
    # Legacy overrides (missing from annuity_performance/constants.py - Story 5.5-1 gap)
    "内蒙": "G31",
    "战略": "G37",
    "中国": "G37",
    "济南": "G21",  # Different key from '山东': 'G21'
    "北京其他": "G37",
    "北分": "G37",
}

# AnnuityIncome-specific: Column alias for 收入明细 sheet
COLUMN_ALIAS_MAPPING: Dict[str, str] = {"机构": "机构代码"}

# AnnuityIncome-specific: Columns to delete after processing
LEGACY_COLUMNS_TO_DELETE: Sequence[str] = (
    "id",
    "备注",
    "机构名称",  # Used for mapping, then dropped
)

# AnnuityIncome-specific: Default institution code
DEFAULT_INSTITUTION_CODE: str = "G00"

# AnnuityIncome-specific: Gold layer output columns
DEFAULT_ALLOWED_GOLD_COLUMNS: Sequence[str] = (
    "月度",
    "计划号",
    "company_id",
    "客户名称",
    "年金账户名",
    "业务类型",
    "计划类型",
    "组合代码",
    "产品线代码",
    "机构代码",
    "收入金额",
)

# DEPRECATED: COMPANY_ID5_MAPPING
# Per Tech Spec and Story 5.5-1 decision, this fallback is NOT implemented.
# The standard CompanyIdResolutionStep provides consistent behavior across domains.
# Rows that previously resolved via ID5 may remain NULL - documented as intentional
# difference for Story 5.5.3 parity validation.

__all__: list[str] = [
    "BUSINESS_TYPE_CODE_MAPPING",
    "DEFAULT_PORTFOLIO_CODE_MAPPING",
    "PORTFOLIO_QTAN003_BUSINESS_TYPES",
    "COMPANY_BRANCH_MAPPING",
    "COLUMN_ALIAS_MAPPING",
    "LEGACY_COLUMNS_TO_DELETE",
    "DEFAULT_INSTITUTION_CODE",
    "DEFAULT_ALLOWED_GOLD_COLUMNS",
]
