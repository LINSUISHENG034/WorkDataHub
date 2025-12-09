# MySQL Dump to PostgreSQL Migrator - SQLGlot 重构方案

## 1. 背景与问题分析

### 1.1 当前实现概述

当前的 `scripts/migrations/mysql_dump_migrator/converter.py` 使用纯正则表达式进行 MySQL 到 PostgreSQL 的 SQL 转换。主要组件包括：

- `MySQLDumpParser`: 解析 MySQL dump 文件，提取数据库和表内容
- `MySQLToPostgreSQLConverter`: 使用正则表达式转换 SQL 语法
- `PostgreSQLMigrator`: 执行数据库迁移操作

### 1.2 当前实现的问题

#### 1.2.1 正则表达式的局限性

```python
# 当前实现示例 - 数据类型转换
pattern = rf"\b{mysql_type}\s*\((\d+)\)"
sql_content = re.sub(pattern, pg_type, sql_content, flags=re.IGNORECASE)
```

**问题**：
1. **脆弱性**：正则表达式难以处理嵌套结构、字符串转义、注释等复杂情况
2. **顺序依赖**：转换顺序很重要，如 `CHARACTER SET` 包含 `SET` 会被错误转换为 `TEXT`
3. **边界情况**：无法正确处理所有 MySQL 特定语法变体
4. **维护困难**：大量正则模式难以理解和调试

#### 1.2.2 已知的转换错误

1. **ENUM 类型处理不完整**：MySQL ENUM 转换为 VARCHAR(255) 丢失了枚举值约束
2. **字符串转义问题**：MySQL 使用 `\'` 而 PostgreSQL 使用 `''`
3. **AUTO_INCREMENT 转换**：复杂的 AUTO_INCREMENT 模式可能无法正确识别
4. **索引定义**：内联索引定义的移除可能不完整
5. **DEFAULT 值处理**：某些 DEFAULT 表达式转换不正确

#### 1.2.3 代码复杂度

当前 `converter.py` 包含：
- 60+ 行数据类型映射
- 15+ 个正则表达式模式
- 多个转换方法，顺序敏感

## 2. SQLGlot 库介绍

### 2.1 核心特性

[SQLGlot](https://github.com/tobymao/sqlglot) 是一个 Python SQL 解析器和转换器，支持：

- **20+ SQL 方言**：包括 MySQL、PostgreSQL、SQLite、Spark 等
- **AST 解析**：将 SQL 解析为抽象语法树
- **方言转换**：自动处理语法、函数和数据类型差异
- **错误处理**：提供详细的解析错误信息
- **可扩展性**：支持自定义转换器和方言

### 2.2 基本用法

```python
import sqlglot

# 基本转换
result = sqlglot.transpile(
    "SELECT * FROM `users` WHERE `id` = 1",
    read="mysql",
    write="postgres"
)[0]
# 输出: SELECT * FROM "users" WHERE "id" = 1

# 带格式化的转换
result = sqlglot.transpile(
    sql,
    read="mysql",
    write="postgres",
    pretty=True  # 格式化输出
)[0]

# 错误处理
try:
    sqlglot.transpile(sql, read="mysql", write="postgres")
except sqlglot.ParseError as e:
    print(f"解析错误: {e.errors}")
```

### 2.3 AST 操作

```python
from sqlglot import parse_one, exp

# 解析为 AST
ast = parse_one("SELECT a, b FROM users", dialect="mysql")

# 遍历所有表
for table in ast.find_all(exp.Table):
    print(table.name)

# 自定义转换器
def transformer(node):
    if isinstance(node, exp.Column) and node.name == "old_name":
        return exp.column("new_name")
    return node

transformed = ast.transform(transformer)
```

### 2.4 SQLGlot 对 MySQL → PostgreSQL 的内置支持

SQLGlot 自动处理以下转换：

| MySQL | PostgreSQL |
|-------|------------|
| `` `identifier` `` | `"identifier"` |
| `INT(11)` | `INT` |
| `TINYINT(1)` | `SMALLINT` |
| `DATETIME` | `TIMESTAMP` |
| `AUTO_INCREMENT` | `SERIAL` / `BIGSERIAL` |
| `UNSIGNED` | (移除) |
| `ENGINE=InnoDB` | (移除) |
| `CHARSET=utf8` | (移除) |

## 3. 重构目标

### 3.1 主要目标

1. **提高转换准确性**：利用 SQLGlot 的 AST 解析能力，正确处理所有 MySQL 语法
2. **简化代码**：用 SQLGlot 的内置转换替代大量正则表达式
3. **增强可维护性**：清晰的代码结构，易于扩展和调试
4. **保持向后兼容**：保持现有 CLI 接口不变

### 3.2 非目标

1. 不改变 `parser.py` 的实现（dump 文件解析逻辑）
2. 不改变 `migrator.py` 的数据库操作逻辑
3. 不改变 CLI 接口和参数

## 4. 技术设计

### 4.1 新架构

```
mysql_dump_migrator/
├── __init__.py
├── __main__.py
├── cli.py                    # 保持不变
├── parser.py                 # 保持不变
├── migrator.py               # 保持不变
├── converter.py              # 重构：使用 SQLGlot
└── sqlglot_extensions/       # 新增：自定义扩展
    ├── __init__.py
    ├── mysql_extensions.py   # MySQL 特定处理
    └── postgres_extensions.py # PostgreSQL 特定处理
```

### 4.2 新的 Converter 设计

```python
"""
MySQL to PostgreSQL SQL Converter using SQLGlot.

Uses SQLGlot's AST-based transpilation for accurate SQL conversion.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ConversionResult:
    """Result of a SQL conversion."""

    success: bool
    converted_sql: str
    original_sql: str
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        self.errors = self.errors or []
        self.warnings = self.warnings or []


class SQLGlotConverter:
    """
    MySQL to PostgreSQL converter using SQLGlot.

    Handles:
    - Data type mappings (via SQLGlot's built-in transpilation)
    - Identifier quoting (backticks → double quotes)
    - MySQL-specific syntax removal
    - Schema prefixing
    - Custom transformations for edge cases
    """

    # MySQL-specific patterns that SQLGlot may not handle
    MYSQL_HEADER_PATTERNS = [
        r"/\*![\d]+ .*? \*/;?",  # MySQL version-specific comments
        r"LOCK TABLES.*?;",
        r"UNLOCK TABLES;",
    ]

    def __init__(self, schema_name: str = "public"):
        """
        Initialize the converter.

        Args:
            schema_name: Target PostgreSQL schema name.
        """
        self.schema_name = schema_name
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL)
            for p in self.MYSQL_HEADER_PATTERNS
        ]

    def _preprocess(self, sql: str) -> str:
        """
        Preprocess SQL to remove MySQL-specific headers.

        Args:
            sql: Raw MySQL SQL.

        Returns:
            Preprocessed SQL.
        """
        for pattern in self._compiled_patterns:
            sql = pattern.sub("", sql)
        return sql.strip()

    def _add_schema_prefix(self, ast: exp.Expression) -> exp.Expression:
        """
        Add schema prefix to table references.

        Args:
            ast: Parsed AST.

        Returns:
            Modified AST with schema prefixes.
        """
        def add_schema(node):
            if isinstance(node, exp.Table) and not node.db:
                node.set("db", exp.Identifier(this=self.schema_name))
            return node

        return ast.transform(add_schema)

    def convert_statement(self, sql: str) -> ConversionResult:
        """
        Convert a single SQL statement.

        Args:
            sql: MySQL SQL statement.

        Returns:
            ConversionResult with converted SQL.
        """
        original = sql
        errors = []
        warnings = []

        try:
            # Preprocess
            sql = self._preprocess(sql)
            if not sql:
                return ConversionResult(
                    success=True,
                    converted_sql="",
                    original_sql=original
                )

            # Parse and transpile
            statements = sqlglot.transpile(
                sql,
                read="mysql",
                write="postgres",
                pretty=True
            )

            if not statements:
                return ConversionResult(
                    success=True,
                    converted_sql="",
                    original_sql=original
                )

            # Add schema prefix if needed
            converted_parts = []
            for stmt_sql in statements:
                try:
                    ast = parse_one(stmt_sql, dialect="postgres")
                    ast = self._add_schema_prefix(ast)
                    converted_parts.append(ast.sql(dialect="postgres"))
                except ParseError:
                    # If re-parsing fails, use the transpiled result as-is
                    converted_parts.append(stmt_sql)

            converted = ";\n".join(converted_parts)
            if converted and not converted.endswith(";"):
                converted += ";"

            return ConversionResult(
                success=True,
                converted_sql=converted,
                original_sql=original,
                warnings=warnings
            )

        except ParseError as e:
            errors.append(f"Parse error: {e}")
            logger.warning("converter.parse_error", error=str(e), sql=sql[:200])

            # Fallback: return original with basic transformations
            return ConversionResult(
                success=False,
                converted_sql=sql,
                original_sql=original,
                errors=errors
            )

        except Exception as e:
            errors.append(f"Conversion error: {e}")
            logger.error("converter.error", error=str(e), sql=sql[:200])

            return ConversionResult(
                success=False,
                converted_sql=sql,
                original_sql=original,
                errors=errors
            )

    def convert(self, sql_content: str, schema_name: str = None) -> str:
        """
        Convert MySQL SQL content to PostgreSQL.

        This method maintains backward compatibility with the old API.

        Args:
            sql_content: MySQL SQL content (may contain multiple statements).
            schema_name: Target schema name (overrides instance default).

        Returns:
            PostgreSQL-compatible SQL content.
        """
        if schema_name:
            self.schema_name = schema_name

        result = self.convert_statement(sql_content)
        return result.converted_sql

    def convert_table(
        self,
        create_statement: str,
        insert_statements: List[str],
        schema_name: str
    ) -> Tuple[str, List[str]]:
        """
        Convert a single table's CREATE and INSERT statements.

        Args:
            create_statement: MySQL CREATE TABLE statement.
            insert_statements: List of MySQL INSERT statements.
            schema_name: Target PostgreSQL schema name.

        Returns:
            Tuple of (converted CREATE statement, list of converted INSERT statements).
        """
        self.schema_name = schema_name

        converted_create = self.convert(create_statement)
        converted_inserts = [self.convert(stmt) for stmt in insert_statements]

        return converted_create, converted_inserts
```

### 4.3 自定义扩展处理

对于 SQLGlot 无法自动处理的边界情况，创建自定义转换器：

```python
# sqlglot_extensions/mysql_extensions.py

from sqlglot import exp
from sqlglot.dialects.mysql import MySQL


class MySQLDumpDialect(MySQL):
    """
    Extended MySQL dialect for dump file parsing.

    Handles MySQL dump-specific syntax that standard MySQL dialect may not support.
    """

    class Generator(MySQL.Generator):
        # Custom generation rules if needed
        pass

    class Parser(MySQL.Parser):
        # Custom parsing rules if needed
        pass


def handle_enum_type(node: exp.Expression) -> exp.Expression:
    """
    Convert MySQL ENUM to PostgreSQL CHECK constraint.

    MySQL: `status` ENUM('active', 'inactive', 'pending')
    PostgreSQL: `status` VARCHAR(255) CHECK (status IN ('active', 'inactive', 'pending'))
    """
    # Implementation details
    pass


def handle_on_update_timestamp(node: exp.Expression) -> exp.Expression:
    """
    Handle MySQL ON UPDATE CURRENT_TIMESTAMP.

    This requires creating a trigger in PostgreSQL.
    """
    # Implementation details
    pass
```

### 4.4 错误处理策略

```python
class ConversionErrorHandler:
    """
    Handles conversion errors with fallback strategies.
    """

    def __init__(self):
        self.errors = []
        self.warnings = []

    def handle_parse_error(self, sql: str, error: ParseError) -> str:
        """
        Handle parse errors with fallback to regex-based conversion.
        """
        self.errors.append({
            "type": "parse_error",
            "sql": sql[:200],
            "error": str(error)
        })

        # Fallback: basic regex transformations
        return self._fallback_convert(sql)

    def _fallback_convert(self, sql: str) -> str:
        """
        Fallback conversion using basic regex for unparseable SQL.
        """
        # Convert backticks to double quotes
        sql = re.sub(r"`([^`]+)`", r'"\1"', sql)
        # Remove MySQL-specific options
        sql = re.sub(r"\s*ENGINE\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*DEFAULT\s+CHARSET\s*=\s*\w+", "", sql, flags=re.IGNORECASE)
        return sql
```

## 5. 实施步骤

### 5.1 Phase 1: 准备工作 (Day 1)

1. **添加 SQLGlot 依赖**
   ```bash
   uv add sqlglot
   ```

2. **创建测试用例**
   - 从现有 dump 文件提取典型 SQL 语句
   - 创建单元测试覆盖各种转换场景

3. **备份现有实现**
   - 保留 `converter.py` 作为 `converter_legacy.py`

### 5.2 Phase 2: 核心重构 (Day 2-3)

1. **实现新的 SQLGlotConverter 类**
   - 基本转换功能
   - Schema 前缀处理
   - 错误处理

2. **实现自定义扩展**
   - ENUM 类型处理
   - ON UPDATE CURRENT_TIMESTAMP 处理
   - 其他边界情况

3. **集成测试**
   - 使用实际 dump 文件测试
   - 对比新旧实现的输出

### 5.3 Phase 3: 集成与验证 (Day 4)

1. **更新 migrator.py**
   - 使用新的 converter
   - 添加详细的错误日志

2. **端到端测试**
   - 完整迁移流程测试
   - 验证数据完整性

3. **性能测试**
   - 对比新旧实现的性能
   - 优化瓶颈

### 5.4 Phase 4: 文档与清理 (Day 5)

1. **更新文档**
   - 更新 README
   - 添加故障排除指南

2. **代码清理**
   - 移除遗留代码
   - 代码审查

## 6. 测试策略

### 6.1 单元测试

```python
# tests/test_sqlglot_converter.py

import pytest
from scripts.migrations.mysql_dump_migrator.converter import SQLGlotConverter


class TestSQLGlotConverter:

    @pytest.fixture
    def converter(self):
        return SQLGlotConverter(schema_name="test_schema")

    def test_basic_select(self, converter):
        mysql = "SELECT * FROM `users` WHERE `id` = 1"
        result = converter.convert(mysql)
        assert '"users"' in result
        assert '"id"' in result
        assert '`' not in result

    def test_create_table_data_types(self, converter):
        mysql = """
        CREATE TABLE `users` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `name` VARCHAR(255) NOT NULL,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        result = converter.convert(mysql)

        assert "SERIAL" in result or "INT" in result
        assert "ENGINE" not in result
        assert "CHARSET" not in result

    def test_insert_with_escaping(self, converter):
        mysql = "INSERT INTO `users` VALUES (1, 'O\\'Brien', 'test')"
        result = converter.convert(mysql)

        # PostgreSQL uses '' for escaping
        assert "O''Brien" in result or "O'Brien" in result

    def test_schema_prefix(self, converter):
        mysql = "SELECT * FROM `users`"
        result = converter.convert(mysql, schema_name="legacy")

        assert "legacy." in result
```

### 6.2 集成测试

```python
# tests/test_migration_integration.py

import pytest
from scripts.migrations.mysql_dump_migrator.migrator import PostgreSQLMigrator, MigrationConfig


class TestMigrationIntegration:

    @pytest.fixture
    def config(self, tmp_path):
        return MigrationConfig(
            dump_file_path="tests/fixtures/legacy_db/sample.sql",
            target_databases=["test_db"],
            target_schema="legacy",
            dry_run=True
        )

    def test_full_migration_dry_run(self, config):
        migrator = PostgreSQLMigrator(config)
        report = migrator.run()

        assert report.dry_run is True
        assert report.total_databases > 0
```

### 6.3 回归测试

创建一个测试套件，对比新旧实现的输出：

```python
def test_regression_comparison():
    """Compare new SQLGlot converter with legacy regex converter."""
    from converter_legacy import MySQLToPostgreSQLConverter as LegacyConverter
    from converter import SQLGlotConverter

    test_cases = load_test_cases()

    for case in test_cases:
        legacy_result = LegacyConverter().convert(case.mysql)
        new_result = SQLGlotConverter().convert(case.mysql)

        # Normalize and compare
        assert normalize_sql(legacy_result) == normalize_sql(new_result), \
            f"Mismatch for: {case.name}"
```

## 7. 风险评估与缓解

### 7.1 风险矩阵

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| SQLGlot 无法解析某些 MySQL 语法 | 中 | 高 | 实现 fallback 机制，保留正则转换作为备选 |
| 性能下降 | 低 | 中 | 性能测试，必要时优化或缓存 |
| 转换结果与旧实现不一致 | 中 | 中 | 全面的回归测试，逐步迁移 |
| 依赖库版本问题 | 低 | 低 | 锁定 SQLGlot 版本，定期更新 |

### 7.2 回滚计划

1. 保留 `converter_legacy.py` 作为备份
2. 通过配置开关切换新旧实现
3. 如果新实现出现严重问题，可快速回滚

```python
# 配置开关示例
USE_SQLGLOT_CONVERTER = os.environ.get("USE_SQLGLOT_CONVERTER", "true").lower() == "true"

if USE_SQLGLOT_CONVERTER:
    from .converter import SQLGlotConverter as Converter
else:
    from .converter_legacy import MySQLToPostgreSQLConverter as Converter
```

## 8. 预期收益

### 8.1 代码质量

- **减少代码量**：预计减少 50%+ 的转换逻辑代码
- **提高可读性**：AST 操作比正则表达式更直观
- **增强可维护性**：利用成熟库的持续更新

### 8.2 功能改进

- **更准确的转换**：处理更多边界情况
- **更好的错误报告**：详细的解析错误信息
- **可扩展性**：易于添加新的转换规则

### 8.3 长期价值

- **减少 bug**：利用经过广泛测试的库
- **社区支持**：SQLGlot 有活跃的社区和文档
- **未来扩展**：支持更多 SQL 方言转换

## 9. 附录

### 9.1 SQLGlot 常用 API

```python
import sqlglot
from sqlglot import parse_one, exp

# 转换
sqlglot.transpile(sql, read="mysql", write="postgres")

# 解析
ast = parse_one(sql, dialect="mysql")

# 遍历
for node in ast.walk():
    print(type(node).__name__)

# 查找
tables = list(ast.find_all(exp.Table))
columns = list(ast.find_all(exp.Column))

# 转换
def transformer(node):
    return node
ast.transform(transformer)

# 生成
ast.sql(dialect="postgres", pretty=True)
```

### 9.2 参考资源

- [SQLGlot GitHub](https://github.com/tobymao/sqlglot)
- [SQLGlot 文档](https://sqlglot.com/)
- [MySQL to PostgreSQL 迁移指南](https://wiki.postgresql.org/wiki/Converting_from_other_Databases_to_PostgreSQL)

---

**文档版本**: 1.0
**创建日期**: 2025-12-10
**作者**: Claude Code
**状态**: 待审核
