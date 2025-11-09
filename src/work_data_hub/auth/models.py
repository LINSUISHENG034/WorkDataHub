"""
Pydantic models and exception hierarchy for EQC authentication flows.

These abstractions are consumed both by runtime code and the unit tests in
``tests/auth`` that assert strict validation behaviour, so they intentionally
mirror the constraints described in Story 1.2.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class AuthenticationError(Exception):
    """Base exception for authentication failures."""


class AuthTimeoutError(AuthenticationError):
    """Raised when the interactive authentication exceeds the allotted time."""


class BrowserError(AuthenticationError):
    """Raised when Playwright/Chromium encounters a fatal error."""


class AuthTokenResult(BaseModel):
    """
    Token metadata captured from EQC authentication.

    Attributes:
        token: Authentication token captured from EQC headers.
        source_url: Source page that produced the token.
        captured_at: UTC timestamp when the token was captured.
        validated: Whether downstream verification has been performed.
    """

    token: str = Field(..., min_length=20, max_length=100)
    source_url: str = Field(..., min_length=1)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validated: bool = False

    @field_validator("token")
    @classmethod
    def normalize_token(cls, value: str) -> str:
        """Trim whitespace and enforce the minimum length check."""
        cleaned = value.strip()
        if len(cleaned) < 20:
            msg = "Token must be at least 20 characters long"
            raise ValueError(msg)
        return cleaned

    model_config = {"str_strip_whitespace": True}


__all__ = [
    "AuthenticationError",
    "AuthTimeoutError",
    "BrowserError",
    "AuthTokenResult",
]
