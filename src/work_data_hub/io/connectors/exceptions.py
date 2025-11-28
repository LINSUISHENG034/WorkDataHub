"""Discovery exceptions for file discovery failures.

Provides structured context for Epic 3 Story 3.5 with clear stage markers.
"""

from enum import Enum
from typing import Dict, Literal


class DiscoveryStage(str, Enum):
    """Enum for discovery pipeline stages."""

    CONFIG_VALIDATION = "config_validation"
    VERSION_DETECTION = "version_detection"
    FILE_MATCHING = "file_matching"
    EXCEL_READING = "excel_reading"
    NORMALIZATION = "normalization"


class DiscoveryError(Exception):
    """Structured error for file discovery failures with stage context."""

    def __init__(
        self,
        domain: str,
        failed_stage: Literal[
            "config_validation",
            "version_detection",
            "file_matching",
            "excel_reading",
            "normalization",
        ],
        original_error: Exception,
        message: str,
    ):
        self.domain = domain
        self.failed_stage = failed_stage
        self.original_error = original_error
        super().__init__(message)

    def __str__(self) -> str:  # pragma: no cover - trivial string repr
        return (
            f"Discovery failed for domain '{self.domain}' "
            f"at stage '{self.failed_stage}': {self.args[0]}"
        )

    def to_dict(self) -> Dict[str, str]:
        """Convert to structured dict for logging."""
        return {
            "error_type": "DiscoveryError",
            "domain": self.domain,
            "failed_stage": self.failed_stage,
            "message": str(self),
            "original_error_type": type(self.original_error).__name__,
            "original_error_message": str(self.original_error),
        }
