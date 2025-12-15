"""Integration tests for Enterprise Schema migration (Stories 6.1, 6.2-P5, 6.2-P7).

Tests verify:
- AC1: Schema creation is idempotent
- AC2: base_info table structure (37+ legacy columns + new columns)
- AC3: business_info table structure with normalized types
- AC4: biz_label table structure with FK constraints
- AC5: company_mapping table structure with constraints
- AC6: enrichment_requests table with partial unique index
- AC7: Migration reversibility (upgrade/downgrade)
- AC8: company_master table does NOT exist (removed in 6.2-P7)
- AC9: Indexes for performance optimization
- AC10: Smoke tests for table/index existence

These tests require a PostgreSQL database connection.
Skip if DATABASE_URL is not configured or points to SQLite.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from work_data_hub.config import get_settings
from work_data_hub.io.schema import migration_runner


SCHEMA_NAME = "enterprise"
MIGRATION_REVISION = "20251206_000001"
DOWN_REVISION = "20251129_000001"

_DB_RESET_FLAG = "WDH_ALLOW_DB_RESET_FOR_TESTS"
_DB_RESET_ANY_DB_FLAG = "WDH_ALLOW_DB_RESET_ANY_DB"


def _allow_destructive_db_reset(engine: Engine) -> tuple[bool, str]:
    """Return (allowed, reason) for destructive DB reset tests.

    This test calls `alembic downgrade base`, which is intentionally destructive.
    """
    if os.getenv(_DB_RESET_FLAG, "").strip().lower() not in {"1", "true", "yes"}:
        return (
            False,
            f"Destructive reset disabled; set {_DB_RESET_FLAG}=1 to enable (runs `alembic downgrade base`).",
        )

    db_name = (engine.url.database or "").lower()
    if "test" not in db_name and os.getenv(_DB_RESET_ANY_DB_FLAG, "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        return (
            False,
            f"Refusing to reset non-test database '{db_name}'. Rename DB to include 'test' or set {_DB_RESET_ANY_DB_FLAG}=1.",
        )

    return True, ""


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

    def test_base_info_table_exists(self, migrated_db: Engine):
        """AC2: Verify base_info table exists with all expected columns."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "base_info" in tables, "base_info table should exist"

        columns = {
            c["name"]
            for c in inspector.get_columns("base_info", schema=SCHEMA_NAME)
        }

        # Key canonical columns (should exist and be used)
        canonical_columns = {
            "company_id",
            "search_key_word",
            "unite_code",
            "companyFullName",  # Note: quoted identifier in PG
            "raw_data",
            "raw_business_info",
            "raw_biz_label",
            "api_fetched_at",
            "updated_at",
        }

        # Legacy columns from archive_base_info
        legacy_columns = {
            "name", "name_display", "symbol", "rank_score", "country",
            "company_en_name", "smdb_code", "is_hk", "coname", "is_list",
            "company_nature", "_score", "type", "registeredStatus",
            "organization_code", "le_rep", "reg_cap", "is_pa_relatedparty",
            "province", "est_date", "company_short_name", "id", "is_debt",
            "registered_status", "cocode", "default_score", "company_former_name",
            "is_rank_list", "trade_register_code", "companyId", "is_normal",
            "company_full_name",
        }

        expected_columns = canonical_columns | legacy_columns
        assert expected_columns.issubset(columns), (
            f"base_info missing columns: {expected_columns - columns}"
        )

    def test_base_info_primary_key(self, migrated_db: Engine):
        """AC2: Verify base_info has company_id as primary key."""
        inspector = inspect(migrated_db)
        pk = inspector.get_pk_constraint("base_info", schema=SCHEMA_NAME)
        assert pk["constrained_columns"] == ["company_id"], (
            "base_info PK should be company_id"
        )

    def test_base_info_indexes(self, migrated_db: Engine):
        """AC9: Verify base_info has performance indexes."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("base_info", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]

        expected_indexes = [
            "idx_base_info_unite_code",
            "idx_base_info_search_key",
            "idx_base_info_api_fetched",
        ]

        for idx_name in expected_indexes:
            assert idx_name in index_names, f"Index {idx_name} should exist on base_info"

    def test_business_info_table_exists(self, migrated_db: Engine):
        """AC3: Verify business_info table exists with normalized field types."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "business_info" in tables, "business_info table should exist"

        columns = inspector.get_columns("business_info", schema=SCHEMA_NAME)
        column_types = {c["name"]: c["type"].__class__.__name__ for c in columns}

        # Check normalized types
        assert column_types.get("registered_date") == "DATE", (
            "registered_date should be DATE type"
        )
        assert column_types.get("registered_capital") == "NUMERIC", (
            "registered_capital should be NUMERIC type"
        )
        assert column_types.get("start_date") == "DATE", (
            "start_date should be DATE type"
        )
        assert column_types.get("end_date") == "DATE", (
            "end_date should be DATE type"
        )
        assert column_types.get("colleagues_num") == "INTEGER", (
            "colleagues_num should be INTEGER type (fixed typo)"
        )
        assert column_types.get("actual_capital") == "NUMERIC", (
            "actual_capital should be NUMERIC type"
        )

    def test_business_info_foreign_key(self, migrated_db: Engine):
        """AC3: Verify business_info has FK to base_info."""
        inspector = inspect(migrated_db)
        fk_constraints = inspector.get_foreign_keys("business_info", schema=SCHEMA_NAME)

        has_base_info_fk = any(
            fk["constrained_columns"] == ["company_id"]
            and fk["referred_table"] == "base_info"
            and fk["referred_columns"] == ["company_id"]
            for fk in fk_constraints
        )

        assert has_base_info_fk, (
            "business_info should have FK to base_info(company_id)"
        )

    def test_biz_label_table_exists(self, migrated_db: Engine):
        """AC4: Verify biz_label table exists with proper structure."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "biz_label" in tables, "biz_label table should exist"

        columns = {
            c["name"]
            for c in inspector.get_columns("biz_label", schema=SCHEMA_NAME)
        }

        expected_columns = {
            "id", "company_id", "type", "lv1_name", "lv2_name",
            "lv3_name", "lv4_name", "created_at", "updated_at"
        }

        assert expected_columns.issubset(columns), (
            f"biz_label missing columns: {expected_columns - columns}"
        )

    def test_biz_label_foreign_key(self, migrated_db: Engine):
        """AC4: Verify biz_label has FK to base_info."""
        inspector = inspect(migrated_db)
        fk_constraints = inspector.get_foreign_keys("biz_label", schema=SCHEMA_NAME)

        has_base_info_fk = any(
            fk["constrained_columns"] == ["company_id"]
            and fk["referred_table"] == "base_info"
            and fk["referred_columns"] == ["company_id"]
            for fk in fk_constraints
        )

        assert has_base_info_fk, (
            "biz_label should have FK to base_info(company_id)"
        )

    def test_biz_label_indexes(self, migrated_db: Engine):
        """AC9: Verify biz_label has performance indexes."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("biz_label", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]

        assert "idx_biz_label_company_id" in index_names, (
            "idx_biz_label_company_id index should exist"
        )
        assert "idx_biz_label_hierarchy" in index_names, (
            "idx_biz_label_hierarchy composite index should exist"
        )

    def test_company_master_not_exists(self, migrated_db: Engine):
        """AC8: Verify company_master table does NOT exist (removed in 6.2-P7)."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "company_master" not in tables, (
            "company_master table should NOT exist (removed in 6.2-P7)"
        )

    def test_company_mapping_table_exists(self, migrated_db: Engine):
        """AC5: Verify company_mapping table exists with correct columns."""
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
        """AC5: Verify (alias_name, match_type) unique constraint."""
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
        """AC5: Verify idx_company_mapping_lookup index exists."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("company_mapping", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "idx_company_mapping_lookup" in index_names, (
            "idx_company_mapping_lookup index should exist"
        )

    def test_enrichment_requests_table_exists(self, migrated_db: Engine):
        """AC6: Verify enrichment_requests table exists with correct columns."""
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
        """AC6: Verify idx_enrichment_requests_status index exists."""
        inspector = inspect(migrated_db)
        indexes = inspector.get_indexes("enrichment_requests", schema=SCHEMA_NAME)
        index_names = [idx["name"] for idx in indexes]
        assert "idx_enrichment_requests_status" in index_names, (
            "idx_enrichment_requests_status index should exist"
        )

    def test_enrichment_requests_partial_unique_index(self, migrated_db: Engine):
        """AC6: Verify partial unique index on normalized_name for pending/processing."""
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
        """AC7/AC10: Upgrade then downgrade should remove tables/indexes."""
        url = db_engine.url.render_as_string(hide_password=False)
        migration_runner.upgrade(url, MIGRATION_REVISION)
        migration_runner.downgrade(url, DOWN_REVISION)

        inspector = inspect(db_engine)
        tables = set(inspector.get_table_names(schema=SCHEMA_NAME))

        # All new tables should be removed
        assert "base_info" not in tables
        assert "business_info" not in tables
        assert "biz_label" not in tables
        assert "company_mapping" not in tables
        assert "enrichment_requests" not in tables
        # company_master was already removed, so shouldn't exist either

        # Re-upgrade to ensure reversibility and idempotency
        migration_runner.upgrade(url, MIGRATION_REVISION)


class TestPipelineIndependence:
    """Test that existing pipelines don't depend on new tables (AC11)."""

    def test_no_import_dependency(self):
        """AC11: Core pipeline modules should not import enterprise tables."""
        # Import core pipeline modules - they should work without enterprise schema
        from work_data_hub.infrastructure.transforms import Pipeline, MappingStep
        from work_data_hub.infrastructure.enrichment.company_id_resolver import (
            CompanyIdResolver,
        )

        # These imports should succeed without database connection
        assert Pipeline is not None
        assert MappingStep is not None
        assert CompanyIdResolver is not None


class TestFreshDatabaseMigration:
    """Test migration works on fresh database (critical for 6.2-P7)."""

    def test_fresh_database_upgrade(self, db_engine: Engine):
        """AC10: Migration should work on fresh database from scratch."""
        allowed, reason = _allow_destructive_db_reset(db_engine)
        if not allowed:
            pytest.skip(reason)

        url = db_engine.url.render_as_string(hide_password=False)

        # Start from a clean state
        migration_runner.downgrade(url, "base")

        # Upgrade to head
        migration_runner.upgrade(url, "head")

        # Verify all expected tables exist
        inspector = inspect(db_engine)
        tables = set(inspector.get_table_names(schema=SCHEMA_NAME))

        expected_tables = {
            "base_info",
            "business_info",
            "biz_label",
            "company_mapping",
            "enrichment_requests",
        }

        assert expected_tables.issubset(tables), (
            f"Missing tables after fresh upgrade: {expected_tables - tables}"
        )

        # company_master should NOT exist
        assert "company_master" not in tables, (
            "company_master should not exist after fresh upgrade"
        )
