"""Integration tests for Enterprise Schema migration (Story 6.1).

Tests verify:
- AC1: Schema creation is idempotent
- AC2: company_master table structure
- AC3: company_mapping table structure with constraints
- AC4: enrichment_requests table with partial unique index
- AC5: Migration reversibility (upgrade/downgrade)
- AC6: Smoke tests for table/index existence

These tests require a PostgreSQL database connection.
Skip if DATABASE_URL is not configured or points to SQLite.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from work_data_hub.config import get_settings
from work_data_hub.io.schema import migration_runner


SCHEMA_NAME = "enterprise"
MIGRATION_REVISION = "20251206_000001"
DOWN_REVISION = "20251129_000001"


def get_test_engine() -> Engine | None:
    """Get database engine for testing, or None if not available."""
    try:
        settings = get_settings()
        url = settings.get_database_connection_string()
        # Skip SQLite - enterprise schema requires PostgreSQL
        if "sqlite" in url.lower():
            return None
        return create_engine(url)
    except Exception:
        return None


@pytest.fixture(scope="module")
def db_engine():
    """Provide database engine, skip if not available."""
    engine = get_test_engine()
    if engine is None:
        pytest.skip("PostgreSQL database not available for migration tests")
    return engine


@pytest.fixture
def migrated_db(db_engine: Engine):
    """Upgrade to the target revision for the test, then downgrade afterward."""
    url = db_engine.url.render_as_string(hide_password=False)
    migration_runner.upgrade(url, MIGRATION_REVISION)
    try:
        yield db_engine
    finally:
        migration_runner.downgrade(url, DOWN_REVISION)


class TestEnterpriseSchemaExists:
    """Test that enterprise schema and tables exist after migration."""

    def test_schema_exists(self, migrated_db: Engine):
        """AC1: Verify enterprise schema exists."""
        with migrated_db.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name = :schema"
                ),
                {"schema": SCHEMA_NAME},
            )
            schemas = [row[0] for row in result]
            assert SCHEMA_NAME in schemas, f"Schema '{SCHEMA_NAME}' should exist"

    def test_company_master_table_exists(self, migrated_db: Engine):
        """AC2: Verify company_master table exists with correct columns."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "company_master" in tables, "company_master table should exist"

        columns = {
            c["name"]
            for c in inspector.get_columns("company_master", schema=SCHEMA_NAME)
        }
        expected_columns = {
            "company_id",
            "official_name",
            "unified_credit_code",
            "aliases",
            "source",
            "created_at",
            "updated_at",
        }
        assert expected_columns.issubset(columns), (
            f"company_master missing columns: {expected_columns - columns}"
        )

    def test_company_master_primary_key(self, migrated_db: Engine):
        """AC2: Verify company_master has company_id as primary key."""
        inspector = inspect(migrated_db)
        pk = inspector.get_pk_constraint("company_master", schema=SCHEMA_NAME)
        assert pk["constrained_columns"] == ["company_id"], (
            "company_master PK should be company_id"
        )

    def test_company_master_unique_constraint(self, migrated_db: Engine):
        """AC2: Verify unified_credit_code has unique constraint."""
        inspector = inspect(migrated_db)
        unique_constraints = inspector.get_unique_constraints(
            "company_master", schema=SCHEMA_NAME
        )
        ucc_columns = [uc["column_names"] for uc in unique_constraints]
        # unified_credit_code should be unique (either via constraint or unique index)
        indexes = inspector.get_indexes("company_master", schema=SCHEMA_NAME)
        unique_indexes = [idx for idx in indexes if idx.get("unique")]
        ucc_in_unique = any(
            "unified_credit_code" in (uc.get("column_names", []) or [])
            for uc in unique_constraints
        ) or any(
            "unified_credit_code" in idx.get("column_names", [])
            for idx in unique_indexes
        )
        assert ucc_in_unique, "unified_credit_code should have unique constraint"

    def test_company_mapping_table_exists(self, migrated_db: Engine):
        """AC3: Verify company_mapping table exists with correct columns."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "company_mapping" in tables, "company_mapping table should exist"

        columns = {
            c["name"]
            for c in inspector.get_columns("company_mapping", schema=SCHEMA_NAME)
        }
        expected_columns = {
            "id",
            "alias_name",
            "canonical_id",
            "match_type",
            "priority",
            "source",
            "created_at",
            "updated_at",
        }
        assert expected_columns.issubset(columns), (
            f"company_mapping missing columns: {expected_columns - columns}"
        )

    def test_company_mapping_unique_constraint(self, migrated_db: Engine):
        """AC3: Verify (alias_name, match_type) unique constraint."""
        inspector = inspect(migrated_db)
        unique_constraints = inspector.get_unique_constraints(
            "company_mapping", schema=SCHEMA_NAME
        )
        has_alias_type_unique = any(
            set(uc["column_names"]) == {"alias_name", "match_type"}
            for uc in unique_constraints
        )
        assert has_alias_type_unique, (
            "company_mapping should have UNIQUE(alias_name, match_type)"
        )

    def test_company_mapping_lookup_index(self, migrated_db: Engine):
        """AC3: Verify idx_company_mapping_lookup index exists."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("company_mapping", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "idx_company_mapping_lookup" in index_names, (
            "idx_company_mapping_lookup index should exist"
        )

    def test_company_mapping_priority_check(self, migrated_db: Engine):
        """AC3: Verify priority CHECK constraint (1-5)."""
        inspector = inspect(migrated_db)
        check_constraints = inspector.get_check_constraints(
            "company_mapping", schema=SCHEMA_NAME
        )
        has_priority_check = any(
            "priority" in (c.get("sqltext", "") or "") for c in check_constraints
        )
        assert has_priority_check, (
            "company_mapping should have CHECK constraint on priority"
        )

    def test_company_mapping_match_type_check(self, migrated_db: Engine):
        """AC3: Verify match_type CHECK constraint for allowed values."""
        inspector = inspect(migrated_db)
        check_constraints = inspector.get_check_constraints(
            "company_mapping", schema=SCHEMA_NAME
        )
        has_match_type_check = any(
            "match_type" in (c.get("sqltext", "") or "")
            and "account_name" in (c.get("sqltext", "") or "")
            for c in check_constraints
        )
        assert has_match_type_check, (
            "company_mapping should restrict match_type to allowed values"
        )

    def test_enrichment_requests_table_exists(self, migrated_db: Engine):
        """AC4: Verify enrichment_requests table exists with correct columns."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "enrichment_requests" in tables, "enrichment_requests table should exist"

        columns = {
            c["name"]
            for c in inspector.get_columns("enrichment_requests", schema=SCHEMA_NAME)
        }
        expected_columns = {
            "id",
            "raw_name",
            "normalized_name",
            "temp_id",
            "status",
            "attempts",
            "last_error",
            "resolved_company_id",
            "created_at",
            "updated_at",
        }
        assert expected_columns.issubset(columns), (
            f"enrichment_requests missing columns: {expected_columns - columns}"
        )

    def test_enrichment_requests_status_index(self, migrated_db: Engine):
        """AC4: Verify idx_enrichment_requests_status index exists."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("enrichment_requests", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "idx_enrichment_requests_status" in index_names, (
            "idx_enrichment_requests_status index should exist"
        )

    def test_enrichment_requests_partial_unique_index(self, migrated_db: Engine):
        """AC4: Verify partial unique index on normalized_name for pending/processing."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("enrichment_requests", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "idx_enrichment_requests_normalized" in index_names, (
            "idx_enrichment_requests_normalized partial unique index should exist"
        )


class TestMigrationIdempotency:
    """Test that migration operations are idempotent."""

    def test_schema_creation_idempotent(self, migrated_db: Engine):
        """AC1: Creating schema twice should not fail."""
        with migrated_db.connect() as conn:
            # This should not raise even if schema exists
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
            conn.commit()


class TestMigrationReversibility:
    """Test that downgrade removes objects created by the migration."""

    def test_downgrade_removes_objects(self, db_engine: Engine):
        """AC5/AC6: Upgrade then downgrade should remove tables/indexes."""
        url = db_engine.url.render_as_string(hide_password=False)
        migration_runner.upgrade(url, MIGRATION_REVISION)
        migration_runner.downgrade(url, DOWN_REVISION)

        inspector = inspect(db_engine)
        tables = set(inspector.get_table_names(schema=SCHEMA_NAME))
        assert "company_master" not in tables
        assert "company_mapping" not in tables
        assert "enrichment_requests" not in tables

        # Re-upgrade to ensure reversibility and idempotency
        migration_runner.upgrade(url, MIGRATION_REVISION)


class TestPipelineIndependence:
    """Test that existing pipelines don't depend on new tables (AC7)."""

    def test_no_import_dependency(self):
        """AC7: Core pipeline modules should not import enterprise tables."""
        # Import core pipeline modules - they should work without enterprise schema
        from work_data_hub.infrastructure.transforms import Pipeline, MappingStep
        from work_data_hub.infrastructure.enrichment.company_id_resolver import (
            CompanyIdResolver,
        )

        # These imports should succeed without database connection
        assert Pipeline is not None
        assert MappingStep is not None
        assert CompanyIdResolver is not None
