"""
Unit tests for EqcLookupConfig dataclass (Story 6.2-P17 AC-1).

Tests factory methods, serialization, and semantic enforcement.
"""

import argparse
from work_data_hub.infrastructure.enrichment.eqc_lookup_config import EqcLookupConfig


def test_disabled_factory():
    """Test disabled() factory creates safe default state."""
    config = EqcLookupConfig.disabled()

    assert not config.enabled
    assert config.sync_budget == 0
    assert not config.auto_create_provider
    assert config.export_unknown_names is False
    assert config.auto_refresh_token is False
    assert not config.should_auto_create_provider  # Computed property


def test_from_cli_args_semantic_enforcement():
    """Test --no-enrichment disables ALL features (Story 6.2-P17 AC-4)."""
    # Case 1: --no-enrichment should ignore sync_budget
    args = argparse.Namespace(
        enrichment_enabled=False,
        enrichment_sync_budget=100,  # This should be IGNORED
        export_unknown_names=True,
    )
    config = EqcLookupConfig.from_cli_args(args)

    assert not config.enabled
    assert config.sync_budget == 0  # Forced to 0 despite CLI arg
    assert config.export_unknown_names is False  # Disabled forces all features off
    assert config.auto_refresh_token is False

    # Case 2: Enrichment enabled
    args2 = argparse.Namespace(
        enrichment_enabled=True,
        enrichment_sync_budget=10,
        export_unknown_names=False,
        no_auto_refresh_token=True,
    )
    config2 = EqcLookupConfig.from_cli_args(args2)

    assert config2.enabled
    assert config2.sync_budget == 10
    assert config2.auto_create_provider is True  # Default when enabled
    assert not config2.export_unknown_names
    assert not config2.auto_refresh_token


def test_from_dict_to_dict_roundtrip():
    """Test Dagster serialization roundtrip (Story 6.2-P17 AC-4)."""
    original = EqcLookupConfig(
        enabled=True,
        sync_budget=5,
        auto_create_provider=False,
        export_unknown_names=False,
        auto_refresh_token=False,
    )

    # Serialize
    data = original.to_dict()
    assert isinstance(data, dict)
    assert data["enabled"] is True
    assert data["sync_budget"] == 5

    # Deserialize
    restored = EqcLookupConfig.from_dict(data)
    assert restored.enabled == original.enabled
    assert restored.sync_budget == original.sync_budget
    assert restored.auto_create_provider == original.auto_create_provider
    assert restored.export_unknown_names == original.export_unknown_names
    assert restored.auto_refresh_token == original.auto_refresh_token


def test_should_auto_create_provider_property():
    """Test computed property logic (Story 6.2-P17)."""
    # Case 1: enabled=False → should_auto_create=False
    config1 = EqcLookupConfig(enabled=False, auto_create_provider=True)
    assert not config1.should_auto_create_provider

    # Case 2: enabled=True, auto_create=False → False
    config2 = EqcLookupConfig(enabled=True, auto_create_provider=False)
    assert not config2.should_auto_create_provider

    # Case 3: enabled=True, auto_create=True → True
    config3 = EqcLookupConfig(enabled=True, auto_create_provider=True)
    assert config3.should_auto_create_provider


def test_from_settings_graceful_fallback():
    """Test from_settings() handles missing settings gracefully."""
    # This should not raise even if settings fail to load
    config = EqcLookupConfig.from_settings()

    # Should return a config object (may be disabled if settings missing)
    assert isinstance(config, EqcLookupConfig)
