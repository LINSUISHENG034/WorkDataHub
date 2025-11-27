"""Shared utilities and common types."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

__all__ = [
    "OTPResult",
    "PATokenClient",
    "build_client_from_env",
    "load_env_file",
    "ValidationError",
    "ValidationSummary",
    "ValidationThresholdExceeded",
    "ValidationErrorReporter",
]

if TYPE_CHECKING:  # pragma: no cover - imported only for typing
    from .error_reporter import (
        ValidationError,
        ValidationErrorReporter,
        ValidationSummary,
        ValidationThresholdExceeded,
    )
    from .patoken_client import (
        OTPResult,
        PATokenClient,
        build_client_from_env,
        load_env_file,
    )


def __getattr__(name: str) -> Any:
    if name in __all__:
        if name in (
            "ValidationError",
            "ValidationSummary",
            "ValidationThresholdExceeded",
            "ValidationErrorReporter",
        ):
            module = importlib.import_module(".error_reporter", __name__)
        else:
            module = importlib.import_module(".patoken_client", __name__)
        return getattr(module, name)
    raise AttributeError(f"module 'work_data_hub.utils' has no attribute {name!r}")
