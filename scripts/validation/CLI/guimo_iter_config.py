"""
Configuration constants for Annuity Performance Cleaner Comparison.

This module centralizes all configuration values used across the comparison scripts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

# =============================================================================
# Path Configuration
# =============================================================================

# Script directory
SCRIPT_DIR = Path(__file__).parent
ARTIFACTS_DIR = SCRIPT_DIR / "_artifacts"
DEBUG_SNAPSHOTS_SUBDIR = "debug_snapshots"

# Legacy path for imports
LEGACY_PATH = SCRIPT_DIR.parent.parent.parent / "legacy"

# =============================================================================
# Field Classification
# =============================================================================

# Numeric fields requiring zero-tolerance comparison
# NULL and 0 are treated as equivalent
NUMERIC_FIELDS: List[str] = [
    "期初资产规模",
    "期末资产规模",
    "供款",
    "流失(含待遇支付)",  # Legacy column name
    "流失",
    "待遇支付",
]

# Column name mapping: Legacy → New Pipeline
COLUMN_NAME_MAPPING: Dict[str, str] = {
    "流失(含待遇支付)": "流失_含待遇支付",
}

# Derived fields: computed from source via mappings/transformations
DERIVED_FIELDS: List[str] = [
    "月度",
    "机构代码",
    "计划代码",
    "组合代码",
    "产品线代码",
]

# Upgrade fields: intentionally enhanced in New Pipeline
UPGRADE_FIELDS: List[str] = [
    "company_id",
    "客户名称",
]

# =============================================================================
# Classification Rules for company_id Differences
# =============================================================================

# Temporary ID patterns
TEMP_ID_PATTERNS: List[str] = [
    "IN",  # New Pipeline temp ID prefix
]

INVALID_COMPANY_ID_VALUES: List[str] = [
    "",
    "N",
    "None",
    "nan",
]

# Classification types
CLASSIFICATION_UPGRADE_EQC_RESOLVED = "upgrade_eqc_resolved"
CLASSIFICATION_REGRESSION_MISSING = "regression_missing_resolution"
CLASSIFICATION_REGRESSION_MISMATCH = "regression_company_id_mismatch"
CLASSIFICATION_NEEDS_REVIEW = "needs_review"
CLASSIFICATION_UPGRADE_NAME_CLEANING = "upgrade_name_cleaning"

# =============================================================================
# Report Configuration
# =============================================================================

# Maximum examples to show per difference type
MAX_EXAMPLES_PER_DIFF = 5

# Report file naming
REPORT_PREFIX = "diff_report"
SUMMARY_PREFIX = "diff_summary"
REPORT_DATE_FORMAT = "%Y%m%d_%H%M%S"

# =============================================================================
# Default Values
# =============================================================================

DEFAULT_SHEET_NAME = "规模明细"
DEFAULT_ROW_LIMIT = 100
