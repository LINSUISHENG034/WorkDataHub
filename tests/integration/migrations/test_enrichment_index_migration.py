"""Integration tests for Enrichment Index migration (Story 6.1.1).

Tests verify:
- AC1: enrichment_index table exists with all required columns
- AC2: UNIQUE constraint on (lookup_key, lookup_type)
- AC3: Performance indexes exist
- AC5: Migration is idempotent (IF NOT EXISTS patterns)
- Migration reversibility (upgrade/downgrade)

Story 7.1-9 Note: Updated to use postgres_db_with_migrations fixture
to avoid production database access issues. Tests that need to run
specific migrations (idempotency, reversibility) use a custom
ephemeral_db fixture that creates a fresh temporary database.

Story 7.2-4 Note: Skip decorators removed, tests aligned with new
001/002/003 migration chain.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from tests.conftest import _create_ephemeral_database, _drop_database
from work_data_hub.io.schema import migration_runner


SCHEMA_NAME = "enterprise"
MIGRATION_REVISION = (
    "20251228_000001"  # 001_initial_infrastructure creates enrichment_index
)
DOWN_REVISION = None  # Base migration has no down_revision


def get_engine_from_dsn(dsn: str) -> Engine:
    """Create SQLAlchemy engine from DSN string."""
    return create_engine(dsn)


@pytest.fixture
def migrated_db(postgres_db_with_migrations: str) -> Engine:
    """
    Use the temporary test database created by postgres_db_with_migrations.

    The fixture has already run all migrations, including the enrichment_index
    migration we're testing. We just need to create an engine for it.
    """
    return get_engine_from_dsn(postgres_db_with_migrations)


@pytest.fixture
def ephemeral_db() -> Engine:
    """
    Create a fresh temporary database for migration testing.

    This fixture is for tests that need to run specific migrations
    (idempotency, reversibility tests) rather than using the
    fully-migrated postgres_db_with_migrations fixture.
    """
    from tests.conftest import _resolve_postgres_dsn

    base_dsn = _resolve_postgres_dsn()
    temp_dsn, temp_db, admin_dsn = _create_ephemeral_database(base_dsn)

    engine = get_engine_from_dsn(temp_dsn)

    yield engine

    # Cleanup
    _validate_test_database(temp_dsn)
    _drop_database(admin_dsn, temp_db)


def _validate_test_database(dsn: str) -> None:
    """
    Validate that the database is a test database before destructive operations.

    Raises RuntimeError if the database name doesn't contain test markers.
    """
    from tests.conftest import _validate_test_database

    _validate_test_database(dsn)


class TestEnrichmentIndexTableExists:
    """Test that enrichment_index table exists after migration (AC1)."""

    def test_table_exists(self, migrated_db: Engine):
        """AC1: Verify enrichment_index table exists."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "enrichment_index" in tables, "enrichment_index table should exist"

    def test_table_has_required_columns(self, migrated_db: Engine):
        """AC1: Verify enrichment_index has all required columns."""
        inspector = inspect(migrated_db)
        columns = {
            c["name"]
            for c in inspector.get_columns("enrichment_index", schema=SCHEMA_NAME)
        }
        expected_columns = {
            "id",
            "lookup_key",
            "lookup_type",
            "company_id",
            "confidence",
            "source",
            "source_domain",
            "source_table",
            "hit_count",
            "last_hit_at",
            "created_at",
            "updated_at",
        }
        assert expected_columns.issubset(columns), (
            f"enrichment_index missing columns: {expected_columns - columns}"
        )

    def test_id_is_primary_key(self, migrated_db: Engine):
        """AC1: Verify id is the primary key."""
        inspector = inspect(migrated_db)
        pk = inspector.get_pk_constraint("enrichment_index", schema=SCHEMA_NAME)
        assert pk["constrained_columns"] == ["id"], "enrichment_index PK should be id"

    def test_column_types(self, migrated_db: Engine):
        """AC1: Verify column types are correct."""
        inspector = inspect(migrated_db)
        columns = {
            c["name"]: c
            for c in inspector.get_columns("enrichment_index", schema=SCHEMA_NAME)
        }

        # lookup_key should be VARCHAR(255)
        assert "VARCHAR" in str(columns["lookup_key"]["type"]).upper()

        # lookup_type should be VARCHAR(20)
        assert "VARCHAR" in str(columns["lookup_type"]["type"]).upper()

        # company_id should be VARCHAR(100)
        assert "VARCHAR" in str(columns["company_id"]["type"]).upper()

        # confidence should be NUMERIC(3,2)
        assert "NUMERIC" in str(columns["confidence"]["type"]).upper()

        # hit_count should be INTEGER
        assert "INTEGER" in str(columns["hit_count"]["type"]).upper()


class TestEnrichmentIndexConstraints:
    """Test enrichment_index constraints (AC2)."""

    def test_unique_constraint_on_key_type(self, migrated_db: Engine):
        """AC2: Verify UNIQUE constraint on (lookup_key, lookup_type)."""
        inspector = inspect(migrated_db)
        unique_constraints = inspector.get_unique_constraints(
            "enrichment_index", schema=SCHEMA_NAME
        )
        has_key_type_unique = any(
            set(uc["column_names"]) == {"lookup_key", "lookup_type"}
            for uc in unique_constraints
        )
        assert has_key_type_unique, (
            "enrichment_index should have UNIQUE(lookup_key, lookup_type)"
        )

    def test_lookup_type_check_constraint(self, migrated_db: Engine):
        """AC1: Verify lookup_type CHECK constraint for allowed values."""
        inspector = inspect(migrated_db)
        check_constraints = inspector.get_check_constraints(
            "enrichment_index", schema=SCHEMA_NAME
        )
        has_lookup_type_check = any(
            "lookup_type" in (c.get("sqltext", "") or "")
            and "plan_code" in (c.get("sqltext", "") or "")
            for c in check_constraints
        )
        assert has_lookup_type_check, (
            "enrichment_index should have CHECK constraint on lookup_type"
        )

    def test_source_check_constraint(self, migrated_db: Engine):
        """AC1: Verify source CHECK constraint for allowed values."""
        inspector = inspect(migrated_db)
        check_constraints = inspector.get_check_constraints(
            "enrichment_index", schema=SCHEMA_NAME
        )
        has_source_check = any(
            "source" in (c.get("sqltext", "") or "")
            and "yaml" in (c.get("sqltext", "") or "")
            for c in check_constraints
        )
        assert has_source_check, (
            "enrichment_index should have CHECK constraint on source"
        )

    def test_confidence_check_constraint(self, migrated_db: Engine):
        """AC1: Verify confidence CHECK constraint (0.00-1.00)."""
        inspector = inspect(migrated_db)
        check_constraints = inspector.get_check_constraints(
            "enrichment_index", schema=SCHEMA_NAME
        )
        has_confidence_check = any(
            "confidence" in (c.get("sqltext", "") or "") for c in check_constraints
        )
        assert has_confidence_check, (
            "enrichment_index should have CHECK constraint on confidence"
        )


class TestEnrichmentIndexIndexes:
    """Test enrichment_index indexes (AC3)."""

    def test_type_key_index_exists(self, migrated_db: Engine):
        """AC3: Verify ix_enrichment_index_type_key index exists."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("enrichment_index", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "ix_enrichment_index_type_key" in index_names, (
            "ix_enrichment_index_type_key index should exist"
        )

    def test_type_key_index_columns(self, migrated_db: Engine):
        """AC3: Verify ix_enrichment_index_type_key has correct columns."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("enrichment_index", schema=SCHEMA_NAME)
        type_key_index = next(
            (idx for idx in indexes if idx["name"] == "ix_enrichment_index_type_key"),
            None,
        )
        assert type_key_index is not None
        assert set(type_key_index["column_names"]) == {"lookup_type", "lookup_key"}

    def test_source_index_exists(self, migrated_db: Engine):
        """AC3: Verify ix_enrichment_index_source index exists."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("enrichment_index", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "ix_enrichment_index_source" in index_names, (
            "ix_enrichment_index_source index should exist"
        )

    def test_source_domain_index_exists(self, migrated_db: Engine):
        """AC3: Verify ix_enrichment_index_source_domain index exists."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("enrichment_index", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "ix_enrichment_index_source_domain" in index_names, (
            "ix_enrichment_index_source_domain index should exist"
        )


class TestMigrationIdempotency:
    """Test that migration operations are idempotent (AC5)."""

    def test_upgrade_twice_no_error(self, ephemeral_db: Engine):
        """AC5: Running upgrade twice should not fail."""
        url = ephemeral_db.url.render_as_string(hide_password=False)
        # First upgrade
        migration_runner.upgrade(url, MIGRATION_REVISION)
        # Second upgrade should be no-op (idempotent)
        migration_runner.upgrade(url, MIGRATION_REVISION)

        # Verify table still exists
        inspector = inspect(ephemeral_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "enrichment_index" in tables

        # Cleanup (fixture handles teardown)


class TestMigrationReversibility:
    """Test that downgrade removes objects created by the migration."""

    def test_downgrade_removes_table(self, ephemeral_db: Engine):
        """Upgrade then downgrade should remove enrichment_index table."""
        url = ephemeral_db.url.render_as_string(hide_password=False)
        migration_runner.upgrade(url, MIGRATION_REVISION)
        _validate_test_database(url)
        migration_runner.downgrade(url, DOWN_REVISION)

        inspector = inspect(ephemeral_db)
        tables = set(inspector.get_table_names(schema=SCHEMA_NAME))
        assert "enrichment_index" not in tables

        # Re-upgrade to ensure reversibility and idempotency
        migration_runner.upgrade(url, MIGRATION_REVISION)
        inspector = inspect(ephemeral_db)  # refresh inspector cache after DDL
        tables = set(inspector.get_table_names(schema=SCHEMA_NAME))
        assert "enrichment_index" in tables

        # Final cleanup (fixture will handle teardown)

    def test_downgrade_removes_indexes(self, ephemeral_db: Engine):
        """Downgrade should remove all enrichment_index indexes."""
        url = ephemeral_db.url.render_as_string(hide_password=False)
        migration_runner.upgrade(url, MIGRATION_REVISION)
        _validate_test_database(url)
        migration_runner.downgrade(url, DOWN_REVISION)

        # Check indexes are gone (table doesn't exist, so no indexes)
        with ephemeral_db.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = :schema
                    AND indexname LIKE 'ix_enrichment_index%'
                    """
                ),
                {"schema": SCHEMA_NAME},
            )
            indexes = [row[0] for row in result]
            assert len(indexes) == 0, "All enrichment_index indexes should be removed"


class TestEnrichmentIndexDataOperations:
    """Test basic data operations on enrichment_index table."""

    def test_insert_and_select(self, migrated_db: Engine):
        """Verify basic insert and select operations work."""
        with migrated_db.connect() as conn:
            # Insert a test record
            conn.execute(
                text(
                    """
                    INSERT INTO enterprise.enrichment_index
                        (lookup_key, lookup_type, company_id, source)
                    VALUES
                        (:lookup_key, :lookup_type, :company_id, :source)
                    """
                ),
                {
                    "lookup_key": "TEST_KEY",
                    "lookup_type": "plan_code",
                    "company_id": "TEST_COMPANY",
                    "source": "yaml",
                },
            )
            conn.commit()

            # Select the record
            result = conn.execute(
                text(
                    """
                    SELECT lookup_key, lookup_type, company_id, confidence, source,
                           hit_count
                    FROM enterprise.enrichment_index
                    WHERE lookup_key = :lookup_key
                    """
                ),
                {"lookup_key": "TEST_KEY"},
            )
            row = result.fetchone()

            assert row is not None
            assert row[0] == "TEST_KEY"
            assert row[1] == "plan_code"
            assert row[2] == "TEST_COMPANY"
            assert float(row[3]) == 1.00  # Default confidence
            assert row[4] == "yaml"
            assert row[5] == 0  # Default hit_count

            # Cleanup
            conn.execute(
                text("DELETE FROM enterprise.enrichment_index WHERE lookup_key = :key"),
                {"key": "TEST_KEY"},
            )
            conn.commit()

    def test_unique_constraint_violation(self, migrated_db: Engine):
        """Verify unique constraint prevents duplicate (lookup_key, lookup_type)."""
        with migrated_db.connect() as conn:
            # Insert first record
            conn.execute(
                text(
                    """
                    INSERT INTO enterprise.enrichment_index
                        (lookup_key, lookup_type, company_id, source)
                    VALUES
                        (:lookup_key, :lookup_type, :company_id, :source)
                    """
                ),
                {
                    "lookup_key": "UNIQUE_TEST",
                    "lookup_type": "plan_code",
                    "company_id": "COMPANY_1",
                    "source": "yaml",
                },
            )
            conn.commit()

            # Try to insert duplicate - should fail
            with pytest.raises(Exception) as exc_info:
                conn.execute(
                    text(
                        """
                        INSERT INTO enterprise.enrichment_index
                            (lookup_key, lookup_type, company_id, source)
                        VALUES
                            (:lookup_key, :lookup_type, :company_id, :source)
                        """
                    ),
                    {
                        "lookup_key": "UNIQUE_TEST",
                        "lookup_type": "plan_code",
                        "company_id": "COMPANY_2",
                        "source": "eqc_api",
                    },
                )
                conn.commit()

            # Verify it's a unique constraint violation
            assert (
                "unique" in str(exc_info.value).lower()
                or "duplicate" in str(exc_info.value).lower()
            )

            # Cleanup (rollback happened due to exception)
            conn.rollback()
            conn.execute(
                text("DELETE FROM enterprise.enrichment_index WHERE lookup_key = :key"),
                {"key": "UNIQUE_TEST"},
            )
            conn.commit()

    def test_on_conflict_do_update(self, migrated_db: Engine):
        """Verify ON CONFLICT DO UPDATE works correctly."""
        with migrated_db.connect() as conn:
            # Insert first record
            conn.execute(
                text(
                    """
                    INSERT INTO enterprise.enrichment_index
                        (lookup_key, lookup_type, company_id, confidence, source)
                    VALUES
                        (:lookup_key, :lookup_type, :company_id, :confidence, :source)
                    """
                ),
                {
                    "lookup_key": "CONFLICT_TEST",
                    "lookup_type": "plan_code",
                    "company_id": "COMPANY_1",
                    "confidence": 0.80,
                    "source": "domain_learning",
                },
            )
            conn.commit()

            # Upsert with higher confidence
            conn.execute(
                text(
                    """
                    INSERT INTO enterprise.enrichment_index
                        (lookup_key, lookup_type, company_id, confidence, source)
                    VALUES
                        (:lookup_key, :lookup_type, :company_id, :confidence, :source)
                    ON CONFLICT (lookup_key, lookup_type) DO UPDATE SET
                        confidence = GREATEST(
                            enterprise.enrichment_index.confidence,
                            EXCLUDED.confidence
                        ),
                        hit_count = enterprise.enrichment_index.hit_count + 1,
                        updated_at = NOW()
                    """
                ),
                {
                    "lookup_key": "CONFLICT_TEST",
                    "lookup_type": "plan_code",
                    "company_id": "COMPANY_2",
                    "confidence": 0.95,
                    "source": "eqc_api",
                },
            )
            conn.commit()

            # Verify confidence was updated to higher value
            result = conn.execute(
                text(
                    """
                    SELECT confidence, hit_count
                    FROM enterprise.enrichment_index
                    WHERE lookup_key = :lookup_key
                    """
                ),
                {"lookup_key": "CONFLICT_TEST"},
            )
            row = result.fetchone()
            assert float(row[0]) == 0.95  # Higher confidence
            assert row[1] == 1  # hit_count incremented

            # Cleanup
            conn.execute(
                text("DELETE FROM enterprise.enrichment_index WHERE lookup_key = :key"),
                {"key": "CONFLICT_TEST"},
            )
            conn.commit()
