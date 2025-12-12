"""
Data models for reference sync operations.

This module defines Pydantic models for configuring reference data sync
from authoritative sources (Legacy MySQL, config files, etc.).
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


class ColumnMapping(BaseModel):
    """
    Configuration for mapping columns from source to target table.

    Represents the relationship between source columns in the data source
    and target columns in the reference table.
    """

    model_config = ConfigDict(extra='forbid')

    source: str = Field(..., description="Source column name to extract from")
    target: str = Field(..., description="Target table column name to fill")

    @field_validator('source', 'target')
    @classmethod
    def validate_column_names(cls, v: str) -> str:
        """Validate column names are non-empty strings."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Column names must be non-empty strings")
        return v.strip()


class IncrementalConfig(BaseModel):
    """
    Configuration for incremental sync operations.

    Defines how to perform incremental updates based on timestamp columns.
    """

    model_config = ConfigDict(extra='forbid')

    where: str = Field(
        ...,
        description="WHERE clause for incremental sync (e.g., 'updated_at >= :last_synced_at')"
    )
    updated_at_column: str = Field(
        ...,
        description="Column name containing update timestamp"
    )

    @field_validator('where', 'updated_at_column')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Validate fields are non-empty strings."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Incremental config fields must be non-empty strings")
        return v.strip()


class LegacyMySQLSourceConfig(BaseModel):
    """
    Configuration for Legacy MySQL data source.

    Defines table name, column mappings, and optional incremental sync settings.
    """

    model_config = ConfigDict(extra='forbid')

    table: str = Field(..., description="Source table name in Legacy MySQL")
    columns: List[ColumnMapping] = Field(
        ...,
        description="Column mappings from source to target"
    )
    incremental: Optional[IncrementalConfig] = Field(
        None,
        description="Optional incremental sync configuration"
    )

    @field_validator('table')
    @classmethod
    def validate_table(cls, v: str) -> str:
        """Validate table name is non-empty."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Table name must be a non-empty string")
        return v.strip()

    @field_validator('columns')
    @classmethod
    def validate_columns(cls, v: List[ColumnMapping]) -> List[ColumnMapping]:
        """Validate at least one column mapping is provided."""
        if not v or len(v) == 0:
            raise ValueError("At least one column mapping must be provided")
        return v


class ConfigFileSourceConfig(BaseModel):
    """
    Configuration for config file data source.

    Defines file path and expected schema version.
    """

    model_config = ConfigDict(extra='forbid')

    file_path: str = Field(..., description="Path to YAML config file")
    schema_version: str = Field(..., description="Expected schema version")

    @field_validator('file_path', 'schema_version')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Validate fields are non-empty strings."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Config file fields must be non-empty strings")
        return v.strip()


class ReferenceSyncTableConfig(BaseModel):
    """
    Configuration for syncing a single reference table.

    Defines source type, target table, sync mode, and source-specific configuration.
    """

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., description="Human-readable name for this sync operation")
    target_table: str = Field(..., description="Target reference table name")
    target_schema: str = Field(
        default="business",
        description="Target schema name"
    )
    source_type: Literal["legacy_mysql", "config_file"] = Field(
        ...,
        description="Type of data source"
    )
    source_config: Dict[str, Any] = Field(
        ...,
        description="Source-specific configuration"
    )
    sync_mode: Literal["upsert", "delete_insert"] = Field(
        default="upsert",
        description="Sync mode: upsert or delete_insert"
    )
    primary_key: str = Field(..., description="Primary key column name")
    batch_size: Optional[int] = Field(
        default=None,
        ge=100,
        le=50000,
        description="Optional batch size override for this table (falls back to global batch_size)",
    )

    @field_validator('name', 'target_table', 'primary_key')
    @classmethod
    def validate_identifiers(cls, v: str) -> str:
        """Validate identifiers are non-empty strings."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Identifiers must be non-empty strings")
        return v.strip()


class ReferenceSyncConfig(BaseModel):
    """
    Root configuration for reference sync operations.

    Container for all reference table sync configurations.
    """

    model_config = ConfigDict(extra='forbid')

    enabled: bool = Field(default=True, description="Whether reference sync is enabled")
    schedule: str = Field(
        default="0 1 * * *",
        description="Cron schedule for sync operations"
    )
    tables: List[ReferenceSyncTableConfig] = Field(
        default_factory=list,
        description="List of table sync configurations"
    )

    # Configurable defaults
    concurrency: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of concurrent sync operations"
    )
    batch_size: int = Field(
        default=5000,
        ge=100,
        le=50000,
        description="Batch size for bulk operations"
    )

    @field_validator('tables')
    @classmethod
    def validate_tables(cls, v: List[ReferenceSyncTableConfig]) -> List[ReferenceSyncTableConfig]:
        """Validate table names are unique."""
        if v:
            names = [table.name for table in v]
            if len(names) != len(set(names)):
                duplicates = [name for name in names if names.count(name) > 1]
                raise ValueError(f"Duplicate table sync names found: {duplicates}")
        return v
