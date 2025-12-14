"""
Data models for reference backfill operations.

This module defines Pydantic models representing reference table candidates
that can be derived from processed fact data, and configuration models for
the generic backfill framework.
"""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class AnnuityPlanCandidate(BaseModel):
    """
    Candidate model for 年金计划 (Annuity Plan) reference table.

    Derived from processed annuity performance fact data to create
    missing reference entries before fact loading.
    """

    年金计划号: str = Field(
        ..., min_length=1, max_length=255, description="Plan code identifier"
    )
    计划全称: Optional[str] = Field(None, max_length=255, description="Full plan name")
    计划类型: Optional[str] = Field(None, max_length=255, description="Plan type")
    客户名称: Optional[str] = Field(None, max_length=255, description="Client name")
    company_id: Optional[str] = Field(
        None, max_length=50, description="Company identifier"
    )


class PortfolioCandidate(BaseModel):
    """
    Candidate model for 组合计划 (Portfolio Plan) reference table.

    Derived from processed annuity performance fact data to create
    missing reference entries before fact loading.
    """

    组合代码: str = Field(
        ..., min_length=1, max_length=255, description="Portfolio code identifier"
    )
    年金计划号: str = Field(
        ..., min_length=1, max_length=255, description="Plan code (FK)"
    )
    组合名称: Optional[str] = Field(None, max_length=255, description="Portfolio name")
    组合类型: Optional[str] = Field(None, max_length=255, description="Portfolio type")
    运作开始日: Optional[date] = Field(None, description="Operation start date")


# Generic Backfill Framework Configuration Models

class BackfillColumnMapping(BaseModel):
    """
    Configuration for mapping columns from fact data to reference table columns.

    Represents the relationship between source columns in the fact data
    and target columns in the reference table.
    """

    model_config = ConfigDict(extra='forbid')

    source: str = Field(..., description="Fact data column name to extract from")
    target: str = Field(..., description="Reference table column name to fill")
    optional: bool = Field(default=False, description="Whether missing source data should be skipped")

    @field_validator('source', 'target')
    @classmethod
    def validate_column_names(cls, v):
        """Validate column names are non-empty strings."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Column names must be non-empty strings")
        return v.strip()


class ForeignKeyConfig(BaseModel):
    """
    Configuration for a foreign key relationship and its backfill operation.

    Defines how to derive reference table candidates from fact data,
    including column mappings, dependencies, and processing mode.
    """

    model_config = ConfigDict(extra='forbid')

    name: str = Field(..., description="Unique identifier for this foreign key configuration")
    source_column: str = Field(..., description="Column in fact data containing the foreign key values")
    target_table: str = Field(..., description="Reference table name to backfill")
    target_schema: str = Field(
        default="public",
        description="Target schema containing the reference table",
    )
    target_key: str = Field(..., description="Primary key column in target reference table")
    backfill_columns: List[BackfillColumnMapping] = Field(
        ..., description="Column mappings from fact data to reference table"
    )
    mode: Literal["insert_missing", "fill_null_only"] = Field(
        default="insert_missing",
        description="Processing mode: insert_missing adds new records, fill_null_only updates nulls"
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of foreign key names that must be processed before this one"
    )
    skip_blank_values: bool = Field(
        default=False,
        description="Skip blank-like FK values (e.g., empty strings, '(空白)') during candidate derivation",
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate FK name is a non-empty string."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Foreign key name must be a non-empty string")
        return v.strip()

    @field_validator('source_column', 'target_table', 'target_key')
    @classmethod
    def validate_identifiers(cls, v):
        """Validate table/column identifiers are non-empty strings."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Source column, target table, and target key must be non-empty strings")
        return v.strip()

    @field_validator("target_schema")
    @classmethod
    def validate_target_schema(cls, v: str) -> str:
        """Validate schema identifier is non-empty."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError("Target schema must be a non-empty string")
        return v.strip()

    @field_validator('backfill_columns')
    @classmethod
    def validate_backfill_columns(cls, v):
        """Validate at least one backfill column is provided."""
        if not v or len(v) == 0:
            raise ValueError("At least one backfill column mapping must be provided")
        return v


class DomainForeignKeysConfig(BaseModel):
    """
    Configuration for all foreign keys within a domain.

    Container for all foreign key configurations that need to be processed
    for a specific domain's backfill operations.
    """

    model_config = ConfigDict(extra='forbid')

    foreign_keys: List[ForeignKeyConfig] = Field(
        default_factory=list,
        description="List of foreign key configurations for this domain"
    )

    @field_validator('foreign_keys')
    @classmethod
    def validate_foreign_keys(cls, v):
        """Validate foreign key names are unique within the domain."""
        if v:
            names = [fk.name for fk in v]
            if len(names) != len(set(names)):
                duplicates = [name for name in names if names.count(name) > 1]
                raise ValueError(f"Duplicate foreign key names found: {duplicates}")
        return v

    @model_validator(mode="after")
    def validate_dependencies(self):
        """
        Validate depends_on references and detect circular dependencies.

        Rules:
        - depends_on 只能引用同一域内已声明的 FK
        - 不允许自引用
        - 检测环依赖并报错
        """
        names = {fk.name for fk in self.foreign_keys}
        # 同域存在性校验
        for fk in self.foreign_keys:
            missing = [dep for dep in fk.depends_on if dep not in names]
            if missing:
                raise ValueError(
                    f"depends_on must reference same-domain FK: missing {missing}"
                )
            if fk.name in fk.depends_on:
                raise ValueError("circular dependency detected: self reference")

        # 环依赖检测
        graph = {fk.name: fk.depends_on for fk in self.foreign_keys}
        visiting = set()
        visited = set()

        def dfs(node, path):
            if node in visiting:
                cycle_path = "->".join(path + [node])
                raise ValueError(f"circular dependency detected: {cycle_path}")
            if node in visited:
                return
            visiting.add(node)
            for dep in graph.get(node, []):
                dfs(dep, path + [node])
            visiting.remove(node)
            visited.add(node)

        for start in graph:
            dfs(start, [])

        return self
