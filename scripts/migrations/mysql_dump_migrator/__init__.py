"""
MySQL Dump to PostgreSQL Migrator.

This module provides tools to migrate MySQL dump files to PostgreSQL,
supporting multi-database dumps with schema-based organization.
"""

from .converter import MySQLToPostgreSQLConverter
from .migrator import MigrationConfig, MigrationReport, PostgreSQLMigrator
from .parser import DatabaseContent, MySQLDumpParser

__all__ = [
    "MySQLDumpParser",
    "DatabaseContent",
    "MySQLToPostgreSQLConverter",
    "PostgreSQLMigrator",
    "MigrationConfig",
    "MigrationReport",
]
