#!/usr/bin/env python3
"""
MySQL到PostgreSQL Schema同步工具

用于根据MySQL SQL文件为PostgreSQL数据库表自动添加索引和外键约束。

使用方法:
    python sync_schema.py --table schema.table_name
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from sqlglot_parser import SQLGlotParser, find_sql_file_for_table, MySQLTableDefinition
from ddl_generator import PostgreSQLDDLGenerator
from dependency_checker import DependencyChecker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sync_schema.log')
    ]
)

logger = logging.getLogger(__name__)


class SchemaSynchronizer:
    """Schema同步器"""

    def __init__(self, db_connection: str, sql_dir: str):
        """
        初始化同步器

        Args:
            db_connection: PostgreSQL连接字符串
            sql_dir: SQL文件目录
        """
        self.db_connection = db_connection
        self.sql_dir = Path(sql_dir)
        self.parser = SQLGlotParser()
        self.dependency_checker = DependencyChecker(db_connection)

    def sync_table(self, schema: str, table_name: str, dry_run: bool = False) -> Dict:
        """
        同步指定表的索引和外键

        Args:
            schema: Schema名
            table_name: 表名
            dry_run: 是否只显示要执行的SQL而不实际执行

        Returns:
            同步结果报告
        """
        report = {
            'schema': schema,
            'table_name': table_name,
            'sql_file_found': False,
            'sql_file_path': None,
            'mysql_table_def': None,
            'indexes_to_create': [],
            'foreign_keys_to_create': [],
            'skipped_items': [],
            'errors': [],
            'success': False
        }

        logger.info(f"开始同步表 {schema}.{table_name}")

        try:
            # 1. 查找SQL文件
            sql_file = find_sql_file_for_table(self.sql_dir, schema, table_name)
            if not sql_file:
                report['errors'].append(f"未找到表 {schema}.{table_name} 对应的SQL文件")
                return report

            report['sql_file_found'] = True
            report['sql_file_path'] = str(sql_file)
            logger.info(f"找到SQL文件: {sql_file}")

            # 2. 解析SQL文件
            mysql_table_def = self.parser.parse_sql_file(sql_file)
            if not mysql_table_def:
                report['errors'].append("解析SQL文件失败")
                return report

            report['mysql_table_def'] = mysql_table_def
            logger.info(f"解析完成: {len(mysql_table_def.indexes)} 个索引, {len(mysql_table_def.foreign_keys)} 个外键")

            # 3. 检查目标表是否存在
            if not self.dependency_checker.check_table_exists(schema, table_name):
                report['errors'].append(f"目标表 {schema}.{table_name} 不存在")
                return report

            # 4. 生成DDL
            ddl_generator = PostgreSQLDDLGenerator(schema, table_name)
            ddl_statements = ddl_generator.generate_batch_ddl(
                mysql_table_def.indexes,
                mysql_table_def.foreign_keys
            )

            # 5. 检查依赖
            dependency_report = self.dependency_checker.get_dependency_report(
                schema, table_name,
                mysql_table_def.indexes,
                mysql_table_def.foreign_keys
            )

            # 6. 过滤要执行的项目
            indexes_to_create = []
            foreign_keys_to_create = []

            # 处理索引
            for stmt_type, name, ddl in ddl_statements:
                if stmt_type == 'INDEX':
                    # 检查索引是否已存在
                    pg_index_name = ddl_generator._generate_postgres_index_name(
                        next(idx for idx in mysql_table_def.indexes if idx.name == name)
                    )
                    if pg_index_name not in dependency_report['existing_indexes']:
                        indexes_to_create.append((name, ddl))
                    else:
                        report['skipped_items'].append(f"索引 {name} 已存在，跳过")

            # 处理外键
            if dependency_report['can_create_foreign_keys']:
                for stmt_type, name, ddl in ddl_statements:
                    if stmt_type == 'FOREIGN_KEY':
                        if name not in dependency_report['existing_foreign_keys']:
                            foreign_keys_to_create.append((name, ddl))
                        else:
                            report['skipped_items'].append(f"外键 {name} 已存在，跳过")
            else:
                # 跳过所有外键
                for fk in mysql_table_def.foreign_keys:
                    ref_table_info = dependency_report['foreign_key_dependencies'].get(fk.ref_table, {})
                    if not ref_table_info.get('exists'):
                        report['skipped_items'].append(f"外键 {fk.name} - 引用表 {fk.ref_table} 不存在")

            report['indexes_to_create'] = indexes_to_create
            report['foreign_keys_to_create'] = foreign_keys_to_create

            # 7. 执行DDL（如果不是dry run）
            if not dry_run:
                execution_report = self._execute_ddl(
                    schema, table_name,
                    indexes_to_create,
                    foreign_keys_to_create
                )
                report.update(execution_report)
            else:
                logger.info("DRY RUN模式 - 显示将要执行的SQL:")
                for name, ddl in indexes_to_create + foreign_keys_to_create:
                    print(f"\n-- {name}")
                    print(ddl)
                    print(";")

            report['success'] = True
            logger.info(f"同步完成: {len(indexes_to_create)} 个索引, {len(foreign_keys_to_create)} 个外键")

        except Exception as e:
            logger.error(f"同步失败: {e}")
            report['errors'].append(str(e))

        return report

    def _execute_ddl(self, schema: str, table_name: str,
                    indexes: List[Tuple[str, str]],
                    foreign_keys: List[Tuple[str, str]]) -> Dict:
        """
        执行DDL语句

        Args:
            schema: Schema名
            table_name: 表名
            indexes: 要创建的索引列表
            foreign_keys: 要创建的外键列表

        Returns:
            执行结果
        """
        import psycopg2

        execution_report = {
            'executed_statements': [],
            'execution_errors': []
        }

        try:
            with psycopg2.connect(self.db_connection) as conn:
                conn.autocommit = True
                cursor = conn.cursor()

                # 执行索引创建
                for name, ddl in indexes:
                    try:
                        cursor.execute(ddl)
                        execution_report['executed_statements'].append(f"索引 {name}")
                        logger.info(f"创建索引成功: {name}")
                    except Exception as e:
                        error_msg = f"创建索引失败 {name}: {e}"
                        execution_report['execution_errors'].append(error_msg)
                        logger.error(error_msg)

                # 执行外键创建
                for name, ddl in foreign_keys:
                    try:
                        cursor.execute(ddl)
                        execution_report['executed_statements'].append(f"外键 {name}")
                        logger.info(f"创建外键成功: {name}")
                    except Exception as e:
                        error_msg = f"创建外键失败 {name}: {e}"
                        execution_report['execution_errors'].append(error_msg)
                        logger.error(error_msg)

                cursor.close()

        except Exception as e:
            error_msg = f"数据库连接/执行错误: {e}"
            execution_report['execution_errors'].append(error_msg)
            logger.error(error_msg)

        return execution_report


def print_report(report: Dict):
    """打印同步报告"""
    print("\n" + "=" * 60)
    print("MySQL到PostgreSQL Schema同步报告")
    print("=" * 60)

    print(f"\n目标表: {report['schema']}.{report['table_name']}")

    if report['sql_file_found']:
        print(f"SQL文件: {report['sql_file_path']}")
    else:
        print("❌ SQL文件: 未找到")
        for error in report['errors']:
            print(f"  错误: {error}")
        return

    if report['mysql_table_def']:
        mysql_def = report['mysql_table_def']
        print(f"发现: {len(mysql_def.indexes)} 个索引, {len(mysql_def.foreign_keys)} 个外键")

    print(f"\n✅ 成功创建: {len(report['executed_statements']) if 'executed_statements' in report else 0}")
    for stmt in report.get('executed_statements', []):
        print(f"  - {stmt}")

    if report.get('execution_errors'):
        print(f"\n❌ 执行错误: {len(report['execution_errors'])}")
        for error in report['execution_errors']:
            print(f"  - {error}")

    print(f"\n⏭️ 跳过项目: {len(report['skipped_items'])}")
    for item in report['skipped_items']:
        print(f"  - {item}")

    print("\n" + "=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MySQL到PostgreSQL Schema同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --table business.规模明细
  %(prog)s --table mapping.产品线 --dry-run
  %(prog)s --table business.规模明细 --verbose
        """
    )

    parser.add_argument(
        '--table',
        required=True,
        help='目标PostgreSQL表名 (格式: schema.table_name)'
    )

    parser.add_argument(
        '--sql-dir',
        default='tests/fixtures/legacy_db/schema',
        help='SQL文件目录路径 (默认: tests/fixtures/legacy_db/schema)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只显示要执行的SQL，不实际执行'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细日志'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='强制执行，忽略某些错误'
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 获取数据库连接字符串
    db_connection = (
        os.getenv('WDH_DATABASE__URI') or
        os.getenv('DATABASE_URL') or
        'postgresql://postgres:Post.169828@localhost:5432/postgres'
    )

    # 解析表名
    if '.' not in args.table:
        print("错误: 表名格式不正确，应为 schema.table_name")
        sys.exit(1)

    schema, table_name = args.table.split('.', 1)

    # 创建同步器并执行同步
    try:
        synchronizer = SchemaSynchronizer(db_connection, args.sql_dir)
        report = synchronizer.sync_table(schema, table_name, args.dry_run)
        print_report(report)

        # 根据结果设置退出码
        if not report['success']:
            sys.exit(1)

    except Exception as e:
        logger.error(f"同步失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()