"""
Shared Configuration Constants for Cleaner Comparison.

This module contains non-domain-specific constants used across the comparison scripts.
Domain-specific values have been migrated to configs/ directory.

Note: For backward compatibility, some constants are still exported here.
Prefer using the domain config classes in configs/ for domain-specific values.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

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

DEFAULT_ROW_LIMIT = 100
