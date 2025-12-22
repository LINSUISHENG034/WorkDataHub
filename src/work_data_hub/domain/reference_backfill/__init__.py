"""
Reference backfill domain module.

This module provides functionality for deriving and validating reference
table candidates from processed fact data, enabling automatic backfill
of missing reference entries before fact loading.
"""

from .config_loader import get_domain_from_context, load_foreign_keys_config
from .generic_service import BackfillResult, GenericBackfillService
from .hybrid_service import CoverageMetrics, HybridReferenceService, HybridResult
from .models import (
    AnnuityPlanCandidate,
    BackfillColumnMapping,
    DomainForeignKeysConfig,
    ForeignKeyConfig,
    PortfolioCandidate,
)
from .observability import (
    AlertConfig,
    AlertResult,
    ObservabilityService,
    ReferenceDataAuditLogger,
    ReferenceDataMetrics,
)
from .service import (
    derive_plan_candidates,
    derive_portfolio_candidates,
    validate_plan_candidates,
    validate_portfolio_candidates,
)
from .sync_config_loader import load_reference_sync_config
from .sync_service import ReferenceSyncService, SyncResult

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
    "load_reference_sync_config",
    "get_domain_from_context",
    "ObservabilityService",
    "ReferenceDataMetrics",
    "AlertConfig",
    "AlertResult",
    "ReferenceDataAuditLogger",
]
