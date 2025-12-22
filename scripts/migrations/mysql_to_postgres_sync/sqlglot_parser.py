#!/usr/bin/env python3
"""
使用SQLGlot改进的MySQL到PostgreSQL解析器

这个模块使用SQLGlot库来解析MySQL的CREATE TABLE语句，提取索引和外键信息，
并生成PostgreSQL兼容的DDL语句。相比原来的正则表达式方案，这个方案更准确、
更可靠，能处理更复杂的SQL语法。
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sqlglot
from sqlglot import expressions as exp
from sqlglot.dialects import MySQL, Postgres

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MySQLIndex:
    """MySQL索引定义"""

    def __init__(
        self,
        name: str,
        columns: List[str],
        index_type: str = "INDEX",
        unique: bool = False,
        where: Optional[str] = None,
    ):
        self.name = name
        self.columns = columns
        self.index_type = index_type  # PRIMARY, UNIQUE, INDEX, FULLTEXT
        self.unique = unique
        self.where = where  # 用于部分索引

    def __repr__(self):
        return f"MySQLIndex(name='{self.name}', columns={self.columns}, type='{self.index_type}', unique={self.unique})"


class MySQLForeignKey:
    """MySQL外键定义"""

    def __init__(
        self,
        name: str,
        columns: List[str],
        ref_table: str,
        ref_columns: List[str],
        on_delete: str = "RESTRICT",
        on_update: str = "RESTRICT",
        match: Optional[str] = None,
    ):
        self.name = name
        self.columns = columns
        self.ref_table = ref_table
        self.ref_columns = ref_columns
        self.on_delete = on_delete
        self.on_update = on_update
        self.match = match  # MATCH SIMPLE, FULL, etc.

    def __repr__(self):
        return (
            f"MySQLForeignKey(name='{self.name}', columns={self.columns}, "
            f"ref_table='{self.ref_table}', ref_columns={self.ref_columns})"
        )


class MySQLTableDefinition:
    """MySQL表定义"""

    def __init__(self, database: str, table_name: str):
        self.database = database
        self.table_name = table_name
        self.indexes: List[MySQLIndex] = []
        self.foreign_keys: List[MySQLForeignKey] = []
        self.columns: Dict[str, str] = {}  # 列名 -> 类型

    def __repr__(self):
        return (
            f"MySQLTableDefinition(database='{self.database}', table='{self.table_name}', "
            f"indexes={len(self.indexes)}, fks={len(self.foreign_keys)})"
        )


class SQLGlotParser:
    """使用SQLGlot的MySQL SQL解析器"""

    def __init__(self):
        """初始化解析器"""
        self.mysql_parser = MySQL()
        self.pg_transpiler = Postgres()

    def parse_sql_file(self, sql_file_path: Path) -> Optional[MySQLTableDefinition]:
        """
        解析SQL文件

        Args:
            sql_file_path: SQL文件路径

        Returns:
            解析后的表定义
        """
        try:
            with open(sql_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return self.parse_sql_content(content)
        except Exception as e:
            logger.error(f"Error reading file {sql_file_path}: {e}")
            return None

    def parse_sql_content(self, content: str) -> Optional[MySQLTableDefinition]:
        """
        解析SQL内容

        Args:
            content: SQL内容

        Returns:
            解析后的表定义
        """
        try:
            # 从注释中提取数据库名
            database = self._extract_database_from_comments(content)

            # 解析MySQL SQL
            statements = sqlglot.parse(content, read="mysql")

            for stmt in statements:
                if isinstance(stmt, exp.Create) and str(stmt.kind).upper() == "TABLE":
                    return self._extract_table_info(stmt, database)

            logger.error("No CREATE TABLE statement found in SQL content")
            return None

        except Exception as e:
            logger.error(f"Error parsing SQL content: {e}")
            return None

    def _extract_database_from_comments(self, content: str) -> str:
        """
        从SQL注释中提取数据库名

        Args:
            content: SQL内容

        Returns:
            数据库名，如果未找到返回"unknown"
        """
        import re

        match = re.search(r"--\s*数据库:\s*(\w+)", content)
        if match:
            return match.group(1)
        return "unknown"

    def _extract_table_info(
        self, create_stmt: exp.Create, database: str = "unknown"
    ) -> MySQLTableDefinition:
        """
        从CREATE TABLE语句中提取表信息

        Args:
            create_stmt: CREATE TABLE语句
            database: 数据库名

        Returns:
            表定义
        """
        # 获取表名 - 从Schema对象中提取
        if isinstance(create_stmt.this, exp.Schema):
            # Schema对象的this属性包含表名
            if hasattr(create_stmt.this, "this") and hasattr(
                create_stmt.this.this, "name"
            ):
                table_name = create_stmt.this.this.name
            else:
                table_name = "unknown"

            # 获取Schema对象中的expressions（包含列定义和约束）
            schema_expressions = create_stmt.this.args.get("expressions", [])
        else:
            # 处理其他类型的表名表达式
            if hasattr(create_stmt.this, "name"):
                table_name = create_stmt.this.name
            else:
                table_name = str(create_stmt.this)
            schema_expressions = create_stmt.expressions or []

        table_def = MySQLTableDefinition(database, table_name)

        # 提取列定义
        for item in schema_expressions:
            if isinstance(item, exp.ColumnDef):
                col_name = item.this.name
                col_type = item.args.get("kind") or "TEXT"
                table_def.columns[col_name] = str(col_type)

        # 提取约束
        for constraint in schema_expressions:
            if isinstance(constraint, exp.PrimaryKey):
                # 主键
                index = MySQLIndex(
                    name=f"pk_{table_name}",
                    columns=[col.name for col in constraint.expressions],
                    index_type="PRIMARY",
                    unique=True,
                )
                table_def.indexes.append(index)

            elif isinstance(constraint, exp.UniqueColumnConstraint):
                # 唯一索引 (UNIQUE KEY)
                # constraint.this 包含索引名和列信息，例如: "INDEX" ("id")
                # 需要从 constraint.this 中提取索引名和列
                if hasattr(constraint.this, "this"):
                    # constraint.this 是一个包含索引名和列的表达式
                    index_name = (
                        constraint.this.this.name
                        if hasattr(constraint.this.this, "name")
                        else f"uk_{table_name}"
                    )
                    # 列信息在 constraint.this.expressions 中
                    columns = []
                    if (
                        hasattr(constraint.this, "expressions")
                        and constraint.this.expressions
                    ):
                        for col in constraint.this.expressions:
                            if isinstance(col, exp.Identifier):
                                columns.append(col.this)
                            elif hasattr(col, "name"):
                                columns.append(col.name)
                            else:
                                columns.append(str(col))
                else:
                    index_name = (
                        constraint.this.name
                        if hasattr(constraint.this, "name")
                        else f"uk_{table_name}"
                    )
                    columns = []

                index = MySQLIndex(
                    name=index_name, columns=columns, index_type="UNIQUE", unique=True
                )
                table_def.indexes.append(index)

            elif isinstance(constraint, exp.IndexColumnConstraint):
                # 普通索引 (KEY/INDEX)
                # constraint.this 是一个 Identifier，包含索引名
                # 列信息在 constraint.args['expressions'] 或 constraint.expressions 中
                if isinstance(constraint.this, exp.Identifier):
                    index_name = constraint.this.this
                else:
                    index_name = (
                        constraint.this.name
                        if hasattr(constraint.this, "name")
                        else f"idx_{table_name}"
                    )

                # 提取列名 - 从 constraint.args['expressions'] 或 constraint.expressions
                columns = []
                expressions = (
                    constraint.args.get("expressions") or constraint.expressions or []
                )
                for col in expressions:
                    if isinstance(col, exp.Identifier):
                        columns.append(col.this)
                    elif hasattr(col, "name"):
                        columns.append(col.name)
                    else:
                        columns.append(str(col))

                index = MySQLIndex(
                    name=index_name, columns=columns, index_type="INDEX", unique=False
                )
                table_def.indexes.append(index)

            elif isinstance(constraint, exp.Constraint):
                # 约束（可能是外键）
                # 检查约束中是否包含ForeignKey
                constraint_expressions = constraint.args.get("expressions", [])
                if constraint_expressions and isinstance(
                    constraint_expressions[0], exp.ForeignKey
                ):
                    fk_expr = constraint_expressions[0]
                    constraint_name = (
                        constraint.this.name
                        if hasattr(constraint.this, "name")
                        else f"fk_{table_name}"
                    )

                    # 提取列名
                    columns = []
                    if fk_expr.expressions:
                        for col in fk_expr.expressions:
                            # col 是 Identifier 对象，col.this 是实际的列名字符串
                            if isinstance(col, exp.Identifier):
                                columns.append(col.this)
                            elif hasattr(col, "name"):
                                columns.append(col.name)
                            else:
                                columns.append(str(col))

                    # 提取引用表和列
                    reference = fk_expr.args.get("reference")
                    if reference:
                        # reference.this 是一个 Schema 对象，包含 Table 对象
                        ref_schema = reference.this
                        if isinstance(ref_schema, exp.Schema):
                            ref_table = (
                                ref_schema.this.name
                                if hasattr(ref_schema.this, "name")
                                else str(ref_schema.this)
                            )
                        else:
                            ref_table = (
                                ref_schema.name
                                if hasattr(ref_schema, "name")
                                else str(ref_schema)
                            )

                        # 提取引用列名 - reference.expressions 包含引用的列
                        ref_columns = []
                        if reference.expressions:
                            for col in reference.expressions:
                                # col 是 Identifier 对象，col.this 是实际的列名字符串
                                if isinstance(col, exp.Identifier):
                                    ref_columns.append(col.this)
                                elif hasattr(col, "name"):
                                    ref_columns.append(col.name)
                                else:
                                    ref_columns.append(str(col))
                        # 如果 reference.expressions 为空，尝试从 reference.this (Schema) 中提取
                        elif (
                            isinstance(ref_schema, exp.Schema)
                            and ref_schema.expressions
                        ):
                            for col in ref_schema.expressions:
                                if isinstance(col, exp.Identifier):
                                    ref_columns.append(col.this)
                                elif hasattr(col, "name"):
                                    ref_columns.append(col.name)
                                else:
                                    ref_columns.append(str(col))
                    else:
                        ref_table = "unknown"
                        ref_columns = []

                    # 提取 ON DELETE 和 ON UPDATE 动作 - 从 reference.options 中提取
                    on_delete = "RESTRICT"
                    on_update = "RESTRICT"
                    if reference and hasattr(reference, "options"):
                        for option in reference.options:
                            option_str = str(option).upper()
                            if "ON DELETE" in option_str:
                                # 提取 DELETE 后面的动作
                                parts = option_str.split()
                                if len(parts) >= 3:
                                    on_delete = parts[2]
                            elif "ON UPDATE" in option_str:
                                # 提取 UPDATE 后面的动作
                                parts = option_str.split()
                                if len(parts) >= 3:
                                    on_update = parts[2]

                    fk = MySQLForeignKey(
                        name=constraint_name,
                        columns=columns,
                        ref_table=ref_table,
                        ref_columns=ref_columns,
                        on_delete=on_delete,
                        on_update=on_update,
                    )
                    table_def.foreign_keys.append(fk)

        return table_def

    def _get_fk_action(self, action) -> str:
        """获取外键动作"""
        if action is None:
            return "RESTRICT"
        if isinstance(action, str):
            return action.upper()
        if hasattr(action, "name"):
            return action.name.upper()
        return str(action).upper()

    def _get_fk_match(self, match) -> Optional[str]:
        """获取外键匹配类型"""
        if match is None:
            return None
        if isinstance(match, str):
            return match.upper()
        if hasattr(match, "name"):
            return match.name.upper()
        return str(match).upper()

    def transpile_to_postgres(self, mysql_sql: str) -> str:
        """
        将MySQL SQL转换为PostgreSQL

        Args:
            mysql_sql: MySQL SQL语句

        Returns:
            PostgreSQL SQL语句
        """
        try:
            # 使用SQLGlot进行转换
            transpiled = sqlglot.transpile(mysql_sql, read="mysql", write="postgres")
            return transpiled[0] if transpiled else mysql_sql
        except Exception as e:
            logger.warning(f"Failed to transpile SQL: {e}")
            return mysql_sql

    def extract_indexes_from_table(self, sql_content: str) -> List[MySQLIndex]:
        """
        从SQL内容中提取所有索引定义

        Args:
            sql_content: SQL内容

        Returns:
            索引列表
        """
        statements = sqlglot.parse(sql_content, read="mysql")
        indexes = []

        for stmt in statements:
            if isinstance(stmt, exp.Create) and str(stmt.kind).upper() == "TABLE":
                table_def = self._extract_table_info(stmt)
                indexes.extend(table_def.indexes)

        return indexes

    def extract_foreign_keys_from_table(
        self, sql_content: str
    ) -> List[MySQLForeignKey]:
        """
        从SQL内容中提取所有外键定义

        Args:
            sql_content: SQL内容

        Returns:
            外键列表
        """
        statements = sqlglot.parse(sql_content, read="mysql")
        foreign_keys = []

        for stmt in statements:
            if isinstance(stmt, exp.Create) and str(stmt.kind).upper() == "TABLE":
                table_def = self._extract_table_info(stmt)
                foreign_keys.extend(table_def.foreign_keys)

        return foreign_keys


class PostgreSQLDDLGenerator:
    """PostgreSQL DDL生成器"""

    def __init__(self, schema: str, table_name: str):
        self.schema = schema
        self.table_name = table_name

    def generate_index_ddl(self, index: MySQLIndex) -> Tuple[str, str]:
        """
        生成PostgreSQL索引DDL

        Args:
            index: MySQL索引定义

        Returns:
            (索引名, DDL语句)
        """
        columns_str = ", ".join([f'"{col}"' for col in index.columns])

        # 生成PostgreSQL兼容的索引名
        pg_index_name = self._generate_postgres_index_name(index)

        # 构建DDL
        if index.index_type == "PRIMARY":
            # PostgreSQL中主键通常在CREATE TABLE时定义
            return (index.name, "-- Primary key should be defined in CREATE TABLE")

        elif index.index_type == "UNIQUE":
            ddl = f'CREATE UNIQUE INDEX "{pg_index_name}" ON "{self.schema}"."{self.table_name}" ({columns_str})'
        else:
            # FULLTEXT 转换为普通索引
            ddl = f'CREATE INDEX "{pg_index_name}" ON "{self.schema}"."{self.table_name}" ({columns_str})'

        # 添加WHERE子句（部分索引）
        if index.where:
            ddl += f" WHERE {index.where}"

        return (pg_index_name, ddl)

    def generate_foreign_key_ddl(self, fk: MySQLForeignKey) -> Tuple[str, str]:
        """
        生成PostgreSQL外键DDL

        Args:
            fk: MySQL外键定义

        Returns:
            (外键名, DDL语句)
        """
        columns_str = ", ".join([f'"{col}"' for col in fk.columns])
        ref_columns_str = ", ".join([f'"{col}"' for col in fk.ref_columns])

        # 生成PostgreSQL兼容的外键名
        pg_fk_name = self._generate_postgres_fk_name(fk)

        # 构建DDL
        ddl = (
            f'ALTER TABLE "{self.schema}"."{self.table_name}" '
            f'ADD CONSTRAINT "{pg_fk_name}" '
            f"FOREIGN KEY ({columns_str}) "
            f'REFERENCES "{fk.ref_table}" ({ref_columns_str})'
        )

        # 添加ON DELETE和ON UPDATE
        if fk.on_delete and fk.on_delete.upper() != "RESTRICT":
            ddl += f" ON DELETE {fk.on_delete.upper()}"
        if fk.on_update and fk.on_update.upper() != "RESTRICT":
            ddl += f" ON UPDATE {fk.on_update.upper()}"

        # 添加MATCH（如果存在）
        if fk.match:
            ddl += f" MATCH {fk.match.upper()}"

        return (pg_fk_name, ddl)

    def generate_batch_ddl(
        self, indexes: List[MySQLIndex], foreign_keys: List[MySQLForeignKey]
    ) -> List[Tuple[str, str, str]]:
        """
        批量生成DDL语句

        Args:
            indexes: 索引列表
            foreign_keys: 外键列表

        Returns:
            [(类型, 名称, DDL语句)] 列表
        """
        ddl_statements = []

        # 先创建索引
        for index in indexes:
            if index.index_type != "PRIMARY":  # 跳过主键
                name, ddl = self.generate_index_ddl(index)
                ddl_statements.append(("INDEX", name, ddl))

        # 再创建外键
        for fk in foreign_keys:
            name, ddl = self.generate_foreign_key_ddl(fk)
            ddl_statements.append(("FOREIGN_KEY", name, ddl))

        return ddl_statements

    def _generate_postgres_index_name(self, index: MySQLIndex) -> str:
        """生成PostgreSQL兼容的索引名"""
        # 清理特殊字符并限制长度
        name = index.name or f"idx_{self.table_name}_{index.columns[0]}"
        # 替换中文和特殊字符
        name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name)
        # 限制PostgreSQL标识符长度为63字符
        return name[:63] if len(name) > 63 else name

    def _generate_postgres_fk_name(self, fk: MySQLForeignKey) -> str:
        """生成PostgreSQL兼容的外键名"""
        name = fk.name or f"fk_{self.table_name}_{fk.ref_table}"
        # 替换中文和特殊字符
        name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name)
        # 限制PostgreSQL标识符长度
        return name[:63] if len(name) > 63 else name


def find_sql_file_for_table(
    sql_dir: Path, schema: str, table_name: str
) -> Optional[Path]:
    """
    根据PostgreSQL的schema和表名查找对应的MySQL SQL文件

    Args:
        sql_dir: SQL文件目录
        schema: PostgreSQL schema名
        table_name: PostgreSQL表名

    Returns:
        找到的SQL文件路径，如果未找到返回None
    """
    # 尝试多种文件名匹配模式
    possible_names = [
        f"{table_name}.sql",
        f"{schema}_{table_name}.sql",
    ]

    # 在schema子目录中查找
    schema_dir = sql_dir / schema
    if schema_dir.exists():
        for name in possible_names:
            file_path = schema_dir / name
            if file_path.exists():
                logger.debug(f"找到SQL文件: {file_path}")
                return file_path

    # 在整个目录中递归查找
    for name in possible_names:
        for file_path in sql_dir.rglob(name):
            logger.debug(f"递归找到SQL文件: {file_path}")
            return file_path

    # 如果没找到，尝试模糊匹配（忽略大小写）
    table_name_lower = table_name.lower()
    for file_path in sql_dir.rglob("*.sql"):
        if table_name_lower in file_path.name.lower():
            logger.debug(f"模糊匹配找到SQL文件: {file_path}")
            return file_path

    return None


def main():
    """测试函数"""
    # 示例MySQL SQL
    mysql_sql = """
    CREATE TABLE `test_table` (
        `id` int(11) NOT NULL AUTO_INCREMENT,
        `name` varchar(255) DEFAULT NULL,
        `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `idx_name` (`name`),
        UNIQUE KEY `uk_name_created` (`name`, `created_at`),
        CONSTRAINT `fk_test_ref` FOREIGN KEY (`id`) REFERENCES `ref_table` (`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """

    # 使用SQLGlot解析
    parser = SQLGlotParser()
    table_def = parser.parse_sql_content(mysql_sql)

    if table_def:
        print(f"Table: {table_def.database}.{table_def.table_name}")
        print(f"Columns: {len(table_def.columns)}")
        print(f"Indexes: {len(table_def.indexes)}")
        print(f"Foreign Keys: {len(table_def.foreign_keys)}")

        # 生成PostgreSQL DDL
        ddl_gen = PostgreSQLDDLGenerator("public", table_def.table_name)
        ddl_statements = ddl_gen.generate_batch_ddl(
            table_def.indexes, table_def.foreign_keys
        )

        print("\nGenerated PostgreSQL DDL:")
        for stmt_type, name, ddl in ddl_statements:
            print(f"\n-- {stmt_type}: {name}")
            print(ddl + ";")


if __name__ == "__main__":
    main()
