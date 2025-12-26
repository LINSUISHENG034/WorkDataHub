"""Auth boundary (compat shim).

Auth implementations live under `work_data_hub.io.auth` to keep the Clean
Architecture dependency direction consistent. This package provides a stable
import path for existing code/tests.

**Note:** The previous EQC auth handler facade was removed in Story 7.1-15
to fix TID251 Clean Architecture violations. Import auth functions directly
from `work_data_hub.io.auth.eqc_auth_handler`.
"""

__all__: list[str] = []
