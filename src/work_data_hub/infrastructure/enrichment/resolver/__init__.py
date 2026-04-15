"""
Company ID Resolver package.

This package provides batch-optimized company ID resolution with hierarchical
strategy support. It centralizes the company ID resolution logic from domain
layer for cross-domain reuse.

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- AD-010: Infrastructure Layer & Pipeline Composition

Resolution Flow (annuity-performance relevant view):
1. YAML overrides (active execution path in yaml_strategy.py: plan → hardcode → name)
2. Database cache lookup (enrichment_index - Story 6.1.1)
3. Existing company_id column passthrough + backflow
4. EQC sync lookup (budgeted, cached)
5. Temporary ID generation (HMAC-SHA1 based)

Compatibility note: `account` / `account_name` YAML files may still appear in
compatibility-oriented loaders, but they are not part of the active
annuity-performance YAML override execution path.

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
