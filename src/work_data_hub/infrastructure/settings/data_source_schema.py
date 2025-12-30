"""
Schema validation for WorkDataHub data sources configuration.

This module provides Pydantic models to validate the structure of
data_sources.yml configuration file, ensuring required fields are
present and properly typed.

IMPORTANT: This module contains TWO schema versions:
1. Legacy schema (DomainConfig, DataSourcesConfig) - for existing pattern-based config
2. Epic 3 schema (DomainConfigV2, DataSourceConfigV2) - for new base_path +
    version_strategy config

12. Story 3.0 implements Epic 3 schema while maintaining backward compatibility.

Migrated from config/schema.py in Story 5.3.
"""

import copy
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


class DomainConfig(BaseModel):
    """Schema for individual domain configuration."""

    description: Optional[str] = Field(None, description="Human-readable description")
    pattern: str = Field(..., description="Regex pattern for file matching")
    select: Literal["latest_by_year_month", "latest_by_mtime"] = Field(
        ..., description="Selection strategy for multiple files"
    )
    sheet: Union[int, str] = Field(0, description="Excel sheet to process")
    table: str = Field(..., description="Target database table")
    pk: List[str] = Field(..., min_length=1, description="Primary key columns")
    required_columns: Optional[List[str]] = Field(
        None, description="Required data columns"
    )
    validation: Optional[Dict[str, Any]] = Field(None, description="Validation rules")


class DiscoveryConfig(BaseModel):
    """Schema for global discovery configuration."""

    file_extensions: Optional[List[str]] = Field(
        None, description="File extensions to scan"
    )
    exclude_directories: Optional[List[str]] = Field(
        None, description="Directories to exclude"
    )
    ignore_patterns: Optional[List[str]] = Field(
        None, description="File patterns to ignore"
    )
    max_depth: Optional[int] = Field(10, description="Maximum directory scan depth")
    follow_symlinks: Optional[bool] = Field(False, description="Follow symbolic links")


class DataSourcesConfig(BaseModel):
    """Schema for complete data_sources.yml structure."""

    domains: Dict[str, DomainConfig] = Field(
        ..., min_length=1, description="Domain configurations"
    )
    discovery: Optional[DiscoveryConfig] = Field(
        None, description="Global discovery settings"
    )


class DataSourcesValidationError(Exception):
    """Raised when data sources configuration validation fails."""

    pass


def validate_data_sources_config(
    config_path: str = "config/data_sources.yml",
) -> bool:
    """
    Validate data_sources.yml against Epic 3 schema (DataSourceConfigV2).

    Args:
        config_path: Path to the data_sources.yml file to validate

    Returns:
        True if valid

    Raises:
        DataSourcesValidationError: If validation fails
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise DataSourcesValidationError(f"Configuration file not found: {config_path}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise DataSourcesValidationError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        raise DataSourcesValidationError(f"Failed to load configuration file: {e}")

    try:
        # Epic 3: Use DataSourceConfigV2 for new base_path + version_strategy schema
        config = DataSourceConfigV2(**data)
        logger.info(
            "Successfully validated data_sources configuration with "
            f"{len(config.domains)} domains"
        )
        return True
    except ValidationError as e:
        raise DataSourcesValidationError(f"data_sources.yml validation failed: {e}")


def get_domain_config(
    domain_name: str, config_path: str = "config/data_sources.yml"
) -> "DomainConfigV2":
    """
    Get validated Epic 3 configuration for a specific domain.

    Args:
        domain_name: Name of the domain to get config for
        config_path: Path to the data_sources.yml file

    Returns:
        Validated DomainConfigV2 instance

    Raises:
        DataSourcesValidationError: If validation fails or domain not found
    """
    # First validate the entire config
    validate_data_sources_config(config_path)

    # Load and return specific domain config
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if domain_name not in data.get("domains", {}):
        raise DataSourcesValidationError(
            f"Domain '{domain_name}' not found in configuration"
        )

    return DomainConfigV2(**data["domains"][domain_name])


# ============================================================================
# Epic 3 Schema (Story 3.0) - New base_path + version_strategy architecture
# ============================================================================


class OutputConfig(BaseModel):
    """Configuration for data output destination."""

    table: str = Field(..., description="Target database table name")
    schema_name: str = Field("public", description="Target database schema")
    pk: List[str] = Field(
        default_factory=list, description="Primary key columns for delete_insert mode"
    )


class DomainConfigV2(BaseModel):
    """
    Epic 3 domain configuration schema with version-aware file discovery.

    This schema supports the new architecture from Epic 3 Tech Spec:
    - base_path with template variables ({YYYYMM}, {YYYY}, {MM})
    - file_patterns for glob-based matching
    - version_strategy for intelligent version folder selection
    - output configuration for database destination
    - Security: Path traversal prevention and template variable whitelist
    """

    base_path: str = Field(
        ...,
        description="Path template with {YYYYMM}, {YYYY}, {MM} placeholders",
        examples=["reference/monthly/{YYYYMM}/收集数据/数据采集"],
    )

    file_patterns: List[str] = Field(
        ...,
        min_length=1,
        description="Glob patterns to match files",
        examples=[["*年金终稿*.xlsx", "*规模明细*.xlsx"]],
    )

    exclude_patterns: List[str] = Field(
        default_factory=list,
        description="Glob patterns to exclude (temp files, emails)",
        examples=[["~$*", "*回复*", "*.eml"]],
    )

    sheet_name: Union[str, int] = Field(
        ...,
        description="Excel sheet name (string) or 0-based index (int)",
        examples=["规模明细", 0],
    )

    version_strategy: Literal["highest_number", "latest_modified", "manual"] = Field(
        default="highest_number",
        description="Strategy for selecting version folder",
    )

    fallback: Literal["error", "use_latest_modified"] = Field(
        default="error",
        description="Fallback behavior when version detection ambiguous",
    )

    output: Optional[OutputConfig] = Field(
        default=None,
        description="Output destination configuration (table, schema)",
    )

    requires_backfill: bool = Field(
        default=False,
        description="Whether domain requires FK backfill (Story 7.4-2)",
    )

    @field_validator("base_path")
    @classmethod
    def validate_base_path(cls, v: str) -> str:
        """
        Validate base_path for security and template variable correctness.

        Security checks:
        1. Prevent directory traversal attacks (no '..' in path)
        2. Whitelist template variables (only {YYYYMM}, {YYYY}, {MM} allowed)

        Args:
            v: base_path value to validate

        Returns:
            Validated base_path

        Raises:
            ValueError: If path contains '..' or invalid template variables
        """
        # Security: Prevent directory traversal
        if ".." in v:
            raise ValueError("base_path cannot contain '..' (directory traversal)")

        # Security: Whitelist template variables (prevent injection)
        allowed_vars = {"{YYYYMM}", "{YYYY}", "{MM}"}
        found_vars = set(re.findall(r"\{[^}]+\}", v))
        invalid_vars = found_vars - allowed_vars
        if invalid_vars:
            raise ValueError(
                f"Invalid template variables: {invalid_vars}. "
                f"Only allowed: {allowed_vars}"
            )

        return v

    @field_validator("file_patterns")
    @classmethod
    def validate_file_patterns(cls, v: List[str]) -> List[str]:
        """
        Ensure at least one file pattern is specified.

        Args:
            v: List of file patterns

        Returns:
            Validated file patterns list

        Raises:
            ValueError: If file_patterns list is empty
        """
        if len(v) == 0:
            raise ValueError("file_patterns must have at least 1 pattern")
        return v


class DataSourceConfigV2(BaseModel):
    """
    Epic 3 top-level configuration for all domains.

    This schema validates the complete data_sources.yml structure with:
    - schema_version for backward compatibility tracking
    - domains mapping with Epic 3 DomainConfigV2 structure
    - Story 6.2-P14 AC-4: Optional defaults section for inheritance
    """

    schema_version: str = Field(
        default="1.0",
        description="Config schema version for backward compatibility",
    )

    defaults: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Story 6.2-P14: Default values applied to all domains",
    )

    domains: Dict[str, DomainConfigV2] = Field(
        ...,
        description="Mapping of domain names to their configurations",
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        """
        Ensure compatible schema version.

        Args:
            v: Schema version string

        Returns:
            Validated schema version

        Raises:
            ValueError: If schema version is not supported
        """
        # Story 6.2-P14: Added version 1.1 for defaults support
        # Story 7.4-2: Added version 1.2 for requires_backfill field
        supported_versions = ["1.0", "1.1", "1.2"]
        if v not in supported_versions:
            raise ValueError(
                f"Unsupported schema version '{v}'. "
                f"Supported versions: {supported_versions}"
            )
        return v

    @field_validator("domains")
    @classmethod
    def validate_domains(
        cls, v: Dict[str, DomainConfigV2]
    ) -> Dict[str, DomainConfigV2]:
        """
        Ensure at least one domain is configured.

        Args:
            v: Domains dictionary

        Returns:
            Validated domains dictionary

        Raises:
            ValueError: If domains dictionary is empty
        """
        if len(v) == 0:
            raise ValueError("domains cannot be empty, at least 1 domain required")
        return v


def validate_data_sources_config_v2(
    config_path: str = "config/data_sources.yml",
) -> bool:
    """
    Validate Epic 3 data_sources.yml against V2 schema.

    This function validates the new Epic 3 configuration structure with
    base_path, file_patterns, and version_strategy fields.

    Args:
        config_path: Path to the data_sources.yml file to validate

    Returns:
        True if valid

    Raises:
        DataSourcesValidationError: If validation fails
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise DataSourcesValidationError(f"Configuration file not found: {config_path}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise DataSourcesValidationError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        raise DataSourcesValidationError(f"Failed to load configuration file: {e}")

    try:
        # Validate using Epic 3 Pydantic schema
        config = DataSourceConfigV2(**data)
        logger.info(
            "configuration.validated",
            extra={
                "schema_version": "v2",
                "domain_count": len(config.domains),
                "domains": list(config.domains.keys()),
            },
        )
        return True
    except ValidationError as e:
        raise DataSourcesValidationError(f"data_sources.yml validation failed: {e}")


def get_domain_config_v2(
    domain_name: str, config_path: str = "config/data_sources.yml"
) -> DomainConfigV2:
    """
    Get validated Epic 3 configuration for a specific domain.

    Args:
        domain_name: Name of the domain to get config for
        config_path: Path to the data_sources.yml file

    Returns:
        Validated DomainConfigV2 instance

    Raises:
        DataSourcesValidationError: If validation fails or domain not found
    """
    # First validate the entire config
    validate_data_sources_config_v2(config_path)

    # Load and return specific domain config
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if domain_name not in data.get("domains", {}):
        raise DataSourcesValidationError(
            f"Domain '{domain_name}' not found in configuration"
        )

    domain_raw: Dict[str, Any] = data["domains"][domain_name] or {}
    defaults: Dict[str, Any] = data.get("defaults") or {}

    merged = _merge_with_defaults(domain_raw, defaults) if defaults else domain_raw
    return DomainConfigV2(**merged)


def _merge_with_defaults(
    domain_config: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge domain config with defaults using inheritance rules.

    Story 6.2-P14: Implements defaults/overrides pattern for data_sources.yml

    Merge Rules:
    - Scalars: domain value wins over default
    - Lists: replace by default. Use "+" prefix to extend (e.g., "+*pattern*")
    - Dicts: deep merge (domain values override defaults)

    Args:
        domain_config: Domain-specific configuration
        defaults: Default configuration values

    Returns:
        Merged configuration dictionary
    """
    result = copy.deepcopy(defaults)

    for key, value in domain_config.items():
        if key not in result:
            # Key only exists in domain, add it
            result[key] = value
        elif isinstance(value, dict) and isinstance(result[key], dict):
            # Deep merge for dicts
            result[key] = _merge_with_defaults(value, result[key])
        elif isinstance(value, list):
            # Check for extend pattern (+ prefix)
            extend_items = [
                v[1:] for v in value if isinstance(v, str) and v.startswith("+")
            ]
            replace_items = [
                v for v in value if not (isinstance(v, str) and v.startswith("+"))
            ]

            if extend_items and not replace_items:
                # Extend only: add to defaults
                base_list = result.get(key, [])
                result[key] = (
                    list(base_list) + extend_items
                    if isinstance(base_list, list)
                    else extend_items
                )
            elif replace_items:
                # Replace mode: use domain value plus any extends
                result[key] = replace_items + extend_items
            else:
                # Empty list: clear defaults
                result[key] = []
        else:
            # Scalar: domain wins
            result[key] = value

    return result
