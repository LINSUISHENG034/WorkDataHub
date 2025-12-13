"""
Reference backfill domain module.

This module provides functionality for deriving and validating reference
table candidates from processed fact data, enabling automatic backfill
of missing reference entries before fact loading.
"""

from .models import (
    AnnuityPlanCandidate,
    PortfolioCandidate,
    BackfillColumnMapping,
    ForeignKeyConfig,
    DomainForeignKeysConfig,
)
from .service import (
    derive_plan_candidates,
    derive_portfolio_candidates,
    validate_plan_candidates,
    validate_portfolio_candidates,
)
from .generic_service import GenericBackfillService, BackfillResult
from .sync_service import ReferenceSyncService, SyncResult
from .hybrid_service import HybridReferenceService, HybridResult, CoverageMetrics
from .config_loader import load_foreign_keys_config, get_domain_from_context
from .observability import (
    ObservabilityService,
    ReferenceDataMetrics,
    AlertConfig,
    AlertResult,
    ReferenceDataAuditLogger,
)

__all__ = [
    "AnnuityPlanCandidate",
    "PortfolioCandidate",
    "BackfillColumnMapping",
    "ForeignKeyConfig",
    "DomainForeignKeysConfig",
    "derive_plan_candidates",
    "derive_portfolio_candidates",
    "validate_plan_candidates",
    "validate_portfolio_candidates",
    "GenericBackfillService",
    "BackfillResult",
    "ReferenceSyncService",
    "SyncResult",
    "HybridReferenceService",
    "HybridResult",
    "CoverageMetrics",
    "load_foreign_keys_config",
    "get_domain_from_context",
    "ObservabilityService",
    "ReferenceDataMetrics",
    "AlertConfig",
    "AlertResult",
    "ReferenceDataAuditLogger",
]
