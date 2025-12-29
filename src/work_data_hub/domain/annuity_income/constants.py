from __future__ import annotations

from typing import Dict, Sequence

# Shared mappings imported from infrastructure (Story 5.5.4 extraction)
from work_data_hub.infrastructure.mappings import (
    BUSINESS_TYPE_CODE_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)

# AnnuityIncome-specific: Column alias for 收入明细 sheet
# 2025-12-27: Normalize "计划号" → "计划代码" to match annuity_performance
COLUMN_ALIAS_MAPPING: Dict[str, str] = {
    "机构": "机构代码",
    "计划号": "计划代码",  # Normalize legacy "计划号" to standard "计划代码"
}

# AnnuityIncome-specific: Columns to delete after processing
LEGACY_COLUMNS_TO_DELETE: Sequence[str] = (
    "id",
    "备注",
)

# AnnuityIncome-specific: Default institution code
DEFAULT_INSTITUTION_CODE: str = "G00"

# Story 7.3-6: Plan code corrections (typo fixes)
PLAN_CODE_CORRECTIONS: Dict[str, str] = {"1P0290": "P0290", "1P0807": "P0807"}

# Story 7.3-6: Plan code defaults (for empty values based on plan type)
PLAN_CODE_DEFAULTS: Dict[str, str] = {"集合计划": "AN001", "单一计划": "AN002"}

# AnnuityIncome-specific: Gold layer output columns
# Story 5.5.5: Four income fields instead of 收入金额
DEFAULT_ALLOWED_GOLD_COLUMNS: Sequence[str] = (
    "月度",
    "计划代码",
    "company_id",
    "客户名称",
    "年金账户名",
    "业务类型",
    "计划类型",
    "组合代码",
    "产品线代码",
    "机构代码",
    "计划名称",
    "组合类型",
    "组合名称",
    "机构名称",
    "固费",
    "浮费",
    "回补",
    "税",
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
    "PLAN_CODE_CORRECTIONS",  # Story 7.3-6
    "PLAN_CODE_DEFAULTS",  # Story 7.3-6
]
