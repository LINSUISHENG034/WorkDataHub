"""
Company ID Resolver package.

This package provides batch-optimized company ID resolution with hierarchical
strategy support. It centralizes the company ID resolution logic from domain
layer for cross-domain reuse.

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- AD-010: Infrastructure Layer & Pipeline Composition

Resolution Priority (Story 6.4 - Multi-Tier Lookup):
1. YAML overrides (5 priority levels: plan → account → hardcode → name → account_name)
2. Database cache lookup (enrichment_index - Story 6.1.1)
3. Existing company_id column passthrough + backflow
4. EQC sync lookup (budgeted, cached)
5. Temporary ID generation (HMAC-SHA1 based)

Note: company_mapping table removed in Story 7.1-4 (Zero Legacy).
All legacy fallback paths have been removed.

This is a refactored module - see Story 7.3 for decomposition details.
All public exports are re-exported here for backward compatibility.
"""

from .cache_warming import CacheWarmer
from .core import CompanyIdResolver
from .progress import ProgressReporter

# Re-export all public symbols for backward compatibility
__all__ = [
    "CacheWarmer",
    "CompanyIdResolver",
    "ProgressReporter",
]
