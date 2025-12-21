"""
Unit test for CLI schema inheritance fix.

Story: CLI Schema Inheritance Issue
Verifies that get_domain_config_v2() properly inherits schema_name from defaults.
"""

import pytest
from work_data_hub.infrastructure.settings.data_source_schema import get_domain_config_v2


def test_annuity_performance_inherits_schema_name_from_defaults():
    """
    Verify annuity_performance config inherits schema_name='business' from defaults.
    
    This test validates Story 6.2-P14 fix: CLI should use get_domain_config_v2()
    which applies _merge_with_defaults() to inherit schema_name from defaults section.
    """
    # Load annuity_performance config (has no explicit schema_name in domain section)
    config = get_domain_config_v2('annuity_performance', 'config/data_sources.yml')
    
    # Should have inherited schema_name: "business" from defaults
    assert config.output is not None, "annuity_performance should have output config"
    assert config.output.schema_name == "business", \
        f"Expected schema_name='business' (inherited from defaults), got '{config.output.schema_name}'"
    assert config.output.table == "规模明细", \
        f"Expected table='规模明细', got '{config.output.table}'"


def test_annuity_income_inherits_schema_name_from_defaults():
    """Verify annuity_income also inherits schema_name='business' from defaults."""
    config = get_domain_config_v2('annuity_income', 'config/data_sources.yml')
    
    assert config.output is not None
    assert config.output.schema_name == "business"


def test_sandbox_trustee_overrides_schema_name():
    """
    Verify sandbox_trustee_performance overrides schema_name='sandbox' (not using defaults).
    
    This domain explicitly sets schema_name='sandbox' in its config, overriding the
    default 'business'. Tests that overrides work correctly.
    """
    config = get_domain_config_v2('sandbox_trustee_performance', 'config/data_sources.yml')
    
    assert config.output is not None
    assert config.output.schema_name == "sandbox", \
        f"Expected schema_name='sandbox' (explicit override), got '{config.output.schema_name}'"
