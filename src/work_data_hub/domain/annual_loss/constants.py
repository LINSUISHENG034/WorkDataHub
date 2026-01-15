"""Annual Loss (当年流失) domain - Constants.

Mappings and configuration for annual loss data processing.
Unifies TrusteeLossCleaner (企年受托流失) and InvesteeLossCleaner (企年投资流失).
"""

from __future__ import annotations

from typing import Dict, Sequence

# Shared mappings imported from infrastructure (consistent with other domains)
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
    "客户全称": "上报客户名称",  # Rename per requirement #5
    "受托人": "原受托人",  # Rename per requirement #3
    "机构": "机构名称",  # Preserve as 机构名称
}

# Columns to drop during transformation
# Per requirement #1: 删除 区域, 年金中心, 上报人, 考核标签
# Per requirement #2: 投资流失特有字段直接忽略
COLUMNS_TO_DROP: Sequence[str] = (
    "区域",  # Requirement #1
    "年金中心",  # Requirement #1
    "上报人",  # Requirement #1 (may not exist in source)
    "考核标签",  # Requirement #1
    # Investment-only redundant fields (per requirement #2)
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
