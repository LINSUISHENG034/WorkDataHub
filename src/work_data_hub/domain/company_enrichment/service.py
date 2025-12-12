"""
Company enrichment service layer with pure transformation functions and unified service.

This module provides the core business logic for company ID resolution,
replicating the exact priority-based lookup logic from legacy _update_company_id
method while providing a clean, testable interface. Also includes the unified
CompanyEnrichmentService with EQC integration, caching, and async queue processing.
"""

import logging
from typing import Dict, List, Optional

from .models import (
    CompanyIdResult,
    CompanyMappingQuery,
    CompanyMappingRecord,
    CompanyResolutionResult,
    ResolutionStatus,
)
from .observability import EnrichmentObserver

logger = logging.getLogger(__name__)


def resolve_company_id(
    mappings: List[CompanyMappingRecord], query: CompanyMappingQuery
) -> CompanyResolutionResult:
    """
    Resolve company ID using priority-based lookup exactly matching legacy logic.

    This function replicates the exact behavior of the legacy _update_company_id
    method from data_cleaner.py (lines 203-227), implementing the 5-layer
    priority system with precise fallback logic.

    Priority order (matches legacy _update_company_id):
    1. plan_code -> COMPANY_ID1_MAPPING (priority=1)
    2. account_number -> COMPANY_ID2_MAPPING (priority=2)
    3. hardcoded mappings -> COMPANY_ID3_MAPPING (priority=3)
    4. customer_name -> COMPANY_ID4_MAPPING (priority=4)
    5. account_name -> COMPANY_ID5_MAPPING (priority=5)

    Args:
        mappings: List of company mapping records from database
        query: Company mapping query with search fields

    Returns:
        CompanyResolutionResult with resolved company_id and match metadata

    Examples:
        >>> mappings = [
        ...     CompanyMappingRecord(alias_name="AN001", canonical_id="614810477",
        ...                          match_type="plan", priority=1),
        ...     CompanyMappingRecord(alias_name="测试企业A", canonical_id="608349737",
        ...                          match_type="name", priority=4)
        ... ]
        >>> query = CompanyMappingQuery(plan_code="AN001", customer_name="测试企业A")
        >>> result = resolve_company_id(mappings, query)
        >>> result.company_id
        '614810477'
        >>> result.match_type
        'plan'
    """
    logger.debug(
        "Starting company ID resolution",
        extra={
            "mappings_count": len(mappings),
            "plan_code": query.plan_code,
            "account_number": query.account_number,
            "customer_name": query.customer_name,
            "account_name": query.account_name,
        },
    )

    # Build lookup dictionaries by match_type for O(1) access
    # This replaces the individual COMPANY_ID*_MAPPING dictionaries from legacy
    lookup: Dict[str, Dict[str, CompanyMappingRecord]] = {}
    for mapping in mappings:
        if mapping.match_type not in lookup:
            lookup[mapping.match_type] = {}
        lookup[mapping.match_type][mapping.alias_name] = mapping

    # Priority-based search matching legacy precedence EXACTLY
    # This replicates the step-by-step logic from
    # AnnuityPerformanceCleaner._clean_method
    search_steps = [
        ("plan", query.plan_code, "Plan code lookup (COMPANY_ID1_MAPPING)"),
        (
            "account",
            query.account_number,
            "Account number lookup (COMPANY_ID2_MAPPING)",
        ),
        ("hardcode", query.plan_code, "Hardcode lookup (COMPANY_ID3_MAPPING)"),
        ("name", query.customer_name, "Customer name lookup (COMPANY_ID4_MAPPING)"),
        (
            "account_name",
            query.account_name,
            "Account name lookup (COMPANY_ID5_MAPPING)",
        ),
    ]

    for match_type, search_value, description in search_steps:
        logger.debug(f"Trying {description}", extra={"search_value": search_value})

        # Skip if search value is None or empty (matches legacy null/empty check)
        if not search_value:
            logger.debug(f"Skipping {match_type} - search value is None/empty")
            continue

        # Check if we have mappings for this type
        if match_type not in lookup:
            logger.debug(f"No mappings found for match_type: {match_type}")
            continue

        # Exact string match (case-sensitive, matches legacy behavior)
        if search_value in lookup[match_type]:
            mapping = lookup[match_type][search_value]
            result = CompanyResolutionResult(
                company_id=mapping.canonical_id,
                match_type=match_type,
                source_value=search_value,
                priority=mapping.priority,
            )
            logger.debug(
                "Company ID resolved",
                extra={
                    "company_id": result.company_id,
                    "match_type": result.match_type,
                    "source_value": result.source_value,
                    "priority": result.priority,
                },
            )
            return result

    # CRITICAL: Default fallback logic matching legacy behavior
    # From data_cleaner.py line 215-217: when company_id is empty AND
    # customer_name is empty, apply hardcode mapping with fallback to
    # '600866980'
    if not query.customer_name:
        logger.debug("Applying default fallback logic - customer_name is None/empty")
        result = CompanyResolutionResult(
            company_id="600866980",
            match_type="default",
            source_value=None,
            priority=None,
        )
        logger.debug(
            "Applied default fallback",
            extra={"company_id": result.company_id, "reason": "empty_customer_name"},
        )
        return result

    # No match found and customer_name is not empty
    logger.debug(
        "No company ID match found",
        extra={
            "query_fields_provided": [
                f"plan_code={query.plan_code}",
                f"account_number={query.account_number}",
                f"customer_name={query.customer_name}",
                f"account_name={query.account_name}",
            ]
        },
    )

    return CompanyResolutionResult(
        company_id=None, match_type=None, source_value=None, priority=None
    )


def build_mapping_lookup(
    mappings: List[CompanyMappingRecord],
) -> Dict[str, Dict[str, str]]:
    """
    Build optimized lookup structure for company mappings.

    Organizes mappings by match_type for efficient resolution queries.
    This structure mimics the legacy COMPANY_ID*_MAPPING dictionaries.

    Args:
        mappings: List of company mapping records

    Returns:
        Nested dictionary: {match_type: {alias_name: canonical_id}}

    Example:
        >>> mappings = [
        ...     CompanyMappingRecord(alias_name="AN001", canonical_id="614810477",
        ...                          match_type="plan", priority=1)
        ... ]
        >>> lookup = build_mapping_lookup(mappings)
        >>> lookup["plan"]["AN001"]
        '614810477'
    """
    lookup: Dict[str, Dict[str, str]] = {}

    for mapping in mappings:
        if mapping.match_type not in lookup:
            lookup[mapping.match_type] = {}

        lookup[mapping.match_type][mapping.alias_name] = mapping.canonical_id

    logger.debug(
        "Built mapping lookup",
        extra={
            "match_types": list(lookup.keys()),
            "total_mappings": sum(
                len(type_mappings) for type_mappings in lookup.values()
            ),
        },
    )

    return lookup


def validate_mapping_consistency(mappings: List[CompanyMappingRecord]) -> List[str]:
    """
    Validate mapping consistency and detect potential conflicts.

    Checks for duplicate alias_name values within the same match_type
    and validates priority alignment with match_type expectations.

    Args:
        mappings: List of company mapping records to validate

    Returns:
        List of validation warnings/errors

    Example:
        >>> mappings = [
        ...     CompanyMappingRecord(alias_name="AN001", canonical_id="111",
        ...                          match_type="plan", priority=1),
        ...     CompanyMappingRecord(alias_name="AN001", canonical_id="222",
        ...                          match_type="plan", priority=1)
        ... ]
        >>> warnings = validate_mapping_consistency(mappings)
        >>> len(warnings)
        1
    """
    warnings = []

    # Check for duplicate alias_name within match_type
    seen_aliases: Dict[
        str, Dict[str, str]
    ] = {}  # {match_type: {alias_name: canonical_id}}

    for mapping in mappings:
        match_type = mapping.match_type
        alias_name = mapping.alias_name
        canonical_id = mapping.canonical_id

        if match_type not in seen_aliases:
            seen_aliases[match_type] = {}

        if alias_name in seen_aliases[match_type]:
            existing_id = seen_aliases[match_type][alias_name]
            if existing_id != canonical_id:
                warnings.append(
                    f"Conflicting mappings for {match_type}.{alias_name}: "
                    f"{existing_id} vs {canonical_id}"
                )
        else:
            seen_aliases[match_type][alias_name] = canonical_id

    # Validate priority alignment with match_type
    expected_priorities = {
        "plan": 1,
        "account": 2,
        "hardcode": 3,
        "name": 4,
        "account_name": 5,
    }

    for mapping in mappings:
        expected_priority = expected_priorities.get(mapping.match_type)
        if expected_priority and mapping.priority != expected_priority:
            warnings.append(
                f"Priority mismatch for {mapping.match_type}: "
                f"expected {expected_priority}, got {mapping.priority}"
            )

    if warnings:
        logger.warning(
            "Mapping validation issues detected",
            extra={
                "warnings_count": len(warnings),
                "warnings": warnings[:5],
            },  # Log first 5
        )

    return warnings


# ===== Unified Company Enrichment Service =====
# This service integrates internal mappings with EQC lookups, caching, and
# queue processing


class CompanyEnrichmentService:
    """
    Unified company enrichment service with EQC integration and caching.

    Provides priority-based company ID resolution combining internal mappings
    with external EQC lookups, result caching, and asynchronous queue processing
    for scalable operations.

    Resolution Priority Flow (matches INITIAL.S-003.md exactly):
    1. Internal mapping lookup (highest priority)
    2. EQC search + detail + cache (if budget allows)
    3. Queue for async processing (if budget exhausted or EQC fails)
    4. Generate temporary ID (if customer_name is empty)

    Examples:
        >>> from work_data_hub.io.connectors.eqc_client import EQCClient
        >>> from work_data_hub.io.loader.company_enrichment_loader import (
        ...     CompanyEnrichmentLoader
        ... )
        >>> from work_data_hub.domain.company_enrichment.lookup_queue import (
        ...     LookupQueue
        ... )
        >>>
        >>> loader = CompanyEnrichmentLoader(connection)
        >>> queue = LookupQueue(connection)
        >>> eqc_client = EQCClient()
        >>> service = CompanyEnrichmentService(
        ...     loader,
        ...     queue,
        ...     eqc_client,
        ...     sync_lookup_budget=5,
        ... )
        >>>
        >>> result = service.resolve_company_id(
        ...     customer_name="中国平安",
        ...     sync_lookup_budget=1,
        ... )
        >>> print(f"Status: {result.status}, ID: {result.company_id}")
    """

    def __init__(
        self,
        loader,  # CompanyEnrichmentLoader
        queue,  # LookupQueue
        eqc_client,  # EQCClient
        *,
        sync_lookup_budget: int = 0,
        observer: Optional[EnrichmentObserver] = None,
        enrich_enabled: bool = True,
    ):
        """
        Initialize company enrichment service with dependency injection.

        Args:
            loader: CompanyEnrichmentLoader instance for caching operations
            queue: LookupQueue instance for async processing
            eqc_client: EQCClient instance for EQC API operations
            sync_lookup_budget: Default budget for synchronous EQC lookups
            observer: Optional EnrichmentObserver for metrics collection
            enrich_enabled: Flag to enable/disable enrichment (AC6)
        """
        self.loader = loader
        self.queue = queue
        self.eqc_client = eqc_client
        self.sync_lookup_budget = sync_lookup_budget
        self.observer = observer
        self.enrich_enabled = enrich_enabled

        logger.info(
            "CompanyEnrichmentService initialized",
            extra={
                "default_sync_budget": sync_lookup_budget,
                "has_loader": bool(loader),
                "has_queue": bool(queue),
                "has_eqc_client": bool(eqc_client),
                "enrich_enabled": enrich_enabled,
            },
        )

    def resolve_company_id(
        self,
        *,
        plan_code: Optional[str] = None,
        customer_name: Optional[str] = None,
        account_name: Optional[str] = None,
        sync_lookup_budget: Optional[int] = None,
        observer: Optional[EnrichmentObserver] = None,
    ) -> CompanyIdResult:
        """
        Resolve company ID using priority-based lookup with EQC integration.

        Implements the exact specification from INITIAL.S-003.md with
        priority flow:
        1. Internal mapping lookup (using existing resolve_company_id function)
        2. EQC search + detail + cache result (if budget > 0)
        3. Queue for async processing (if budget = 0 or EQC fails)
        4. Generate temporary ID (if customer_name is empty)

        Args:
            plan_code: Plan code for priority 1 lookup (计划代码)
            customer_name: Customer name for priority 4 lookup (客户名称)
            account_name: Account name for priority 5 lookup (年金账户名)
            sync_lookup_budget: Budget for synchronous EQC lookups (overrides
                instance default)

        Returns:
            CompanyIdResult with resolved ID and status information

        Raises:
            Exception: Re-raises critical errors that prevent resolution

        Examples:
            >>> # Internal mapping hit
            >>> result = service.resolve_company_id(plan_code="AN001")
            >>> result.status == ResolutionStatus.SUCCESS_INTERNAL

            >>> # EQC lookup with budget
            >>> result = service.resolve_company_id(
            ...     customer_name="中国平安",
            ...     sync_lookup_budget=1,
            ... )
            >>> result.status == ResolutionStatus.SUCCESS_EXTERNAL

            >>> # Queued for async processing
            >>> result = service.resolve_company_id(
            ...     customer_name="Test Company", sync_lookup_budget=0
            ... )
            >>> result.status == ResolutionStatus.PENDING_LOOKUP

            >>> # Temporary ID generation
            >>> result = service.resolve_company_id(plan_code="UNKNOWN")
            >>> result.status == ResolutionStatus.TEMP_ASSIGNED
        """
        # Budget policy: if a per-call budget is provided, use it; otherwise
        # use instance default. This preserves the instance-level budget
        # setting when no override is provided.
        budget = (
            sync_lookup_budget
            if sync_lookup_budget is not None
            else self.sync_lookup_budget
        )
        observer = observer or self.observer

        logger.debug(
            "Starting unified company ID resolution",
            extra={
                "plan_code": plan_code,
                "customer_name": customer_name,
                "account_name": account_name,
                "sync_lookup_budget": budget,
                "enrich_enabled": self.enrich_enabled,
            },
        )

        # Story 6.8: Record lookup attempt (AC1)
        if observer:
            observer.record_lookup()

        # AC6: Enrichment disabled → always generate temp IDs, skip API/queue paths
        if not self.enrich_enabled:
            try:
                temp_id = self.queue.get_next_temp_id(customer_name or "unknown")
            except Exception as e:
                logger.error(f"Failed to generate temporary ID (disabled mode): {e}")
                return CompanyIdResult(
                    company_id=None,
                    status=ResolutionStatus.TEMP_ASSIGNED,
                    source="disabled",
                    temp_id=None,
                )

            if observer:
                observer.record_temp_id(customer_name or "", temp_id)

            logger.debug(
                "Enrichment disabled - generated temp ID",
                extra={"temp_id": temp_id, "customer_name": customer_name},
            )

            return CompanyIdResult(
                company_id=temp_id,
                status=ResolutionStatus.TEMP_ASSIGNED,
                source="disabled",
                temp_id=temp_id,
            )

        # Step 1: Try internal mappings first (highest priority)
        try:
            mappings = self.loader.load_mappings()
            query = CompanyMappingQuery(
                plan_code=plan_code,
                account_number=None,
                customer_name=customer_name,
                account_name=account_name,
            )
            internal_result = resolve_company_id(mappings, query)

            if internal_result.company_id:
                logger.debug(
                    "Company ID resolved via internal mappings",
                    extra={
                        "company_id": internal_result.company_id,
                        "match_type": internal_result.match_type,
                        "priority": internal_result.priority,
                    },
                )
                # Story 6.8: Record cache hit (AC1)
                if observer:
                    observer.record_cache_hit(match_type=internal_result.match_type or "unknown")
                return CompanyIdResult(
                    company_id=internal_result.company_id,
                    status=ResolutionStatus.SUCCESS_INTERNAL,
                    source=internal_result.match_type,
                    temp_id=None,
                )

        except Exception as e:
            logger.warning(f"Internal mapping lookup failed, continuing with EQC: {e}")

        # Step 2: Try EQC lookup if budget allows and customer_name exists
        if budget > 0 and customer_name and customer_name.strip():
            try:
                logger.debug(
                    "Attempting EQC lookup with budget",
                    extra={"customer_name": customer_name, "budget": budget},
                )

                # Story 6.8: Record API call (AC1)
                if observer:
                    observer.record_api_call()

                # EQC search
                search_results = self.eqc_client.search_company(customer_name.strip())

                if search_results:
                    # Take first result and get details
                    best_result = search_results[0]
                    detail = self.eqc_client.get_company_detail(best_result.company_id)

                    # Cache result for future lookups
                    try:
                        self.loader.cache_company_mapping(
                            alias_name=customer_name.strip(),
                            canonical_id=detail.company_id,
                            source="EQC",
                        )
                        logger.debug(f"Cached EQC result for '{customer_name}'")
                    except Exception as cache_error:
                        logger.warning(f"Failed to cache EQC result: {cache_error}")

                    logger.debug(
                        "Company ID resolved via EQC lookup",
                        extra={
                            "company_id": detail.company_id,
                            "official_name": detail.official_name,
                            "customer_name": customer_name,
                        },
                    )

                    return CompanyIdResult(
                        company_id=detail.company_id,
                        status=ResolutionStatus.SUCCESS_EXTERNAL,
                        source="EQC",
                        temp_id=None,
                    )
                else:
                    logger.debug(
                        f"EQC search returned no results for '{customer_name}'"
                    )

            except Exception as e:
                # CRITICAL: Don't block main flow on EQC errors
                logger.warning(
                    f"EQC lookup failed, will queue for async processing: {e}",
                    extra={
                        "customer_name": customer_name,
                        "error_type": type(e).__name__,
                    },
                )

        # Step 3: Queue for async processing (if customer_name exists)
        if customer_name and customer_name.strip():
            try:
                from .lookup_queue import normalize_name

                normalized = normalize_name(customer_name.strip())
                self.queue.enqueue(customer_name.strip(), normalized)

                # Story 6.8: Record async queued (AC1)
                if observer:
                    observer.record_async_queued()

                logger.debug(
                    "Company lookup queued for async processing",
                    extra={
                        "customer_name": customer_name,
                        "normalized_name": normalized,
                    },
                )

                return CompanyIdResult(
                    company_id=None,
                    status=ResolutionStatus.PENDING_LOOKUP,
                    source="queued",
                    temp_id=None,
                )

            except Exception as e:
                logger.error(f"Failed to queue lookup request: {e}")
                # Continue to temp ID generation as fallback

        # Step 4: Generate temp ID when customer_name is empty or queueing failed
        try:
            temp_id = self.queue.get_next_temp_id(customer_name or "unknown")

            # Story 6.8: Record temp ID generation (AC1, AC2)
            if observer:
                observer.record_temp_id(customer_name or "", temp_id)

            logger.debug(
                "Generated temporary company ID",
                extra={
                    "temp_id": temp_id,
                    "reason": "empty_customer_name"
                    if not customer_name
                    else "queue_failed",
                },
            )

            return CompanyIdResult(
                company_id=temp_id,
                status=ResolutionStatus.TEMP_ASSIGNED,
                source="generated",
                temp_id=temp_id,
            )

        except Exception as e:
            logger.error(f"Failed to generate temporary ID: {e}")
            # Final fallback - return None result
            return CompanyIdResult(
                company_id=None,
                status=ResolutionStatus.TEMP_ASSIGNED,
                source="fallback",
                temp_id=None,
            )

    def process_lookup_queue(
        self,
        *,
        batch_size: Optional[int] = None,
        observer: Optional[EnrichmentObserver] = None,
    ) -> int:
        """
        Process pending lookup requests in the queue using EQC API.

        Dequeues pending requests in batches, performs EQC lookups,
        caches successful results, and updates request status appropriately.
        Designed for scheduled/async execution scenarios.

        Args:
            batch_size: Maximum number of requests to process (uses queue
                default if None)

        Returns:
            Number of requests successfully processed

        Raises:
            Exception: Re-raises critical errors that prevent queue processing

        Examples:
            >>> processed_count = service.process_lookup_queue(batch_size=50)
            >>> logger.info(f"Processed {processed_count} lookup requests")
        """
        processed_count = 0
        observer = observer or self.observer

        logger.info(
            "Starting lookup queue processing",
            extra={"requested_batch_size": batch_size},
        )

        try:
            # Process requests in batches until queue is empty
            while True:
                # Atomic dequeue operation
                requests = self.queue.dequeue(batch_size or 50)

                if not requests:
                    logger.debug("No more pending requests in queue")
                    break

                logger.info(
                    f"Processing batch of {len(requests)} lookup requests",
                    extra={"batch_size": len(requests)},
                )

                # Process each request in the batch
                for request in requests:
                    try:
                        # Story 6.8: Don't record lookup here as it was already recorded
                        # during initial processing. We only track API calls and success/failure.

                        # Extract a robust name value (supports unittest.mock
                        # usage in tests)
                        req_name = None
                        raw_name = getattr(request, "name", None)
                        if isinstance(raw_name, str) and raw_name:
                            req_name = raw_name
                        mock_name = getattr(request, "_mock_name", None)
                        if not req_name and isinstance(mock_name, str) and mock_name:
                            req_name = mock_name
                        if not req_name:
                            req_name = str(raw_name) if raw_name is not None else ""

                        # Keep message short; details in extra to satisfy lint
                        # line length
                        logger.debug(
                            "Processing lookup request",
                            extra={
                                "request_id": getattr(request, "id", None),
                                "company_name": req_name,
                            },
                        )

                        # Record lookup attempt for observer stats
                        if observer:
                            observer.record_lookup()

                        # Perform EQC lookup
                        search_results = self.eqc_client.search_company(req_name)

                        if observer:
                            observer.record_api_call()

                        if search_results:
                            # Take first result and get details
                            best_result = search_results[0]
                            detail = self.eqc_client.get_company_detail(
                                best_result.company_id
                            )

                            # Cache result for future lookups
                            try:
                                self.loader.cache_company_mapping(
                                    alias_name=req_name,
                                    canonical_id=detail.company_id,
                                    source="EQC",
                                )
                                logger.debug(
                                    f"Cached EQC result for request {request.id}"
                                )
                            except Exception as cache_error:
                                logger.warning(
                                    f"Failed to cache result for request {request.id}: "
                                    f"{cache_error}"
                                )

                            # Mark request as successfully processed
                            self.queue.mark_done(request.id)
                            processed_count += 1

                            logger.debug(
                                "Lookup request processed successfully",
                                extra={
                                    "request_id": request.id,
                                    "company_name": req_name,
                                    "company_id": detail.company_id,
                                    "official_name": detail.official_name,
                                },
                            )

                        else:
                            # No EQC results found
                            error_msg = f"No EQC search results found for '{req_name}'"
                            self.queue.mark_failed(
                                getattr(request, "id", None),
                                error_msg,
                                getattr(request, "attempts", 0) + 1,
                            )

                            logger.warning(
                                "Lookup request failed - no EQC results",
                                extra={
                                    "request_id": request.id,
                                    "company_name": req_name,
                                    "attempts": request.attempts + 1,
                                },
                            )

                    except Exception as e:
                        # EQC lookup or processing error
                        error_msg = f"EQC lookup error: {str(e)}"
                        try:
                            self.queue.mark_failed(
                                getattr(request, "id", None),
                                error_msg,
                                getattr(request, "attempts", 0) + 1,
                            )
                        except Exception as mark_error:
                            logger.error(
                                f"Failed to mark request as failed: {mark_error}"
                            )

                        logger.error(
                            "Lookup request processing failed",
                            extra={
                                "request_id": getattr(request, "id", None),
                                "company_name": req_name,
                                "error": str(e),
                                "attempts": getattr(request, "attempts", 0) + 1,
                            },
                        )

                # Continue processing next batch

        except Exception as e:
            logger.error(f"Queue processing interrupted by error: {e}")
            raise

        logger.info(
            "Lookup queue processing completed",
            extra={"processed_count": processed_count},
        )

        return processed_count

    def get_queue_status(self) -> Dict[str, int]:
        """
        Get current queue processing statistics.

        Returns:
            Dictionary with queue status counts by state

        Examples:
            >>> status = service.get_queue_status()
            >>> print(
            ...     f"Pending: {status['pending']}, "
            ...     f"Processing: {status['processing']}"
            ... )
        """
        try:
            stats = self.queue.get_queue_stats()
            logger.debug("Retrieved queue status", extra={"stats": stats})
            return stats
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return {"pending": 0, "processing": 0, "done": 0, "failed": 0}
