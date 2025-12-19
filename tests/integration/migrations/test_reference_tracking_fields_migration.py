"""Integration tests for Reference Tracking Fields migration (Story 6.2.2).

Tests verify:
- AC1: Tracking columns added to all 4 reference tables
- AC2: Target tables (年金计划, 组合计划, 产品线, 组织架构)
- AC3: Backward compatibility (existing records get defaults)
- AC4: Performance indexes on _source and _needs_review
- AC5: Idempotent migration (IF NOT EXISTS patterns)
- AC6: Rollback support (downgrade removes columns and indexes)
- AC7: Schema validation (tables must exist)

These tests require a PostgreSQL database connection.
Skip if DATABASE_URL is not configured or points to SQLite.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
import uuid

import os

from work_data_hub.config import get_settings
from work_data_hub.io.schema import migration_runner


MIGRATION_REVISION = "20251212_120000"
DOWN_REVISION = "20251208_000001"

# Target reference tables
TARGET_TABLES = ["年金计划", "组合计划", "产品线", "组织架构"]

# Primary key columns per table (existing schema columns in mapping/business)
PK_COLUMNS = {
    "年金计划": "年金计划号",
    "组合计划": "组合代码",
    "产品线": "产品线代码",
    "组织架构": "机构代码",
}

# Optional display/name columns present in current schema (used only if needed)
NAME_COLUMNS = {
    "年金计划": "计划简称",
    "组合计划": "组合名称",
    "产品线": "产品线",
    "组织架构": "机构",
}

# Tracking columns to verify
TRACKING_COLUMNS = ["_source", "_needs_review", "_derived_from_domain", "_derived_at"]


def get_test_engine() -> Engine | None:
    """Get database engine for testing, or None if not available."""
    try:
        settings = get_settings()
        url = settings.get_database_connection_string()
        # Skip SQLite - business schema requires PostgreSQL
        if "sqlite" in url.lower():
            return None
        engine = create_engine(url)
        # Test the connection to ensure database is accessible
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception:
        return None


@pytest.fixture(scope="module")
def db_engine():
    """Provide database engine, skip if not available.

    This fixture validates that:
    1. Database settings are configured
    2. Database is PostgreSQL (not SQLite)
    3. Database connection is actually working
    """
    engine = get_test_engine()
    if engine is None:
        pytest.skip("PostgreSQL database not available or not accessible for migration tests")
    return engine


@pytest.fixture(scope="module", autouse=True)
def reference_schema(db_engine: Engine) -> str:
    """
    Create an isolated reference schema for this test module and point the
    migration at it via WDH_REFERENCE_SCHEMA.

    This avoids mutating or depending on production-like schemas (e.g. mapping)
    that may already contain large legacy tables.
    """
    schema = f"wdh_test_reference_{uuid.uuid4().hex[:8]}"
    previous = os.environ.get("WDH_REFERENCE_SCHEMA")
    os.environ["WDH_REFERENCE_SCHEMA"] = schema

    with db_engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {schema}."年金计划" (
                    "年金计划号" VARCHAR(255) PRIMARY KEY,
                    "计划简称" VARCHAR(255)
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {schema}."组合计划" (
                    "组合代码" VARCHAR(255) PRIMARY KEY,
                    "组合名称" VARCHAR(255)
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {schema}."产品线" (
                    "产品线代码" VARCHAR(255) PRIMARY KEY,
                    "产品线" VARCHAR(255)
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {schema}."组织架构" (
                    "机构代码" VARCHAR(255) PRIMARY KEY,
                    "机构" VARCHAR(255)
                )
                """
            )
        )
        conn.commit()

    try:
        yield schema
    finally:
        with db_engine.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            conn.commit()
        if previous is None:
            os.environ.pop("WDH_REFERENCE_SCHEMA", None)
        else:
            os.environ["WDH_REFERENCE_SCHEMA"] = previous


@pytest.fixture
def migrated_db(db_engine: Engine):
    """Upgrade to the target revision for the test, then downgrade afterward."""
    # Note: migration_runner needs the full URL with password for DB connection
    # This is only used internally and not logged
    url = str(db_engine.url)
    migration_runner.upgrade(url, MIGRATION_REVISION)
    try:
        yield db_engine
    finally:
        migration_runner.downgrade(url, DOWN_REVISION)


class TestTrackingColumnsExist:
    """Test that tracking columns exist on all reference tables (AC1, AC2)."""

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_table_has_tracking_columns(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC1, AC2: Verify each reference table has all tracking columns."""
        inspector = inspect(migrated_db)
        columns = {
            c["name"]
            for c in inspector.get_columns(table_name, schema=reference_schema)
        }

        for tracking_col in TRACKING_COLUMNS:
            assert tracking_col in columns, (
                f"Table {table_name} missing tracking column: {tracking_col}"
            )

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_source_column_properties(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC1: Verify _source column has correct type and default."""
        inspector = inspect(migrated_db)
        columns = {
            c["name"]: c
            for c in inspector.get_columns(table_name, schema=reference_schema)
        }

        source_col = columns["_source"]
        # Should be VARCHAR(20)
        assert "VARCHAR" in str(source_col["type"]).upper()
        # Should be NOT NULL
        assert source_col["nullable"] is False
        # Should have default 'authoritative'
        assert source_col["default"] is not None

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_needs_review_column_properties(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC1: Verify _needs_review column has correct type and default."""
        inspector = inspect(migrated_db)
        columns = {
            c["name"]: c
            for c in inspector.get_columns(table_name, schema=reference_schema)
        }

        needs_review_col = columns["_needs_review"]
        # Should be BOOLEAN
        assert "BOOLEAN" in str(needs_review_col["type"]).upper()
        # Should be NOT NULL
        assert needs_review_col["nullable"] is False
        # Should have default false
        assert needs_review_col["default"] is not None

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_derived_from_domain_column_properties(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC1: Verify _derived_from_domain column is nullable VARCHAR(50)."""
        inspector = inspect(migrated_db)
        columns = {
            c["name"]: c
            for c in inspector.get_columns(table_name, schema=reference_schema)
        }

        derived_col = columns["_derived_from_domain"]
        # Should be VARCHAR(50)
        assert "VARCHAR" in str(derived_col["type"]).upper()
        # Should be NULLABLE
        assert derived_col["nullable"] is True

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_derived_at_column_properties(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC1: Verify _derived_at column is nullable TIMESTAMP WITH TIME ZONE."""
        inspector = inspect(migrated_db)
        columns = {
            c["name"]: c
            for c in inspector.get_columns(table_name, schema=reference_schema)
        }

        derived_at_col = columns["_derived_at"]
        # Should be TIMESTAMP or DATETIME
        col_type_str = str(derived_at_col["type"]).upper()
        assert "TIMESTAMP" in col_type_str or "DATETIME" in col_type_str
        # Should be NULLABLE
        assert derived_at_col["nullable"] is True


class TestPerformanceIndexes:
    """Test that performance indexes exist on all reference tables (AC4)."""

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_source_index_exists(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC4: Verify _source index exists for each table."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes(table_name, schema=reference_schema)
        index_names = [idx["name"] for idx in indexes]

        expected_index = f"ix_{table_name}_source"
        assert expected_index in index_names, (
            f"Index {expected_index} should exist on {table_name}"
        )

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_source_index_columns(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC4: Verify _source index has correct column."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes(table_name, schema=reference_schema)

        expected_index = f"ix_{table_name}_source"
        source_index = next(
            (idx for idx in indexes if idx["name"] == expected_index),
            None,
        )
        assert source_index is not None
        assert "_source" in source_index["column_names"]

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_needs_review_index_exists(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC4: Verify _needs_review index exists for each table."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes(table_name, schema=reference_schema)
        index_names = [idx["name"] for idx in indexes]

        expected_index = f"ix_{table_name}_needs_review"
        assert expected_index in index_names, (
            f"Index {expected_index} should exist on {table_name}"
        )

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_needs_review_index_columns(
        self, migrated_db: Engine, reference_schema: str, table_name: str
    ):
        """AC4: Verify _needs_review index has correct column."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes(table_name, schema=reference_schema)

        expected_index = f"ix_{table_name}_needs_review"
        review_index = next(
            (idx for idx in indexes if idx["name"] == expected_index),
            None,
        )
        assert review_index is not None
        assert "_needs_review" in review_index["column_names"]


class TestBackwardCompatibility:
    """Test backward compatibility with existing data (AC3)."""

    def test_existing_records_get_defaults(
        self, migrated_db: Engine, reference_schema: str
    ):
        """AC3: Verify existing records automatically get default values.

        This test simulates the scenario where data exists before migration.
        Since we're in a test environment, we'll insert data after migration
        and verify defaults work correctly.
        """
        # Use 产品线 table for testing (Product Line)
        table_name = "产品线"
        pk_col = PK_COLUMNS[table_name]

        with migrated_db.connect() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {reference_schema}."{table_name}"
                        ({pk_col})
                    VALUES
                        (:code)
                    """
                ),
                {"code": "TEST_PRODUCT_LINE"},
            )
            conn.commit()

            # Verify tracking fields have default values
            result = conn.execute(
                text(
                    f"""
                    SELECT _source, _needs_review, _derived_from_domain, _derived_at
                    FROM {reference_schema}."{table_name}"
                    WHERE {pk_col} = :code
                    """
                ),
                {"code": "TEST_PRODUCT_LINE"},
            )
            row = result.fetchone()

            assert row is not None
            assert row[0] == "authoritative"  # _source default
            assert row[1] is False  # _needs_review default
            assert row[2] is None  # _derived_from_domain nullable
            assert row[3] is None  # _derived_at nullable

            # Cleanup
            conn.execute(
                text(
                    f'DELETE FROM {reference_schema}."{table_name}" WHERE {pk_col} = :code'
                ),
                {"code": "TEST_PRODUCT_LINE"},
            )
            conn.commit()


class TestSchemaValidation:
    """Test schema validation before migration (AC7)."""

    def test_upgrade_validates_table_existence(
        self, db_engine: Engine, reference_schema: str
    ):
        """AC7: Migration should verify tables exist before adding columns.

        This test verifies that the _table_exists check in upgrade() works correctly.
        We can't easily test the ValueError case without dropping tables, but we can
        verify the validation logic exists by checking the migration runs successfully
        when tables do exist.
        """
        url = str(db_engine.url)
        # This should succeed because all 4 tables exist
        migration_runner.upgrade(url, MIGRATION_REVISION)

        # Verify all tables were processed (columns added)
        inspector = inspect(db_engine)
        for table_name in TARGET_TABLES:
            columns = {
                c["name"]
                for c in inspector.get_columns(table_name, schema=reference_schema)
            }
            assert "_source" in columns, f"Table {table_name} should have _source column"

        # Cleanup
        migration_runner.downgrade(url, DOWN_REVISION)


class TestMigrationIdempotency:
    """Test that migration operations are idempotent (AC5)."""

    def test_upgrade_twice_no_error(self, db_engine: Engine, reference_schema: str):
        """AC5: Running upgrade twice should not fail."""
        url = str(db_engine.url)
        # First upgrade
        migration_runner.upgrade(url, MIGRATION_REVISION)
        # Second upgrade should be no-op (idempotent)
        migration_runner.upgrade(url, MIGRATION_REVISION)

        # Verify columns still exist on all tables
        inspector = inspect(db_engine)
        for table_name in TARGET_TABLES:
            columns = {
                c["name"]
                for c in inspector.get_columns(table_name, schema=reference_schema)
            }
            for tracking_col in TRACKING_COLUMNS:
                assert tracking_col in columns

        # Cleanup
        migration_runner.downgrade(url, DOWN_REVISION)


class TestMigrationReversibility:
    """Test that downgrade removes objects created by the migration (AC6)."""

    def test_downgrade_removes_columns(self, db_engine: Engine, reference_schema: str):
        """AC6: Upgrade then downgrade should remove tracking columns."""
        url = str(db_engine.url)
        migration_runner.upgrade(url, MIGRATION_REVISION)
        migration_runner.downgrade(url, DOWN_REVISION)

        inspector = inspect(db_engine)
        for table_name in TARGET_TABLES:
            columns = {
                c["name"]
                for c in inspector.get_columns(table_name, schema=reference_schema)
            }
            # Tracking columns should be removed
            for tracking_col in TRACKING_COLUMNS:
                assert tracking_col not in columns, (
                    f"Column {tracking_col} should be removed from {table_name}"
                )

        # Re-upgrade to ensure reversibility and idempotency
        migration_runner.upgrade(url, MIGRATION_REVISION)
        inspector_after_upgrade = inspect(db_engine)
        for table_name in TARGET_TABLES:
            columns = {
                c["name"]
                for c in inspector_after_upgrade.get_columns(
                    table_name, schema=reference_schema
                )
            }
            for tracking_col in TRACKING_COLUMNS:
                assert tracking_col in columns

        # Final cleanup
        migration_runner.downgrade(url, DOWN_REVISION)

    def test_downgrade_removes_indexes(self, db_engine: Engine, reference_schema: str):
        """AC6: Downgrade should remove all tracking field indexes."""
        url = str(db_engine.url)
        migration_runner.upgrade(url, MIGRATION_REVISION)
        migration_runner.downgrade(url, DOWN_REVISION)

        # Check indexes are gone for all tables
        with db_engine.connect() as conn:
            for table_name in TARGET_TABLES:
                result = conn.execute(
                    text(
                        """
                        SELECT indexname FROM pg_indexes
                        WHERE schemaname = :schema
                        AND tablename = :table
                        AND (indexname LIKE :source_pattern
                             OR indexname LIKE :review_pattern)
                        """
                    ),
                    {
                        "schema": reference_schema,
                        "table": table_name,
                        "source_pattern": f"ix_{table_name}_source",
                        "review_pattern": f"ix_{table_name}_needs_review",
                    },
                )
                indexes = [row[0] for row in result]
                assert len(indexes) == 0, (
                    f"All tracking indexes should be removed from {table_name}"
                )


class TestIntegrationWithBackfillService:
    """Test integration with GenericBackfillService from Story 6.2.1 (AC9)."""

    def test_backfill_service_can_write_tracking_fields(
        self, migrated_db: Engine, reference_schema: str
    ):
        """AC9: GenericBackfillService can write tracking fields to enhanced tables.

        This test verifies that the schema enhancement is compatible with
        the backfill service implemented in Story 6.2.1.
        """
        # Use 组织架构 table for testing (Organization)
        table_name = "组织架构"
        pk_col = PK_COLUMNS[table_name]
        name_col = NAME_COLUMNS[table_name]
        code = f"TEST_ORG_{uuid.uuid4().hex[:8]}"

        with migrated_db.connect() as conn:
            # Simulate what GenericBackfillService does:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {reference_schema}."{table_name}"
                        ({pk_col}, {name_col}, _source, _needs_review,
                         _derived_from_domain, _derived_at)
                    VALUES
                        (:code, :name, :source, :needs_review,
                         :derived_from, :derived_at)
                    """
                ),
                {
                    "code": code,
                    "name": "Test Organization",
                    "source": "auto_derived",
                    "needs_review": True,
                    "derived_from": "annuity_performance",
                    "derived_at": "2025-12-12 12:00:00+00",
                },
            )
            conn.commit()

            # Verify tracking fields were written correctly
            result = conn.execute(
                text(
                    f"""
                    SELECT _source, _needs_review, _derived_from_domain, _derived_at
                    FROM {reference_schema}."{table_name}"
                    WHERE {pk_col} = :code
                    """
                ),
                {"code": code},
            )
            row = result.fetchone()

            assert row is not None
            assert row[0] == "auto_derived"  # _source
            assert row[1] is True  # _needs_review
            assert row[2] == "annuity_performance"  # _derived_from_domain
            assert row[3] is not None  # _derived_at

            # Cleanup
            conn.execute(
                text(
                    f'DELETE FROM {reference_schema}."{table_name}" WHERE {pk_col} = :code'
                ),
                {"code": code},
            )
            conn.commit()

    def test_query_by_source_type(self, migrated_db: Engine, reference_schema: str):
        """AC4: Verify _source index enables efficient filtering by source type."""
        table_name = "年金计划"
        pk_col = PK_COLUMNS[table_name]
        name_col = NAME_COLUMNS[table_name]

        with migrated_db.connect() as conn:
            # Insert test records with different sources
            conn.execute(
                text(
                    f"""
                    INSERT INTO {reference_schema}."{table_name}"
                        ({pk_col}, {name_col}, _source)
                    VALUES
                        (:code1, :name1, 'authoritative'),
                        (:code2, :name2, 'auto_derived')
                    """
                ),
                {
                    "code1": "TEST_PLAN_AUTH",
                    "name1": "Authoritative Plan",
                    "code2": "TEST_PLAN_AUTO",
                    "name2": "Auto-derived Plan",
                },
            )
            conn.commit()

            # Query by source type (should use index)
            result = conn.execute(
                text(
                    f"""
                    SELECT {pk_col}, _source
                    FROM {reference_schema}."{table_name}"
                    WHERE _source = :source
                    ORDER BY {pk_col}
                    """
                ),
                {"source": "auto_derived"},
            )
            rows = result.fetchall()

            assert len(rows) >= 1
            assert any(row[0] == "TEST_PLAN_AUTO" for row in rows)

            # Cleanup
            conn.execute(
                text(
                    f"""
                    DELETE FROM {reference_schema}."{table_name}"
                    WHERE {pk_col} IN (:code1, :code2)
                    """
                ),
                {"code1": "TEST_PLAN_AUTH", "code2": "TEST_PLAN_AUTO"},
            )
            conn.commit()

    def test_query_records_needing_review(
        self, migrated_db: Engine, reference_schema: str
    ):
        """AC4: Verify _needs_review index enables efficient filtering."""
        table_name = "组合计划"

        with migrated_db.connect() as conn:
            # Insert test records with different review flags
            conn.execute(
                text(
                    f"""
                    INSERT INTO {reference_schema}."{table_name}"
                        (组合代码, 组合名称, _needs_review)
                    VALUES
                        (:code1, :name1, false),
                        (:code2, :name2, true)
                    """
                ),
                {
                    "code1": "TEST_PORTFOLIO_OK",
                    "name1": "Reviewed Portfolio",
                    "code2": "TEST_PORTFOLIO_REVIEW",
                    "name2": "Needs Review Portfolio",
                },
            )
            conn.commit()

            # Query records needing review (should use index)
            result = conn.execute(
                text(
                    f"""
                    SELECT 组合代码, _needs_review
                    FROM {reference_schema}."{table_name}"
                    WHERE _needs_review = true
                    ORDER BY 组合代码
                    """
                ),
            )
            rows = result.fetchall()

            assert any(row[0] == "TEST_PORTFOLIO_REVIEW" for row in rows)

            # Cleanup
            conn.execute(
                text(
                    f"""
                    DELETE FROM {reference_schema}."{table_name}"
                    WHERE 组合代码 IN (:code1, :code2)
                    """
                ),
                {"code1": "TEST_PORTFOLIO_OK", "code2": "TEST_PORTFOLIO_REVIEW"},
            )
            conn.commit()
