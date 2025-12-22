"""
File discovery connector anchored in the I/O layer (Story 1.6).
(Facade module for backward compatibility)
"""

import logging

# Re-export from new package structure
from work_data_hub.io.connectors.discovery import (
    DataDiscoveryResult,
    DiscoveryMatch,
    FileDiscoveryService,
)

logger = logging.getLogger(__name__)

__all__ = [
    "FileDiscoveryService",
    "DiscoveryMatch",
    "DataDiscoveryResult",
]
