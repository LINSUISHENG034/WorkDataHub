"""
PostgreSQL DDL生成模块

用于根据MySQL的索引和外键定义生成PostgreSQL兼容的DDL语句。
"""

import logging
from typing import List

from sqlglot_parser import MySQLForeignKey, MySQLIndex

logger = logging.getLogger(__name__)


class PostgreSQLDDLGenerator:
    """PostgreSQL DDL生成器"""

    def __init__(self, schema: str, table_name: str):
        self.schema = schema
        self.table_name = table_name
        self.quoted_table_name = f'{schema}."{table_name}"'

    def generate_create_index_sql(self, index: MySQLIndex) -> str:
        """
        生成CREATE INDEX语句

        Args:
            index: MySQL索引定义

        Returns:
            PostgreSQL CREATE INDEX语句
        """
        # 生成索引名称（确保符合PostgreSQL命名规则）
        pg_index_name = self._generate_postgres_index_name(index)

        # 生成列名列表
        columns = [f'"{col}"' for col in index.columns]

        # 构建SQL语句
        if index.unique:
            sql = f"CREATE UNIQUE INDEX IF NOT EXISTS {pg_index_name}\n"
        else:
            sql = f"CREATE INDEX IF NOT EXISTS {pg_index_name}\n"

        sql += f"    ON {self.quoted_table_name}\n"
        sql += f"    ({', '.join(columns)});"

        return sql

    def generate_alter_table_foreign_key_sql(self, foreign_key: MySQLForeignKey) -> str:
        """
        生成ALTER TABLE ADD FOREIGN KEY语句

        Args:
            foreign_key: MySQL外键定义

        Returns:
            PostgreSQL ALTER TABLE语句
        """
        # 生成列名列表
        columns = [f'"{col}"' for col in foreign_key.columns]
        ref_columns = [f'"{col}"' for col in foreign_key.ref_columns]

        # 处理ON DELETE和ON UPDATE规则
        on_delete = self._convert_foreign_key_action(foreign_key.on_delete)
        on_update = self._convert_foreign_key_action(foreign_key.on_update)

        # 构建SQL语句 - 引用表需要指定schema
        ref_schema = "mapping"  # 根据业务逻辑，引用表通常在mapping schema中
        sql = f"ALTER TABLE {self.quoted_table_name}\n"
        sql += f"    ADD CONSTRAINT {foreign_key.name}\n"
        sql += f"    FOREIGN KEY ({', '.join(columns)})\n"
        sql += f'    REFERENCES {ref_schema}."{foreign_key.ref_table}"({", ".join(ref_columns)})\n'

        if on_delete:
            sql += f"    ON DELETE {on_delete}\n"
        if on_update:
            sql += f"    ON UPDATE {on_update}"

        sql += ";"

        return sql

    def _generate_postgres_index_name(self, index: MySQLIndex) -> str:
        """
        生成PostgreSQL兼容的索引名称

        Args:
            index: MySQL索引定义

        Returns:
            PostgreSQL索引名称
        """
        # 清理索引名称，确保符合PostgreSQL命名规则
        clean_name = index.name

        # 替换不支持的字符
        clean_name = clean_name.replace("-", "_")
        clean_name = clean_name.replace(" ", "_")
        clean_name = clean_name.replace("(", "_")
        clean_name = clean_name.replace(")", "_")

        # 如果名称过长或为空，生成一个标准名称
        if not clean_name or len(clean_name) > 63:
            if index.index_type == "PRIMARY":
                clean_name = f"pk_{self.table_name}"
            elif index.unique:
                clean_name = f"uk_{self.table_name}_{'_'.join(index.columns[:2])}"
            else:
                clean_name = f"idx_{self.table_name}_{'_'.join(index.columns[:2])}"

        # 确保名称以字母或下划线开头
        if clean_name[0].isdigit():
            clean_name = f"idx_{clean_name}"

        # 添加schema前缀避免冲突
        return f"{clean_name}"

    def _convert_foreign_key_action(self, action: str) -> str:
        """
        转换外键动作

        Args:
            action: MySQL外键动作

        Returns:
            PostgreSQL外键动作
        """
        action_map = {
            "CASCADE": "CASCADE",
            "SET_NULL": "SET NULL",
            "RESTRICT": "RESTRICT",
            "NO_ACTION": "NO ACTION",
        }

        return action_map.get(action.upper(), "RESTRICT")

    def generate_batch_ddl(
        self, indexes: List[MySQLIndex], foreign_keys: List[MySQLForeignKey]
    ) -> List[str]:
        """
        批量生成DDL语句

        Args:
            indexes: 索引列表
            foreign_keys: 外键列表

        Returns:
            DDL语句列表
        """
        ddl_statements = []

        # 生成索引DDL
        for index in indexes:
            try:
                ddl = self.generate_create_index_sql(index)
                ddl_statements.append(("INDEX", index.name, ddl))
                logger.debug(f"生成索引DDL: {index.name}")
            except Exception as e:
                logger.error(f"生成索引DDL失败 {index.name}: {e}")

        # 生成外键DDL
        for fk in foreign_keys:
            try:
                ddl = self.generate_alter_table_foreign_key_sql(fk)
                ddl_statements.append(("FOREIGN_KEY", fk.name, ddl))
                logger.debug(f"生成外键DDL: {fk.name}")
            except Exception as e:
                logger.error(f"生成外键DDL失败 {fk.name}: {e}")

        return ddl_statements

    def generate_dependency_check_sql(
        self, foreign_keys: List[MySQLForeignKey]
    ) -> List[str]:
        """
        生成依赖检查SQL

        Args:
            foreign_keys: 外键列表

        Returns:
            依赖检查SQL列表
        """
        check_sqls = []

        # 收集所有引用的表
        ref_tables = set(fk.ref_table for fk in foreign_keys)

        for table in ref_tables:
            # 检查表是否存在的SQL
            sql = f"""
SELECT
    '{table}' as table_name,
    EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'mapping' AND table_name = '{table}'
    ) as exists_in_mapping,
    EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'business' AND table_name = '{table}'
    ) as exists_in_business,
    EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = '{table}'
    ) as exists_in_public;
"""
            check_sqls.append(sql)

        return check_sqls


def main():
    """测试函数"""
    # 创建测试索引
    index1 = MySQLIndex("KY_客户名称", ["客户名称"], "INDEX", False)
    index2 = MySQLIndex("FK_组织架构_规模明细", ["机构代码"], "INDEX", False)
    index3 = MySQLIndex("PRIMARY", ["id"], "PRIMARY", True)

    # 创建测试外键
    fk1 = MySQLForeignKey(
        "规模明细_ibfk_1",
        ["产品线代码"],
        "产品线",
        ["产品线代码"],
        "RESTRICT",
        "CASCADE",
    )

    # 生成DDL
    generator = PostgreSQLDDLGenerator("business", "规模明细")

    print("=== 索引DDL ===")
    for idx in [index1, index2, index3]:
        print(generator.generate_create_index_sql(idx))
        print()

    print("=== 外键DDL ===")
    print(generator.generate_alter_table_foreign_key_sql(fk1))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
