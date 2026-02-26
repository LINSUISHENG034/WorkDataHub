"""Annual Award (中标客户明细) domain - Constants.

Mappings and configuration for annual award data processing.
Uses shared mappings from infrastructure for consistency with other domains.
"""

from __future__ import annotations

from typing import Dict, Sequence

# Shared mappings imported from infrastructure (consistent with annuity_performance)
from work_data_hub.infrastructure.mappings import (
    BUSINESS_TYPE_CODE_MAPPING,  # 业务类型 → 产品线代码 (PL201/PL202)
    COMPANY_BRANCH_MAPPING,  # 机构名称 → 机构代码
)

# Business type normalization: raw values → canonical product line names
# Per user requirement: 受托→企年受托, 投资→企年投资, 投管→企年投资
BUSINESS_TYPE_NORMALIZATION: Dict[str, str] = {
    "受托": "企年受托",
    "投资": "企年投资",
    "投管": "企年投资",  # 投管 is alias for 投资
    "企年受托": "企年受托",  # Already canonical
    "企年投资": "企年投资",  # Already canonical
}

# Plan type mapping: raw values → canonical plan type names
PLAN_TYPE_MAPPING: Dict[str, str] = {
    "集合": "集合计划",
    "单一": "单一计划",
    "集合计划": "集合计划",  # Already canonical
    "单一计划": "单一计划",  # Already canonical
}

# Column renaming mapping
COLUMN_MAPPING: Dict[str, str] = {
    "客户全称": "上报客户名称",  # Rename per requirement #3
    "受托人": "原受托人",  # Rename trustee field
    "机构": "机构名称",  # Preserve as 机构名称 per issue #4
}

# Columns to drop during transformation
COLUMNS_TO_DROP: Sequence[str] = (
    "区域",  # Requirement #1
    "年金中心",  # Requirement #1
    "上报人",  # Requirement #1
    "insert_sql",  # Legacy column
    # Investment-only redundant fields (per user feedback)
    "战区前五大",
    "中心前十大",
    "机构前十大",
    "五亿以上",
)

DEFAULT_INSTITUTION_CODE: str = "G00"

__all__ = [
    "BUSINESS_TYPE_NORMALIZATION",
    "BUSINESS_TYPE_CODE_MAPPING",  # Re-exported from infrastructure
    "PLAN_TYPE_MAPPING",
    "COLUMN_MAPPING",
    "COLUMNS_TO_DROP",
    "COMPANY_BRANCH_MAPPING",  # Re-exported from infrastructure
    "DEFAULT_INSTITUTION_CODE",
]
