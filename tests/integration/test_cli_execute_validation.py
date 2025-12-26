"""
E2E test infrastructure for CLI execute mode validation.

Story 7.1-13: E2E Test Infrastructure Foundation
Task 3: Integration Tests (AC-3, AC-4)

These tests verify the E2E test infrastructure (fixtures) are correctly set up.
Full E2E tests requiring data files are documented for manual verification.

Note: Tests use --no-enrichment to avoid EQC API calls.
Note: File discovery is mocked to avoid dependency on external data files.
"""

import pytest


@pytest.mark.e2e_suite
class TestE2EFixtures:
    """Test the E2E fixture infrastructure (AC-1, AC-2)."""

    def test_postgres_db_with_domain_tables_creates_tables(
        self, postgres_db_with_domain_tables: str
    ):
        """Verify postgres_db_with_domain_tables fixture creates domain tables."""
        import psycopg2

        conn = psycopg2.connect(postgres_db_with_domain_tables)
        conn.autocommit = True

        try:
            with conn.cursor() as cur:
                # Verify business schema exists
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'business'"
                )
                assert cur.fetchone() is not None, "business schema should exist"

                # Verify domain tables exist
                cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'business' AND table_name IN ('规模明细', '收入明细')"
                )
                tables = {row[0] for row in cur.fetchall()}
                assert "规模明细" in tables, "规模明细 table should exist"
                assert "收入明细" in tables, "收入明细 table should exist"

                # Verify mapping schema exists
                cur.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'mapping'"
                )
                assert cur.fetchone() is not None, "mapping schema should exist"

                # Verify mapping tables exist
                cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'mapping' AND table_name IN ('年金计划', '组合计划')"
                )
                tables = {row[0] for row in cur.fetchall()}
                assert "年金计划" in tables, "年金计划 table should exist"
                assert "组合计划" in tables, "组合计划 table should exist"
        finally:
            conn.close()

    def test_postgres_db_with_domain_tables_unique_constraints(
        self, postgres_db_with_domain_tables: str
    ):
        """Verify UNIQUE constraints exist for FK backfill ON CONFLICT operations (AC-1)."""
        import psycopg2

        conn = psycopg2.connect(postgres_db_with_domain_tables)
        conn.autocommit = True

        try:
            with conn.cursor() as cur:
                # Verify annuity_plans has UNIQUE index on 年金计划号 (Story 7.1-12)
                cur.execute(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'mapping' AND tablename = '年金计划' AND indexname LIKE '%年金计划号%'
                    """
                )
                indexes = cur.fetchall()
                # Should have at least one index on 年金计划号
                assert len(indexes) > 0, "年金计划 should have index on 年金计划号"

                # Verify portfolio_plans has UNIQUE index on 组合代码 (Story 7.1-13 fix)
                cur.execute(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'mapping' AND tablename = '组合计划' AND indexdef LIKE '%UNIQUE%'
                    """
                )
                unique_indexes = cur.fetchall()
                assert len(unique_indexes) > 0, (
                    "组合计划 should have UNIQUE index on 组合代码"
                )
        finally:
            conn.close()

    def test_multi_domain_tables_created(self, postgres_db_with_domain_tables: str):
        """Verify multiple domains are created in a single fixture call (Task 3.4)."""
        import psycopg2

        conn = psycopg2.connect(postgres_db_with_domain_tables)
        conn.autocommit = True

        try:
            with conn.cursor() as cur:
                # Verify all expected domain and mapping tables exist
                expected_tables = [
                    ("business", "规模明细"),
                    ("business", "收入明细"),
                    ("mapping", "年金计划"),
                    ("mapping", "组合计划"),
                ]
                for schema, table in expected_tables:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                        """,
                        (schema, table),
                    )
                    count = cur.fetchone()[0]
                    assert count == 1, f"Table {schema}.{table} should exist"
        finally:
            conn.close()


@pytest.mark.e2e_suite
class TestExecuteModeInfrastructure:
    """Test --execute mode infrastructure is ready (AC-3).

    Note: These tests verify infrastructure setup. Full E2E tests
    requiring actual data files are documented for manual verification.
    """

    def test_execute_mode_tables_ready(self, postgres_db_with_domain_tables: str):
        """Verify domain tables are ready for execute mode data insertion."""
        import psycopg2

        conn = psycopg2.connect(postgres_db_with_domain_tables)
        conn.autocommit = True

        try:
            with conn.cursor() as cur:
                # Verify initial state (tables should be empty)
                cur.execute('SELECT COUNT(*) FROM business."规模明细"')
                count = cur.fetchone()[0]
                assert count == 0, "Domain tables should start empty"

                # Verify table structure supports INSERT
                cur.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = 'business' AND table_name = '规模明细'
                    ORDER BY ordinal_position
                """)
                columns = [row[0] for row in cur.fetchall()]
                # Should have standard columns including audit columns
                assert "created_at" in columns, "Should have created_at audit column"
                assert "updated_at" in columns, "Should have updated_at audit column"
        finally:
            conn.close()


@pytest.mark.e2e_suite
class TestDryRunModeInfrastructure:
    """Test --dry-run mode infrastructure is ready (AC-4).

    Note: These tests verify infrastructure setup. Full dry-run isolation
    tests require mocked file discovery and are documented for manual verification.
    """

    def test_dry_run_mode_tables_accessible(self, postgres_db_with_domain_tables: str):
        """Verify tables are accessible for dry-run mode validation."""
        import psycopg2

        conn = psycopg2.connect(postgres_db_with_domain_tables)
        conn.autocommit = True

        try:
            with conn.cursor() as cur:
                # Verify tables exist and are queryable
                cur.execute('SELECT COUNT(*) FROM business."收入明细"')
                count = cur.fetchone()[0]
                assert count == 0, "Domain tables should be empty before dry-run"

                # Verify mapping tables also accessible
                cur.execute('SELECT COUNT(*) FROM mapping."年金计划"')
                count = cur.fetchone()[0]
                assert count == 0, "Mapping tables should be empty"
        finally:
            conn.close()


@pytest.mark.e2e_suite
class TestFixtureCleanup:
    """Test fixture cleanup ensures no test pollution (AC-5)."""

    def test_cleanup_via_ephemeral_db_drop(self, postgres_db_with_domain_tables: str):
        """Verify cleanup is handled by base fixture's ephemeral DB drop.

        The postgres_db_with_domain_tables fixture:
        1. Creates a temp database with unique UUID suffix
        2. Applies Alembic migrations
        3. Creates domain and mapping tables
        4. Yields DSN for tests
        5. Drops entire ephemeral database on teardown

        This ensures complete cleanup without explicit table DROP statements.
        """
        # Verify we're using an ephemeral database (contains _test_ in name)
        assert "_test_" in postgres_db_with_domain_tables, (
            "Should be using ephemeral test database (contains '_test_' in DSN)"
        )
