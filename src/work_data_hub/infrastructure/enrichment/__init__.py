"""
Company Enrichment and ID Resolution

Provides company identification and enrichment services for domains that require
company information resolution and standardization.

Components:
- CompanyIdResolver: Batch-optimized company ID resolution with hierarchical strategy
- EqcProvider: EQC platform API provider for sync company ID lookup (Story 6.6)
- ResolutionStrategy: Configuration for resolution behavior
- ResolutionStatistics: Statistics from batch resolution operations
- normalize_for_temp_id: Legacy-compatible name normalization for temp ID generation

Architecture Reference:
- AD-002: Legacy-Compatible Temporary Company ID Generation
- AD-010: Infrastructure Layer & Pipeline Composition
"""

from __future__ import annotations

import importlib
from typing import Any

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
    # Story 6.6: EQC Provider
    "EqcProvider",
    "EqcTokenInvalidError",
    "CompanyInfo",
    "EnterpriseInfoProvider",
    "validate_eqc_token",
    # Story 6.1.3: Domain Learning
    "DomainLearningService",
    "DomainLearningConfig",
    "DomainLearningResult",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "CompanyIdResolver": (".company_id_resolver", "CompanyIdResolver"),
    "CompanyMappingRepository": (".mapping_repository", "CompanyMappingRepository"),
    "MatchResult": (".mapping_repository", "MatchResult"),
    "InsertBatchResult": (".mapping_repository", "InsertBatchResult"),
    "ResolutionStrategy": (".types", "ResolutionStrategy"),
    "ResolutionStatistics": (".types", "ResolutionStatistics"),
    "ResolutionResult": (".types", "ResolutionResult"),
    "ResolutionSource": (".types", "ResolutionSource"),
    "normalize_for_temp_id": (".normalizer", "normalize_for_temp_id"),
    "generate_temp_company_id": (".normalizer", "generate_temp_company_id"),
    # Story 6.6: EQC Provider
    "EqcProvider": (".eqc_provider", "EqcProvider"),
    "EqcTokenInvalidError": (".eqc_provider", "EqcTokenInvalidError"),
    "CompanyInfo": (".eqc_provider", "CompanyInfo"),
    "EnterpriseInfoProvider": (".eqc_provider", "EnterpriseInfoProvider"),
    "validate_eqc_token": (".eqc_provider", "validate_eqc_token"),
    # Story 6.1.3: Domain Learning
    "DomainLearningService": (".domain_learning_service", "DomainLearningService"),
    "DomainLearningConfig": (".types", "DomainLearningConfig"),
    "DomainLearningResult": (".types", "DomainLearningResult"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(_LAZY_IMPORTS.keys())))
