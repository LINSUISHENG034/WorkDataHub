"""
Company Enrichment and ID Resolution

Provides company identification and enrichment services for domains that require
company information resolution and standardization.

Components:
- CompanyIdResolver: Batch-optimized company ID resolution with hierarchical strategy
- ResolutionStrategy: Configuration for resolution behavior
- ResolutionStatistics: Statistics from batch resolution operations
- normalize_for_temp_id: Legacy-compatible name normalization for temp ID generation

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- AD-010: Infrastructure Layer & Pipeline Composition
"""

from .company_id_resolver import CompanyIdResolver
from .mapping_repository import (
    CompanyMappingRepository,
    InsertBatchResult,
    MatchResult,
)
from .normalizer import generate_temp_company_id, normalize_for_temp_id
from .types import (
    ResolutionResult,
    ResolutionSource,
    ResolutionStatistics,
    ResolutionStrategy,
)

__all__ = [
    "CompanyIdResolver",
    "CompanyMappingRepository",
    "MatchResult",
    "InsertBatchResult",
    "ResolutionStrategy",
    "ResolutionStatistics",
    "ResolutionResult",
    "ResolutionSource",
    "normalize_for_temp_id",
    "generate_temp_company_id",
]
