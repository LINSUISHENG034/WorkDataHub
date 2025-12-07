"""
Tests for CompanyEnrichmentService with EQC integration and caching.

This module tests the unified company enrichment service that combines
internal mappings with external EQC lookups, result caching, and async
queue processing for comprehensive company ID resolution.
"""

from unittest.mock import Mock, patch
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.work_data_hub.domain.company_enrichment.models import (
    CompanyDetail,
    CompanyIdResult,
    CompanyMappingQuery,
    CompanyMappingRecord,
    CompanyResolutionResult,
    CompanySearchResult,
    ResolutionStatus,
)
from src.work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
from src.work_data_hub.domain.company_enrichment.observability import EnrichmentObserver
from src.work_data_hub.io.connectors.eqc_client import EQCClientError


@pytest.fixture
def mock_loader():
    """Mock CompanyEnrichmentLoader for testing."""
    loader = Mock()

    # Default: return empty mappings (no internal match)
    loader.load_mappings.return_value = []

    return loader


@pytest.fixture
def mock_queue():
    """Mock LookupQueue for testing."""
    queue = Mock()

    # Default: successful enqueue and temp ID generation
    queue.enqueue.return_value = Mock(id=1, name="Test Company", status="pending")
    queue.get_next_temp_id.return_value = "TEMP_000001"

    return queue


@pytest.fixture
def mock_eqc_client():
    """Mock EQCClient for testing."""
    eqc_client = Mock()

    # Default: successful EQC search and detail
    mock_search_result = CompanySearchResult(
        company_id="614810477",
        official_name="中国平安保险集团股份有限公司",
        unite_code="91110000000000001X",
        match_score=0.95,
    )
    eqc_client.search_company.return_value = [mock_search_result]

    mock_detail = CompanyDetail(
        company_id="614810477",
        official_name="中国平安保险集团股份有限公司",
        unite_code="91110000000000001X",
        aliases=["中国平安", "平安保险"],
        business_status="存续",
    )
    eqc_client.get_company_detail.return_value = mock_detail

    return eqc_client


@pytest.fixture
def enrichment_service(mock_loader, mock_queue, mock_eqc_client):
    """CompanyEnrichmentService with mocked dependencies."""
    return CompanyEnrichmentService(
        loader=mock_loader,
        queue=mock_queue,
        eqc_client=mock_eqc_client,
    )


@pytest.fixture
def internal_mappings():
    """Sample internal company mappings for testing."""
    return [
        CompanyMappingRecord(
            alias_name="AN001",
            canonical_id="614810477",
            source="internal",
            match_type="plan",
            priority=1,
        ),
        CompanyMappingRecord(
            alias_name="测试企业A",
            canonical_id="608349737",
            source="internal",
            match_type="name",
            priority=4,
        ),
        CompanyMappingRecord(
            alias_name="年金账户测试",
            canonical_id="601234567",
            source="internal",
            match_type="account_name",
            priority=5,
        ),
    ]


class TestCompanyEnrichmentServiceInitialization:
    """Test service initialization and dependency injection."""

    def test_service_initialization_with_dependencies(
        self, mock_loader, mock_queue, mock_eqc_client
    ):
        """Test successful service initialization."""
        service = CompanyEnrichmentService(
            loader=mock_loader,
            queue=mock_queue,
            eqc_client=mock_eqc_client,
            sync_lookup_budget=10,
        )

        assert service.loader == mock_loader
        assert service.queue == mock_queue
        assert service.eqc_client == mock_eqc_client
        assert service.sync_lookup_budget == 10

    def test_service_initialization_default_budget(
        self, mock_loader, mock_queue, mock_eqc_client
    ):
        """Test service initialization with default budget."""
        service = CompanyEnrichmentService(
            loader=mock_loader, queue=mock_queue, eqc_client=mock_eqc_client
        )

        assert service.sync_lookup_budget == 0


class TestInternalMappingResolution:
    """Test internal mapping lookup (SUCCESS_INTERNAL status)."""

    def test_internal_mapping_hit_plan_code(
        self, enrichment_service, mock_loader, internal_mappings
    ):
        """Test internal mapping lookup returns SUCCESS_INTERNAL for plan code."""
        # Setup: loader returns internal mappings
        mock_loader.load_mappings.return_value = internal_mappings

        # Mock the resolve_company_id function
        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id="614810477",
                match_type="plan",
                source_value="AN001",
                priority=1,
            )

            result = enrichment_service.resolve_company_id(plan_code="AN001")

            assert result.status == ResolutionStatus.SUCCESS_INTERNAL
            assert result.company_id == "614810477"
            assert result.source == "plan"
            assert result.temp_id is None

    def test_internal_mapping_hit_customer_name(
        self, enrichment_service, mock_loader, internal_mappings
    ):
        """Test internal mapping lookup returns SUCCESS_INTERNAL for customer name."""
        mock_loader.load_mappings.return_value = internal_mappings

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id="608349737",
                match_type="name",
                source_value="测试企业A",
                priority=4,
            )

            result = enrichment_service.resolve_company_id(customer_name="测试企业A")

            assert result.status == ResolutionStatus.SUCCESS_INTERNAL
            assert result.company_id == "608349737"
            assert result.source == "name"

    def test_internal_mapping_hit_account_name(
        self, enrichment_service, mock_loader, internal_mappings
    ):
        """Test internal mapping lookup returns SUCCESS_INTERNAL for account name."""
        mock_loader.load_mappings.return_value = internal_mappings

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id="601234567",
                match_type="account_name",
                source_value="年金账户测试",
                priority=5,
            )

            result = enrichment_service.resolve_company_id(account_name="年金账户测试")

            assert result.status == ResolutionStatus.SUCCESS_INTERNAL
            assert result.company_id == "601234567"
            assert result.source == "account_name"


class TestEQCSuccessWithCaching:
    """Test EQC lookup success with result caching (SUCCESS_EXTERNAL status)."""

    def test_eqc_success_with_caching(
        self, enrichment_service, mock_loader, mock_eqc_client
    ):
        """Test EQC lookup with budget returns SUCCESS_EXTERNAL and caches result."""
        # Setup: no internal mappings, EQC success
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            # No internal mapping found
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None, source_value=None, priority=None
            )

            result = enrichment_service.resolve_company_id(
                customer_name="中国平安", sync_lookup_budget=1
            )

            # Verify EQC was called
            mock_eqc_client.search_company.assert_called_once_with("中国平安")
            mock_eqc_client.get_company_detail.assert_called_once_with("614810477")

            # Verify caching was called
            enrichment_service.loader.cache_company_mapping.assert_called_once_with(
                alias_name="中国平安", canonical_id="614810477", source="EQC"
            )

            # Verify result
            assert result.status == ResolutionStatus.SUCCESS_EXTERNAL
            assert result.company_id == "614810477"
            assert result.source == "EQC"
            assert result.temp_id is None

    def test_eqc_success_no_budget_queues_request(
        self, enrichment_service, mock_loader, mock_queue
    ):
        """Test EQC lookup with zero budget queues request."""
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(
                customer_name="Test Company", sync_lookup_budget=0
            )

            # Verify EQC was not called due to zero budget
            enrichment_service.eqc_client.search_company.assert_not_called()

            # Verify queueing was called
            mock_queue.enqueue.assert_called_once()

            # Verify result
            assert result.status == ResolutionStatus.PENDING_LOOKUP
            assert result.company_id is None
            assert result.source == "queued"


class TestBudgetExhaustionQueuing:
    """Test budget exhaustion queuing (PENDING_LOOKUP status)."""

    def test_budget_exhaustion_queues_request(
        self, enrichment_service, mock_loader, mock_queue
    ):
        """Test budget=0 queues request for async processing."""
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(
                customer_name="Test Company", sync_lookup_budget=0
            )

            # Verify queuing was called
            mock_queue.enqueue.assert_called_once()
            enqueue_call = mock_queue.enqueue.call_args
            assert "Test Company" in enqueue_call[0]  # name parameter

            # Verify result
            assert result.status == ResolutionStatus.PENDING_LOOKUP
            assert result.company_id is None
            assert result.source == "queued"

    def test_no_customer_name_and_no_internal_match_generates_temp_id(
        self, enrichment_service, mock_loader, mock_queue
    ):
        """Test empty customer_name generates TEMP_* ID."""
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(plan_code="UNKNOWN")

            # Verify temp ID generation was called
            mock_queue.get_next_temp_id.assert_called_once()

            # Verify result
            assert result.status == ResolutionStatus.TEMP_ASSIGNED
            assert result.company_id == "TEMP_000001"
            assert result.source == "generated"
            assert result.temp_id == "TEMP_000001"


class TestBudgetDefaultBehavior:
    """Test budget default and override behavior."""

    def test_resolve_company_id_uses_instance_budget_when_no_override(
        self, mock_loader, mock_queue, mock_eqc_client
    ):
        """Test that resolve_company_id uses instance budget when sync_lookup_budget is not provided."""
        # Create service with non-zero instance budget
        service = CompanyEnrichmentService(
            loader=mock_loader,
            queue=mock_queue,
            eqc_client=mock_eqc_client,
            sync_lookup_budget=5,
        )

        # Setup: no internal mappings, so it will attempt EQC lookup
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            # Call without sync_lookup_budget parameter - should use instance default of 5
            result = service.resolve_company_id(customer_name="Test Company")

            # Verify EQC client was called (budget > 0)
            mock_eqc_client.search_company.assert_called_once_with("Test Company")

            # Verify result indicates EQC lookup was attempted
            assert result.status == ResolutionStatus.SUCCESS_EXTERNAL
            assert result.company_id == "614810477"
            assert result.source == "EQC"

    def test_resolve_company_id_uses_override_budget_when_provided(
        self, mock_loader, mock_queue, mock_eqc_client
    ):
        """Test that resolve_company_id uses provided sync_lookup_budget when explicitly set."""
        # Create service with non-zero instance budget
        service = CompanyEnrichmentService(
            loader=mock_loader,
            queue=mock_queue,
            eqc_client=mock_eqc_client,
            sync_lookup_budget=5,
        )

        # Setup: no internal mappings, so it will attempt EQC lookup or queue
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            # Call with sync_lookup_budget=0 - should override instance default and queue instead
            result = service.resolve_company_id(
                customer_name="Test Company", sync_lookup_budget=0
            )

            # Verify EQC client was NOT called (budget = 0)
            mock_eqc_client.search_company.assert_not_called()

            # Verify request was queued instead
            mock_queue.enqueue.assert_called_once()
            assert result.status == ResolutionStatus.PENDING_LOOKUP
            assert result.source == "queued"

    def test_resolve_company_id_zero_instance_budget_with_override(
        self, mock_loader, mock_queue, mock_eqc_client
    ):
        """Test that resolve_company_id respects override even with zero instance budget."""
        # Create service with zero instance budget
        service = CompanyEnrichmentService(
            loader=mock_loader,
            queue=mock_queue,
            eqc_client=mock_eqc_client,
            sync_lookup_budget=0,
        )

        # Setup: no internal mappings, so it will attempt EQC lookup
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            # Call with sync_lookup_budget=1 - should override instance default and use EQC
            result = service.resolve_company_id(
                customer_name="Test Company", sync_lookup_budget=1
            )

            # Verify EQC client was called (budget = 1)
            mock_eqc_client.search_company.assert_called_once_with("Test Company")

            # Verify result indicates EQC lookup was attempted
            assert result.status == ResolutionStatus.SUCCESS_EXTERNAL
            assert result.company_id == "614810477"
            assert result.source == "EQC"


class TestTempIdGeneration:
    """Test temporary ID generation (TEMP_ASSIGNED status)."""

    def test_empty_customer_name_generates_temp_id(
        self, enrichment_service, mock_loader, mock_queue
    ):
        """Test empty customer_name generates TEMP_* ID."""
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(plan_code="UNKNOWN")

            # Verify temp ID generation
            mock_queue.get_next_temp_id.assert_called_once()

            assert result.status == ResolutionStatus.TEMP_ASSIGNED
            assert result.company_id == "TEMP_000001"
            assert result.temp_id == "TEMP_000001"

    def test_queue_failure_fallback_to_temp_id(
        self, enrichment_service, mock_loader, mock_queue
    ):
        """Test queue failure falls back to temp ID generation."""
        mock_loader.load_mappings.return_value = []
        mock_queue.enqueue.side_effect = Exception("Queue error")

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(customer_name="Test Company")

            # Verify temp ID generation was called after queue failure
            mock_queue.get_next_temp_id.assert_called_once()

            assert result.status == ResolutionStatus.TEMP_ASSIGNED
            assert result.company_id == "TEMP_000001"


class TestEQCErrorHandling:
    """Test EQC error handling and graceful fallback to queue."""

    def test_eqc_error_falls_back_to_queue(
        self, enrichment_service, mock_loader, mock_eqc_client, mock_queue
    ):
        """Test EQC errors don't block main flow, fallback to queueing."""
        mock_loader.load_mappings.return_value = []
        mock_eqc_client.search_company.side_effect = EQCClientError("Rate limited")

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(
                customer_name="Test Company", sync_lookup_budget=1
            )

            # Verify EQC was attempted
            mock_eqc_client.search_company.assert_called_once_with("Test Company")

            # Verify graceful fallback to queueing
            mock_queue.enqueue.assert_called_once()

            assert result.status == ResolutionStatus.PENDING_LOOKUP
            assert result.source == "queued"

    def test_eqc_timeout_error_graceful_handling(
        self, enrichment_service, mock_loader, mock_eqc_client, mock_queue
    ):
        """Test EQC timeout errors are handled gracefully."""
        mock_loader.load_mappings.return_value = []
        mock_eqc_client.search_company.side_effect = Exception("Request timeout")

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(
                customer_name="Timeout Company", sync_lookup_budget=1
            )

            # Should not raise exception, should queue instead
            mock_queue.enqueue.assert_called_once()
            assert result.status == ResolutionStatus.PENDING_LOOKUP

    def test_eqc_no_results_queues_request(
        self, enrichment_service, mock_loader, mock_eqc_client, mock_queue
    ):
        """Test EQC returning no results queues request."""
        mock_loader.load_mappings.return_value = []
        mock_eqc_client.search_company.return_value = []  # No results

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(
                customer_name="Unknown Company", sync_lookup_budget=1
            )

            # Should queue when no EQC results found
            mock_queue.enqueue.assert_called_once()
            assert result.status == ResolutionStatus.PENDING_LOOKUP


class TestProcessLookupQueue:
    """Test async queue processing functionality."""

    def test_process_lookup_queue_successful(
        self, enrichment_service, mock_queue, mock_eqc_client
    ):
        """Test successful queue processing."""
        # Setup: mock pending requests
        mock_request = Mock(id=1, name="Test Company", attempts=0)
        mock_queue.dequeue.side_effect = [[mock_request], []]  # One batch, then empty

        processed_count = enrichment_service.process_lookup_queue(batch_size=10)

        # Verify EQC lookup was performed
        mock_eqc_client.search_company.assert_called_once_with("Test Company")
        mock_eqc_client.get_company_detail.assert_called_once_with("614810477")

        # Verify caching was called
        enrichment_service.loader.cache_company_mapping.assert_called_once()

        # Verify request marked as done
        mock_queue.mark_done.assert_called_once_with(1)

        assert processed_count == 1

    def test_process_lookup_queue_eqc_failure(
        self, enrichment_service, mock_queue, mock_eqc_client
    ):
        """Test queue processing handles EQC failures."""
        mock_request = Mock(id=2, name="Failed Company", attempts=1)
        mock_queue.dequeue.side_effect = [[mock_request], []]
        mock_eqc_client.search_company.side_effect = Exception("EQC error")

        processed_count = enrichment_service.process_lookup_queue()

        # Verify request marked as failed
        mock_queue.mark_failed.assert_called_once_with(
            2, "EQC lookup error: EQC error", 2
        )

        assert processed_count == 0

    def test_process_lookup_queue_no_eqc_results(
        self, enrichment_service, mock_queue, mock_eqc_client
    ):
        """Test queue processing handles no EQC results."""
        mock_request = Mock(id=3, name="No Results Company", attempts=0)
        mock_queue.dequeue.side_effect = [[mock_request], []]
        mock_eqc_client.search_company.return_value = []  # No results

        processed_count = enrichment_service.process_lookup_queue()

        # Verify request marked as failed with appropriate message
        mock_queue.mark_failed.assert_called_once_with(
            3, "No EQC search results found for 'No Results Company'", 1
        )

        assert processed_count == 0


class TestQueueStatusReporting:
    """Test queue status and statistics reporting."""

    def test_get_queue_status_successful(self, enrichment_service, mock_queue):
        """Test successful queue status retrieval."""
        mock_queue.get_queue_stats.return_value = {
            "pending": 10,
            "processing": 2,
            "done": 100,
            "failed": 5,
        }

        status = enrichment_service.get_queue_status()

        assert status["pending"] == 10
        assert status["processing"] == 2
        assert status["done"] == 100
        assert status["failed"] == 5

    def test_get_queue_status_error_handling(self, enrichment_service, mock_queue):
        """Test queue status error handling."""
        mock_queue.get_queue_stats.side_effect = Exception("Database error")

        status = enrichment_service.get_queue_status()

        # Should return default values on error
        assert status == {"pending": 0, "processing": 0, "done": 0, "failed": 0}


class TestObserverIntegration:
    """Observer wiring and disabled-mode coverage."""

    def test_disabled_mode_generates_temp_ids_and_logs_stats(
        self, mock_loader, mock_queue, mock_eqc_client
    ):
        observer = EnrichmentObserver()
        service = CompanyEnrichmentService(
            loader=mock_loader,
            queue=mock_queue,
            eqc_client=mock_eqc_client,
            enrich_enabled=False,
            observer=observer,
        )

        result = service.resolve_company_id(customer_name="Disabled Co")

        assert result.status == ResolutionStatus.TEMP_ASSIGNED
        assert result.temp_id == "TEMP_000001"
        stats = observer.get_stats()
        assert stats.total_lookups == 1
        assert stats.temp_ids_generated == 1
        assert stats.api_calls == 0
        assert stats.async_queued == 0
        assert stats.cache_hits == 0

    def test_process_lookup_queue_records_observer_stats(
        self, mock_loader, mock_queue, mock_eqc_client
    ):
        observer = EnrichmentObserver()
        service = CompanyEnrichmentService(
            loader=mock_loader,
            queue=mock_queue,
            eqc_client=mock_eqc_client,
            observer=observer,
        )
        mock_request = Mock(id=1, name="Test Company", attempts=0)
        mock_queue.dequeue.side_effect = [[mock_request], []]

        processed_count = service.process_lookup_queue(
            batch_size=5, observer=observer
        )

        assert processed_count == 1
        stats = observer.get_stats()
        assert stats.total_lookups == 1
        assert stats.api_calls == 1
        assert stats.sync_budget_used == 1
        assert stats.temp_ids_generated == 0


class TestEdgeCasesAndValidation:
    """Test edge cases and input validation."""

    def test_whitespace_handling_in_customer_name(
        self, enrichment_service, mock_loader
    ):
        """Test proper whitespace handling in customer names."""
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id(
                customer_name="  Test Company  ", sync_lookup_budget=1
            )

            # EQC should be called with trimmed name
            enrichment_service.eqc_client.search_company.assert_called_once_with(
                "Test Company"
            )

    def test_all_parameters_none(self, enrichment_service, mock_loader, mock_queue):
        """Test behavior when all parameters are None."""
        mock_loader.load_mappings.return_value = []

        with patch(
            "src.work_data_hub.domain.company_enrichment.service.resolve_company_id"
        ) as mock_resolve:
            mock_resolve.return_value = CompanyResolutionResult(
                company_id=None, match_type=None
            )

            result = enrichment_service.resolve_company_id()

            # Should generate temp ID when no parameters provided
            mock_queue.get_next_temp_id.assert_called_once()
            assert result.status == ResolutionStatus.TEMP_ASSIGNED

    def test_internal_mapping_loader_error_continues_to_eqc(
        self, enrichment_service, mock_loader, mock_eqc_client
    ):
        """Test internal mapping loader error doesn't prevent EQC lookup."""
        mock_loader.load_mappings.side_effect = Exception("Database connection error")

        result = enrichment_service.resolve_company_id(
            customer_name="Test Company", sync_lookup_budget=1
        )

        # Should continue to EQC lookup despite internal mapping error
        mock_eqc_client.search_company.assert_called_once_with("Test Company")
        assert result.status == ResolutionStatus.SUCCESS_EXTERNAL
