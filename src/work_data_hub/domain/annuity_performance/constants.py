"""
Annuity Performance Domain Constants.

Consolidated from config.py (Story 4.10) and constants.py (Story 4.4) in Story 5.3.

This module centralizes all static mappings and configuration constants that were
previously hardcoded in pipeline_steps.py and other modules. This enables:
- Configuration-driven generic steps (DataFrameMappingStep, DataFrameValueReplacementStep)
- Single source of truth for domain-specific mappings
- Easy maintenance and updates without code changes
- Reference implementation for Epic 9 domain migrations

Usage:
    from work_data_hub.domain.annuity_performance.constants import (
        PLAN_CODE_CORRECTIONS,
        BUSINESS_TYPE_CODE_MAPPING,
        DEFAULT_PORTFOLIO_CODE_MAPPING,
        DEFAULT_ALLOWED_GOLD_COLUMNS,
    )
"""

from __future__ import annotations

from typing import Dict, Sequence

# =============================================================================
# Gold Layer Column Definition (from original constants.py - Story 4.4)
# =============================================================================
# Columns that exist in the annuity performance gold table. This mirrors the
# structure enforced by Story 4.4 and is reused by both the legacy service path
# and the pipeline-based Gold projection step.
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
    "company_id",
)


# =============================================================================
# Plan Code Corrections (PlanCodeCleansingStep)
# =============================================================================
# Specific plan code replacements from legacy cleaner
PLAN_CODE_CORRECTIONS: Dict[str, str] = {
    "1P0290": "P0290",
    "1P0807": "P0807",
}

# Default plan codes based on plan type when plan code is empty
PLAN_CODE_DEFAULTS: Dict[str, str] = {
    "集合计划": "AN001",
    "单一计划": "AN002",
}


# =============================================================================
# Business Type to Product Line Code Mapping (BusinessTypeCodeMappingStep)
# =============================================================================
# Maps business types to product line codes from legacy MySQL 产品线 table
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


# =============================================================================
# Portfolio Code Defaults (PortfolioCodeDefaultStep)
# =============================================================================
# Default portfolio codes used when source is blank, based on plan type
DEFAULT_PORTFOLIO_CODE_MAPPING: Dict[str, str] = {
    "集合计划": "QTAN001",
    "单一计划": "QTAN002",
    "职业年金": "QTAN003",
}

# Business types that trigger QTAN003 portfolio code
PORTFOLIO_QTAN003_BUSINESS_TYPES: Sequence[str] = ("职年受托", "职年投资")


# =============================================================================
# Institution/Branch Code Mapping (InstitutionCodeMappingStep)
# =============================================================================
# Maps institution names to branch codes
COMPANY_BRANCH_MAPPING: Dict[str, str] = {
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
}

# Default institution code when null or empty
DEFAULT_INSTITUTION_CODE: str = "G00"


# =============================================================================
# Legacy Columns to Delete (GoldProjectionStep)
# =============================================================================
# Columns that should never reach the Gold layer
LEGACY_COLUMNS_TO_DELETE: Sequence[str] = (
    "id",
    "备注",
    "子企业号",
    "子企业名称",
    "集团企业客户号",
    "集团企业客户名称",
)


# =============================================================================
# Column Alias Mappings (GoldProjectionStep)
# =============================================================================
# Column name standardization for database compatibility
COLUMN_ALIAS_MAPPING: Dict[str, str] = {
    "流失(含待遇支付)": "流失_含待遇支付",
}


# =============================================================================
# Company ID Resolution Constants (CompanyIdResolutionStep)
# =============================================================================
# Default company ID when customer name is empty/null
DEFAULT_COMPANY_ID: str = "600866980"


# =============================================================================
# Module Exports
# =============================================================================
__all__: list[str] = [
    # Gold layer columns (from original constants.py)
    "DEFAULT_ALLOWED_GOLD_COLUMNS",
    # Plan code configuration
    "PLAN_CODE_CORRECTIONS",
    "PLAN_CODE_DEFAULTS",
    # Business type mapping
    "BUSINESS_TYPE_CODE_MAPPING",
    # Portfolio code configuration
    "DEFAULT_PORTFOLIO_CODE_MAPPING",
    "PORTFOLIO_QTAN003_BUSINESS_TYPES",
    # Institution/branch mapping
    "COMPANY_BRANCH_MAPPING",
    "DEFAULT_INSTITUTION_CODE",
    # Gold layer configuration
    "LEGACY_COLUMNS_TO_DELETE",
    "COLUMN_ALIAS_MAPPING",
    # Company ID resolution
    "DEFAULT_COMPANY_ID",
]
