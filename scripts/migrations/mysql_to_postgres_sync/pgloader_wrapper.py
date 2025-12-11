#!/usr/bin/env python3
"""
pgloader Python包装器

提供Python接口来调用pgloader进行MySQL到PostgreSQL的迁移。
支持灵活的配置选项和迁移策略。
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PgloaderWrapper:
    """pgloader Python包装器"""

    def __init__(self, check_pgloader: bool = True):
        """
        初始化包装器

        Args:
            check_pgloader: 是否检查pgloader是否已安装
        """
        if check_pgloader:
            self._check_pgloader_installation()

    def _check_pgloader_installation(self) -> None:
        """检查pgloader是否已安装"""
        try:
            result = subprocess.run(
                ['pgloader', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"pgloader version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("pgloader is not installed or not in PATH")
            logger.error("Install pgloader: https://pgloader.io/")
            sys.exit(1)

    def migrate_databases(self,
                         source_uri: str,
                         target_uri: str,
                         options: Optional[Dict] = None,
                         config_file: Optional[str] = None) -> bool:
        """
        迁移数据库

        Args:
            source_uri: 源数据库连接字符串
            target_uri: 目标数据库连接字符串
            options: 迁移选项
            config_file: 配置文件路径

        Returns:
            迁移是否成功
        """
        cmd = ['pgloader']

        # 如果提供了配置文件
        if config_file:
            cmd.append(config_file)
        else:
            # 使用命令行参数
            cmd.extend([source_uri, target_uri])

            # 添加选项
            if options:
                if options.get('verbose'):
                    cmd.append('--verbose')
                if options.get('debug'):
                    cmd.append('--debug')
                if options.get('dry_run'):
                    cmd.append('--dry-run')

        logger.info(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Migration completed successfully")
            if result.stdout:
                logger.info(f"Output:\n{result.stdout}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Migration failed: {e}")
            if e.stdout:
                logger.info(f"Output:\n{e.stdout}")
            if e.stderr:
                logger.error(f"Error:\n{e.stderr}")
            return False

    def create_config_file(self,
                          source_uri: str,
                          target_uri: str,
                          schema: Optional[str] = None,
                          tables: Optional[List[str]] = None,
                          type_mappings: Optional[Dict] = None,
                          include_data: bool = True,
                          create_tables: bool = True,
                          create_indexes: bool = True,
                          include_foreign_keys: bool = True,
                          reset_sequences: bool = True,
                          batch_size: int = 10000,
                          concurrency: int = 4) -> str:
        """
        创建pgloader配置文件

        Args:
            source_uri: 源数据库连接字符串
            target_uri: 目标数据库连接字符串
            schema: 要迁移的schema
            tables: 要迁移的表列表
            type_mappings: 类型映射
            include_data: 是否包含数据
            create_tables: 是否创建表
            create_indexes: 是否创建索引
            include_foreign_keys: 是否包含外键
            reset_sequences: 是否重置序列
            batch_size: 批处理大小
            concurrency: 并发数

        Returns:
            配置文件路径
        """
        config_lines = []

        # 基础迁移配置
        config_lines.append("load database")
        config_lines.append(f"    from {source_uri}")
        config_lines.append(f"    into {target_uri}")

        # WITH子句
        with_options = []
        if create_tables:
            with_options.append("create tables")
        if create_indexes:
            with_options.append("create indexes")
        if include_data:
            with_options.append("include drop")
        else:
            with_options.append("schema only")
        if reset_sequences:
            with_options.append("reset sequences")
        if include_foreign_keys:
            with_options.append("foreign keys")

        config_lines.append(f"WITH include drop, {', '.join(with_options)}")

        # 性能调优
        config_lines.extend([
            f"    set work_mem to '256MB',",
            f"    maintenance_work_mem to '512MB',",
            f"    batch size = {batch_size},",
            f"    prefetch rows = {batch_size},",
            f"    concurrency = {concurrency}"
        ])

        # 类型映射
        if type_mappings:
            config_lines.append("\nCAST")
            for mysql_type, pg_type in type_mappings.items():
                config_lines.append(f"    type {mysql_type} to {pg_type}")

        # 表选择
        if tables:
            config_lines.append("\nINCLUDING ONLY TABLE NAMES MATCHING")
            for table in tables:
                config_lines.append(f"    '{table}'")

        config_content = '\n'.join(config_lines) + '\n'

        # 写入临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.load', delete=False) as f:
            f.write(config_content)
            config_file = f.name

        logger.info(f"Created pgloader config file: {config_file}")
        return config_file

    def migrate_with_tables(self,
                           source_uri: str,
                           target_uri: str,
                           tables: List[str],
                           options: Optional[Dict] = None) -> bool:
        """
        迁移指定的表

        Args:
            source_uri: 源数据库连接字符串
            target_uri: 目标数据库连接字符串
            tables: 要迁移的表列表
            options: 迁移选项

        Returns:
            迁移是否成功
        """
        config_file = self.create_config_file(
            source_uri=source_uri,
            target_uri=target_uri,
            tables=tables,
            **options or {}
        )

        try:
            return self.migrate_databases(
                source_uri=source_uri,
                target_uri=target_uri,
                config_file=config_file,
                options=options
            )
        finally:
            # 清理临时文件
            os.unlink(config_file)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="pgloader MySQL to PostgreSQL migration wrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --source mysql://root@localhost/db1 --target postgresql:///db2
  %(prog)s --source mysql://... --target postgresql://... --tables table1,table2
  %(prog)s --config migration.load --dry-run
        """
    )

    parser.add_argument(
        '--source',
        help='Source MySQL connection URI'
    )

    parser.add_argument(
        '--target',
        help='Target PostgreSQL connection URI'
    )

    parser.add_argument(
        '--config',
        help='pgloader configuration file path'
    )

    parser.add_argument(
        '--tables',
        help='Comma-separated list of tables to migrate'
    )

    parser.add_argument(
        '--schema-only',
        action='store_true',
        help='Migrate schema only, no data'
    )

    parser.add_argument(
        '--no-foreign-keys',
        action='store_true',
        help='Skip foreign key constraints'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=10000,
        help='Batch size for data loading (default: 10000)'
    )

    parser.add_argument(
        '--concurrency',
        type=int,
        default=4,
        help='Number of concurrent workers (default: 4)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without actually doing it'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )

    args = parser.parse_args()

    # 验证参数
    if not args.config and (not args.source or not args.target):
        parser.error("Either --config or both --source and --target must be provided")

    # 创建pgloader包装器
    wrapper = PgloaderWrapper()

    # 准备选项
    options = {
        'verbose': args.verbose,
        'debug': args.debug,
        'dry_run': args.dry_run,
        'schema_only': args.schema_only,
        'create_tables': not args.schema_only,
        'include_foreign_keys': not args.no_foreign_keys,
        'batch_size': args.batch_size,
        'concurrency': args.concurrency
    }

    success = False

    if args.config:
        # 使用配置文件
        success = wrapper.migrate_databases(
            source_uri="",
            target_uri="",
            config_file=args.config,
            options=options
        )
    else:
        # 使用命令行参数
        if args.tables:
            # 迁移指定表
            tables = [t.strip() for t in args.tables.split(',')]
            success = wrapper.migrate_with_tables(
                source_uri=args.source,
                target_uri=args.target,
                tables=tables,
                options=options
            )
        else:
            # 迁移整个数据库
            success = wrapper.migrate_databases(
                source_uri=args.source,
                target_uri=args.target,
                options=options
            )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()