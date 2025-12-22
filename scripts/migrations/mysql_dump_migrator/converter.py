"""
MySQL to PostgreSQL SQL Converter using SQLGlot.

Uses SQLGlot's AST-based transpilation for accurate SQL conversion.
Replaces the legacy regex-based converter with proper SQL parsing.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import structlog
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError

logger = structlog.get_logger(__name__)


@dataclass
class ConversionResult:
    """Result of a SQL conversion."""

    success: bool
    converted_sql: str
    original_sql: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MySQLToPostgreSQLConverter:
    """
    MySQL to PostgreSQL converter using SQLGlot.

    Handles:
    - Data type mappings (via SQLGlot's built-in transpilation)
    - Identifier quoting (backticks → double quotes)
    - MySQL-specific syntax removal
    - Schema prefixing
    - Custom transformations for edge cases
    """

    # MySQL-specific patterns that need preprocessing
    MYSQL_PREPROCESSOR_PATTERNS = [
        # MySQL version-specific comments: /*!40101 ... */
        (r"/\*!\d+\s+.*?\*/;?", ""),
        # LOCK/UNLOCK TABLES
        (r"LOCK\s+TABLES\s+.*?;", ""),
        (r"UNLOCK\s+TABLES\s*;", ""),
        # SET statements
        (r"SET\s+@\w+\s*=.*?;", ""),
        (r"SET\s+NAMES\s+\w+\s*;", ""),
        # ALTER TABLE ... DISABLE/ENABLE KEYS
        (r"ALTER\s+TABLE\s+[`\"]?[\w\d_]+[`\"]?\s+DISABLE\s+KEYS\s*;", ""),
        (r"ALTER\s+TABLE\s+[`\"]?[\w\d_]+[`\"]?\s+ENABLE\s+KEYS\s*;", ""),
    ]

    # Patterns to clean from CREATE/INSERT that SQLGlot may not handle
    CREATE_TABLE_CLEANUP_PATTERNS = [
        # Remove size from integer types (PostgreSQL doesn't support INT(n), SMALLINT(n), etc.)
        (r"\bSMALLINT\s*\(\d+\)", "SMALLINT"),
        (r"\bINT\s*\(\d+\)", "INT"),
        (r"\bINTEGER\s*\(\d+\)", "INTEGER"),
        (r"\bBIGINT\s*\(\d+\)", "BIGINT"),
        (r"\bTINYINT\s*\(\d+\)", "SMALLINT"),
        (r"\bUTINYINT\b", "SMALLINT"),
        (r"\bMEDIUMINT\s*\(\d+\)", "INTEGER"),
        # ENGINE options
        (r"\s*ENGINE\s*=\s*\w+", ""),
        # CHARSET options
        (r"\s*DEFAULT\s+CHARSET\s*=\s*\w+", ""),
        (r"\s*CHARSET\s*=\s*\w+", ""),
        (r"\s*CHARACTER\s+SET\s+\w+\s+COLLATE\s+\w+", ""),
        (r"\s*CHARACTER\s+SET\s+\w+", ""),
        (r"\s*COLLATE\s*=?\s*[\w-]+", ""),
        # ROW_FORMAT
        (r"\s*ROW_FORMAT\s*=\s*\w+", ""),
        # AUTO_INCREMENT table option
        (r"\s*AUTO_INCREMENT\s*=\s*\d+", ""),
        # COMMENT options (avoid stripping columns named "comment")
        (r"(?<![\"`])\bCOMMENT\b\s*=\s*'(?:[^']|'')*'", ""),
        (r'(?<!["`])\bCOMMENT\b\s*=\s*"(?:[^"]|"")*"', ""),
        (r"\s+\bCOMMENT\b\s+'(?:[^']|'')*'", ""),
        (r'\s+\bCOMMENT\b\s+"(?:[^"]|"")*"', ""),
        # USING BTREE for indexes
        (r"\s+USING\s+BTREE", ""),
        # ON UPDATE CURRENT_TIMESTAMP
        (r"\s+ON\s+UPDATE\s+CURRENT_TIMESTAMP(?:\(\))?", ""),
        # Remove FOREIGN KEY constraints (data integrity issues in source)
        # Match both backticks (before conversion) and double quotes (after conversion)
        (
            r',\s*CONSTRAINT\s+[`"][^`"]*[`"]\s+FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+[`"][^`"]*[`"]\s*\([^)]+\)(?:\s+ON\s+DELETE\s+\w+)?(?:\s+ON\s+UPDATE\s+\w+)?',
            "",
        ),
        (
            r',\s*FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+[`"][^`"]*[`"]\s*\([^)]+\)(?:\s+ON\s+DELETE\s+\w+)?(?:\s+ON\s+UPDATE\s+\w+)?',
            "",
        ),
    ]

    POSTGRES_CLEANUP_PATTERNS = [
        (r"\s+ENGINE\s*=\s*\w+", ""),
        (r"\s+DEFAULT\s+CHARACTER\s+SET\s*=\s*\w+", ""),
        (r"\s+CHARACTER\s+SET\s*=\s*\w+", ""),
        (r"\s+ROW_FORMAT\s*=\s*\w+", ""),
        (r"\s+WITH\s*\(\s*STATS_PERSISTENT\s*=\s*\d+\s*\)", ""),
        (r"\s+STATS_PERSISTENT\s*=\s*\d+", ""),
    ]

    def __init__(self, schema_name: str = "public"):
        """
        Initialize the converter.

        Args:
            schema_name: Target PostgreSQL schema name.
        """
        self.schema_name = schema_name
        self._preprocessor_patterns = [
            (re.compile(p, re.IGNORECASE | re.DOTALL), r)
            for p, r in self.MYSQL_PREPROCESSOR_PATTERNS
        ]
        self._cleanup_patterns = [
            (re.compile(p, re.IGNORECASE), r)
            for p, r in self.CREATE_TABLE_CLEANUP_PATTERNS
        ]
        self._postgres_cleanup_patterns = [
            (re.compile(p, re.IGNORECASE), r) for p, r in self.POSTGRES_CLEANUP_PATTERNS
        ]

    def _preprocess(self, sql: str) -> str:
        """
        Preprocess SQL to remove MySQL-specific constructs before parsing.

        Args:
            sql: Raw MySQL SQL.

        Returns:
            Preprocessed SQL.
        """
        for pattern, replacement in self._preprocessor_patterns:
            sql = pattern.sub(replacement, sql)
        return sql.strip()

    def _cleanup_create_table(self, sql: str) -> str:
        """
        Clean up MySQL-specific CREATE TABLE options.

        Args:
            sql: SQL that may contain CREATE TABLE statements.

        Returns:
            Cleaned SQL.
        """
        for pattern, replacement in self._cleanup_patterns:
            sql = pattern.sub(replacement, sql)
        return sql

    def _convert_identifiers(self, sql: str) -> str:
        """
        Convert MySQL backtick identifiers to PostgreSQL double quotes.

        Args:
            sql: SQL with backtick identifiers.

        Returns:
            SQL with double-quoted identifiers.
        """
        return re.sub(r"`([^`]+)`", r'"\1"', sql)

    def _add_schema_prefix_regex(self, sql: str, schema_name: str) -> str:
        """
        Add schema prefix to table references using regex.

        Args:
            sql: SQL content.
            schema_name: Schema name to prefix.

        Returns:
            SQL with schema-prefixed table names.
        """
        # Add schema to CREATE TABLE
        sql = re.sub(
            r'CREATE TABLE IF NOT EXISTS "([^"]+)"',
            rf'CREATE TABLE IF NOT EXISTS {schema_name}."\1"',
            sql,
        )
        sql = re.sub(
            r'CREATE TABLE "([^"]+)"',
            rf'CREATE TABLE {schema_name}."\1"',
            sql,
        )

        # Add schema to DROP TABLE
        sql = re.sub(
            r'DROP TABLE IF EXISTS "([^"]+)"',
            rf'DROP TABLE IF EXISTS {schema_name}."\1"',
            sql,
        )

        # Add schema to INSERT
        sql = re.sub(
            r'INSERT INTO "([^"]+)"',
            rf'INSERT INTO {schema_name}."\1"',
            sql,
        )

        # Add schema to DELETE
        sql = re.sub(
            r'DELETE FROM "([^"]+)"',
            rf'DELETE FROM {schema_name}."\1"',
            sql,
        )

        return sql

    def _convert_auto_increment(self, sql: str) -> str:
        """
        Convert MySQL AUTO_INCREMENT to PostgreSQL SERIAL types.

        Args:
            sql: SQL with AUTO_INCREMENT.

        Returns:
            SQL with SERIAL/BIGSERIAL.
        """
        # INT/INTEGER AUTO_INCREMENT -> SERIAL
        sql = re.sub(
            r'"(\w+)"\s+(?:INT|INTEGER)(?:\s*\(\d+\))?\s+NOT\s+NULL\s+AUTO_INCREMENT',
            r'"\1" SERIAL',
            sql,
            flags=re.IGNORECASE,
        )
        # BIGINT AUTO_INCREMENT -> BIGSERIAL
        sql = re.sub(
            r'"(\w+)"\s+BIGINT(?:\s*\(\d+\))?\s+NOT\s+NULL\s+AUTO_INCREMENT',
            r'"\1" BIGSERIAL',
            sql,
            flags=re.IGNORECASE,
        )
        # SMALLINT AUTO_INCREMENT -> SMALLSERIAL
        sql = re.sub(
            r'"(\w+)"\s+SMALLINT(?:\s*\(\d+\))?\s+NOT\s+NULL\s+AUTO_INCREMENT',
            r'"\1" SMALLSERIAL',
            sql,
            flags=re.IGNORECASE,
        )
        return sql

    def _remove_unsigned(self, sql: str) -> str:
        """Remove UNSIGNED attribute from numeric types."""
        return re.sub(r"\s+UNSIGNED\b", "", sql, flags=re.IGNORECASE)

    def _remove_inline_indexes(self, sql: str) -> str:
        """Remove inline KEY/INDEX definitions (PostgreSQL doesn't support them in CREATE TABLE)."""
        sql = re.sub(r',\s*KEY\s+"[^"]*"\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)
        sql = re.sub(
            r',\s*UNIQUE\s+KEY\s+"[^"]*"\s*\([^)]+\)', "", sql, flags=re.IGNORECASE
        )
        sql = re.sub(r',\s*INDEX\s+"[^"]*"\s*\([^)]+\)', "", sql, flags=re.IGNORECASE)
        return sql

    def _fix_string_escaping(self, sql: str) -> str:
        """
        Fix string escaping from MySQL to PostgreSQL.

        MySQL uses \' for escaping, PostgreSQL uses ''.
        """

        def fix_string(match: re.Match) -> str:
            content = match.group(1)
            # Replace \' with ''
            content = content.replace("\\'", "''")
            # Replace \" with "
            content = content.replace('\\"', '"')
            return f"'{content}'"

        return re.sub(r"'([^']*(?:\\'[^']*)*)'", fix_string, sql)

    def _remove_on_update_constraints(self, column: exp.ColumnDef) -> exp.ColumnDef:
        """Drop ON UPDATE column constraints that PostgreSQL does not support."""
        constraints = []
        for constraint in column.args.get("constraints", []):
            kind = constraint.args.get("kind")
            if isinstance(kind, exp.OnUpdateColumnConstraint):
                continue
            constraints.append(constraint)
        column.set("constraints", constraints)
        return column

    def _transform_ast(self, ast: exp.Expression, schema_name: str) -> exp.Expression:
        """Apply PostgreSQL-friendly transforms to the parsed AST."""

        def _visitor(node: exp.Expression) -> Optional[exp.Expression]:
            # Ensure schema qualification
            if isinstance(node, exp.Table) and not node.args.get("db"):
                node.set("db", exp.to_identifier(schema_name))

            # Remove MySQL-only column constraints
            if isinstance(node, exp.ColumnDef):
                return self._remove_on_update_constraints(node)

            # Drop table properties, foreign keys, and inline indexes to avoid ordering issues
            if isinstance(
                node,
                (
                    exp.ForeignKey,
                    exp.Reference,
                    exp.Index,
                    exp.Properties,
                    exp.UniqueColumnConstraint,
                    exp.IndexColumnConstraint,
                    exp.Constraint,
                ),
            ):
                return None

            return node

        # Clear table-level properties and indexes if present
        ast.set("properties", None)
        ast.set("indexes", None)

        return ast.transform(_visitor, copy=False)

    def _postprocess_postgres_sql(self, sql: str, schema_name: str) -> str:
        """Remove remaining MySQL artifacts after SQLGlot rendering."""
        for pattern, replacement in self._postgres_cleanup_patterns:
            sql = pattern.sub(replacement, sql)

        # Remove MySQL character set introducers like _utf8mb3'text'
        sql = re.sub(r"_utf8mb\d+\s*'", "'", sql)
        sql = re.sub(r"_utf8mb\d+\s*\"", '"', sql)

        sql = self._cleanup_create_table(sql)
        sql = self._add_schema_prefix_regex(sql, schema_name)

        # Normalize whitespace
        sql = re.sub(r"\n\s*\n\s*\n", "\n\n", sql)
        return sql.strip()

    def _fallback_convert(self, sql: str, schema_name: str) -> str:
        """
        Fallback conversion path using the previous regex-based pipeline.
        """
        sql = self._cleanup_create_table(sql)
        sql = self._convert_identifiers(sql)
        sql = self._remove_unsigned(sql)
        sql = self._convert_auto_increment(sql)
        sql = self._remove_inline_indexes(sql)
        sql = self._fix_string_escaping(sql)
        sql = self._add_schema_prefix_regex(sql, schema_name)
        return sql.strip()

    def convert_statement(self, sql: str) -> ConversionResult:
        """
        Convert a single SQL statement from MySQL to PostgreSQL.

        Args:
            sql: MySQL SQL statement.

        Returns:
            ConversionResult with converted SQL.
        """
        original = sql
        errors: List[str] = []
        warnings: List[str] = []
        schema_name = self.schema_name

        try:
            # Step 1: Preprocess to remove MySQL-specific headers
            sql = self._preprocess(sql)
            if not sql:
                return ConversionResult(
                    success=True, converted_sql="", original_sql=original
                )

            converted_sql = ""

            # Step 2: Try SQLGlot AST-based conversion
            try:
                ast = parse_one(sql, read="mysql", error_level=ErrorLevel.RAISE)
                ast = self._transform_ast(ast, schema_name)
                converted_sql = ast.sql(dialect="postgres")
            except ParseError as e:
                warnings.append(f"SQLGlot parse failed: {e}")
                logger.debug("converter.parse_error", error=str(e), sql=sql[:200])
            except Exception as e:
                warnings.append(f"SQLGlot conversion skipped: {e}")
                logger.debug(
                    "converter.ast_conversion_error", error=str(e), sql=sql[:200]
                )

            # Step 3: Fallback to regex pipeline if SQLGlot failed
            if not converted_sql:
                converted_sql = self._fallback_convert(sql, schema_name)
                warnings.append("Used regex fallback conversion")

            converted_sql = self._postprocess_postgres_sql(converted_sql, schema_name)

            return ConversionResult(
                success=not errors,
                converted_sql=converted_sql,
                original_sql=original,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            errors.append(f"Conversion error: {e}")
            logger.error("converter.error", error=str(e), sql=original[:200])

            return ConversionResult(
                success=False,
                converted_sql=original,
                original_sql=original,
                errors=errors,
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
        self, create_statement: str, insert_statements: List[str], schema_name: str
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


# Backward compatibility alias
SQLGlotConverter = MySQLToPostgreSQLConverter
