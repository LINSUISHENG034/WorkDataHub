from __future__ import annotations

from typing import Dict, Sequence

# Shared mappings imported from infrastructure (Story 5.5.4 extraction)
from work_data_hub.infrastructure.mappings import (
    BUSINESS_TYPE_CODE_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    PLAN_CODE_CORRECTIONS,  # Story 7.4-6
    PLAN_CODE_DEFAULTS,  # Story 7.4-6
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)

DEFAULT_ALLOWED_GOLD_COLUMNS: Sequence[str] = (
    "月度",
    "业务类型",
    "计划类型",
    "计划代码",
    "计划名称",
    "组合类型",
    "组合代码",
    "组合名称",
    "客户名称",
    "期初资产规模",
    "期末资产规模",
    "供款",
    "流失_含待遇支付",
    "流失",
    "待遇支付",
    "投资收益",
    "年化收益率",
    "机构代码",
    "机构名称",
    "产品线代码",
    "年金账户号",
    "年金账户名",
    "子企业号",
    "子企业名称",
    "集团企业客户号",
    "集团企业客户名称",
    "company_id",
)

# Note: BUSINESS_TYPE_CODE_MAPPING, DEFAULT_PORTFOLIO_CODE_MAPPING,
# PLAN_CODE_CORRECTIONS, PLAN_CODE_DEFAULTS,
# PORTFOLIO_QTAN003_BUSINESS_TYPES, and COMPANY_BRANCH_MAPPING are now
# imported from infrastructure.mappings (Story 5.5.4 and 7.4-6 extraction)

DEFAULT_INSTITUTION_CODE: str = "G00"

LEGACY_COLUMNS_TO_DELETE: Sequence[str] = (
    "id",
    "备注",
)

COLUMN_ALIAS_MAPPING: Dict[str, str] = {"流失(含待遇支付)": "流失_含待遇支付"}

# Legacy column renames (Source: cleansing-rules Section 5)
COLUMN_MAPPING: Dict[str, str] = {
    "机构": "机构名称",
    "计划号": "计划代码",
    "流失（含待遇支付）": "流失_含待遇支付",
    "流失(含待遇支付)": "流失_含待遇支付",
}

DEFAULT_COMPANY_ID: str = "600866980"

# Data Loading Configuration (Source: cleansing-rules Section 3/Service Config)
# For detail tables (REFRESH mode)
DEFAULT_REFRESH_KEYS: Sequence[str] = ("月度", "业务类型", "计划类型")

# For aggregate tables (UPSERT mode) - defined for completeness
DEFAULT_UPSERT_KEYS: Sequence[str] = ("月度", "计划代码", "组合代码", "company_id")

__all__: list[str] = [
    "DEFAULT_ALLOWED_GOLD_COLUMNS",
    "PLAN_CODE_CORRECTIONS",  # Re-exported from infrastructure for backward compatibility
    "PLAN_CODE_DEFAULTS",  # Re-exported from infrastructure for backward compatibility
    "BUSINESS_TYPE_CODE_MAPPING",  # Re-exported from infrastructure for backward compatibility
    "DEFAULT_PORTFOLIO_CODE_MAPPING",  # Re-exported from infrastructure for backward compatibility
    "PORTFOLIO_QTAN003_BUSINESS_TYPES",  # Re-exported from infrastructure for backward compatibility
    "COMPANY_BRANCH_MAPPING",  # Re-exported from infrastructure for backward compatibility
    "DEFAULT_INSTITUTION_CODE",
    "LEGACY_COLUMNS_TO_DELETE",
    "COLUMN_ALIAS_MAPPING",
    "COLUMN_MAPPING",
    "DEFAULT_COMPANY_ID",
    "DEFAULT_REFRESH_KEYS",
    "DEFAULT_UPSERT_KEYS",
]
