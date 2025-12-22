"""
EQC Connector Models and Exceptions.
"""

class EQCClientError(Exception):
    """Base exception for EQC client errors."""

    pass


class EQCAuthenticationError(EQCClientError):
    """Raised when EQC authentication fails (401)."""

    pass


class EQCRateLimitError(EQCClientError):
    """Raised when rate limit exceeded and retries exhausted."""

    pass


class EQCNotFoundError(EQCClientError):
    """Raised when requested resource not found (404)."""

    pass
