"""Warehouse loader that stays inside the Clean Architecture I/O ring (Story 1.6).

All database connectivity, transactional logic, and bulk loading behaviors live
here so that domain pipelines from Story 1.5 remain pure. Orchestration layers
inject this loader.
"""

import logging

from work_data_hub.utils.logging import get_logger

from .core import WarehouseLoader
from .insert_builder import (
    _adapt_param,
    _ensure_list_of_dicts,
    _get_column_order,
    _prepare_unique_pk_tuples,
    build_delete_sql,
    build_insert_sql,
    build_insert_sql_with_conflict,
)

# Re-exporting from submodules
from .models import DataWarehouseLoaderError, LoadResult
from .operations import (
    fill_null_only,
    insert_missing,
    load,
)
from .sql_utils import quote_ident, quote_qualified, quote_table

# Logger for backward compatibility (though likely unused externally)
logger = logging.getLogger(__name__)
structured_logger = get_logger(__name__)

__all__ = [
    "DataWarehouseLoaderError",
    "LoadResult",
    "WarehouseLoader",
    "quote_ident",
    "quote_qualified",
    "quote_table",
    "_ensure_list_of_dicts",
    "_get_column_order",
    "build_insert_sql",
    "build_insert_sql_with_conflict",
    "build_delete_sql",
    "_prepare_unique_pk_tuples",
    "_adapt_param",
    "insert_missing",
    "fill_null_only",
    "load",
]
