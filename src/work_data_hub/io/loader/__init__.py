"""
PostgreSQL data warehouse loader for WorkDataHub.

This module provides transactional bulk loading capabilities with SQL injection
protection, performance optimization through chunking, and comprehensive error handling.
"""

from .warehouse_loader import (
    DataWarehouseLoaderError,
    build_delete_sql,
    build_insert_sql,
    load,
    quote_ident,
)

__all__ = [
    "DataWarehouseLoaderError",
    "build_delete_sql",
    "build_insert_sql",
    "load",
    "quote_ident",
]
