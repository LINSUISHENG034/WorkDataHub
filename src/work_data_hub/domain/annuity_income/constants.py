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
