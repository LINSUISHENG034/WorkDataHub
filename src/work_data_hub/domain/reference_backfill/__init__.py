"""
Reference backfill domain module.

This module provides functionality for deriving and validating reference
table candidates from processed fact data, enabling automatic backfill
of missing reference entries before fact loading.
"""

from .models import AnnuityPlanCandidate, PortfolioCandidate
from .service import (
    derive_plan_candidates,
    derive_portfolio_candidates,
    validate_plan_candidates,
    validate_portfolio_candidates,
)

__all__ = [
    "AnnuityPlanCandidate",
    "PortfolioCandidate",
    "derive_plan_candidates",
    "derive_portfolio_candidates",
    "validate_plan_candidates",
    "validate_portfolio_candidates",
]
