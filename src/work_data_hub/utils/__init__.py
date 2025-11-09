"""Shared utilities and common types."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

__all__ = [
    "OTPResult",
    "PATokenClient",
    "build_client_from_env",
    "load_env_file",
]

if TYPE_CHECKING:  # pragma: no cover - imported only for typing
    from .patoken_client import (
        OTPResult,
        PATokenClient,
        build_client_from_env,
        load_env_file,
    )


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = importlib.import_module(".patoken_client", __name__)
        return getattr(module, name)
    raise AttributeError(f"module 'work_data_hub.utils' has no attribute {name!r}")
