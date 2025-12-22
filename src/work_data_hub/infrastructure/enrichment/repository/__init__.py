"""
Company Mapping Repository package.

This package provides the CompanyMappingRepository class for batch-optimized
database operations on the enterprise schema tables.

Story 6.3: Internal Mapping Tables and Database Schema
Story 6.1.1: Extended with enrichment_index table operations
Architecture Reference: AD-010 Infrastructure Layer

Repository Pattern:
- Accepts upstream Connection/Session; caller owns commit/rollback
- No implicit autocommit; wrap inserts in explicit transaction
- Always parameterize via text(); no f-strings
- Log counts only; never log alias/company_id values

Story 7.3: This is a refactored module - all public exports are re-exported
here for backward compatibility.
"""

from .core import CompanyMappingRepository
from .models import EnqueueResult, InsertBatchResult, MatchResult

__all__ = [
    "CompanyMappingRepository",
    "MatchResult",
    "InsertBatchResult",
    "EnqueueResult",
]
