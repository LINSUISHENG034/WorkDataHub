"""
Company ID Resolver for batch company identification.

This module provides the CompanyIdResolver class for batch-optimized company ID
resolution with hierarchical strategy support. It extracts and centralizes the
company ID resolution logic from domain layer for cross-domain reuse.

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- AD-010: Infrastructure Layer & Pipeline Composition

Resolution Priority (Story 6.4 - Multi-Tier Lookup):
1. YAML overrides (5 priority levels: plan → account → hardcode → name → account_name)
2. Database cache lookup (enterprise.company_mapping)
3. Existing company_id column passthrough + backflow
4. EQC sync lookup (budgeted, cached)
5. Temporary ID generation (HMAC-SHA1 based)

Story 7.3: This file is now a facade module re-exporting from the resolver package.
All public symbols are preserved for backward compatibility.
"""

# Re-export all public symbols from resolver package for backward compatibility
from work_data_hub.infrastructure.cleansing import normalize_company_name

# Re-export normalize functions for test compatibility
# Tests monkeypatch these via the facade module path (Story 7.3 AC-4)
from .normalizer import normalize_for_temp_id
from .resolver import CompanyIdResolver

# Export constants that may be used externally
from .resolver.core import (
    DEFAULT_SALT,
    SALT_ENV_VAR,
    YAML_PRIORITY_ORDER,
)

# Re-export _stdlib_logger from db_strategy for test compatibility
# Tests mock company_id_resolver._stdlib_logger (Story 7.3 AC-4)
from .resolver.db_strategy import _stdlib_logger

__all__ = [
    "CompanyIdResolver",
    "DEFAULT_SALT",
    "SALT_ENV_VAR",
    "YAML_PRIORITY_ORDER",
    "_stdlib_logger",
    "normalize_for_temp_id",
    "normalize_company_name",
]
