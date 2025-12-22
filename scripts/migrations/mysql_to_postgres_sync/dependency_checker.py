"""
依赖检查模块

用于检查外键引用的表是否存在于PostgreSQL数据库中。
"""

import logging
import os
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DependencyChecker:
    """依赖检查器"""

    def __init__(self, connection_string: str):
        """
        初始化依赖检查器

        Args:
            connection_string: PostgreSQL连接字符串
        """
        self.connection_string = connection_string
        self._connection = None

    def connect(self):
        """建立数据库连接"""
        try:
            import psycopg2

            self._connection = psycopg2.connect(self.connection_string)
            self._connection.autocommit = True
            logger.debug("数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def disconnect(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("数据库连接已关闭")

    def check_table_exists(self, schema: str, table_name: str) -> bool:
        """
        检查表是否存在

        Args:
            schema: Schema名
            table_name: 表名

        Returns:
            表是否存在
        """
        if not self._connection:
            self.connect()

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                )
            """,
                (schema, table_name),
            )

            exists = cursor.fetchone()[0]
            cursor.close()
            return exists

        except Exception as e:
            logger.error(f"检查表存在性失败 {schema}.{table_name}: {e}")
            return False

    def find_table_location(self, table_name: str) -> Optional[str]:
        """
        查找表在哪个schema中

        Args:
            table_name: 表名

        Returns:
            找到的schema名，如果未找到返回None
        """
        if not self._connection:
            self.connect()

        # 常见的schema列表，按优先级排序
        schemas_to_check = ["mapping", "business", "public", "wdh_dev"]

        for schema in schemas_to_check:
            if self.check_table_exists(schema, table_name):
                logger.debug(f"在schema {schema} 中找到表 {table_name}")
                return schema

        logger.warning(f"未找到表 {table_name}")
        return None

    def check_foreign_key_dependencies(self, foreign_keys: List) -> Dict[str, Dict]:
        """
        检查外键依赖表

        Args:
            foreign_keys: 外键列表

        Returns:
            依赖检查结果
        """
        results = {}

        # 收集所有引用的表
        ref_tables = set()
        for fk in foreign_keys:
            ref_tables.add(fk.ref_table)

        for table_name in ref_tables:
            table_info = {
                "table_name": table_name,
                "exists": False,
                "schema": None,
                "can_create_fk": False,
            }

            # 查找表位置
            schema = self.find_table_location(table_name)
            if schema:
                table_info["exists"] = True
                table_info["schema"] = schema
                table_info["can_create_fk"] = True
                logger.info(f"依赖表 {table_name} 存在于 schema {schema}")
            else:
                logger.warning(f"依赖表 {table_name} 不存在，相关外键将被跳过")

            results[table_name] = table_info

        return results

    def check_existing_indexes(self, schema: str, table_name: str) -> Set[str]:
        """
        检查已存在的索引

        Args:
            schema: Schema名
            table_name: 表名

        Returns:
            已存在的索引名称集合
        """
        if not self._connection:
            self.connect()

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = %s AND tablename = %s
            """,
                (schema, table_name),
            )

            existing_indexes = {row[0] for row in cursor.fetchall()}
            cursor.close()
            return existing_indexes

        except Exception as e:
            logger.error(f"查询现有索引失败 {schema}.{table_name}: {e}")
            return set()

    def check_existing_foreign_keys(self, schema: str, table_name: str) -> Set[str]:
        """
        检查已存在的外键

        Args:
            schema: Schema名
            table_name: 表名

        Returns:
            已存在的外键名称集合
        """
        if not self._connection:
            self.connect()

        try:
            cursor = self._connection.cursor()
            cursor.execute(
                """
                SELECT conname FROM pg_constraint
                WHERE conrelid = %s.%s::regclass AND contype = 'f'
            """,
                (schema, table_name),
            )

            existing_fks = {row[0] for row in cursor.fetchall()}
            cursor.close()
            return existing_fks

        except Exception as e:
            logger.error(f"查询现有外键失败 {schema}.{table_name}: {e}")
            return set()

    def get_dependency_report(
        self, schema: str, table_name: str, indexes: List, foreign_keys: List
    ) -> Dict:
        """
        生成完整的依赖报告

        Args:
            schema: Schema名
            table_name: 表名
            indexes: 索引列表
            foreign_keys: 外键列表

        Returns:
            依赖报告
        """
        report = {
            "target_table": f"{schema}.{table_name}",
            "target_exists": self.check_table_exists(schema, table_name),
            "existing_indexes": self.check_existing_indexes(schema, table_name),
            "existing_foreign_keys": self.check_existing_foreign_keys(
                schema, table_name
            ),
            "foreign_key_dependencies": self.check_foreign_key_dependencies(
                foreign_keys
            ),
            "can_create_indexes": True,
            "can_create_foreign_keys": True,
        }

        # 检查是否可以创建外键
        for table_name, dep_info in report["foreign_key_dependencies"].items():
            if not dep_info["exists"]:
                report["can_create_foreign_keys"] = False
                break

        return report


def main():
    """测试函数"""
    # 从环境变量获取数据库连接
    db_uri = os.getenv("WDH_DATABASE__URI") or os.getenv("DATABASE_URL")
    if not db_uri:
        print("错误：未设置数据库连接环境变量")
        return

    checker = DependencyChecker(db_uri)

    try:
        # 测试表存在检查
        print("=== 表存在检查 ===")
        print(
            f"business.规模明细: {checker.check_table_exists('business', '规模明细')}"
        )
        print(f"mapping.产品线: {checker.check_table_exists('mapping', '产品线')}")
        print(f"unknown.table: {checker.check_table_exists('unknown', 'table')}")

        # 测试表位置查找
        print("\n=== 表位置查找 ===")
        print(f"规模明细: {checker.find_table_location('规模明细')}")
        print(f"产品线: {checker.find_table_location('产品线')}")

    finally:
        checker.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
