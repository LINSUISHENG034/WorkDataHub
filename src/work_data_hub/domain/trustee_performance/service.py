"""Compatibility layer that re-exports trustee performance services."""

from src.work_data_hub.domain.sample_trustee_performance.service import *  # noqa: F401,F403

__all__ = [name for name in globals() if not name.startswith("_")]
