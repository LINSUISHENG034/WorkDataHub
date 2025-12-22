"""Domain schema definitions package.

Story 7.5: Domain Registry Pre-modularization
Auto-imports and registers all domain schema definitions.
"""

# Import all domain definitions to trigger auto-registration
from . import (
    annuity_income,  # noqa: F401
    annuity_performance,  # noqa: F401
    annuity_plans,  # noqa: F401
    portfolio_plans,  # noqa: F401
)

__all__ = [
    "annuity_performance",
    "annuity_income",
    "annuity_plans",
    "portfolio_plans",
]
