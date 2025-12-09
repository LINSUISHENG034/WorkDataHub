"""
PostgreSQL Migrator.

Handles database operations for migrating MySQL dump content to PostgreSQL.
"""

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from .converter import MySQLToPostgreSQLConverter
from .parser import DatabaseContent, MySQLDumpParser

logger = structlog.get_logger(__name__)


@dataclass
class MigrationConfig:
    """Configuration for the migration process."""

    # Source configuration
    dump_file_path: str
    target_databases: List[str]

    # Target configuration
    target_schema: str = "legacy"
    database_url: Optional[str] = None

    # PostgreSQL connection (used if database_url not provided)
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = "postgres"
    pg_password: str = ""
    pg_database: str = "postgres"

    # Migration options
    dry_run: bool = False
    batch_size: int = 1000
    save_converted_sql: bool = True
    output_dir: Optional[str] = None

    def get_database_url(self) -> str:
        """Get the database URL for connection."""
        if self.database_url:
            # Normalize postgres scheme for SQLAlchemy
            if self.database_url.startswith("postgres://"):
                return self.database_url.replace("postgres://", "postgresql://", 1)
            return self.database_url
        url = (
            f"postgresql://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_database}"
        )
        return url

    @classmethod
    def from_env(
        cls,
        dump_file_path: str,
        target_databases: List[str],
        **kwargs,
    ) -> "MigrationConfig":
        """Create config from environment variables."""
        database_url = (
            os.environ.get("LEGACY_DATABASE__URI")
            or os.environ.get("WDH_DATABASE__URI")
        )

        # Allow overriding the target database name specifically for legacy migration
        db_name = (
            os.environ.get("LEGACY_DATABASE_DB")
            or os.environ.get("WDH_DATABASE_DB", "legacy")
        )

        return cls(
            dump_file_path=dump_file_path,
            target_databases=target_databases,
            database_url=database_url,
            pg_host=os.environ.get("WDH_DATABASE_HOST", "localhost"),
            pg_port=int(os.environ.get("WDH_DATABASE_PORT", "5432")),
            pg_user=os.environ.get("WDH_DATABASE_USER", "postgres"),
            pg_password=os.environ.get("WDH_DATABASE_PASSWORD", ""),
            pg_database=db_name,
            **kwargs,
        )


@dataclass
class TableMigrationResult:
    """Result of migrating a single table."""

    table_name: str
    success: bool
    rows_migrated: int = 0
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class DatabaseMigrationResult:
    """Result of migrating a single database."""

    database_name: str
    schema_name: str
    tables: List[TableMigrationResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return all(t.success for t in self.tables)

    @property
    def total_tables(self) -> int:
        return len(self.tables)

    @property
    def successful_tables(self) -> int:
        return sum(1 for t in self.tables if t.success)

    @property
    def total_rows(self) -> int:
        return sum(t.rows_migrated for t in self.tables)


@dataclass
class MigrationReport:
    """Full migration report."""

    databases: List[DatabaseMigrationResult] = field(default_factory=list)
    dry_run: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return sum(d.duration_seconds for d in self.databases)

    @property
    def total_databases(self) -> int:
        return len(self.databases)

    @property
    def successful_databases(self) -> int:
        return sum(1 for d in self.databases if d.success)

    @property
    def total_tables(self) -> int:
        return sum(d.total_tables for d in self.databases)

    @property
    def successful_tables(self) -> int:
        return sum(d.successful_tables for d in self.databases)

    @property
    def total_rows(self) -> int:
        return sum(d.total_rows for d in self.databases)

    def print_summary(self) -> None:
        """Print human-readable summary."""
        print("\n" + "=" * 70)
        print("MYSQL TO POSTGRESQL MIGRATION REPORT")
        if self.dry_run:
            print(">>> DRY RUN MODE - No data was actually migrated <<<")
        print("=" * 70)

        for db_result in self.databases:
            status = "✓" if db_result.success else "✗"
            print(f"\n{status} Database: {db_result.database_name} → Schema: {db_result.schema_name}")
            print(f"  Tables: {db_result.successful_tables}/{db_result.total_tables}")
            print(f"  Rows: {db_result.total_rows:,}")
            print(f"  Duration: {db_result.duration_seconds:.2f}s")

            # Show failed tables
            failed = [t for t in db_result.tables if not t.success]
            if failed:
                print("  Failed tables:")
                for t in failed:
                    print(f"    - {t.table_name}: {t.error}")

        print("\n" + "-" * 70)
        print("TOTALS:")
        print(f"  Databases: {self.successful_databases}/{self.total_databases}")
        print(f"  Tables: {self.successful_tables}/{self.total_tables}")
        print(f"  Rows: {self.total_rows:,}")
        print(f"  Duration: {self.duration_seconds:.2f}s")
        print("=" * 70 + "\n")


class PostgreSQLMigrator:
    """
    Handles PostgreSQL database operations for migration.

    Manages schema creation, table creation, and data insertion.
    """

    def __init__(self, config: MigrationConfig):
        """
        Initialize the migrator.

        Args:
            config: Migration configuration.
        """
        self.config = config
        self.converter = MySQLToPostgreSQLConverter()
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        """Get or create SQLAlchemy engine."""
        if self._engine is None:
            self._engine = create_engine(self.config.get_database_url())
        return self._engine

    @contextmanager
    def get_connection(self) -> Generator[Connection, None, None]:
        """Context manager for database connections."""
        with self.engine.connect() as conn:
            yield conn

    def create_schema(self, schema_name: str) -> None:
        """
        Create a PostgreSQL schema if it doesn't exist.

        Args:
            schema_name: Name of the schema to create.
        """
        if self.config.dry_run:
            logger.info("migrator.create_schema.dry_run", schema=schema_name)
            return

        with self.get_connection() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            conn.commit()
            logger.info("migrator.schema_created", schema=schema_name)

    def execute_sql(
        self, conn: Connection, sql_content: str, description: str = ""
    ) -> int:
        """
        Execute SQL content.

        Args:
            conn: Database connection.
            sql_content: SQL to execute.
            description: Description for logging.

        Returns:
            Number of rows affected.
        """
        if self.config.dry_run:
            logger.debug("migrator.execute.dry_run", description=description)
            return 0

        # Split into statements and execute
        statements = [s.strip() for s in sql_content.split(";") if s.strip()]
        total_rows = 0

        for stmt in statements:
            if stmt:
                result = conn.execute(text(stmt))
                if result.rowcount > 0:
                    total_rows += result.rowcount

        return total_rows

    def migrate_table(
        self,
        conn: Connection,
        table_name: str,
        create_statement: str,
        insert_statements: List[str],
        schema_name: str,
    ) -> TableMigrationResult:
        """
        Migrate a single table.

        Args:
            conn: Database connection.
            table_name: Name of the table.
            create_statement: CREATE TABLE statement.
            insert_statements: List of INSERT statements.
            schema_name: Target schema name.

        Returns:
            TableMigrationResult with migration outcome.
        """
        start_time = time.perf_counter()
        result = TableMigrationResult(table_name=table_name, success=False)
        converted_create = ""

        try:
            # Convert CREATE statement
            converted_create = self.converter.convert(create_statement, schema_name)

            # Execute CREATE TABLE
            if not self.config.dry_run:
                # Drop table if exists first
                drop_sql = f'DROP TABLE IF EXISTS {schema_name}."{table_name}" CASCADE'
                conn.execute(text(drop_sql))
                conn.execute(text(converted_create))

            # Convert and execute INSERT statements
            for insert_stmt in insert_statements:
                converted_insert = self.converter.convert(insert_stmt, schema_name)
                rows = self.execute_sql(conn, converted_insert, f"INSERT into {table_name}")
                result.rows_migrated += rows

            result.success = True
            logger.info(
                "migrator.table_migrated",
                table=table_name,
                schema=schema_name,
                rows=result.rows_migrated,
            )

        except Exception as e:
            result.error = str(e)
            logger.error(
                "migrator.table_failed",
                table=table_name,
                schema=schema_name,
                error=str(e),
                create_sql=converted_create[:500],
                insert_statements=len(insert_statements),
            )
            if not self.config.dry_run:
                conn.rollback()

        result.duration_seconds = time.perf_counter() - start_time
        return result

    def migrate_database(
        self, db_content: DatabaseContent
    ) -> DatabaseMigrationResult:
        """
        Migrate a single database to a PostgreSQL schema.

        Args:
            db_content: Extracted database content.

        Returns:
            DatabaseMigrationResult with migration outcome.
        """
        start_time = time.perf_counter()
        schema_name = f"{self.config.target_schema}.{db_content.name}"

        # Use just the database name as schema under legacy
        # e.g., legacy.mapping, legacy.business
        actual_schema = db_content.name

        result = DatabaseMigrationResult(
            database_name=db_content.name,
            schema_name=f"{self.config.target_schema}.{actual_schema}",
        )

        logger.info(
            "migrator.database_starting",
            database=db_content.name,
            schema=actual_schema,
            tables=db_content.table_count,
        )

        # Create schema
        self.create_schema(actual_schema)

        # Migrate each table
        with self.get_connection() as conn:
            for table_name, table_content in db_content.tables.items():
                table_result = self.migrate_table(
                    conn=conn,
                    table_name=table_name,
                    create_statement=table_content.create_statement,
                    insert_statements=table_content.insert_statements,
                    schema_name=actual_schema,
                )
                result.tables.append(table_result)

            if not self.config.dry_run:
                conn.commit()

        result.duration_seconds = time.perf_counter() - start_time

        logger.info(
            "migrator.database_completed",
            database=db_content.name,
            schema=actual_schema,
            success=result.success,
            tables=result.successful_tables,
            rows=result.total_rows,
            duration=result.duration_seconds,
        )

        return result

    def save_converted_sql(
        self, db_content: DatabaseContent, output_dir: Path
    ) -> Path:
        """
        Save converted SQL to file for review.

        Args:
            db_content: Database content to convert.
            output_dir: Directory to save converted SQL.

        Returns:
            Path to the saved file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{db_content.name}_converted.sql"

        schema_name = db_content.name
        lines = [
            f"-- Converted from MySQL database: {db_content.name}",
            f"-- Target PostgreSQL schema: {schema_name}",
            f"-- Generated: {datetime.now().isoformat()}",
            "",
            f'CREATE SCHEMA IF NOT EXISTS "{schema_name}";',
            "",
        ]

        for table_name, table_content in db_content.tables.items():
            lines.append(f"-- Table: {table_name}")
            converted_create = self.converter.convert(
                table_content.create_statement, schema_name
            )
            lines.append(converted_create)
            lines.append("")

            for insert_stmt in table_content.insert_statements[:5]:  # Sample only
                converted_insert = self.converter.convert(insert_stmt, schema_name)
                lines.append(converted_insert)

            if len(table_content.insert_statements) > 5:
                lines.append(f"-- ... and {len(table_content.insert_statements) - 5} more INSERT statements")
            lines.append("")

        output_file.write_text("\n".join(lines), encoding="utf-8")
        logger.info("migrator.sql_saved", path=str(output_file))

        return output_file

    def run(self) -> MigrationReport:
        """
        Run the full migration process.

        Returns:
            MigrationReport with complete results.
        """
        report = MigrationReport(
            dry_run=self.config.dry_run,
            start_time=datetime.now(),
        )

        logger.info(
            "migrator.starting",
            dump_file=self.config.dump_file_path,
            databases=self.config.target_databases,
            target_schema=self.config.target_schema,
            dry_run=self.config.dry_run,
        )

        # Parse dump file
        parser = MySQLDumpParser(self.config.dump_file_path)

        # Verify target databases exist in dump
        available_dbs = parser.scan_databases()
        missing_dbs = set(self.config.target_databases) - set(available_dbs)
        if missing_dbs:
            logger.warning(
                "migrator.databases_not_found",
                missing=list(missing_dbs),
                available=available_dbs,
            )

        # Create parent schema if needed
        self.create_schema(self.config.target_schema)

        # Process each target database
        for db_name in self.config.target_databases:
            if db_name not in available_dbs:
                logger.warning("migrator.skipping_database", database=db_name)
                continue

            # Extract database content
            db_content = parser.extract_database(db_name)

            # Optionally save converted SQL
            if self.config.save_converted_sql and self.config.output_dir:
                self.save_converted_sql(
                    db_content, Path(self.config.output_dir)
                )

            # Migrate database
            db_result = self.migrate_database(db_content)
            report.databases.append(db_result)

        report.end_time = datetime.now()

        logger.info(
            "migrator.completed",
            databases=report.successful_databases,
            tables=report.successful_tables,
            rows=report.total_rows,
            duration=report.duration_seconds,
        )

        return report
