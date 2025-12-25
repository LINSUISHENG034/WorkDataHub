"""
Company Mapping Repository for database access layer.

This module provides the CompanyMappingRepository class for batch-optimized
database operations on the enterprise schema tables.

Note: company_mapping table removed in Story 7.1-4 (Zero Legacy).
Repository now exclusively serves enrichment_index (Story 6.1.1).

Story 6.3: Internal Mapping Tables and Database Schema
Story 6.1.1: Extended with enrichment_index table operations
Architecture Reference: AD-010 Infrastructure Layer

Repository Pattern:
- Accepts upstream Connection/Session; caller owns commit/rollback
- No implicit autocommit; wrap inserts in explicit transaction
- Always parameterize via text(); no f-strings
- Log counts only; never log alias/company_id values

Story 7.3: This file is now a facade module re-exporting from the repository package.
All public symbols are preserved for backward compatibility.
"""

# Re-export all public symbols from repository package for backward compatibility
from .repository import (
    CompanyMappingRepository,
    EnqueueResult,
    InsertBatchResult,
    MatchResult,
)

__all__ = [
    "CompanyMappingRepository",
    "MatchResult",
    "InsertBatchResult",
    "EnqueueResult",
]
