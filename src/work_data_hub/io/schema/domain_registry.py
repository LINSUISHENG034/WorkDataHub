"""Compatibility shim for domain registry (Story 6.2-P13).

Clean Architecture linting forbids other layers importing `work_data_hub.io`.
The canonical implementation lives in `work_data_hub.infrastructure.schema`.

This module remains for backward compatibility with existing imports:
`from work_data_hub.io.schema.domain_registry import ...`.
"""

from work_data_hub.infrastructure.schema.domain_registry import (
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
