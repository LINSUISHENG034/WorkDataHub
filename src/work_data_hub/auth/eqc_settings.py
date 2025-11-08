"""EQC auth settings loader.

Centralizes configuration for EQC authentication. Values are read from:
- Environment variables with prefix `EQC_`
- A project-local `.env` file (root of repo) if present

This allows durable, checked-in defaults via `.env.example` while keeping
sensitive values outside of version control.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EQCAuthSettings(BaseSettings):
    # Core endpoints
    login_url: str = Field(
        default="https://eqc.pingan.com/#/login?redirect=%2Fhome",
        description="EQC login page URL",
    )

    # Credentials and factors
    username: Optional[str] = None
    password: Optional[str] = None
    otp: Optional[str] = None

    # Behavior flags
    auto_slider: bool = True
    reuse_session: bool = True
    clear_session: bool = False
    reset_storage: bool = False

    # Session persistence
    storage_state: str = ".cache/eqc_storage_state.json"

    # Token capture filter (comma separated substrings)
    capture_url_substr: str = "/kg-api-hfd/api/search/"

    model_config = SettingsConfigDict(
        env_prefix="EQC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Singleton settings instance
settings = EQCAuthSettings()
