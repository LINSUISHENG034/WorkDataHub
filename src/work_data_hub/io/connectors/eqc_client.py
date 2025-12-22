"""
EQC (Enterprise Query Center) HTTP client for WorkDataHub.
(Facade module for backward compatibility)
"""

import logging

# Re-export from new package structure
from work_data_hub.io.connectors.eqc.core import EQCClient
from work_data_hub.io.connectors.eqc.models import (
    EQCAuthenticationError,
    EQCClientError,
    EQCNotFoundError,
    EQCRateLimitError,
)

logger = logging.getLogger(__name__)

__all__ = [
    "EQCClient",
    "EQCClientError",
    "EQCAuthenticationError",
    "EQCRateLimitError",
    "EQCNotFoundError",
]
