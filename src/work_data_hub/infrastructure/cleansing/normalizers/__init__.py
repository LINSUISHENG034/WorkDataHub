"""Customer name normalization utilities.

This module provides unified customer/company name normalization functions
for consistent name handling across the entire codebase.

Primary export:
    normalize_customer_name: Unified normalization function
"""

from work_data_hub.infrastructure.cleansing.normalizers.customer_name import (
    INVALID_PLACEHOLDERS,
    STATUS_MARKERS,
    normalize_customer_name,
)

__all__ = ["normalize_customer_name", "STATUS_MARKERS", "INVALID_PLACEHOLDERS"]
