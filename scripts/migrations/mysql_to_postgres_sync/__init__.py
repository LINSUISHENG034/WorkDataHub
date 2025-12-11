"""
MySQL to PostgreSQL Schema Synchronization Tool

这个包提供了从MySQL SQL文件到PostgreSQL数据库的索引和外键同步功能。

主要组件:
- MySQLSQLParser: 解析MySQL SQL文件
- PostgreSQLDDLGenerator: 生成PostgreSQL DDL语句
- DependencyChecker: 检查依赖表是否存在
- SchemaSynchronizer: 主同步器

使用示例:
    from mysql_to_postgres_sync import SchemaSynchronizer

    synchronizer = SchemaSynchronizer(db_connection, sql_dir)
    report = synchronizer.sync_table('business', '规模明细')
"""

from sqlglot_parser import SQLGlotParser, MySQLTableDefinition, MySQLIndex, MySQLForeignKey, find_sql_file_for_table
from ddl_generator import PostgreSQLDDLGenerator
from dependency_checker import DependencyChecker
from sync_schema import SchemaSynchronizer

__version__ = "1.0.0"
__author__ = "WorkDataHub Team"

__all__ = [
    'SQLGlotParser',
    'MySQLTableDefinition',
    'MySQLIndex',
    'MySQLForeignKey',
    'find_sql_file_for_table',
    'PostgreSQLDDLGenerator',
    'DependencyChecker',
    'SchemaSynchronizer'
]