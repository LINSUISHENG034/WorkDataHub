"""
Database cache resolution strategies.

This module handles Step 2 of the resolution priority: DB cache lookup
via enrichment_index.

Note: company_mapping table removed in Story 7.1-4 (Zero Legacy).
All legacy fallback code has been removed.

Story 7.3: Infrastructure Layer Decomposition
"""

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import pandas as pd

from work_data_hub.utils.logging import get_logger

from ..normalizer import normalize_for_temp_id
from ..types import (
    EnrichmentIndexRecord,
    LookupType,
    ResolutionStatistics,
    ResolutionStrategy,
)

if TYPE_CHECKING:
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

logger = get_logger(__name__)
_stdlib_logger = logging.getLogger(__name__)


def resolve_via_db_cache(
    df: pd.DataFrame,
    mask_unresolved: pd.Series,
    strategy: ResolutionStrategy,
    stats: Optional[ResolutionStatistics],
    mapping_repository: "CompanyMappingRepository",
) -> Tuple[pd.Series, Dict[str, int]]:
    """
    Resolve company_id via database cache (enrichment_index).

    Uses CompanyMappingRepository.lookup_enrichment_index_batch() for
    batch-optimized single SQL round-trip.

    Note: company_mapping table removed in Story 7.1-4 (Zero Legacy).
    All legacy fallback code has been removed.

    Story 6.4.1: P4 (customer_name) uses normalized values for lookup,
    while P1 (plan_code), P2 (account_number), P5 (account_name) use RAW values.

    Args:
        df: Input DataFrame.
        mask_unresolved: Boolean mask of unresolved rows.
        strategy: Resolution strategy configuration.
        stats: Optional ResolutionStatistics for tracking decision paths.
        mapping_repository: Repository for database lookups.

    Returns:
        Tuple of (resolved_series, hits_by_priority)
    """
    # Note: company_mapping fallback removed in Story 7.1-4
    # Direct resolution via enrichment_index (Story 6.1.1)
    return _resolve_via_enrichment_index(
        df, mask_unresolved, strategy, stats, mapping_repository
    )


def _resolve_via_enrichment_index(
    df: pd.DataFrame,
    mask_unresolved: pd.Series,
    strategy: ResolutionStrategy,
    stats: Optional[ResolutionStatistics],
    mapping_repository: "CompanyMappingRepository",
) -> Tuple[pd.Series, Dict[str, int]]:
    """
    Resolve company_id via enrichment_index (DB-P1..P5).

    Priority order: plan_code → account_name → account_number →
    customer_name (normalized) → plan_customer (plan|normalized_customer).
    """
    keys_by_type: Dict[LookupType, set[str]] = {
        LookupType.PLAN_CODE: set(),
        LookupType.ACCOUNT_NAME: set(),
        LookupType.ACCOUNT_NUMBER: set(),
        LookupType.CUSTOMER_NAME: set(),
        LookupType.PLAN_CUSTOMER: set(),
    }

    for idx in df[mask_unresolved].index:
        row = df.loc[idx]
        plan_code = row.get(strategy.plan_code_column)
        account_name = row.get(strategy.account_name_column)
        account_number = row.get(strategy.account_number_column)
        customer_name = row.get(strategy.customer_name_column)

        if pd.notna(plan_code):
            keys_by_type[LookupType.PLAN_CODE].add(str(plan_code))
        if pd.notna(account_name):
            keys_by_type[LookupType.ACCOUNT_NAME].add(str(account_name))
        if pd.notna(account_number):
            keys_by_type[LookupType.ACCOUNT_NUMBER].add(str(account_number))
        if pd.notna(customer_name):
            normalized_customer = normalize_for_temp_id(str(customer_name))
            if normalized_customer:
                keys_by_type[LookupType.CUSTOMER_NAME].add(normalized_customer)
                if pd.notna(plan_code):
                    plan_customer_key = f"{plan_code}|{normalized_customer}"
                    keys_by_type[LookupType.PLAN_CUSTOMER].add(plan_customer_key)

    # Remove empty entry types to avoid unnecessary UNNEST arrays
    keys_by_type = {
        key_type: list(keys) for key_type, keys in keys_by_type.items() if keys
    }

    if not keys_by_type:
        return (
            pd.Series(pd.NA, index=df.index, dtype=object),
            {
                "plan_code": 0,
                "account_name": 0,
                "account_number": 0,
                "customer_name": 0,
                "plan_customer": 0,
            },
        )

    resolved = pd.Series(pd.NA, index=df.index, dtype=object)
    used_keys: list[tuple[LookupType, str]] = []
    hits_by_priority: Dict[str, int] = {
        "plan_code": 0,
        "account_name": 0,
        "account_number": 0,
        "customer_name": 0,
        "plan_customer": 0,
    }
    decision_paths: Dict[int, str] = {}

    try:
        results = mapping_repository.lookup_enrichment_index_batch(keys_by_type)
    except Exception as e:
        logger.warning(
            "company_id_resolver.enrichment_index_query_failed",
            error=str(e),
        )
        return (
            pd.Series(pd.NA, index=df.index, dtype=object),
            hits_by_priority,
        )

    # Apply priority order per row
    priority_order = [
        LookupType.PLAN_CODE,
        LookupType.ACCOUNT_NAME,
        LookupType.ACCOUNT_NUMBER,
        LookupType.CUSTOMER_NAME,
        LookupType.PLAN_CUSTOMER,
    ]
    label_by_type = {
        LookupType.PLAN_CODE: "plan_code",
        LookupType.ACCOUNT_NAME: "account_name",
        LookupType.ACCOUNT_NUMBER: "account_number",
        LookupType.CUSTOMER_NAME: "customer_name",
        LookupType.PLAN_CUSTOMER: "plan_customer",
    }
    path_label_by_type = {
        LookupType.PLAN_CODE: "DB-P1",
        LookupType.ACCOUNT_NAME: "DB-P2",
        LookupType.ACCOUNT_NUMBER: "DB-P3",
        LookupType.CUSTOMER_NAME: "DB-P4",
        LookupType.PLAN_CUSTOMER: "DB-P5",
    }

    for idx in df[mask_unresolved].index:
        row = df.loc[idx]
        plan_code = row.get(strategy.plan_code_column)
        account_name = row.get(strategy.account_name_column)
        account_number = row.get(strategy.account_number_column)
        customer_name = row.get(strategy.customer_name_column)
        normalized_customer = (
            normalize_for_temp_id(str(customer_name)) if pd.notna(customer_name) else ""
        )

        candidate_keys = {
            LookupType.PLAN_CODE: str(plan_code) if pd.notna(plan_code) else None,
            LookupType.ACCOUNT_NAME: str(account_name)
            if pd.notna(account_name)
            else None,
            LookupType.ACCOUNT_NUMBER: str(account_number)
            if pd.notna(account_number)
            else None,
            LookupType.CUSTOMER_NAME: normalized_customer or None,
            LookupType.PLAN_CUSTOMER: f"{plan_code}|{normalized_customer}"
            if pd.notna(plan_code) and normalized_customer
            else None,
        }

        path_segments: List[str] = []

        for lookup_type in priority_order:
            key = candidate_keys.get(lookup_type)
            label = path_label_by_type[lookup_type]
            priority_key = label_by_type[lookup_type]
            if not key:
                path_segments.append(f"{label}:MISS")
                continue

            record = results.get((lookup_type, key))
            if isinstance(record, EnrichmentIndexRecord):
                company_id = str(record.company_id).strip()
                # Validate cache entries: reject obvious placeholders like 'N' or empty values.
                invalid_sentinels = {"N", "NA", "N/A", "NONE", "NULL", "NAN"}
                if not company_id or company_id.upper() in invalid_sentinels:
                    path_segments.append(f"{label}:INVALID")
                    continue
                resolved.loc[idx] = company_id
                used_keys.append((lookup_type, key))
                hits_by_priority[priority_key] += 1
                path_segments.append(f"{label}:HIT")
                break
            else:
                path_segments.append(f"{label}:MISS")

        decision_paths[idx] = "→".join(path_segments)

    for row_idx, path in decision_paths.items():
        logger.debug(
            "company_id_resolver.db_cache_decision_path",
            index=int(row_idx),
            path=path,
            decision_path=path,
        )
        _stdlib_logger.debug(
            "company_id_resolver.db_cache_decision_path index=%s path=%s",
            int(row_idx),
            path,
        )

    decision_path_counts: Dict[str, int] = {}
    for path in decision_paths.values():
        decision_path_counts[path] = decision_path_counts.get(path, 0) + 1

    if stats is not None:
        stats.db_decision_path_counts = decision_path_counts

    # Emit summary metrics/logs for per-priority hits (observable counters)
    logger.info(
        "company_id_resolver.db_cache_priority_summary",
        hits_by_priority=hits_by_priority,
        total_hits=sum(hits_by_priority.values()),
        resolved_rows=int(resolved.notna().sum()),
    )
    logger.info(
        "company_id_resolver.db_cache_metrics",
        hits_by_priority=hits_by_priority,
        decision_path_counts=decision_path_counts,
        total_hits=sum(hits_by_priority.values()),
        resolved_rows=int(resolved.notna().sum()),
    )
    _stdlib_logger.info(
        "company_id_resolver.db_cache_metrics total_hits=%s resolved_rows=%s hits_by_priority=%s decision_path_counts=%s",
        sum(hits_by_priority.values()),
        int(resolved.notna().sum()),
        dict(hits_by_priority),
        decision_path_counts,
    )

    # Increment hit_count on matched records (best-effort)
    if used_keys and callable(getattr(mapping_repository, "update_hit_count", None)):
        for lookup_type, key in used_keys:
            try:
                mapping_repository.update_hit_count(key, lookup_type)
            except Exception:
                # Non-blocking
                continue

    return resolved, hits_by_priority


# Note: _resolve_via_company_mapping() removed in Story 7.1-4 (Zero Legacy)
# All company_id resolution now uses enrichment_index (Story 6.1.1)
