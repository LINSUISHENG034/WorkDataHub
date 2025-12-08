"""
Unit tests for DomainLearningService (Story 6.1.3).

Tests cover:
- AC1: DomainLearningService creation and configuration
- AC2: Multi-type learning (all 5 lookup types)
- AC3: Confidence levels per lookup type
- AC4: Source metadata (domain_learning source)
- AC5: Minimum records threshold
- AC8: Normalization consistency
- AC9: Idempotent operation
- AC10: Unit test coverage >90%
- AC11: Config safeguards (enabled_domains, per-lookup gating)
- AC12: Column validation
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from work_data_hub.infrastructure.enrichment.domain_learning_service import (
    DomainLearningService,
)
from work_data_hub.infrastructure.enrichment.mapping_repository import InsertBatchResult
from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
from work_data_hub.infrastructure.enrichment.types import (
    DomainLearningConfig,
    DomainLearningResult,
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)


@pytest.fixture
def mock_repository():
    """Create a mock CompanyMappingRepository."""
    repo = MagicMock()
    repo.insert_enrichment_index_batch.return_value = InsertBatchResult(
        inserted_count=5, skipped_count=0
    )
    return repo


@pytest.fixture
def default_config():
    """Create default DomainLearningConfig."""
    return DomainLearningConfig()


@pytest.fixture
def service(mock_repository, default_config):
    """Create DomainLearningService with mock repository."""
    return DomainLearningService(repository=mock_repository, config=default_config)


@pytest.fixture
def sample_dataframe():
    """Create sample DataFrame with valid data (>= 10 records for threshold)."""
    return pd.DataFrame(
        {
            "计划代码": ["FP0001", "FP0002", "FP0003", "FP0001", "FP0002"] * 2,
            "年金账户名": ["账户A", "账户B", "账户C", "账户A", "账户B"] * 2,
            "年金账户号": ["ACC001", "ACC002", "ACC003", "ACC001", "ACC002"] * 2,
            "客户名称": ["中国平安", "中国人寿", "太平洋保险", "中国平安", "中国人寿"] * 2,
            "company_id": [
                "614810477",
                "614810478",
                "614810479",
                "614810477",
                "614810478",
            ] * 2,
        }
    )


class TestDomainLearningServiceInit:
    """Tests for DomainLearningService initialization."""

    def test_init_with_default_config(self, mock_repository):
        """Test initialization with default configuration."""
        service = DomainLearningService(repository=mock_repository)

        assert service.repository == mock_repository
        assert service.config is not None
        assert "annuity_performance" in service.config.enabled_domains
        assert "annuity_income" in service.config.enabled_domains

    def test_init_with_custom_config(self, mock_repository):
        """Test initialization with custom configuration."""
        config = DomainLearningConfig(
            enabled_domains=["custom_domain"],
            min_records_for_learning=5,
        )
        service = DomainLearningService(repository=mock_repository, config=config)

        assert service.config.enabled_domains == ["custom_domain"]
        assert service.config.min_records_for_learning == 5


class TestDomainLearningConfig:
    """Tests for DomainLearningConfig dataclass."""

    def test_default_enabled_domains(self):
        """Test default enabled domains."""
        config = DomainLearningConfig()
        assert config.enabled_domains == ["annuity_performance", "annuity_income"]

    def test_default_confidence_levels(self):
        """Test default confidence levels per lookup type (AC3)."""
        config = DomainLearningConfig()
        assert config.confidence_levels["plan_code"] == 0.95
        assert config.confidence_levels["account_name"] == 0.90
        assert config.confidence_levels["account_number"] == 0.95
        assert config.confidence_levels["customer_name"] == 0.85
        assert config.confidence_levels["plan_customer"] == 0.90

    def test_default_enabled_lookup_types(self):
        """Test all lookup types enabled by default."""
        config = DomainLearningConfig()
        assert config.enabled_lookup_types["plan_code"] is True
        assert config.enabled_lookup_types["account_name"] is True
        assert config.enabled_lookup_types["account_number"] is True
        assert config.enabled_lookup_types["customer_name"] is True
        assert config.enabled_lookup_types["plan_customer"] is True

    def test_default_thresholds(self):
        """Test default threshold values."""
        config = DomainLearningConfig()
        assert config.min_records_for_learning == 10
        assert config.min_confidence_for_cache == 0.80

    def test_column_mappings(self):
        """Test column mappings for domains."""
        config = DomainLearningConfig()
        assert "annuity_performance" in config.column_mappings
        assert config.column_mappings["annuity_performance"]["plan_code"] == "计划代码"
        assert (
            config.column_mappings["annuity_performance"]["customer_name"] == "客户名称"
        )


class TestDomainLearningResult:
    """Tests for DomainLearningResult dataclass."""

    def test_to_dict(self):
        """Test to_dict method."""
        result = DomainLearningResult(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            total_records=100,
            valid_records=90,
            extracted={"plan_code": 10, "account_name": 8},
            inserted=15,
            updated=3,
            skipped=5,
        )

        d = result.to_dict()
        assert d["domain_name"] == "annuity_performance"
        assert d["total_records"] == 100
        assert d["valid_records"] == 90
        assert d["extracted_total"] == 18
        assert d["inserted"] == 15
        assert d["updated"] == 3
        assert d["skipped"] == 5


class TestLearnFromDomain:
    """Tests for learn_from_domain method."""

    def test_domain_disabled_skips_learning(self, mock_repository):
        """Test that disabled domain skips learning (AC11)."""
        config = DomainLearningConfig(enabled_domains=["other_domain"])
        service = DomainLearningService(repository=mock_repository, config=config)

        df = pd.DataFrame({"company_id": ["123"]})
        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        assert result.skipped_by_reason.get("domain_disabled") == 1
        mock_repository.insert_enrichment_index_batch.assert_not_called()

    def test_missing_column_mapping_skips_learning(self, mock_repository):
        """Test that missing column mapping skips learning."""
        config = DomainLearningConfig(
            enabled_domains=["unknown_domain"], column_mappings={}
        )
        service = DomainLearningService(repository=mock_repository, config=config)

        df = pd.DataFrame({"company_id": ["123"]})
        result = service.learn_from_domain(
            domain_name="unknown_domain",
            table_name="unknown_table",
            df=df,
        )

        assert result.skipped_by_reason.get("no_column_mapping") == 1
        mock_repository.insert_enrichment_index_batch.assert_not_called()

    def test_missing_columns_skips_learning(self, mock_repository, default_config):
        """Test that missing required columns skips learning (AC12)."""
        service = DomainLearningService(
            repository=mock_repository, config=default_config
        )

        # DataFrame missing required columns
        df = pd.DataFrame({"other_column": ["value"]})
        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        assert result.skipped_by_reason.get("missing_columns") == 1
        mock_repository.insert_enrichment_index_batch.assert_not_called()

    def test_below_threshold_skips_learning(self, mock_repository):
        """Test that below threshold skips learning (AC5)."""
        config = DomainLearningConfig(min_records_for_learning=100)
        service = DomainLearningService(repository=mock_repository, config=config)

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"],
                "年金账户名": ["账户A"],
                "年金账户号": ["ACC001"],
                "客户名称": ["中国平安"],
                "company_id": ["614810477"],
            }
        )
        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        assert result.skipped_by_reason.get("below_threshold") == 1
        mock_repository.insert_enrichment_index_batch.assert_not_called()

    def test_successful_learning(self, service, mock_repository, sample_dataframe):
        """Test successful learning from DataFrame."""
        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=sample_dataframe,
        )

        assert result.total_records == 10
        assert result.valid_records == 10
        assert result.inserted == 5  # Mock returns 5
        mock_repository.insert_enrichment_index_batch.assert_called_once()

    def test_extracts_all_lookup_types(self, service, mock_repository, sample_dataframe):
        """Test extraction of all 5 lookup types (AC2)."""
        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=sample_dataframe,
        )

        # Get the records passed to insert_enrichment_index_batch
        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        # Check all lookup types are present
        lookup_types = {r.lookup_type for r in records}
        assert LookupType.PLAN_CODE in lookup_types
        assert LookupType.ACCOUNT_NAME in lookup_types
        assert LookupType.ACCOUNT_NUMBER in lookup_types
        assert LookupType.CUSTOMER_NAME in lookup_types
        assert LookupType.PLAN_CUSTOMER in lookup_types


class TestTempIdFiltering:
    """Tests for temporary ID filtering."""

    def test_temp_ids_excluded(self, service, mock_repository):
        """Test that temporary IDs (IN_*) are excluded (AC1)."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001", "FP0002", "FP0003"],
                "年金账户名": ["账户A", "账户B", "账户C"],
                "年金账户号": ["ACC001", "ACC002", "ACC003"],
                "客户名称": ["中国平安", "中国人寿", "太平洋保险"],
                "company_id": ["614810477", "IN_ABCD1234", "614810479"],
            }
        )

        # Need at least 10 records for default threshold
        df = pd.concat([df] * 4, ignore_index=True)

        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        # 12 total, 4 are temp IDs (IN_*)
        assert result.valid_records == 8
        assert result.skipped_by_reason.get("temp_id") == 4


class TestNullValueHandling:
    """Tests for null value handling."""

    def test_null_company_ids_skipped(self, service, mock_repository):
        """Test that null company_ids are skipped."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001", "FP0002", "FP0003"],
                "年金账户名": ["账户A", "账户B", "账户C"],
                "年金账户号": ["ACC001", "ACC002", "ACC003"],
                "客户名称": ["中国平安", "中国人寿", "太平洋保险"],
                "company_id": ["614810477", None, "614810479"],
            }
        )

        # Need at least 10 records
        df = pd.concat([df] * 4, ignore_index=True)

        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        assert result.skipped_by_reason.get("null_company_id") == 4


class TestNormalization:
    """Tests for normalization consistency (AC8)."""

    def test_customer_name_normalized(self, service, mock_repository):
        """Test that customer_name is normalized correctly."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安 "] * 10,  # trailing space
                "company_id": ["614810477"] * 10,
            }
        )

        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        # Find customer_name record
        customer_records = [
            r for r in records if r.lookup_type == LookupType.CUSTOMER_NAME
        ]
        assert len(customer_records) == 1

        # Should be normalized (no trailing space)
        expected_key = normalize_for_temp_id("中国平安 ")
        assert customer_records[0].lookup_key == expected_key

    def test_plan_customer_normalized(self, service, mock_repository):
        """Test that plan_customer key is normalized correctly."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安-已转出"] * 10,  # with status marker
                "company_id": ["614810477"] * 10,
            }
        )

        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        # Find plan_customer record
        plan_customer_records = [
            r for r in records if r.lookup_type == LookupType.PLAN_CUSTOMER
        ]
        assert len(plan_customer_records) == 1

        # Should be normalized
        normalized_name = normalize_for_temp_id("中国平安-已转出")
        expected_key = f"FP0001|{normalized_name}"
        assert plan_customer_records[0].lookup_key == expected_key


class TestConfidenceLevels:
    """Tests for confidence levels (AC3)."""

    def test_correct_confidence_per_lookup_type(self, service, mock_repository):
        """Test that correct confidence is applied per lookup type."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安"] * 10,
                "company_id": ["614810477"] * 10,
            }
        )

        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        # Check confidence per type
        for record in records:
            if record.lookup_type == LookupType.PLAN_CODE:
                assert record.confidence == Decimal("0.95")
            elif record.lookup_type == LookupType.ACCOUNT_NAME:
                assert record.confidence == Decimal("0.90")
            elif record.lookup_type == LookupType.ACCOUNT_NUMBER:
                assert record.confidence == Decimal("0.95")
            elif record.lookup_type == LookupType.CUSTOMER_NAME:
                assert record.confidence == Decimal("0.85")
            elif record.lookup_type == LookupType.PLAN_CUSTOMER:
                assert record.confidence == Decimal("0.90")


class TestSourceMetadata:
    """Tests for source metadata (AC4)."""

    def test_source_is_domain_learning(self, service, mock_repository):
        """Test that source is set to domain_learning."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安"] * 10,
                "company_id": ["614810477"] * 10,
            }
        )

        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        for record in records:
            assert record.source == SourceType.DOMAIN_LEARNING
            assert record.source_domain == "annuity_performance"
            assert record.source_table == "annuity_performance_new"


class TestLookupTypeGating:
    """Tests for per-lookup type enable/disable (AC11)."""

    def test_disabled_lookup_type_skipped(self, mock_repository):
        """Test that disabled lookup types are skipped."""
        config = DomainLearningConfig(
            enabled_lookup_types={
                "plan_code": True,
                "account_name": False,  # Disabled
                "account_number": True,
                "customer_name": False,  # Disabled
                "plan_customer": True,
            }
        )
        service = DomainLearningService(repository=mock_repository, config=config)

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安"] * 10,
                "company_id": ["614810477"] * 10,
            }
        )

        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        lookup_types = {r.lookup_type for r in records}
        assert LookupType.PLAN_CODE in lookup_types
        assert LookupType.ACCOUNT_NAME not in lookup_types  # Disabled
        assert LookupType.ACCOUNT_NUMBER in lookup_types
        assert LookupType.CUSTOMER_NAME not in lookup_types  # Disabled
        assert LookupType.PLAN_CUSTOMER in lookup_types


class TestMinConfidenceForCache:
    """Tests for min_confidence_for_cache threshold (AC11)."""

    def test_low_confidence_skipped(self, mock_repository):
        """Test that lookup types below min_confidence_for_cache are skipped."""
        config = DomainLearningConfig(
            min_confidence_for_cache=0.92,  # Higher than customer_name (0.85)
            confidence_levels={
                "plan_code": 0.95,
                "account_name": 0.90,
                "account_number": 0.95,
                "customer_name": 0.85,  # Below threshold
                "plan_customer": 0.90,
            },
        )
        service = DomainLearningService(repository=mock_repository, config=config)

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安"] * 10,
                "company_id": ["614810477"] * 10,
            }
        )

        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        lookup_types = {r.lookup_type for r in records}
        assert LookupType.PLAN_CODE in lookup_types
        assert LookupType.ACCOUNT_NUMBER in lookup_types
        # Below min_confidence_for_cache
        assert LookupType.CUSTOMER_NAME not in lookup_types
        assert LookupType.ACCOUNT_NAME not in lookup_types
        assert LookupType.PLAN_CUSTOMER not in lookup_types


class TestIdempotency:
    """Tests for idempotent operation (AC9)."""

    def test_multiple_runs_consistent(self, service, mock_repository):
        """Test that multiple runs produce consistent results."""
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安"] * 10,
                "company_id": ["614810477"] * 10,
            }
        )

        # Run twice
        result1 = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )
        result2 = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        # Both should extract same number of records
        assert result1.extracted == result2.extracted


class TestStatisticsTracking:
    """Tests for statistics tracking (AC7)."""

    def test_statistics_accurate(self, mock_repository):
        """Test that statistics are accurately tracked."""
        mock_repository.insert_enrichment_index_batch.return_value = InsertBatchResult(
            inserted_count=10, skipped_count=5  # 5 updates
        )

        config = DomainLearningConfig()
        service = DomainLearningService(repository=mock_repository, config=config)

        df = pd.DataFrame(
            {
                "计划代码": ["FP0001", "FP0002"] * 6,
                "年金账户名": ["账户A", "账户B"] * 6,
                "年金账户号": ["ACC001", "ACC002"] * 6,
                "客户名称": ["中国平安", "中国人寿"] * 6,
                "company_id": ["614810477", "614810478"] * 6,
            }
        )

        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        assert result.total_records == 12
        assert result.valid_records == 12
        assert result.inserted == 10
        assert result.updated == 5
        assert "plan_code" in result.extracted
        assert "account_name" in result.extracted
        assert "account_number" in result.extracted
        assert "customer_name" in result.extracted
        assert "plan_customer" in result.extracted


class TestEmptyDataFrame:
    """Tests for empty DataFrame handling."""

    def test_empty_dataframe(self, service, mock_repository):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame(
            columns=["计划代码", "年金账户名", "年金账户号", "客户名称", "company_id"]
        )

        result = service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        assert result.total_records == 0
        assert result.skipped_by_reason.get("below_threshold") == 0
        mock_repository.insert_enrichment_index_batch.assert_not_called()


class TestDuplicateHandling:
    """Tests for duplicate record handling."""

    def test_duplicates_deduplicated(self, service, mock_repository):
        """Test that duplicate mappings are deduplicated before insert."""
        # Same plan_code -> company_id mapping repeated
        df = pd.DataFrame(
            {
                "计划代码": ["FP0001"] * 10,
                "年金账户名": ["账户A"] * 10,
                "年金账户号": ["ACC001"] * 10,
                "客户名称": ["中国平安"] * 10,
                "company_id": ["614810477"] * 10,
            }
        )

        service.learn_from_domain(
            domain_name="annuity_performance",
            table_name="annuity_performance_new",
            df=df,
        )

        call_args = mock_repository.insert_enrichment_index_batch.call_args
        records = call_args[0][0]

        # Should only have 5 unique records (one per lookup type)
        assert len(records) == 5
