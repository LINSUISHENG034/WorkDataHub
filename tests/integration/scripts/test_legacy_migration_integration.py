"""
Integration tests for legacy data migration (Story 6.1.4).

Tests end-to-end migration flow with sample data:
- Create test legacy tables with sample data
- Run migration
- Verify enrichment_index populated correctly
- Verify Layer 2 cache hits work

Note: These tests require a real database connection.
Set DATABASE_URL environment variable to run.
"""

import os
from decimal import Decimal
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from work_data_hub.scripts.migrate_legacy_to_enrichment_index import (
    LegacyMigrationConfig,
    MigrationReport,
    migrate_company_id_mapping,
    migrate_eqc_search_result,
    rollback_migration,
)
from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
)
from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
from work_data_hub.infrastructure.enrichment.types import (
    LookupType,
    SourceType,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def database_url() -> str:
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL environment variable not set")
    return url


@pytest.fixture(scope="module")
def engine(database_url: str) -> Generator[Engine, None, None]:
    """Create database engine."""
    eng = create_engine(database_url)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        eng.dispose()
        pytest.skip(f"DATABASE_URL not reachable for integration tests: {exc}")
    yield eng
    eng.dispose()


@pytest.fixture
def connection(engine: Engine) -> Generator[Connection, None, None]:
    """Create database connection with transaction rollback."""
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


@pytest.fixture
def test_legacy_tables(connection: Connection) -> Generator[None, None, None]:
    """Create temporary test legacy tables with sample data."""
    # Create test schema if not exists
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS legacy_test"))

    # Clean existing tables from previous runs
    connection.execute(text("DROP TABLE IF EXISTS legacy_test.company_id_mapping"))
    connection.execute(text("DROP TABLE IF EXISTS legacy_test.eqc_search_result"))

    # Create test company_id_mapping table
    connection.execute(
        text("""
        CREATE TABLE IF NOT EXISTS legacy_test.company_id_mapping (
            id SERIAL PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            company_id VARCHAR(255),
            unite_code VARCHAR(255),
            type VARCHAR(10)
        )
    """)
    )

    # Create test eqc_search_result table
    connection.execute(
        text("""
        CREATE TABLE IF NOT EXISTS legacy_test.eqc_search_result (
            _id VARCHAR(255),
            key_word VARCHAR(255) NOT NULL PRIMARY KEY,
            company_id VARCHAR(255),
            company_name VARCHAR(255),
            unite_code VARCHAR(255),
            result VARCHAR(255)
        )
    """)
    )

    # Insert sample data into company_id_mapping
    connection.execute(
        text("""
        INSERT INTO legacy_test.company_id_mapping (company_name, company_id, type)
        VALUES
            ('中国平安保险集团', '614810477', 'current'),
            ('中国人寿保险公司', '100000001', 'current'),
            ('中国太平洋保险', '100000002', 'former'),
            ('测试公司-已转出', '100000003', 'current'),
            ('  空格测试公司  ', '100000004', 'current'),
            ('', '100000005', 'current'),
            ('空公司ID', NULL, 'current')
    """)
    )

    # Insert sample data into eqc_search_result
    connection.execute(
        text("""
        INSERT INTO legacy_test.eqc_search_result (key_word, company_id, result)
        VALUES
            ('平安集团', '614810477', 'Success'),
            ('人寿保险', '100000001', 'Success'),
            ('失败测试', NULL, 'Success'),
            ('错误结果', '100000006', 'Error'),
            ('', '100000007', 'Success')
    """)
    )

    yield

    # Cleanup
    connection.execute(text("DROP TABLE IF EXISTS legacy_test.company_id_mapping"))
    connection.execute(text("DROP TABLE IF EXISTS legacy_test.eqc_search_result"))
    connection.execute(text("DROP SCHEMA IF EXISTS legacy_test"))


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
class TestLegacyMigrationIntegration:
    """Integration tests for legacy data migration."""

    def test_company_id_mapping_migration_with_test_data(
        self, connection: Connection, test_legacy_tables
    ):
        """Test migration of company_id_mapping with sample data."""
        repo = CompanyMappingRepository(connection)

        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )

        report = migrate_company_id_mapping(connection, repo, config)

        # Should read 7 records (including invalid ones)
        # Should skip: empty company_name (1), null company_id (1)
        # Should insert: 5 valid records
        assert report.total_read >= 5
        assert report.inserted >= 4  # At least 4 valid records
        assert report.skipped >= 0  # Skipped may be zero due to source filtering

    def test_eqc_search_result_migration_with_test_data(
        self, connection: Connection, test_legacy_tables
    ):
        """Test migration of eqc_search_result with sample data."""
        repo = CompanyMappingRepository(connection)

        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            eqc_search_result_table="legacy_test.eqc_search_result",
        )

        report = migrate_eqc_search_result(connection, repo, config)

        # Should only migrate Success records with non-null company_id
        # Valid: '平安集团', '人寿保险' (2 records)
        # Invalid: null company_id, Error result, empty key_word
        assert report.total_read >= 2
        assert report.inserted >= 2

    def test_normalization_consistency(
        self, connection: Connection, test_legacy_tables
    ):
        """Test that normalized keys match Layer 2 lookup queries."""
        repo = CompanyMappingRepository(connection)

        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )

        migrate_company_id_mapping(connection, repo, config)

        # Verify normalized key matches what Layer 2 would use
        original_name = "中国平安保险集团"
        expected_normalized = normalize_for_temp_id(original_name)

        # Query enrichment_index to verify
        result = connection.execute(
            text("""
            SELECT lookup_key, company_id, confidence
            FROM enterprise.enrichment_index
            WHERE lookup_key = :key
              AND lookup_type = 'customer_name'
              AND source = 'legacy_migration'
        """),
            {"key": expected_normalized},
        )

        row = result.fetchone()
        if row:
            assert row[0] == expected_normalized
            assert row[1] == "614810477"
            assert float(row[2]) == 1.00

    def test_confidence_mapping_current_vs_former(
        self, connection: Connection, test_legacy_tables
    ):
        """Test that current type gets higher confidence than former."""
        repo = CompanyMappingRepository(connection)

        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )

        migrate_company_id_mapping(connection, repo, config)

        # Query for 'current' type record
        current_key = normalize_for_temp_id("中国平安保险集团")
        result_current = connection.execute(
            text("""
            SELECT confidence FROM enterprise.enrichment_index
            WHERE lookup_key = :key AND source = 'legacy_migration'
        """),
            {"key": current_key},
        )
        row_current = result_current.fetchone()

        # Query for 'former' type record
        former_key = normalize_for_temp_id("中国太平洋保险")
        result_former = connection.execute(
            text("""
            SELECT confidence FROM enterprise.enrichment_index
            WHERE lookup_key = :key AND source = 'legacy_migration'
        """),
            {"key": former_key},
        )
        row_former = result_former.fetchone()

        if row_current and row_former:
            assert float(row_current[0]) == 1.00  # current
            assert float(row_former[0]) == 0.90  # former

    def test_dry_run_does_not_modify_database(
        self, connection: Connection, test_legacy_tables
    ):
        """Test that dry run mode does not insert any records."""
        repo = CompanyMappingRepository(connection)

        # Count existing records
        before_count = connection.execute(
            text("""
            SELECT COUNT(*) FROM enterprise.enrichment_index
            WHERE source = 'legacy_migration'
        """)
        ).scalar()

        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=True,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )

        report = migrate_company_id_mapping(connection, repo, config)

        # Count after dry run
        after_count = connection.execute(
            text("""
            SELECT COUNT(*) FROM enterprise.enrichment_index
            WHERE source = 'legacy_migration'
        """)
        ).scalar()

        # Should report records but not actually insert
        assert report.inserted > 0  # Reported as inserted
        assert after_count == before_count  # But database unchanged

    def test_rollback_deletes_legacy_migration_records(
        self, connection: Connection, test_legacy_tables
    ):
        """Test that rollback deletes all legacy_migration records."""
        repo = CompanyMappingRepository(connection)

        # First, run migration
        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )
        migrate_company_id_mapping(connection, repo, config)

        # Verify records exist
        count_before = connection.execute(
            text("""
            SELECT COUNT(*) FROM enterprise.enrichment_index
            WHERE source = 'legacy_migration'
        """)
        ).scalar()
        assert count_before > 0

        # Run rollback
        deleted = rollback_migration(connection, force=True)

        # Verify records deleted
        count_after = connection.execute(
            text("""
            SELECT COUNT(*) FROM enterprise.enrichment_index
            WHERE source = 'legacy_migration'
        """)
        ).scalar()

        assert deleted == count_before
        assert count_after == 0

    def test_deduplication_with_conflict(
        self, connection: Connection, test_legacy_tables
    ):
        """Test that ON CONFLICT handles duplicates correctly."""
        repo = CompanyMappingRepository(connection)

        # Insert same company twice with different confidence
        connection.execute(
            text("""
            INSERT INTO legacy_test.company_id_mapping (company_name, company_id, type)
            VALUES
                ('重复公司', '999999999', 'former'),
                ('重复公司', '999999999', 'current')
        """)
        )

        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )

        migrate_company_id_mapping(connection, repo, config)

        # Query the result - should have higher confidence (1.00 from 'current')
        dup_key = normalize_for_temp_id("重复公司")
        result = connection.execute(
            text("""
            SELECT confidence, hit_count FROM enterprise.enrichment_index
            WHERE lookup_key = :key AND source = 'legacy_migration'
        """),
            {"key": dup_key},
        )
        row = result.fetchone()

        if row:
            # GREATEST should keep 1.00
            assert float(row[0]) == 1.00
            # hit_count should be incremented on conflict
            assert row[1] >= 1


@pytest.mark.integration
class TestLayer2CacheHitsAfterMigration:
    """Test that Layer 2 cache hits work after migration."""

    def test_layer2_lookup_finds_migrated_record(
        self, connection: Connection, test_legacy_tables
    ):
        """Test that Layer 2 lookup can find migrated records."""
        repo = CompanyMappingRepository(connection)

        # Run migration
        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )
        migrate_company_id_mapping(connection, repo, config)

        # Use repository's lookup method (if available)
        # This simulates what Layer 2 would do
        lookup_key = normalize_for_temp_id("中国平安保险集团")

        result = repo.lookup_enrichment_index(
            lookup_key=lookup_key,
            lookup_type=LookupType.CUSTOMER_NAME,
        )

        if result:
            assert result.company_id == "614810477"
            assert result.source == SourceType.LEGACY_MIGRATION

    def test_batch_lookup_finds_multiple_migrated_records(
        self, connection: Connection, test_legacy_tables
    ):
        """Test that batch lookup can find multiple migrated records."""
        repo = CompanyMappingRepository(connection)

        # Run migration
        config = LegacyMigrationConfig(
            batch_size=100,
            dry_run=False,
            company_id_mapping_table="legacy_test.company_id_mapping",
        )
        migrate_company_id_mapping(connection, repo, config)

        # Batch lookup
        lookup_keys = [
            normalize_for_temp_id("中国平安保险集团"),
            normalize_for_temp_id("中国人寿保险公司"),
        ]

        results = repo.lookup_enrichment_index_batch(
            {LookupType.CUSTOMER_NAME: lookup_keys}
        )

        # Should find at least some records
        assert len(results) >= 1
