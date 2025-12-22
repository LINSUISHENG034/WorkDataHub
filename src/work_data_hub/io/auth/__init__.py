# Authentication module for EQC platform automation
# Story 6.6: Migrated from auth/ to io/auth/ for Clean Architecture compliance

from work_data_hub.io.auth.eqc_auth_handler import (
    get_auth_token_interactively,
    get_auth_token_with_validation,
    run_get_token,
    run_get_token_with_validation,
)
from work_data_hub.io.auth.models import (
    AuthenticationError,
    AuthTimeoutError,
    AuthTokenResult,
    BrowserError,
)

__all__ = [
    "AuthenticationError",
    "AuthTimeoutError",
    "AuthTokenResult",
    "BrowserError",
    "get_auth_token_interactively",
    "get_auth_token_with_validation",
    "run_get_token",
    "run_get_token_with_validation",
]
