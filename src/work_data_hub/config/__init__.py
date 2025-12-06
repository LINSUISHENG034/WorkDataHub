"""Configuration management for WorkDataHub.

This module provides centralized configuration loaded from environment variables
with validation using Pydantic BaseSettings.

Usage:
    >>> from work_data_hub.config import settings
    >>> print(settings.DATABASE_URL)
    >>> print(settings.LOG_LEVEL)

    Or using the factory function:
    >>> from work_data_hub.config import get_settings
    >>> settings = get_settings()
"""

from work_data_hub.config.mapping_loader import (
    PRIORITY_LEVELS,
    get_flat_overrides,
    load_company_id_overrides,
)
from work_data_hub.config.settings import Settings, get_settings

# Pre-instantiated singleton for convenient module-level import
# Note: This will raise ValidationError if DATABASE_URL is not set
# For testing, import get_settings directly and call it with monkeypatched env vars
try:
    settings = get_settings()
except Exception:
    # In test environments or when DATABASE_URL isn't set,
    # settings will be None and users should call get_settings() directly
    settings = None  # type: ignore

__all__ = [
    "Settings",
    "get_settings",
    "settings",
    "load_company_id_overrides",
    "get_flat_overrides",
    "PRIORITY_LEVELS",
]
