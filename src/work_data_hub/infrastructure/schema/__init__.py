"""Infrastructure-level schema registry (Story 6.2-P13).

This package intentionally lives under `infrastructure/` so other layers can
depend on schema definitions without importing `work_data_hub.io`, preserving
Clean Architecture boundaries enforced by linting.
"""

from .domain_registry import (
    ColumnDef,
    ColumnType,
    DomainSchema,
    IndexDef,
    generate_create_table_sql,
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
