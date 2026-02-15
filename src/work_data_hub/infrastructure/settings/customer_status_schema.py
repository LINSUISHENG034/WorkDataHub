"""Pydantic schema for customer status evaluation rules configuration.

Story 7.6-18: Config-Driven Status Evaluation Framework

This module provides Pydantic models to validate the structure of
config/customer_status_rules.yml, ensuring required fields are
present and properly typed.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

# Default config path - centralized for consistency
DEFAULT_CONFIG_PATH = "config/customer_status_rules.yml"


class SourceConfig(BaseModel):
    """Configuration for a data source table."""

    schema_name: str = Field(alias="schema", description="Database schema name")
    table: str = Field(..., description="Table name")
    key_fields: List[str] = Field(..., min_length=1, description="Key columns")


class StatusDefinition(BaseModel):
    """Definition of a status field with business context."""

    description: str = Field(..., description="Human-readable description")
    source: str = Field(..., description="Source name or 'derived'")
    time_scope: Literal["yearly", "monthly"] = Field(
        ..., description="Time scope for evaluation"
    )


class MatchField(BaseModel):
    """Field mapping for condition matching."""

    source_field: str = Field(..., description="Field in main query")
    target_field: str = Field(..., description="Field in subquery table")


class ConditionConfig(BaseModel):
    """Configuration for a single evaluation condition."""

    type: Literal[
        "exists_in_year",
        "field_equals",
        "disappeared",
        "first_appearance",
        "status_reference",
        "negation",
        "aggregated_field",
    ] = Field(..., description="Condition type")

    # For exists_in_year
    source: Optional[str] = Field(None, description="Source table reference")
    year_field: Optional[str] = Field(None, description="Field containing year/date")
    match_fields: Optional[List[MatchField]] = Field(
        None, description="Fields to match"
    )

    # For field_equals
    field: Optional[str] = Field(None, description="Field to check")
    value: Optional[Any] = Field(None, description="Expected value")

    # For status_reference
    status: Optional[str] = Field(None, description="Referenced status name")

    # For negation
    condition: Optional[Dict[str, Any]] = Field(
        None, description="Nested condition to negate"
    )

    # For aggregated_field
    aggregation: Optional[str] = Field(None, description="Aggregation function")

    # For disappeared and first_appearance
    period_field: Optional[str] = Field(
        None, description="Field containing the period (e.g., snapshot_month)"
    )
    scope_field: Optional[str] = Field(
        None, description="Optional field to scope the comparison"
    )


class EvaluationRule(BaseModel):
    """Configuration for a status evaluation rule."""

    granularity: Literal["product_line", "plan"] = Field(
        ..., description="Evaluation granularity level"
    )
    operator: Literal["AND", "OR"] = Field(
        default="AND", description="Logical operator for combining conditions"
    )
    conditions: List[ConditionConfig] = Field(
        ..., min_length=1, description="List of conditions"
    )


class CustomerStatusRulesConfig(BaseModel):
    """Top-level configuration for customer status evaluation rules."""

    schema_version: str = Field(default="1.0", description="Config schema version")
    sources: Dict[str, SourceConfig] = Field(
        ..., description="Source table definitions"
    )
    status_definitions: Dict[str, StatusDefinition] = Field(
        ..., description="Status field definitions"
    )
    evaluation_rules: Dict[str, EvaluationRule] = Field(
        ..., description="Evaluation rules for each status"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        """Ensure compatible schema version."""
        supported_versions = ["1.0"]
        if v not in supported_versions:
            raise ValueError(
                f"Unsupported schema version '{v}'. "
                f"Supported versions: {supported_versions}"
            )
        return v


class CustomerStatusConfigError(Exception):
    """Raised when customer status configuration validation fails."""

    pass


def load_customer_status_config(
    config_path: str = DEFAULT_CONFIG_PATH,
) -> CustomerStatusRulesConfig:
    """Load and validate customer status rules configuration.

    Args:
        config_path: Path to the configuration file

    Returns:
        Validated CustomerStatusRulesConfig instance

    Raises:
        CustomerStatusConfigError: If validation fails
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise CustomerStatusConfigError(f"Configuration file not found: {config_path}")

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise CustomerStatusConfigError(f"Invalid YAML in configuration file: {e}")

    try:
        return CustomerStatusRulesConfig(**data)
    except Exception as e:
        raise CustomerStatusConfigError(f"Configuration validation failed: {e}")
