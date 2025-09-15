"""
Company enrichment service layer with pure transformation functions.

This module provides the core business logic for company ID resolution,
replicating the exact priority-based lookup logic from legacy _update_company_id
method while providing a clean, testable interface.
"""

import logging
from typing import Dict, List

from .models import CompanyMappingQuery, CompanyMappingRecord, CompanyResolutionResult

logger = logging.getLogger(__name__)


def resolve_company_id(
    mappings: List[CompanyMappingRecord],
    query: CompanyMappingQuery
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
            "account_name": query.account_name
        }
    )

    # Build lookup dictionaries by match_type for O(1) access
    # This replaces the individual COMPANY_ID*_MAPPING dictionaries from legacy
    lookup: Dict[str, Dict[str, CompanyMappingRecord]] = {}
    for mapping in mappings:
        if mapping.match_type not in lookup:
            lookup[mapping.match_type] = {}
        lookup[mapping.match_type][mapping.alias_name] = mapping

    # Priority-based search matching legacy precedence EXACTLY
    # This replicates the step-by-step logic from AnnuityPerformanceCleaner._clean_method
    search_steps = [
        ("plan", query.plan_code, "Plan code lookup (COMPANY_ID1_MAPPING)"),
        ("account", query.account_number, "Account number lookup (COMPANY_ID2_MAPPING)"),
        ("hardcode", query.plan_code, "Hardcode lookup (COMPANY_ID3_MAPPING)"),
        ("name", query.customer_name, "Customer name lookup (COMPANY_ID4_MAPPING)"),
        ("account_name", query.account_name, "Account name lookup (COMPANY_ID5_MAPPING)")
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
                priority=mapping.priority
            )
            logger.info(
                "Company ID resolved",
                extra={
                    "company_id": result.company_id,
                    "match_type": result.match_type,
                    "source_value": result.source_value,
                    "priority": result.priority
                }
            )
            return result

    # CRITICAL: Default fallback logic matching legacy behavior
    # From data_cleaner.py line 215-217: when company_id is empty AND customer_name is empty,
    # apply hardcode mapping with fallback to '600866980'
    if not query.customer_name:
        logger.debug("Applying default fallback logic - customer_name is None/empty")
        result = CompanyResolutionResult(
            company_id="600866980",
            match_type="default",
            source_value=None,
            priority=None
        )
        logger.info(
            "Applied default fallback",
            extra={"company_id": result.company_id, "reason": "empty_customer_name"}
        )
        return result

    # No match found and customer_name is not empty
    logger.info("No company ID match found", extra={"query_fields_provided": [
        f"plan_code={query.plan_code}",
        f"account_number={query.account_number}",
        f"customer_name={query.customer_name}",
        f"account_name={query.account_name}"
    ]})

    return CompanyResolutionResult(
        company_id=None,
        match_type=None,
        source_value=None,
        priority=None
    )


def build_mapping_lookup(mappings: List[CompanyMappingRecord]) -> Dict[str, Dict[str, str]]:
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
            "total_mappings": sum(len(type_mappings) for type_mappings in lookup.values())
        }
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
    seen_aliases: Dict[str, Dict[str, str]] = {}  # {match_type: {alias_name: canonical_id}}

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
        "account_name": 5
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
            extra={"warnings_count": len(warnings), "warnings": warnings[:5]}  # Log first 5
        )

    return warnings
