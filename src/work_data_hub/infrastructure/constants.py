"""Shared constants for infrastructure layer (Story 7.1-16).

Constants used across multiple infrastructure modules for date validation,
month formatting, and Unicode processing.
"""

# Date validation - valid year range for business data
MIN_VALID_YEAR = 2000
MAX_VALID_YEAR = 2100

# Calendar constants
MONTHS_PER_YEAR = 12
MIN_MONTH = 1
MAX_MONTH = 12

# YYYYMM format validation
YYYYMM_LENGTH = 6

# Processing validation (Story 7.1-16)
# Drop rate threshold for warning when too many records are filtered
DROP_RATE_THRESHOLD = 0.5  # 50% drop rate triggers warning
