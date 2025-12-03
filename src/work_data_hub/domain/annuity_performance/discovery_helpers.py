"""
File discovery helper functions for annuity performance domain.

Story 4.8: Extracted from service.py to reduce module size and improve
separation of concerns. Contains discovery-related utilities.

Story 5.8: Removed TYPE_CHECKING import from io layer to comply with
TID251 Clean Architecture rules. Uses Protocol-based typing instead.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from work_data_hub.domain.pipelines.types import ErrorContext


# Protocol for FileDiscoveryService to avoid importing from io layer
class FileDiscoveryProtocol(Protocol):
    """Protocol for file discovery service (Clean Architecture boundary)."""

    def discover_and_load(self, *, domain: str, month: str) -> Any:
        """Discover and load data for a domain and month."""
        ...

logger = logging.getLogger(__name__)


def run_discovery(
    *,
    file_discovery: FileDiscoveryProtocol,
    domain: str,
    month: str,
) -> Any:
    """
    Wrapper for FileDiscoveryService.discover_and_load with consistent logging.

    Args:
        file_discovery: Injected FileDiscoveryService instance
        domain: Domain identifier (e.g., 'annuity_performance')
        month: Target month in YYYYMM format

    Returns:
        DataDiscoveryResult with discovered file data

    Raises:
        DiscoveryError: If file discovery fails
    """
    try:
        return file_discovery.discover_and_load(domain=domain, month=month)
    except Exception as exc:
        error_ctx = ErrorContext(
            error_type="discovery_error",
            operation="file_discovery",
            domain=domain,
            stage="discovery",
            error_message=f"Failed to discover file for {domain} month {month}",
            details={"month": month, "exception": str(exc)},
        )
        logger.error("annuity.discovery.failed", extra=error_ctx.to_log_dict())
        raise


def normalize_month(month: str) -> str:
    """
    Validate YYYYMM format and return zero-padded text.

    Args:
        month: Month string to validate

    Returns:
        Validated 6-digit month string

    Raises:
        ValueError: If month format is invalid
    """
    if month is None:
        raise ValueError("month is required (YYYYMM)")

    text = str(month).strip()
    if len(text) != 6 or not text.isdigit():
        raise ValueError("month must be a 6-digit string in YYYYMM format")

    yyyy = int(text[:4])
    mm = int(text[4:])
    if yyyy < 2000 or yyyy > 2100:
        raise ValueError("month year component must be between 2000 and 2100")
    if mm < 1 or mm > 12:
        raise ValueError("month component must be between 01 and 12")
    return text


__all__ = [
    "run_discovery",
    "normalize_month",
]
