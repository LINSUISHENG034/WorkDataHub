"""Data source connectors for file discovery and reference data sync."""

from .exceptions import DiscoveryError
from .version_scanner import VersionedPath, VersionScanner
from .adapter_factory import AdapterFactory, DataSourceAdapter
from .postgres_source_adapter import PostgresSourceAdapter
from .mysql_source_adapter import MySQLSourceAdapter
from .legacy_mysql_connector import LegacyMySQLConnector

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
