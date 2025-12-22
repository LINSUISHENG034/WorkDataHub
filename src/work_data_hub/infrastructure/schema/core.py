"""Core domain schema types for WorkDataHub.

Story 7.5: Domain Registry Pre-modularization
Extracted from domain_registry.py to establish modular structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ColumnType(Enum):
    """Supported column types for domain schemas."""

    STRING = "string"
    DATE = "date"
    DATETIME = "datetime"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    TEXT = "text"


@dataclass
class ColumnDef:
    """Definition of a single column in a domain schema."""

    name: str
    column_type: ColumnType
    nullable: bool = True
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    description: str = ""
    is_primary_key: bool = False


@dataclass
class IndexDef:
    """Definition of a database index."""

    columns: List[str]
    unique: bool = False
    name: Optional[str] = None
    method: Optional[str] = None
    where: Optional[str] = None


@dataclass
class DomainSchema:
    """Complete schema definition for a domain."""

    domain_name: str
    pg_schema: str
    pg_table: str
    sheet_name: str
    primary_key: str = "id"
    delete_scope_key: List[str] = field(default_factory=list)
    composite_key: List[str] = field(default_factory=list)
    columns: List[ColumnDef] = field(default_factory=list)
    indexes: List[IndexDef] = field(default_factory=list)
    bronze_required: List[str] = field(default_factory=list)
    gold_required: List[str] = field(default_factory=list)
    numeric_columns: List[str] = field(default_factory=list)


__all__ = [
    "ColumnType",
    "ColumnDef",
    "IndexDef",
    "DomainSchema",
]
