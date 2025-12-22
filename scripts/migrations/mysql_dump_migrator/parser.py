"""
MySQL Dump File Parser.

Parses large MySQL dump files and extracts content by database.
Supports mysqldump format with multiple databases.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)

# Progress reporting interval (lines)
PROGRESS_INTERVAL = 100000


@dataclass
class TableContent:
    """Content for a single table."""

    name: str
    create_statement: str
    insert_statements: List[str] = field(default_factory=list)
    row_count: int = 0


@dataclass
class DatabaseContent:
    """Content extracted from a MySQL dump for a single database."""

    name: str
    tables: Dict[str, TableContent] = field(default_factory=dict)
    raw_content: str = ""

    @property
    def table_count(self) -> int:
        return len(self.tables)

    @property
    def total_rows(self) -> int:
        return sum(t.row_count for t in self.tables.values())

    def get_table_names(self) -> List[str]:
        return list(self.tables.keys())


class MySQLDumpParser:
    """
    Parser for MySQL dump files.

    Extracts database content from mysqldump format files,
    supporting multi-database dumps.
    """

    # Regex patterns for parsing
    DATABASE_PATTERN = re.compile(r"--\s*Current Database:\s*`([^`]+)`", re.IGNORECASE)
    USE_DATABASE_PATTERN = re.compile(r"USE\s+`([^`]+)`\s*;", re.IGNORECASE)
    CREATE_DATABASE_PATTERN = re.compile(
        r"CREATE DATABASE.*?`([^`]+)`.*?;", re.IGNORECASE | re.DOTALL
    )
    CREATE_TABLE_PATTERN = re.compile(r"CREATE TABLE.*?`([^`]+)`", re.IGNORECASE)
    DROP_TABLE_PATTERN = re.compile(
        r"DROP TABLE IF EXISTS\s+`([^`]+)`\s*;", re.IGNORECASE
    )
    INSERT_PATTERN = re.compile(r"INSERT INTO\s+`([^`]+)`", re.IGNORECASE)

    def __init__(
        self,
        dump_file_path: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize parser with dump file path.

        Args:
            dump_file_path: Path to the MySQL dump file.
            progress_callback: Optional callback for progress updates.
        """
        self.dump_file_path = Path(dump_file_path)
        if not self.dump_file_path.exists():
            raise FileNotFoundError(f"Dump file not found: {dump_file_path}")

        self._databases: Dict[str, DatabaseContent] = {}
        self._current_database: Optional[str] = None
        self._progress_callback = progress_callback or self._default_progress

        # Get file size for progress reporting
        self.file_size = self.dump_file_path.stat().st_size
        self.file_size_mb = self.file_size / (1024 * 1024)

    def _default_progress(self, message: str) -> None:
        """Default progress callback - prints to stderr."""
        print(message, file=sys.stderr, flush=True)

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size to human readable."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def scan_databases(self) -> List[str]:
        """
        Scan the dump file and return list of database names.

        Returns:
            List of database names found in the dump file.
        """
        databases: Set[str] = set()
        bytes_read = 0

        self._progress_callback(
            f"Scanning dump file ({self._format_size(self.file_size)})..."
        )

        with open(self.dump_file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                bytes_read += len(line.encode("utf-8", errors="replace"))

                # Progress update every PROGRESS_INTERVAL lines
                if line_num % PROGRESS_INTERVAL == 0:
                    pct = (bytes_read / self.file_size) * 100
                    self._progress_callback(
                        f"  Scanning... {line_num:,} lines ({pct:.1f}%) - Found {len(databases)} databases"
                    )

                # Check for "Current Database" comment
                match = self.DATABASE_PATTERN.search(line)
                if match:
                    db_name = match.group(1)
                    if db_name not in databases:
                        databases.add(db_name)
                        self._progress_callback(f"  Found database: {db_name}")
                    continue

                # Check for USE statement
                match = self.USE_DATABASE_PATTERN.search(line)
                if match:
                    databases.add(match.group(1))

        self._progress_callback(f"Scan complete: {len(databases)} databases found")
        return sorted(databases)

    def extract_database(self, database_name: str) -> DatabaseContent:
        """
        Extract content for a specific database from the dump file.

        Args:
            database_name: Name of the database to extract.

        Returns:
            DatabaseContent object with extracted tables and data.
        """
        logger.info("parser.extracting_database", database=database_name)
        self._progress_callback(f"Extracting database: {database_name}...")

        content = DatabaseContent(name=database_name)
        in_target_database = False
        current_table: Optional[str] = None
        create_buffer: List[str] = []
        in_create_statement = False
        in_insert_statement = False
        insert_buffer: List[str] = []
        insert_table: Optional[str] = None
        bytes_read = 0
        last_progress_line = 0

        def finalize_insert() -> None:
            nonlocal insert_buffer, insert_table, in_insert_statement
            if in_insert_statement and insert_table and insert_table in content.tables:
                statement = "".join(insert_buffer).strip()
                if statement:
                    content.tables[insert_table].insert_statements.append(statement)
                    content.tables[insert_table].row_count += statement.count("),(") + 1
            insert_buffer = []
            insert_table = None
            in_insert_statement = False

        with open(self.dump_file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                bytes_read += len(line.encode("utf-8", errors="replace"))

                # Progress update every PROGRESS_INTERVAL lines
                if line_num - last_progress_line >= PROGRESS_INTERVAL:
                    last_progress_line = line_num
                    pct = (bytes_read / self.file_size) * 100
                    status = "searching" if not in_target_database else "extracting"
                    self._progress_callback(
                        f"  {status}... {line_num:,} lines ({pct:.1f}%) - {content.table_count} tables"
                    )

                # Check for database switch
                db_match = self.DATABASE_PATTERN.search(line)
                if db_match:
                    if in_insert_statement:
                        finalize_insert()
                    found_db = db_match.group(1)
                    if found_db == database_name:
                        in_target_database = True
                        self._progress_callback(
                            f"  Found database '{database_name}' at line {line_num:,}"
                        )
                        logger.debug(
                            "parser.entered_database",
                            database=database_name,
                            line=line_num,
                        )
                    elif in_target_database:
                        # Exited target database
                        finalize_insert()
                        self._progress_callback(
                            f"  Finished extracting at line {line_num:,}"
                        )
                        logger.debug(
                            "parser.exited_database",
                            database=database_name,
                            line=line_num,
                        )
                        break
                    continue

                if not in_target_database:
                    continue

                # Skip USE and CREATE DATABASE statements
                if self.USE_DATABASE_PATTERN.search(line):
                    continue
                if self.CREATE_DATABASE_PATTERN.search(line):
                    continue

                # Track DROP TABLE
                drop_match = self.DROP_TABLE_PATTERN.search(line)
                if drop_match:
                    current_table = drop_match.group(1)
                    if current_table not in content.tables:
                        content.tables[current_table] = TableContent(
                            name=current_table,
                            create_statement="",
                        )
                    continue

                # Track CREATE TABLE start
                if "CREATE TABLE" in line.upper():
                    in_create_statement = True
                    create_match = self.CREATE_TABLE_PATTERN.search(line)
                    if create_match:
                        current_table = create_match.group(1)
                        if current_table not in content.tables:
                            content.tables[current_table] = TableContent(
                                name=current_table,
                                create_statement="",
                            )
                    create_buffer = [line]
                    continue

                # Continue CREATE TABLE statement
                if in_create_statement:
                    create_buffer.append(line)
                    stripped = line.strip()
                    if stripped.startswith(")") and stripped.endswith(";"):
                        in_create_statement = False
                        if current_table and current_table in content.tables:
                            content.tables[current_table].create_statement = "".join(
                                create_buffer
                            )
                        create_buffer = []
                    continue

                # Track INSERT statements (multi-line friendly)
                insert_match = self.INSERT_PATTERN.search(line)
                if insert_match:
                    finalize_insert()
                    insert_table = insert_match.group(1)
                    if insert_table in content.tables:
                        in_insert_statement = True
                        insert_buffer = [line]
                        if line.rstrip().endswith(";"):
                            finalize_insert()
                    continue

                # Continue INSERT ... VALUES split across multiple lines
                if in_insert_statement:
                    insert_buffer.append(line)
                    if line.rstrip().endswith(";"):
                        finalize_insert()
                    continue

        # Finalize any trailing INSERT at EOF
        if in_insert_statement:
            finalize_insert()

        self._progress_callback(
            f"  Extracted: {content.table_count} tables, ~{content.total_rows:,} rows"
        )
        logger.info(
            "parser.database_extracted",
            database=database_name,
            tables=content.table_count,
            total_rows=content.total_rows,
        )

        return content

    def extract_databases(
        self, database_names: List[str]
    ) -> Generator[DatabaseContent, None, None]:
        """
        Extract content for multiple databases.

        Args:
            database_names: List of database names to extract.

        Yields:
            DatabaseContent objects for each requested database.
        """
        for db_name in database_names:
            yield self.extract_database(db_name)

    def get_database_summary(self) -> Dict[str, Dict]:
        """
        Get a summary of all databases in the dump file.

        Optimized to scan file only once for all databases.

        Returns:
            Dictionary mapping database names to their table counts.
        """
        self._progress_callback(
            f"Gathering database summary ({self._format_size(self.file_size)})..."
        )

        summary: Dict[str, Dict] = {}
        current_db: Optional[str] = None
        bytes_read = 0

        with open(self.dump_file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, 1):
                bytes_read += len(line.encode("utf-8", errors="replace"))

                # Progress update
                if line_num % PROGRESS_INTERVAL == 0:
                    pct = (bytes_read / self.file_size) * 100
                    self._progress_callback(
                        f"  Scanning... {line_num:,} lines ({pct:.1f}%) - {len(summary)} databases"
                    )

                # Check for database switch
                db_match = self.DATABASE_PATTERN.search(line)
                if db_match:
                    current_db = db_match.group(1)
                    if current_db not in summary:
                        summary[current_db] = {"table_count": 0}
                        self._progress_callback(f"  Found database: {current_db}")
                    continue

                # Count tables
                if current_db and "CREATE TABLE" in line.upper():
                    summary[current_db]["table_count"] += 1

        self._progress_callback(f"Summary complete: {len(summary)} databases")
        return summary
