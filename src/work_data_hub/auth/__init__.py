"""Auth boundary (compat shim).

Auth implementations live under `work_data_hub.io.auth` to keep the Clean
Architecture dependency direction consistent. This package provides a stable
import path for existing code/tests.
"""

from work_data_hub.auth.eqc_auth_handler import (  # noqa: F401
    get_auth_token_interactively,
    get_auth_token_with_validation,
    run_get_token,
    run_get_token_with_validation,
)

__all__ = [
    "get_auth_token_interactively",
    "get_auth_token_with_validation",
    "run_get_token",
    "run_get_token_with_validation",
]

