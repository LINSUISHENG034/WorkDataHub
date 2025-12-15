"""Data source connectors for file discovery and reference data sync.

Keep this package import lightweight: pytest and other tooling import submodules
like `eqc_client`, which requires importing this package first. Heavy optional
connectors (e.g., SQLAlchemy-backed adapters) are loaded lazily to avoid import
side effects and improve startup time.
"""

from __future__ import annotations

import importlib
from typing import Any

from .exceptions import DiscoveryError
from .version_scanner import VersionedPath, VersionScanner

__all__ = [
    "DiscoveryError",
    "VersionedPath",
    "VersionScanner",
    "AdapterFactory",
    "DataSourceAdapter",
    "PostgresSourceAdapter",
    "MySQLSourceAdapter",
    "LegacyMySQLConnector",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "AdapterFactory": (".adapter_factory", "AdapterFactory"),
    "DataSourceAdapter": (".adapter_factory", "DataSourceAdapter"),
    "PostgresSourceAdapter": (".postgres_source_adapter", "PostgresSourceAdapter"),
    "MySQLSourceAdapter": (".mysql_source_adapter", "MySQLSourceAdapter"),
    "LegacyMySQLConnector": (".legacy_mysql_connector", "LegacyMySQLConnector"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(_LAZY_IMPORTS.keys())))
