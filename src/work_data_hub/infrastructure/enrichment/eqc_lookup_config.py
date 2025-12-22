"""
EQC Lookup Configuration - Single Source of Truth for EQC enrichment settings.

Story 6.2-P17: EQC Lookup Configuration Unification
This module provides EqcLookupConfig as the centralized configuration dataclass
for all EQC lookup behavior, eliminating hidden "magic" auto-creation logic.

Architecture:
- Frozen dataclass for immutability and compile-time safety
- Multiple factory methods for different initialization contexts
- Serialization support for Dagster config passing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

try:
    from argparse import Namespace
except ImportError:
    Namespace = Any  # type: ignore[misc,assignment]


@dataclass(frozen=True)
class EqcLookupConfig:
    """
    Configuration for EQC (Enterprise Query Center) lookup behavior.

    This dataclass serves as the Single Source of Truth (SSOT) for all EQC
    enrichment configuration, enforcing explicit configuration and preventing
    hidden auto-creation of EQC providers.

    Attributes:
        enabled: Master switch for EQC lookup. When False, all EQC operations
            should be skipped regardless of other settings.
        sync_budget: Maximum number of synchronous EQC API calls allowed per
            batch resolution. 0 disables sync lookups.
        auto_create_provider: Whether CompanyIdResolver should auto-create
            EqcProvider when mapping_repository is available. Only takes effect
            when enabled=True.
        export_unknown_names: Whether to export unresolved company names to CSV
            for manual review.
        auto_refresh_token: Whether to automatically refresh EQC token when
            validation fails at CLI startup.

    Example:
        >>> # Disable all EQC operations
        >>> config = EqcLookupConfig.disabled()
        >>> assert not config.enabled
        >>> assert config.sync_budget == 0

        >>> # Enable with explicit settings
        >>> config = EqcLookupConfig(
        ...     enabled=True,
        ...     sync_budget=10,
        ...     auto_create_provider=True,
        ... )
        >>> assert config.should_auto_create_provider
    """

    enabled: bool = False
    sync_budget: int = 0
    auto_create_provider: bool = False
    export_unknown_names: bool = True
    auto_refresh_token: bool = True

    @property
    def should_auto_create_provider(self) -> bool:
        """
        Computed property: whether EqcProvider should be auto-created.

        Returns True only when BOTH conditions are met:
        1. enabled=True (master switch)
        2. auto_create_provider=True (explicit opt-in)

        This ensures no hidden auto-creation when enrichment is disabled.
        """
        return self.enabled and self.auto_create_provider

    @classmethod
    def disabled(cls) -> EqcLookupConfig:
        """
        Factory: Default disabled state (no EQC operations).

        This is the recommended default for:
        - Unit tests that don't need EQC
        - Domains that don't use enrichment
        - CLI --no-enrichment flag

        Returns:
            EqcLookupConfig with all EQC features disabled.

        Example:
            >>> config = EqcLookupConfig.disabled()
            >>> assert not config.enabled
            >>> assert not config.should_auto_create_provider
        """
        return cls(
            enabled=False,
            sync_budget=0,
            auto_create_provider=False,
            # Story 6.2-P17 semantic enforcement: --no-enrichment disables all EQC features
            # (including related side effects like CSV export and token refresh).
            export_unknown_names=False,
            auto_refresh_token=False,
        )

    @classmethod
    def from_cli_args(cls, args: Namespace) -> EqcLookupConfig:
        """
        Factory: Build config from CLI arguments with semantic enforcement.

        Semantic Rules:
        - If --no-enrichment flag is set, ALL enrichment features are disabled
          regardless of other flags (e.g., --enrichment-sync-budget is ignored)
        - enrichment_enabled controls the master switch
        - auto_refresh_token defaults to True unless --no-auto-refresh-token

        Args:
            args: Parsed argparse.Namespace from CLI

        Returns:
            EqcLookupConfig with values extracted from CLI args.

        Example:
            >>> import argparse
            >>> args = argparse.Namespace(
            ...     enrichment_enabled=False,  # --no-enrichment
            ...     enrichment_sync_budget=10,  # This will be IGNORED
            ... )
            >>> config = EqcLookupConfig.from_cli_args(args)
            >>> assert not config.enabled
            >>> assert config.sync_budget == 0  # Ignored due to disabled
        """
        # Check for --no-enrichment flag (could be enrichment_enabled=False)
        enrichment_enabled = getattr(args, "enrichment_enabled", False)

        # When enrichment is disabled, force all related settings to disabled state
        if not enrichment_enabled:
            return cls.disabled()

        # Enrichment is enabled - extract other settings
        return cls(
            enabled=True,
            sync_budget=getattr(args, "enrichment_sync_budget", 0),
            auto_create_provider=True,  # Default to auto-create when enabled
            export_unknown_names=getattr(args, "export_unknown_names", True),
            auto_refresh_token=not getattr(args, "no_auto_refresh_token", False),
        )

    @classmethod
    def from_settings(cls) -> EqcLookupConfig:
        """
        Factory: Load config from global settings (legacy domain migration).

        This factory is provided for domains that were previously relying on
        implicit global settings loading. New code should prefer explicit
        config passing via from_cli_args() or direct instantiation.

        Returns:
            EqcLookupConfig loaded from global settings.

        Example:
            >>> # For legacy domains not yet refactored to pass explicit config
            >>> config = EqcLookupConfig.from_settings()
        """
        try:
            from work_data_hub.config.settings import get_settings

            settings = get_settings()

            # Check if EQC token is configured
            has_token = bool(getattr(settings, "eqc_token", None))

            # Default to enabled if token exists
            enabled = has_token

            return cls(
                enabled=enabled,
                sync_budget=getattr(settings, "company_sync_lookup_limit", 5),
                auto_create_provider=enabled,  # Auto-create when enabled
                export_unknown_names=True,
                auto_refresh_token=True,
            )
        except Exception as e:
            # Graceful fallback if settings loading fails (explicitly logged to avoid silent misconfig).
            logging.getLogger(__name__).warning(
                "eqc_lookup_config.from_settings_failed",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )
            return cls.disabled()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EqcLookupConfig:
        """
        Factory: Deserialize config from dictionary (Dagster config rehydration).

        This factory is used by Dagster ops to reconstruct EqcLookupConfig from
        the serialized run_config dictionary.

        Args:
            data: Dictionary with config fields (from to_dict())

        Returns:
            Reconstructed EqcLookupConfig instance.

        Example:
            >>> data = {
            ...     "enabled": True,
            ...     "sync_budget": 10,
            ...     "auto_create_provider": True,
            ... }
            >>> config = EqcLookupConfig.from_dict(data)
            >>> assert config.enabled
        """
        return cls(
            enabled=data.get("enabled", False),
            sync_budget=data.get("sync_budget", 0),
            auto_create_provider=data.get("auto_create_provider", False),
            export_unknown_names=data.get("export_unknown_names", True),
            auto_refresh_token=data.get("auto_refresh_token", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize config to dictionary (Dagster config serialization).

        This method is used to serialize EqcLookupConfig for passing through
        Dagster's run_config system.

        Returns:
            Dictionary representation of config fields.

        Example:
            >>> config = EqcLookupConfig(enabled=True, sync_budget=10)
            >>> data = config.to_dict()
            >>> assert data["enabled"] is True
            >>> assert data["sync_budget"] == 10
        """
        return {
            "enabled": self.enabled,
            "sync_budget": self.sync_budget,
            "auto_create_provider": self.auto_create_provider,
            "export_unknown_names": self.export_unknown_names,
            "auto_refresh_token": self.auto_refresh_token,
        }
