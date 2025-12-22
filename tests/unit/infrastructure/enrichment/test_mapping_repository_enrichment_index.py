"""
Unit tests for CompanyMappingRepository enrichment_index methods (Story 6.1.1).

This module tests the database access layer for enrichment_index table using
mocked database connections to ensure fast, isolated unit tests.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
    InsertBatchResult,
)
from work_data_hub.infrastructure.enrichment.types import (
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)


@dataclass
class MockEnrichmentIndexRow:
    """Mock database row for enrichment_index table testing."""

    lookup_key: str
    lookup_type: str
    company_id: str
    confidence: Decimal
    source: str
    source_domain: Optional[str] = None
    source_table: Optional[str] = None
    hit_count: int = 0
    last_hit_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@pytest.fixture
def mock_connection():
    """Create a mock SQLAlchemy connection."""
    return MagicMock()


@pytest.fixture
def repository(mock_connection):
    """Create a CompanyMappingRepository with mock connection."""
    return CompanyMappingRepository(mock_connection)


@pytest.fixture
def sample_enrichment_index_rows():
    """Sample rows returned from enrichment_index lookup query."""
    return [
        MockEnrichmentIndexRow(
            lookup_key="FP0001",
            lookup_type="plan_code",
            company_id="614810477",
            confidence=Decimal("1.00"),
            source="yaml",
            hit_count=5,
        ),
        MockEnrichmentIndexRow(
            lookup_key="账户A",
            lookup_type="account_name",
            company_id="614810477",
            confidence=Decimal("1.00"),
            source="eqc_api",
            hit_count=3,
        ),
        MockEnrichmentIndexRow(
            lookup_key="中国平安",
            lookup_type="customer_name",
            company_id="600866980",
            confidence=Decimal("0.95"),
            source="domain_learning",
            source_domain="annuity_performance",
            hit_count=10,
        ),
    ]


@pytest.fixture
def sample_enrichment_records():
    """Sample EnrichmentIndexRecord objects for insert tests."""
    return [
        EnrichmentIndexRecord(
            lookup_key="FP0001",
            lookup_type=LookupType.PLAN_CODE,
            company_id="614810477",
            source=SourceType.YAML,
        ),
        EnrichmentIndexRecord(
            lookup_key="账户A",
            lookup_type=LookupType.ACCOUNT_NAME,
            company_id="614810477",
            source=SourceType.EQC_API,
        ),
        EnrichmentIndexRecord(
            lookup_key="中国平安",
            lookup_type=LookupType.CUSTOMER_NAME,
            company_id="600866980",
            confidence=Decimal("0.95"),
            source=SourceType.DOMAIN_LEARNING,
            source_domain="annuity_performance",
        ),
    ]


# =============================================================================
# Story 6.1.1: LookupType and SourceType Enum Tests
# =============================================================================


class TestLookupType:
    """Test cases for LookupType enum (Story 6.1.1)."""

    def test_lookup_type_values(self):
        """LookupType has correct values for DB-P1 to DB-P5."""
        assert LookupType.PLAN_CODE.value == "plan_code"
        assert LookupType.ACCOUNT_NAME.value == "account_name"
        assert LookupType.ACCOUNT_NUMBER.value == "account_number"
        assert LookupType.CUSTOMER_NAME.value == "customer_name"
        assert LookupType.PLAN_CUSTOMER.value == "plan_customer"

    def test_lookup_type_from_string(self):
        """LookupType can be created from string value."""
        assert LookupType("plan_code") == LookupType.PLAN_CODE
        assert LookupType("customer_name") == LookupType.CUSTOMER_NAME


class TestSourceType:
    """Test cases for SourceType enum (Story 6.1.1)."""

    def test_source_type_values(self):
        """SourceType has correct values."""
        assert SourceType.YAML.value == "yaml"
        assert SourceType.EQC_API.value == "eqc_api"
        assert SourceType.MANUAL.value == "manual"
        assert SourceType.BACKFLOW.value == "backflow"
        assert SourceType.DOMAIN_LEARNING.value == "domain_learning"
        assert SourceType.LEGACY_MIGRATION.value == "legacy_migration"

    def test_source_type_from_string(self):
        """SourceType can be created from string value."""
        assert SourceType("yaml") == SourceType.YAML
        assert SourceType("domain_learning") == SourceType.DOMAIN_LEARNING


# =============================================================================
# Story 6.1.1: EnrichmentIndexRecord Tests
# =============================================================================


class TestEnrichmentIndexRecord:
    """Test cases for EnrichmentIndexRecord dataclass (Story 6.1.1)."""

    def test_record_creation_minimal(self):
        """EnrichmentIndexRecord can be created with minimal fields."""
        record = EnrichmentIndexRecord(
            lookup_key="FP0001",
            lookup_type=LookupType.PLAN_CODE,
            company_id="614810477",
            source=SourceType.YAML,
        )
        assert record.lookup_key == "FP0001"
        assert record.lookup_type == LookupType.PLAN_CODE
        assert record.company_id == "614810477"
        assert record.source == SourceType.YAML
        assert record.confidence == Decimal("1.00")  # Default
        assert record.hit_count == 0  # Default
        assert record.source_domain is None
        assert record.source_table is None

    def test_record_creation_full(self):
        """EnrichmentIndexRecord can be created with all fields."""
        now = datetime.now()
        record = EnrichmentIndexRecord(
            lookup_key="FP0001|中国平安",
            lookup_type=LookupType.PLAN_CUSTOMER,
            company_id="614810477",
            confidence=Decimal("0.90"),
            source=SourceType.DOMAIN_LEARNING,
            source_domain="annuity_performance",
            source_table="gold_annuity_performance",
            hit_count=5,
            last_hit_at=now,
            created_at=now,
            updated_at=now,
        )
        assert record.lookup_key == "FP0001|中国平安"
        assert record.lookup_type == LookupType.PLAN_CUSTOMER
        assert record.confidence == Decimal("0.90")
        assert record.source_domain == "annuity_performance"
        assert record.source_table == "gold_annuity_performance"
        assert record.hit_count == 5

    def test_record_to_dict(self):
        """EnrichmentIndexRecord.to_dict() returns correct dictionary."""
        record = EnrichmentIndexRecord(
            lookup_key="FP0001",
            lookup_type=LookupType.PLAN_CODE,
            company_id="614810477",
            confidence=Decimal("0.95"),
            source=SourceType.EQC_API,
            source_domain="test_domain",
        )
        d = record.to_dict()

        assert d["lookup_key"] == "FP0001"
        assert d["lookup_type"] == "plan_code"  # String value
        assert d["company_id"] == "614810477"
        assert d["confidence"] == 0.95  # Float
        assert d["source"] == "eqc_api"  # String value
        assert d["source_domain"] == "test_domain"
        assert d["hit_count"] == 0

    def test_record_from_dict(self):
        """EnrichmentIndexRecord.from_dict() creates correct record."""
        data = {
            "lookup_key": "FP0001",
            "lookup_type": "plan_code",
            "company_id": "614810477",
            "confidence": 0.95,
            "source": "eqc_api",
            "source_domain": "test_domain",
            "source_table": None,
            "hit_count": 10,
            "last_hit_at": None,
            "created_at": None,
            "updated_at": None,
        }
        record = EnrichmentIndexRecord.from_dict(data)

        assert record.lookup_key == "FP0001"
        assert record.lookup_type == LookupType.PLAN_CODE
        assert record.company_id == "614810477"
        assert record.confidence == Decimal("0.95")
        assert record.source == SourceType.EQC_API
        assert record.source_domain == "test_domain"
        assert record.hit_count == 10


# =============================================================================
# Story 6.1.1: lookup_enrichment_index Tests (AC4.1)
# =============================================================================


class TestLookupEnrichmentIndex:
    """Test cases for lookup_enrichment_index method (Story 6.1.1 AC4.1)."""

    def test_lookup_found(
        self, repository, mock_connection, sample_enrichment_index_rows
    ):
        """Single lookup returns correct EnrichmentIndexRecord when found."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = sample_enrichment_index_rows[0]
        mock_connection.execute.return_value = mock_result

        record = repository.lookup_enrichment_index("FP0001", LookupType.PLAN_CODE)

        assert record is not None
        assert record.lookup_key == "FP0001"
        assert record.lookup_type == LookupType.PLAN_CODE
        assert record.company_id == "614810477"
        assert record.source == SourceType.YAML
        mock_connection.execute.assert_called_once()

    def test_lookup_not_found(self, repository, mock_connection):
        """Single lookup returns None when not found."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_connection.execute.return_value = mock_result

        record = repository.lookup_enrichment_index("NONEXISTENT", LookupType.PLAN_CODE)

        assert record is None
        mock_connection.execute.assert_called_once()

    def test_lookup_customer_name_normalized(
        self, repository, mock_connection, sample_enrichment_index_rows
    ):
        """Customer name lookup works with normalized key."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = sample_enrichment_index_rows[2]
        mock_connection.execute.return_value = mock_result

        record = repository.lookup_enrichment_index(
            "中国平安", LookupType.CUSTOMER_NAME
        )

        assert record is not None
        assert record.lookup_type == LookupType.CUSTOMER_NAME
        assert record.source == SourceType.DOMAIN_LEARNING
        assert record.source_domain == "annuity_performance"

    def test_lookup_query_parameters(self, repository, mock_connection):
        """Lookup passes correct parameters to query."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_connection.execute.return_value = mock_result

        repository.lookup_enrichment_index("TEST_KEY", LookupType.ACCOUNT_NUMBER)

        call_args = mock_connection.execute.call_args
        params = call_args[0][1]
        assert params["lookup_key"] == "TEST_KEY"
        assert params["lookup_type"] == "account_number"


# =============================================================================
# Story 6.1.1: lookup_enrichment_index_batch Tests (AC4.2)
# =============================================================================


class TestLookupEnrichmentIndexBatch:
    """Test cases for lookup_enrichment_index_batch method (Story 6.1.1 AC4.2)."""

    def test_batch_lookup_multiple_types(
        self, repository, mock_connection, sample_enrichment_index_rows
    ):
        """Batch lookup returns results for multiple lookup types."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_enrichment_index_rows
        mock_connection.execute.return_value = mock_result

        keys_by_type = {
            LookupType.PLAN_CODE: ["FP0001"],
            LookupType.ACCOUNT_NAME: ["账户A"],
            LookupType.CUSTOMER_NAME: ["中国平安"],
        }

        results = repository.lookup_enrichment_index_batch(keys_by_type)

        assert len(results) == 3
        assert (LookupType.PLAN_CODE, "FP0001") in results
        assert (LookupType.ACCOUNT_NAME, "账户A") in results
        assert (LookupType.CUSTOMER_NAME, "中国平安") in results
        mock_connection.execute.assert_called_once()

    def test_batch_lookup_partial_matches(
        self, repository, mock_connection, sample_enrichment_index_rows
    ):
        """Batch lookup returns only found entries."""
        mock_result = MagicMock()
        # Only return first row
        mock_result.fetchall.return_value = [sample_enrichment_index_rows[0]]
        mock_connection.execute.return_value = mock_result

        keys_by_type = {
            LookupType.PLAN_CODE: ["FP0001", "FP0002"],  # FP0002 not found
        }

        results = repository.lookup_enrichment_index_batch(keys_by_type)

        assert len(results) == 1
        assert (LookupType.PLAN_CODE, "FP0001") in results
        assert (LookupType.PLAN_CODE, "FP0002") not in results

    def test_batch_lookup_empty_input(self, repository, mock_connection):
        """Empty input returns empty dict without database call."""
        results = repository.lookup_enrichment_index_batch({})

        assert results == {}
        mock_connection.execute.assert_not_called()

    def test_batch_lookup_empty_keys(self, repository, mock_connection):
        """Empty keys list returns empty dict."""
        keys_by_type = {
            LookupType.PLAN_CODE: [],
        }

        results = repository.lookup_enrichment_index_batch(keys_by_type)

        assert results == {}

    def test_batch_lookup_uses_unnest(self, repository, mock_connection):
        """Batch lookup uses UNNEST for efficient query."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_connection.execute.return_value = mock_result

        keys_by_type = {
            LookupType.PLAN_CODE: ["FP0001", "FP0002"],
            LookupType.CUSTOMER_NAME: ["中国平安"],
        }

        repository.lookup_enrichment_index_batch(keys_by_type)

        call_args = mock_connection.execute.call_args
        query_text = str(call_args[0][0])
        assert "unnest" in query_text.lower()
        params = call_args[0][1]
        assert params["lookup_keys"] == ["FP0001", "FP0002", "中国平安"]
        assert params["lookup_types"] == ["plan_code", "plan_code", "customer_name"]

    def test_batch_lookup_normalizes_keys(self, repository, mock_connection):
        """Lookup normalizes customer_name and plan_customer keys before querying."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_connection.execute.return_value = mock_result

        keys_by_type = {
            LookupType.CUSTOMER_NAME: ["  中国 平安  "],  # whitespace, should normalize
            LookupType.PLAN_CUSTOMER: [
                "P1| CUSTOMER_A "
            ],  # customer part should normalize/lower
        }

        repository.lookup_enrichment_index_batch(keys_by_type)

        params = mock_connection.execute.call_args[0][1]
        # normalize_for_temp_id collapses whitespace and lowercases ascii
        assert "中国平安" in params["lookup_keys"]
        assert "P1|customer_a" in params["lookup_keys"]

    def test_batch_lookup_performance_1000_keys(self, repository, mock_connection):
        """1000 batch lookups complete in <100ms with mock."""
        mock_rows = [
            MockEnrichmentIndexRow(
                lookup_key=f"KEY_{i}",
                lookup_type="plan_code",
                company_id=f"ID_{i}",
                confidence=Decimal("1.00"),
                source="yaml",
            )
            for i in range(1000)
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_result

        keys_by_type = {
            LookupType.PLAN_CODE: [f"KEY_{i}" for i in range(1000)],
        }

        start_time = time.perf_counter()
        results = repository.lookup_enrichment_index_batch(keys_by_type)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert len(results) == 1000
        assert elapsed_ms < 100, f"Lookup took {elapsed_ms:.2f}ms, expected <100ms"
        mock_connection.execute.assert_called_once()


# =============================================================================
# Story 6.1.1: insert_enrichment_index_batch Tests (AC4.3)
# =============================================================================


class TestInsertEnrichmentIndexBatch:
    """Test cases for insert_enrichment_index_batch method (Story 6.1.1 AC4.3)."""

    def test_insert_batch_success(
        self, repository, mock_connection, sample_enrichment_records
    ):
        """Batch insert returns correct count."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        result = repository.insert_enrichment_index_batch(sample_enrichment_records)

        assert result.inserted_count == 3
        assert result.skipped_count == 0
        mock_connection.execute.assert_called_once()

    def test_insert_batch_empty_input(self, repository, mock_connection):
        """Empty input returns zero counts without database call."""
        result = repository.insert_enrichment_index_batch([])

        assert result.inserted_count == 0
        assert result.skipped_count == 0
        mock_connection.execute.assert_not_called()

    def test_insert_batch_uses_unnest(
        self, repository, mock_connection, sample_enrichment_records
    ):
        """Batch insert uses UNNEST for efficient query."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        repository.insert_enrichment_index_batch(sample_enrichment_records)

        call_args = mock_connection.execute.call_args
        query_text = str(call_args[0][0])
        assert "unnest" in query_text.lower()
        assert "ON CONFLICT" in query_text

    def test_insert_batch_conflict_handling(self, repository, mock_connection):
        """Insert with conflict updates confidence using GREATEST."""
        mock_result = MagicMock()
        mock_result.rowcount = 1  # 1 affected (could be insert or update)
        mock_connection.execute.return_value = mock_result

        records = [
            EnrichmentIndexRecord(
                lookup_key="FP0001",
                lookup_type=LookupType.PLAN_CODE,
                company_id="614810477",
                confidence=Decimal("0.95"),
                source=SourceType.DOMAIN_LEARNING,
            ),
        ]

        result = repository.insert_enrichment_index_batch(records)

        assert result.inserted_count == 1
        # Verify ON CONFLICT clause includes GREATEST for confidence
        call_args = mock_connection.execute.call_args
        query_text = str(call_args[0][0])
        assert "GREATEST" in query_text
        assert "hit_count" in query_text

    def test_insert_batch_parameters(
        self, repository, mock_connection, sample_enrichment_records
    ):
        """Insert passes correct parameters to query."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_connection.execute.return_value = mock_result

        repository.insert_enrichment_index_batch(sample_enrichment_records)

        call_args = mock_connection.execute.call_args
        params = call_args[0][1]
        assert params["lookup_keys"] == ["FP0001", "账户A", "中国平安"]
        assert params["lookup_types"] == ["plan_code", "account_name", "customer_name"]
        assert params["company_ids"] == ["614810477", "614810477", "600866980"]
        assert params["sources"] == ["yaml", "eqc_api", "domain_learning"]

    def test_insert_batch_normalizes_keys(self, repository, mock_connection):
        """Insert normalizes customer_name/plan_customer keys before upsert."""
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_connection.execute.return_value = mock_result

        records = [
            EnrichmentIndexRecord(
                lookup_key="  客户A  ",
                lookup_type=LookupType.CUSTOMER_NAME,
                company_id="C1",
                source=SourceType.DOMAIN_LEARNING,
            ),
            EnrichmentIndexRecord(
                lookup_key="P1| CUSTOMER_A ",
                lookup_type=LookupType.PLAN_CUSTOMER,
                company_id="C2",
                source=SourceType.DOMAIN_LEARNING,
            ),
        ]

        repository.insert_enrichment_index_batch(records)

        params = mock_connection.execute.call_args[0][1]
        # normalize_for_temp_id collapses whitespace and lowercases ascii letters
        assert params["lookup_keys"] == ["客户a", "P1|customer_a"]

    def test_insert_batch_performance_100_records(self, repository, mock_connection):
        """100 inserts complete in <50ms with mock."""
        records = [
            EnrichmentIndexRecord(
                lookup_key=f"KEY_{i}",
                lookup_type=LookupType.PLAN_CODE,
                company_id=f"ID_{i}",
                source=SourceType.YAML,
            )
            for i in range(100)
        ]

        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_connection.execute.return_value = mock_result

        start_time = time.perf_counter()
        result = repository.insert_enrichment_index_batch(records)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert result.inserted_count == 100
        assert elapsed_ms < 50, f"Insert took {elapsed_ms:.2f}ms, expected <50ms"
        mock_connection.execute.assert_called_once()


# =============================================================================
# Story 6.1.1: update_hit_count Tests (AC4.4)
# =============================================================================


class TestUpdateHitCount:
    """Test cases for update_hit_count method (Story 6.1.1 AC4.4)."""

    def test_update_hit_count_success(self, repository, mock_connection):
        """Update hit count returns True when record exists."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_connection.execute.return_value = mock_result

        updated = repository.update_hit_count("FP0001", LookupType.PLAN_CODE)

        assert updated is True
        mock_connection.execute.assert_called_once()

    def test_update_hit_count_not_found(self, repository, mock_connection):
        """Update hit count returns False when record not found."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_connection.execute.return_value = mock_result

        updated = repository.update_hit_count("NONEXISTENT", LookupType.PLAN_CODE)

        assert updated is False
        mock_connection.execute.assert_called_once()

    def test_update_hit_count_query(self, repository, mock_connection):
        """Update hit count query includes correct fields."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_connection.execute.return_value = mock_result

        repository.update_hit_count("FP0001", LookupType.PLAN_CODE)

        call_args = mock_connection.execute.call_args
        query_text = str(call_args[0][0])
        assert "hit_count = hit_count + 1" in query_text
        assert "last_hit_at = NOW()" in query_text
        assert "updated_at = NOW()" in query_text
        params = call_args[0][1]
        assert params["lookup_key"] == "FP0001"
        assert params["lookup_type"] == "plan_code"


# =============================================================================
# Story 6.1.1: Regression Tests (AC4.5)
# =============================================================================


class TestRegressionExistingMethods:
    """Regression tests ensuring existing methods remain unaffected (AC4.5)."""

    def test_lookup_batch_still_works(self, repository, mock_connection):
        """Existing lookup_batch method still works after adding new methods."""
        from tests.unit.infrastructure.enrichment.test_mapping_repository import (
            MockRow,
        )

        mock_rows = [
            MockRow(
                alias_name="FP0001",
                canonical_id="614810477",
                match_type="plan",
                priority=1,
                source="internal",
            )
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_result

        results = repository.lookup_batch(["FP0001"])

        assert "FP0001" in results
        assert results["FP0001"].company_id == "614810477"

    def test_insert_batch_still_works(self, repository, mock_connection):
        """Existing insert_batch method still works after adding new methods."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_connection.execute.return_value = mock_result

        mappings = [
            {
                "alias_name": "FP0001",
                "canonical_id": "614810477",
                "match_type": "plan",
                "priority": 1,
            }
        ]

        inserted = repository.insert_batch(mappings)

        assert inserted == 1

    def test_enqueue_for_enrichment_still_works(self, repository, mock_connection):
        """Existing enqueue_for_enrichment method still works."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_connection.execute.return_value = mock_result

        requests = [
            {"raw_name": "公司A", "normalized_name": "公司a", "temp_id": "IN_ABC123"},
        ]

        result = repository.enqueue_for_enrichment(requests)

        assert result.queued_count == 1
