"""
SQL module for centralized SQL generation.

This module provides reusable utilities for building SQL statements with
proper identifier quoting, schema qualification, and dialect-specific syntax.

Story 6.2-P10: SQL Module Architecture
"""

from .core.identifier import qualify_table, quote_identifier
from .core.parameters import build_indexed_params, remap_records
from .dialects.postgresql import PostgreSQLDialect
from .operations.insert import InsertBuilder

__all__ = [
    "quote_identifier",
    "qualify_table",
    "build_indexed_params",
    "remap_records",
    "PostgreSQLDialect",
    "InsertBuilder",
]
