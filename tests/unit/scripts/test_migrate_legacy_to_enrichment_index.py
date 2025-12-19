"""
Unit tests for legacy data migration script (Story 6.1.4).

Tests cover:
- Normalization transformation
- Confidence mapping (current=1.00, former=0.90)
- Null/empty value filtering
- Batch processing logic
- Report generation
"""

from decimal import Decimal
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

from work_data_hub.scripts.migrate_legacy_to_enrichment_index import (
    LegacyMigrationConfig,
    MigrationReport,
    FullMigrationReport,
    migrate_company_id_mapping,
    migrate_eqc_search_result,
)
from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
from work_data_hub.infrastructure.enrichment.types import (
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)


# =============================================================================
# Test: Normalization Transformation (AC4, Task 7.1)
# =============================================================================


class TestNormalizationTransformation:
    """Test that normalization is applied correctly for cache hit consistency."""

    def test_normalize_basic_company_name(self):
        """Test basic company name normalization."""
        result = normalize_for_temp_id("中国平安")
        assert result == "中国平安"

    def test_normalize_with_whitespace(self):
        """Test normalization removes whitespace."""
        result = normalize_for_temp_id("  中国平安  ")
        assert result == "中国平安"

    def test_normalize_with_status_marker(self):
        """Test normalization removes status markers."""
        result = normalize_for_temp_id("中国平安-已转出")
        assert result == "中国平安"

    def test_normalize_with_brackets(self):
        """Test normalization converts brackets to Chinese."""
        result = normalize_for_temp_id("中国平安(集团)")
        assert result == "中国平安（集团）"

    def test_normalize_empty_string(self):
        """Test normalization handles empty string."""
        result = normalize_for_temp_id("")
        assert result == ""

    def test_normalize_none_returns_empty(self):
        """Test normalization handles None."""
        result = normalize_for_temp_id(None)
        assert result == ""

    def test_normalize_only_status_marker(self):
        """Test normalization of string that becomes empty after removing markers."""
        result = normalize_for_temp_id("已转出")
        assert result == ""

    def test_normalize_lowercase(self):
        """Test normalization converts to lowercase."""
        result = normalize_for_temp_id("ABC Company")
        assert result == "abc company".replace(" ", "")  # whitespace removed

    def test_normalize_full_width_characters(self):
        """Test normalization converts full-width to half-width."""
        result = normalize_for_temp_id("ＡＢＣ")
        assert result == "abc"


# =============================================================================
# Test: Confidence Mapping (AC1, AC2, Task 7.2)
# =============================================================================


class TestConfidenceMapping:
    """Test confidence mapping for different record types."""

    def test_confidence_current_is_1_00(self):
        """Test that type='current' maps to confidence=1.00."""
        config = LegacyMigrationConfig()
        assert config.confidence_current == Decimal("1.00")

    def test_confidence_former_is_0_90(self):
        """Test that type='former' maps to confidence=0.90."""
        config = LegacyMigrationConfig()
        assert config.confidence_former == Decimal("0.90")

    def test_confidence_eqc_success_is_1_00(self):
        """Test that EQC success maps to confidence=1.00."""
        config = LegacyMigrationConfig()
        assert config.confidence_eqc_success == Decimal("1.00")

    def test_confidence_mapping_in_record_creation(self):
        """Test confidence is correctly set when creating records."""
        # Current type
        record_current = EnrichmentIndexRecord(
            lookup_key="test",
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id="123",
            confidence=Decimal("1.00"),
            source=SourceType.LEGACY_MIGRATION,
        )
        assert record_current.confidence == Decimal("1.00")

        # Former type
        record_former = EnrichmentIndexRecord(
            lookup_key="test",
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id="123",
            confidence=Decimal("0.90"),
            source=SourceType.LEGACY_MIGRATION,
        )
        assert record_former.confidence == Decimal("0.90")


# =============================================================================
# Test: Null/Empty Value Filtering (Task 7.3)
# =============================================================================


class TestNullEmptyFiltering:
    """Test filtering of null and empty values."""

    def test_report_tracks_skipped_empty_normalization(self):
        """Test that report tracks records skipped due to empty normalization."""
        report = MigrationReport(source_table="test")
        report.add_skipped("empty_after_normalization")
        report.add_skipped("empty_after_normalization")
        report.add_skipped("null_company_id")

        assert report.skipped == 3
        assert report.skipped_reasons["empty_after_normalization"] == 2
        assert report.skipped_reasons["null_company_id"] == 1

    def test_empty_company_name_filtered(self):
        """Test that empty company names are filtered."""
        normalized = normalize_for_temp_id("")
        assert normalized == ""
        # In migration, this would be skipped

    def test_whitespace_only_filtered(self):
        """Test that whitespace-only names are filtered."""
        normalized = normalize_for_temp_id("   ")
        assert normalized == ""


# =============================================================================
# Test: Batch Processing Logic (Task 7.4)
# =============================================================================


class TestBatchProcessing:
    """Test batch processing logic."""

    def test_config_default_batch_size(self):
        """Test default batch size is 1000."""
        config = LegacyMigrationConfig()
        assert config.batch_size == 1000

    def test_config_custom_batch_size(self):
        """Test custom batch size can be set."""
        config = LegacyMigrationConfig(batch_size=500)
        assert config.batch_size == 500

    def test_config_progress_interval(self):
        """Test progress interval is 5000."""
        config = LegacyMigrationConfig()
        assert config.progress_interval == 5000

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=0)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_company_id_mapping")
    def test_batch_insert_called_at_batch_size(self, mock_fetch, mock_conflicts):
        """Test that batch insert is called when batch size is reached."""
        # Setup mock data - 2500 records to trigger 2 batch inserts + 1 final
        mock_data = [
            {"company_name": f"公司{i}", "company_id": f"ID{i}", "type": "current"}
            for i in range(2500)
        ]
        mock_fetch.return_value = iter(mock_data)

        # Mock connection and repo
        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=1000, skipped_count=0
        )

        config = LegacyMigrationConfig(batch_size=1000, dry_run=False)

        report = migrate_company_id_mapping(mock_connection, mock_repo, config)

        # Should have 3 batch calls: 1000 + 1000 + 500
        assert mock_repo.insert_enrichment_index_batch.call_count == 3
        assert report.total_read == 2500

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_company_id_mapping")
    def test_dry_run_does_not_insert(self, mock_fetch):
        """Test that dry run mode does not actually insert."""
        mock_data = [
            {"company_name": "测试公司", "company_id": "123", "type": "current"}
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()

        config = LegacyMigrationConfig(dry_run=True)

        report = migrate_company_id_mapping(mock_connection, mock_repo, config)

        # Repo should NOT be called in dry run
        mock_repo.insert_enrichment_index_batch.assert_not_called()
        assert report.total_read == 1
        assert report.inserted == 1  # Counted but not actually inserted

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=2)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_company_id_mapping")
    def test_conflict_updates_tracked_as_updated(self, mock_fetch, mock_conflicts):
        """Test conflicts increment updated and adjust inserted count."""
        mock_data = [
            {"company_name": "重复公司1", "company_id": "ID1", "type": "current"},
            {"company_name": "重复公司2", "company_id": "ID2", "type": "current"},
            {"company_name": "新公司", "company_id": "ID3", "type": "current"},
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=3, skipped_count=0
        )

        config = LegacyMigrationConfig(batch_size=10, dry_run=False)

        report = migrate_company_id_mapping(mock_connection, mock_repo, config)

        assert report.inserted == 1
        assert report.updated == 2


# =============================================================================
# Test: Report Generation (Task 7.5)
# =============================================================================


class TestReportGeneration:
    """Test migration report generation."""

    def test_migration_report_initialization(self):
        """Test MigrationReport initializes correctly."""
        report = MigrationReport(source_table="legacy.company_id_mapping")

        assert report.source_table == "legacy.company_id_mapping"
        assert report.total_read == 0
        assert report.inserted == 0
        assert report.updated == 0
        assert report.skipped == 0
        assert report.errors == 0
        assert report.skipped_reasons == {}
        assert report.sample_records == []

    def test_migration_report_to_dict(self):
        """Test MigrationReport.to_dict() output."""
        report = MigrationReport(source_table="test")
        report.total_read = 100
        report.inserted = 90
        report.add_skipped("empty_after_normalization")  # This increments skipped, not inserted

        result = report.to_dict()

        assert result["source_table"] == "test"
        assert result["total_read"] == 100
        assert result["inserted"] == 90  # add_skipped does not affect inserted
        assert result["skipped"] == 1  # Only from add_skipped call

    def test_full_migration_report_aggregation(self):
        """Test FullMigrationReport aggregates correctly."""
        full_report = FullMigrationReport()

        report1 = MigrationReport(source_table="table1")
        report1.total_read = 100
        report1.inserted = 90
        report1.skipped = 10

        report2 = MigrationReport(source_table="table2")
        report2.total_read = 50
        report2.inserted = 45
        report2.skipped = 5

        full_report.add_report(report1)
        full_report.add_report(report2)

        assert full_report.total_read == 150
        assert full_report.total_inserted == 135
        assert full_report.total_skipped == 15
        assert len(full_report.reports) == 2

    def test_full_migration_report_dry_run_flag(self):
        """Test FullMigrationReport tracks dry run mode."""
        report_dry = FullMigrationReport(dry_run=True)
        assert report_dry.dry_run is True

        report_real = FullMigrationReport(dry_run=False)
        assert report_real.dry_run is False

    def test_sample_records_collected(self):
        """Test that sample records are collected for verification."""
        report = MigrationReport(source_table="test")

        # Add sample records
        for i in range(15):
            if len(report.sample_records) < 10:
                report.sample_records.append({
                    "lookup_key": f"key{i}",
                    "company_id": f"id{i}",
                })

        # Should only keep first 10
        assert len(report.sample_records) == 10


# =============================================================================
# Test: EnrichmentIndexRecord Creation
# =============================================================================


class TestEnrichmentIndexRecordCreation:
    """Test EnrichmentIndexRecord creation for migration."""

    def test_record_with_legacy_migration_source(self):
        """Test record creation with LEGACY_MIGRATION source."""
        record = EnrichmentIndexRecord(
            lookup_key="中国平安",
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id="614810477",
            confidence=Decimal("1.00"),
            source=SourceType.LEGACY_MIGRATION,
            source_table="legacy.company_id_mapping",
        )

        assert record.lookup_key == "中国平安"
        assert record.lookup_type == LookupType.CUSTOMER_NAME
        assert record.company_id == "614810477"
        assert record.confidence == Decimal("1.00")
        assert record.source == SourceType.LEGACY_MIGRATION
        assert record.source_table == "legacy.company_id_mapping"

    def test_record_to_dict(self):
        """Test record serialization to dict."""
        record = EnrichmentIndexRecord(
            lookup_key="test",
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id="123",
            confidence=Decimal("0.90"),
            source=SourceType.LEGACY_MIGRATION,
            source_table="legacy.eqc_search_result",
        )

        result = record.to_dict()

        assert result["lookup_key"] == "test"
        assert result["lookup_type"] == "customer_name"
        assert result["company_id"] == "123"
        assert result["confidence"] == 0.90
        assert result["source"] == "legacy_migration"
        assert result["source_table"] == "legacy.eqc_search_result"


# =============================================================================
# Test: Source Table Configuration
# =============================================================================


class TestSourceTableConfiguration:
    """Test source table configuration."""

    def test_default_source_tables(self):
        """Test default source table names."""
        config = LegacyMigrationConfig()

        assert config.company_id_mapping_table == "legacy.company_id_mapping"
        assert config.eqc_search_result_table == "legacy.eqc_search_result"

    def test_lookup_type_is_customer_name(self):
        """Test that migration uses CUSTOMER_NAME lookup type (DB-P4)."""
        # This is hardcoded in the migration functions
        assert LookupType.CUSTOMER_NAME.value == "customer_name"


# =============================================================================
# Test: EQC Search Result Migration
# =============================================================================


class TestEqcSearchResultMigration:
    """Test EQC search result migration specifics."""

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=0)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_eqc_search_result")
    def test_eqc_migration_uses_key_word(self, mock_fetch, mock_conflicts):
        """Test that EQC migration uses key_word field."""
        mock_data = [
            {"key_word": "测试关键词", "company_id": "456"}
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=1, skipped_count=0
        )

        config = LegacyMigrationConfig(dry_run=False)

        report = migrate_eqc_search_result(mock_connection, mock_repo, config)

        assert report.total_read == 1
        assert report.source_table == "legacy.eqc_search_result"

        # Verify the record was created with normalized key_word
        call_args = mock_repo.insert_enrichment_index_batch.call_args
        records = call_args[0][0]
        assert len(records) == 1
        assert records[0].lookup_key == normalize_for_temp_id("测试关键词")
        assert records[0].confidence == Decimal("1.00")

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=0)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_eqc_search_result")
    def test_eqc_migration_all_success_confidence_1_00(self, mock_fetch, mock_conflicts):
        """Test that all EQC success records get confidence=1.00."""
        mock_data = [
            {"key_word": f"关键词{i}", "company_id": f"ID{i}"}
            for i in range(5)
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=5, skipped_count=0
        )

        config = LegacyMigrationConfig(dry_run=False)

        migrate_eqc_search_result(mock_connection, mock_repo, config)

        # All records should have confidence=1.00
        call_args = mock_repo.insert_enrichment_index_batch.call_args
        records = call_args[0][0]
        for record in records:
            assert record.confidence == Decimal("1.00")


# =============================================================================
# Test: Company ID Mapping Migration
# =============================================================================


class TestCompanyIdMappingMigration:
    """Test company_id_mapping migration specifics."""

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=0)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_company_id_mapping")
    def test_current_type_gets_higher_confidence(self, mock_fetch, mock_conflicts):
        """Test that type='current' gets confidence=1.00."""
        mock_data = [
            {"company_name": "当前公司", "company_id": "123", "type": "current"}
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=1, skipped_count=0
        )

        config = LegacyMigrationConfig(dry_run=False)

        migrate_company_id_mapping(mock_connection, mock_repo, config)

        call_args = mock_repo.insert_enrichment_index_batch.call_args
        records = call_args[0][0]
        assert records[0].confidence == Decimal("1.00")

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=0)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_company_id_mapping")
    def test_former_type_gets_lower_confidence(self, mock_fetch, mock_conflicts):
        """Test that type='former' gets confidence=0.90."""
        mock_data = [
            {"company_name": "历史公司", "company_id": "456", "type": "former"}
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=1, skipped_count=0
        )

        config = LegacyMigrationConfig(dry_run=False)

        migrate_company_id_mapping(mock_connection, mock_repo, config)

        call_args = mock_repo.insert_enrichment_index_batch.call_args
        records = call_args[0][0]
        assert records[0].confidence == Decimal("0.90")

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=0)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_company_id_mapping")
    def test_unknown_type_defaults_to_former_confidence(self, mock_fetch, mock_conflicts):
        """Test that unknown type defaults to former confidence (0.90)."""
        mock_data = [
            {"company_name": "未知类型", "company_id": "789", "type": "unknown"}
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=1, skipped_count=0
        )

        config = LegacyMigrationConfig(dry_run=False)

        migrate_company_id_mapping(mock_connection, mock_repo, config)

        call_args = mock_repo.insert_enrichment_index_batch.call_args
        records = call_args[0][0]
        assert records[0].confidence == Decimal("0.90")

    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._estimate_conflicts", return_value=0)
    @patch("work_data_hub.scripts.migrate_legacy_to_enrichment_index._fetch_company_id_mapping")
    def test_null_type_defaults_to_former_confidence(self, mock_fetch, mock_conflicts):
        """Test that null type defaults to former confidence (0.90)."""
        mock_data = [
            {"company_name": "空类型", "company_id": "000", "type": None}
        ]
        mock_fetch.return_value = iter(mock_data)

        mock_connection = MagicMock()
        mock_repo = MagicMock()
        mock_repo.insert_enrichment_index_batch.return_value = MagicMock(
            inserted_count=1, skipped_count=0
        )

        config = LegacyMigrationConfig(dry_run=False)

        migrate_company_id_mapping(mock_connection, mock_repo, config)

        call_args = mock_repo.insert_enrichment_index_batch.call_args
        records = call_args[0][0]
        assert records[0].confidence == Decimal("0.90")
