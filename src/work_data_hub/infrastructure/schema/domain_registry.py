"""Domain schema registry (Single Source of Truth) for WorkDataHub.

Story 6.2-P13: Unified Domain Schema Management Architecture
Story 7.5: Domain Registry Pre-modularization

This module serves as a facade for backward compatibility.
All functionality is now modularized into:
- core.py: Type definitions (ColumnType, ColumnDef, IndexDef, DomainSchema)
- registry.py: Registry management functions
- ddl_generator.py: SQL generation logic
- definitions/: Per-domain schema files

Note on layering:
This module lives under `work_data_hub.infrastructure` so other layers can
import schema definitions without importing `work_data_hub.io`, preserving
Clean Architecture boundaries.
"""

from __future__ import annotations

# Trigger domain registration by importing definitions package
from . import definitions  # noqa: F401

# Re-export core types
from .core import ColumnDef, ColumnType, DomainSchema, IndexDef

# Re-export DDL generator
from .ddl_generator import generate_create_table_sql

# Re-export registry functions
from .registry import (
    get_composite_key,
    get_delete_scope_key,
    get_domain,
    list_domains,
    register_domain,
)

__all__ = [
    "ColumnType",
    "ColumnDef",
    "IndexDef",
    "DomainSchema",
    "register_domain",
    "get_domain",
    "list_domains",
    "get_composite_key",
    "get_delete_scope_key",
    "generate_create_table_sql",
]
