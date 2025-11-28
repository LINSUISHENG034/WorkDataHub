"""Discovery exceptions for file discovery failures.

This module provides structured error context for file discovery operations
following Decision #4 from Epic 3 architecture.
"""

from typing import Literal


class DiscoveryError(Exception):
    """Structured error for file discovery failures.

    Provides consistent error context with stage markers for debugging
    and actionable error messages.

    Attributes:
        domain: The domain being processed (e.g., 'annuity_performance')
        failed_stage: The stage where failure occurred
        original_error: The original exception that caused the failure
        message: Actionable error description
    """

    def __init__(
        self,
        domain: str,
        failed_stage: Literal[
            'config_validation',
            'version_detection',
            'file_matching',
            'excel_reading',
            'normalization'
        ],
        original_error: Exception,
        message: str
    ):
        self.domain = domain
        self.failed_stage = failed_stage
        self.original_error = original_error
        self.message = message
        super().__init__(message)
