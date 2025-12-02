"""
Infrastructure Settings and Configuration

Provides utilities for loading and managing infrastructure-level configuration.
This includes configuration loaders, validators, and runtime settings management.

Components (Story 5.3):
- data_source_schema: Pydantic models for data_sources.yml validation
- loader: YAML mapping file loaders
"""

from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourceConfigV2,
    DataSourcesConfig,
    DataSourcesValidationError,
    DiscoveryConfig,
    DomainConfig,
    DomainConfigV2,
    get_domain_config,
    get_domain_config_v2,
    validate_data_sources_config,
    validate_data_sources_config_v2,
)
from work_data_hub.infrastructure.settings.loader import (
    MappingLoaderError,
    get_mappings_dir,
    load_business_type_code,
    load_company_branch,
    load_company_id_overrides_plan,
    load_default_portfolio_code,
    load_yaml_mapping,
)

__all__: list[str] = [
    # Schema models
    "DataSourceConfigV2",
    "DataSourcesConfig",
    "DataSourcesValidationError",
    "DiscoveryConfig",
    "DomainConfig",
    "DomainConfigV2",
    "get_domain_config",
    "get_domain_config_v2",
    "validate_data_sources_config",
    "validate_data_sources_config_v2",
    # Loader functions
    "MappingLoaderError",
    "get_mappings_dir",
    "load_business_type_code",
    "load_company_branch",
    "load_company_id_overrides_plan",
    "load_default_portfolio_code",
    "load_yaml_mapping",
]
