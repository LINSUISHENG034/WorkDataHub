"""
Schema validation for WorkDataHub data sources configuration.

This module provides Pydantic models to validate the structure of
data_sources.yml configuration file, ensuring required fields are
present and properly typed.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, ValidationError

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
    config_path: str = "src/work_data_hub/config/data_sources.yml",
) -> bool:
    """
    Validate data_sources.yml against schema.

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
        # PATTERN: Use Pydantic validation like settings.py
        config = DataSourcesConfig(**data)
        logger.info(
            "Successfully validated data_sources configuration with "
            f"{len(config.domains)} domains"
        )
        return True
    except ValidationError as e:
        raise DataSourcesValidationError(f"data_sources.yml validation failed: {e}")


def get_domain_config(
    domain_name: str, config_path: str = "src/work_data_hub/config/data_sources.yml"
) -> DomainConfig:
    """
    Get validated configuration for a specific domain.

    Args:
        domain_name: Name of the domain to get config for
        config_path: Path to the data_sources.yml file

    Returns:
        Validated DomainConfig instance

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

    return DomainConfig(**data["domains"][domain_name])
