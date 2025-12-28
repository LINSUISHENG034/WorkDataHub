"""Integration tests for Enterprise Schema migration (Stories 6.1, 6.2-P5, 6.2-P7, 7.1-4).

Tests verify:
- AC1: Schema creation is idempotent
- AC2: base_info table structure (37+ legacy columns + new columns)
- AC3: business_info table structure with normalized types
- AC4: biz_label table structure with FK constraints
- AC5: company_mapping table REMOVED (Story 7.1-4 - Zero Legacy)
- AC6: enrichment_requests table with partial unique index
- AC7: Migration reversibility (upgrade/downgrade)
- AC8: company_master table does NOT exist (removed in 6.2-P7)
- AC9: Indexes for performance optimization
- AC10: Smoke tests for table/index existence

These tests use the postgres_db_with_migrations fixture which:
- Creates a temporary test database with "_test_" prefix
- Runs all migrations (including enterprise schema)
- Cleans up automatically after tests complete

Story 7.1-9 Note: Updated to use postgres_db_with_migrations fixture
to avoid production database access issues and simplify test setup.

Story 7.2-4 Note: Skip decorators removed, tests aligned with new
001/002/003 migration chain.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from tests.conftest import (
    _create_ephemeral_database,
    _drop_database,
    _validate_test_database,
)
from work_data_hub.io.schema import migration_runner


SCHEMA_NAME = "enterprise"
MIGRATION_REVISION = "20251228_000001"  # 001_initial_infrastructure
DOWN_REVISION = None  # Base migration has no down_revision


def get_engine_from_dsn(dsn: str) -> Engine:
    """Create SQLAlchemy engine from DSN string."""
    return create_engine(dsn)


@pytest.fixture
def migrated_db(postgres_db_with_migrations: str) -> Engine:
    """
    Use the temporary test database created by postgres_db_with_migrations.

    The fixture has already run all migrations, including the enterprise schema
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
            c["name"] for c in inspector.get_columns("base_info", schema=SCHEMA_NAME)
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
            "name",
            "name_display",
            "symbol",
            "rank_score",
            "country",
            "company_en_name",
            "smdb_code",
            "is_hk",
            "coname",
            "is_list",
            "company_nature",
            "_score",
            "type",
            "registeredStatus",
            "organization_code",
            "le_rep",
            "reg_cap",
            "is_pa_relatedparty",
            "province",
            "est_date",
            "company_short_name",
            "id",
            "is_debt",
            "registered_status",
            "cocode",
            "default_score",
            "company_former_name",
            "is_rank_list",
            "trade_register_code",
            "companyId",
            "is_normal",
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
            assert idx_name in index_names, (
                f"Index {idx_name} should exist on base_info"
            )

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
        assert column_types.get("end_date") == "DATE", "end_date should be DATE type"
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

        assert has_base_info_fk, "business_info should have FK to base_info(company_id)"

    def test_biz_label_table_exists(self, migrated_db: Engine):
        """AC4: Verify biz_label table exists with proper structure."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "biz_label" in tables, "biz_label table should exist"

        columns = {
            c["name"] for c in inspector.get_columns("biz_label", schema=SCHEMA_NAME)
        }

        expected_columns = {
            "id",
            "company_id",
            "type",
            "lv1_name",
            "lv2_name",
            "lv3_name",
            "lv4_name",
            "created_at",
            "updated_at",
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

        assert has_base_info_fk, "biz_label should have FK to base_info(company_id)"

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

    def test_company_mapping_table_does_not_exist(self, migrated_db: Engine):
        """AC5: Verify company_mapping table does NOT exist (removed in Story 7.1-4)."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema=SCHEMA_NAME)
        assert "company_mapping" not in tables, (
            "company_mapping table should NOT exist (Zero Legacy - Story 7.1-4)"
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

    def test_年金客户_table_exists(self, migrated_db: Engine):
        """Verify 年金客户 table exists with correct structure (Story 7.2-2)."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema="mapping")
        assert "年金客户" in tables, "年金客户 table should exist in mapping schema"

        columns = {
            c["name"] for c in inspector.get_columns("年金客户", schema="mapping")
        }

        # Expected 27 columns for 年金客户 table
        expected_columns = {
            "id",
            "客户名称",
            "统一社会信用代码",
            "机构代码",
            "企业类型",
            "联系人",
            "联系电话",
            "注册地址",
            "成立日期",
            "注册资本",
            "经营范围",
            "备注",
            "created_at",
            "updated_at",
            # ... plus 13 more columns for total of 27
        }
        assert len(columns) == 27, f"年金客户 expected 27 columns, got {len(columns)}"
        assert expected_columns.issubset(columns), (
            f"年金客户 missing columns: {expected_columns - columns}"
        )

    def test_产品明细_table_exists(self, migrated_db: Engine):
        """Verify 产品明细 table exists with correct structure and seed data (Story 7.2-2)."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema="mapping")
        assert "产品明细" in tables, "产品明细 table should exist in mapping schema"

        columns = {
            c["name"] for c in inspector.get_columns("产品明细", schema="mapping")
        }

        # Expected 4 columns for 产品明细 table
        expected_columns = {
            "id",
            "产品代码",
            "产品名称",
            "产品线",
        }
        assert columns == expected_columns, (
            f"产品明细 expected columns: {expected_columns}, got: {columns}"
        )

        # Verify seed data (18 rows inserted in 003_seed_static_data)
        with migrated_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM mapping.产品明细"))
            row_count = result.scalar()
            assert row_count == 18, (
                f"产品明细 expected 18 seed data rows, got {row_count}"
            )

    def test_利润指标_table_exists(self, migrated_db: Engine):
        """Verify 利润指标 table exists with correct structure and seed data (Story 7.2-2)."""
        inspector = inspect(migrated_db)
        tables = inspector.get_table_names(schema="mapping")
        assert "利润指标" in tables, "利润指标 table should exist in mapping schema"

        columns = {
            c["name"] for c in inspector.get_columns("利润指标", schema="mapping")
        }

        # Expected 6 columns for 利润指标 table
        expected_columns = {
            "id",
            "指标代码",
            "指标名称",
            "计算方式",
            "单位",
            "说明",
        }
        assert columns == expected_columns, (
            f"利润指标 expected columns: {expected_columns}, got: {columns}"
        )

        # Verify seed data (12 rows inserted in 003_seed_static_data)
        with migrated_db.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM mapping.利润指标"))
            row_count = result.scalar()
            assert row_count == 12, (
                f"利润指标 expected 12 seed data rows, got {row_count}"
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

    def test_downgrade_removes_objects(self, ephemeral_db: Engine):
        """AC7/AC10: Upgrade then downgrade should remove tables/indexes."""
        url = ephemeral_db.url.render_as_string(hide_password=False)
        migration_runner.upgrade(url, MIGRATION_REVISION)
        _validate_test_database(url)  # Safety check: prevent production DB clearing
        migration_runner.downgrade(url, DOWN_REVISION)

        inspector = inspect(ephemeral_db)
        tables = set(inspector.get_table_names(schema=SCHEMA_NAME))

        # All new tables should be removed
        assert "base_info" not in tables
        assert "business_info" not in tables
        assert "biz_label" not in tables
        assert "enrichment_requests" not in tables
        # company_mapping removed in Story 7.1-4 (Zero Legacy)
        # company_master was already removed in 6.2-P7

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

    def test_fresh_database_upgrade(self, ephemeral_db: Engine):
        """AC10: Migration should work on fresh database from scratch."""
        url = ephemeral_db.url.render_as_string(hide_password=False)

        # Upgrade to head (ephemeral_db starts empty)
        migration_runner.upgrade(url, "head")

        # Verify all expected tables exist
        inspector = inspect(ephemeral_db)
        tables = set(inspector.get_table_names(schema=SCHEMA_NAME))

        # Note: company_mapping removed in Story 7.1-4 (Zero Legacy)
        expected_tables = {
            "base_info",
            "business_info",
            "biz_label",
            "enrichment_requests",
        }

        assert expected_tables.issubset(tables), (
            f"Missing tables after fresh upgrade: {expected_tables - tables}"
        )

        # company_master should NOT exist (removed in 6.2-P7)
        assert "company_master" not in tables, (
            "company_master should not exist after fresh upgrade"
        )
        # company_mapping should NOT exist (removed in Story 7.1-4)
        assert "company_mapping" not in tables, (
            "company_mapping should not exist after fresh upgrade (Zero Legacy)"
        )
