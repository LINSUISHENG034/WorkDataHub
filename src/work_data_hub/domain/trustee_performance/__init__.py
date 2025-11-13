"""Compatibility facade for trustee performance domain.

Story 1.6 consolidated the trustee performance implementation under
`sample_trustee_performance`. This package re-exports those symbols to maintain
older import paths used in tests and documentation.
"""

from .models import *  # noqa: F401,F403
from .service import *  # noqa: F401,F403

__all__ = [  # type: ignore[var-annotated]
    *[
        name
        for name in globals()
        if not name.startswith("_") and name not in {"typing", "models", "service"}
    ]
]
