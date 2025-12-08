"""
Integration tests for DomainLearningService (Story 6.1.3).

Tests cover:
- AC6: Pipeline integration (learn_from_domain callable)
- AC9: Idempotent operation with real database
- End-to-end learning from DataFrame to enrichment_index
- Layer 2 cache hits after learning
"""

import os
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from work_data_hub.infrastructure.enrichment.domain_learning_service import (
    DomainLearningService,
)
from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
)
from work_data_hub.infrastructure.enrichment.types import (
    DomainLearningConfig,
    LookupType,
    SourceType,
)


@pytest.fixture(scope="module")
def db_connection():
    """Create database connection for integration tests."""
    db_url = os.environ.get("WDH_DATABASE_URL")
    if not db_url:
        pytest.skip("WDH_DATABASE_URL not set - skipping integration tests")

    engine = create_engine(db_url)
    connection = engine.connect()
    yield connection
    connection.close()
    engine.dispose()


@pytest.fixture
def repository(db_connection):
    """Create CompanyMappingRepository with real connection."""
    return CompanyMappingRepository(db_connection)


@pytest.fixture
def service(repository):
    """Create DomainLearningService with real repository."""
    config = DomainLearningConfig(min_records_for_learning=5)  # Lower for testing
    return DomainLearningService(repository=repository, config=config)


@pytest.fixture
def sample_dataframe():
    """Create sample DataFrame for integration testing."""
    return pd.DataFrame(
        {
            "计划代码": [f"TEST_FP{i:04d}" for i in range(10)],
            "年金账户名": [f"测试账户{i}" for i in range(10)],
            "年金账户号": [f"TEST_ACC{i:04d}" for i in range(10)],
            "客户名称": [f"测试公司{i}" for i in range(10)],
            "company_id": [f"TEST_{i:09d}" for i in range(10)],
        }
    )


@pytest.fixture
def cleanup_test_data(db_connection):
    """Clean up test data after each test."""
    yield
    # Clean up test records
    db_connection.execute(
        text("""
            DELETE FROM enterprise.enrichment_index
            WHERE lookup_key LIKE 'TEST_%'
               OR lookup_key LIKE 'test_%'
               OR company_id LIKE 'TEST_%'
        """)
    )
    db_connection.commit()


class TestDomainLearningIntegration:
    """Integration tests for domain learning with real database."""

    @pytest.mark.integration
    def test_learn_from_domain_end_to_end(
        self, service, sample_dataframe, cleanup_test_data, db_connection
    ):
        """Test end-to-end learning from DataFrame to enrichment_index."""
        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=sample_dataframe,
        )

        # Verify result statistics
        assert result.total_records == 10
        assert result.valid_records == 10
        assert result.inserted > 0

        # Verify records in database
        count_result = db_connection.execute(
            text("""
                SELECT COUNT(*) FROM enterprise.enrichment_index
                WHERE source = 'domain_learning'
                  AND source_domain = 'annuity_performance'
                  AND company_id LIKE 'TEST_%'
            """)
        ).fetchone()

        assert count_result[0] > 0

    @pytest.mark.integration
    def test_idempotent_operation(
        self, service, sample_dataframe, cleanup_test_data, db_connection
    ):
        """Test that multiple runs are idempotent (AC9)."""
        # First run
        result1 = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=sample_dataframe,
        )

        # Second run with same data
        result2 = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=sample_dataframe,
        )

        # Both should extract same number
        assert result1.extracted == result2.extracted

        # Second run should have updates (not new inserts)
        # Note: Due to UPSERT semantics, affected_count includes both
        assert result2.inserted > 0 or result2.updated > 0

    @pytest.mark.integration
    def test_confidence_preserved_on_conflict(
        self, repository, cleanup_test_data, db_connection
    ):
        """Test that higher confidence is preserved on conflict (AC13)."""
        from work_data_hub.infrastructure.enrichment.types import EnrichmentIndexRecord

        # Insert with lower confidence first
        low_conf_record = EnrichmentIndexRecord(
            lookup_key="TEST_CONF_KEY",
            lookup_type=LookupType.PLAN_CODE,
            company_id="TEST_000000001",
            confidence=Decimal("0.80"),
            source=SourceType.DOMAIN_LEARNING,
            source_domain="test_domain",
        )
        repository.insert_enrichment_index_batch([low_conf_record])

        # Insert with higher confidence
        high_conf_record = EnrichmentIndexRecord(
            lookup_key="TEST_CONF_KEY",
            lookup_type=LookupType.PLAN_CODE,
            company_id="TEST_000000001",
            confidence=Decimal("0.95"),
            source=SourceType.DOMAIN_LEARNING,
            source_domain="test_domain",
        )
        repository.insert_enrichment_index_batch([high_conf_record])

        # Verify higher confidence is preserved
        result = db_connection.execute(
            text("""
                SELECT confidence FROM enterprise.enrichment_index
                WHERE lookup_key = 'TEST_CONF_KEY'
                  AND lookup_type = 'plan_code'
            """)
        ).fetchone()

        assert result is not None
        assert float(result[0]) == 0.95

    @pytest.mark.integration
    def test_hit_count_increments_on_conflict(
        self, repository, cleanup_test_data, db_connection
    ):
        """Test that hit_count increments on conflict (AC9)."""
        from work_data_hub.infrastructure.enrichment.types import EnrichmentIndexRecord

        record = EnrichmentIndexRecord(
            lookup_key="TEST_HIT_KEY",
            lookup_type=LookupType.ACCOUNT_NAME,
            company_id="TEST_000000002",
            confidence=Decimal("0.90"),
            source=SourceType.DOMAIN_LEARNING,
            source_domain="test_domain",
        )

        # Insert multiple times
        repository.insert_enrichment_index_batch([record])
        repository.insert_enrichment_index_batch([record])
        repository.insert_enrichment_index_batch([record])

        # Verify hit_count incremented
        result = db_connection.execute(
            text("""
                SELECT hit_count FROM enterprise.enrichment_index
                WHERE lookup_key = 'TEST_HIT_KEY'
                  AND lookup_type = 'account_name'
            """)
        ).fetchone()

        assert result is not None
        assert result[0] >= 2  # At least 2 conflicts


class TestLayerTwoCacheHits:
    """Test that learned mappings result in Layer 2 cache hits."""

    @pytest.mark.integration
    def test_layer2_cache_hit_after_learning(
        self, service, repository, cleanup_test_data, db_connection
    ):
        """Test that Layer 2 lookup finds learned mappings (AC6)."""
        # Create test data
        df = pd.DataFrame(
            {
                "计划代码": ["TEST_CACHE_PLAN"] * 10,
                "年金账户名": ["测试缓存账户"] * 10,
                "年金账户号": ["TEST_CACHE_ACC"] * 10,
                "客户名称": ["测试缓存公司"] * 10,
                "company_id": ["TEST_CACHE_001"] * 10,
            }
        )

        # Learn from data
        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        assert result.inserted > 0

        # Verify lookup works
        lookup_result = repository.lookup_enrichment_index(
            lookup_key="TEST_CACHE_PLAN",
            lookup_type=LookupType.PLAN_CODE,
        )

        assert lookup_result is not None
        assert lookup_result.company_id == "TEST_CACHE_001"
        assert lookup_result.source == SourceType.DOMAIN_LEARNING
