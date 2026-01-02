"""
Backflow and async enrichment operations.

This module handles backflow of new mappings to database cache,
async enrichment queue operations, and temp ID generation.

Story 7.3: Infrastructure Layer Decomposition
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

# Import normalize functions via facade for monkeypatch compatibility
# Tests patch company_id_resolver.normalize_* (Story 7.3 AC-4)
from work_data_hub.infrastructure.enrichment import company_id_resolver as _facade
from work_data_hub.infrastructure.enrichment.normalizer import generate_temp_company_id
from work_data_hub.infrastructure.enrichment.types import ResolutionStrategy
from work_data_hub.utils.logging import get_logger

if TYPE_CHECKING:
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

logger = get_logger(__name__)


def backflow_new_mappings(
    df: pd.DataFrame,
    resolved_indices: List[int],
    strategy: ResolutionStrategy,
    mapping_repository: "CompanyMappingRepository",
) -> Dict[str, int]:
    """
    Backflow new mappings to database cache.

    Collects mappings from rows resolved via existing column and inserts
    them into the database for future cache hits.

    Story 6.4.1: P4 (customer_name) uses normalized values for backflow,
    while P2 (account_number), P5 (account_name) use RAW values.

    Story 7.5-1: P1 (plan_code) added for backflow support, enabling
    subsequent ETL executions to hit enrichment_index cache for plan_code lookups.

    Args:
        df: DataFrame with resolved company IDs.
        resolved_indices: Indices of rows resolved via existing column.
        strategy: Resolution strategy configuration.
        mapping_repository: Repository for database operations.

    Returns:
        Dict with keys: inserted, skipped, conflicts
    """
    new_mappings: List[Dict[str, Any]] = []
    # Story 6.4.1: P4 (customer_name) needs normalization, others use RAW values
    # Story 7.5-1: P1 (plan_code) added for backflow support
    backflow_fields = [
        (strategy.plan_code_column, "plan", 1, False),  # P1: RAW (plan_code)
        (strategy.account_number_column, "account", 2, False),  # P2: RAW
        (strategy.customer_name_column, "name", 4, True),  # P4: NORMALIZED
        (strategy.account_name_column, "account_name", 5, False),  # P5: RAW
    ]

    for idx in resolved_indices:
        row = df.loc[idx]
        company_id = str(row[strategy.output_column])

        # Skip temporary IDs
        if company_id.startswith("IN"):
            continue

        for column, match_type, priority, needs_normalization in backflow_fields:
            if column not in df.columns:
                continue
            alias_value = row.get(column)
            if pd.isna(alias_value) or not str(alias_value).strip():
                continue

            # Story 6.4.1: Apply normalization for P4 only
            if needs_normalization:
                alias_name = _facade.normalize_company_name(str(alias_value))
                if not alias_name:
                    continue  # Skip if normalization returns empty
            else:
                alias_name = str(alias_value).strip()

            new_mappings.append(
                {
                    "alias_name": alias_name,
                    "canonical_id": company_id,
                    "match_type": match_type,
                    "priority": priority,
                    "source": "pipeline_backflow",
                }
            )

    if not new_mappings:
        return {"inserted": 0, "skipped": 0, "conflicts": 0}

    try:
        result = mapping_repository.insert_batch_with_conflict_check(new_mappings)

        if result.conflicts:
            logger.warning(
                "company_id_resolver.backflow.conflicts_detected",
                conflict_count=len(result.conflicts),
            )

        logger.info(
            "company_id_resolver.backflow.completed",
            inserted=result.inserted_count,
            skipped=result.skipped_count,
            conflicts=len(result.conflicts),
        )

        return {
            "inserted": result.inserted_count,
            "skipped": result.skipped_count,
            "conflicts": len(result.conflicts),
        }

    except Exception as e:
        logger.warning(
            "company_id_resolver.backflow.failed",
            error=str(e),
        )
        return {"inserted": 0, "skipped": 0, "conflicts": 0}


def enqueue_for_async_enrichment(
    df: pd.DataFrame,
    temp_id_indices: List[int],
    strategy: ResolutionStrategy,
    mapping_repository: "CompanyMappingRepository",
) -> int:
    """
    Enqueue unresolved company names for async enrichment (Story 6.5).

    Called after temp ID generation to queue names for background
    resolution via the enterprise.enrichment_requests table.

    Args:
        df: DataFrame with resolved company IDs (including temp IDs).
        temp_id_indices: Indices of rows that received temp IDs.
        strategy: Resolution strategy configuration.
        mapping_repository: Repository for database operations.

    Returns:
        Number of requests actually enqueued (excludes duplicates).
    """
    if not temp_id_indices:
        return 0

    # Build enqueue requests using normalize_for_temp_id for dedup parity
    enqueue_requests: List[Dict[str, str]] = []
    seen_normalized: set[str] = set()

    for idx in temp_id_indices:
        row = df.loc[idx]
        raw_name = row.get(strategy.customer_name_column)
        temp_id = row.get(strategy.output_column)

        if pd.isna(raw_name) or not str(raw_name).strip():
            continue

        raw_name_str = str(raw_name)
        normalized = _facade.normalize_for_temp_id(raw_name_str)

        # Deduplicate within batch by normalized name
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)

        enqueue_requests.append(
            {
                "raw_name": raw_name_str,
                "normalized_name": normalized,
                "temp_id": str(temp_id) if pd.notna(temp_id) else "",
            }
        )

    if not enqueue_requests:
        return 0

    # Graceful degradation: enqueue failures don't block pipeline
    try:
        result = mapping_repository.enqueue_for_enrichment(enqueue_requests)

        logger.info(
            "company_id_resolver.async_enqueue.completed",
            queued_count=result.queued_count,
            skipped_count=result.skipped_count,
        )

        return result.queued_count

    except Exception as e:
        logger.warning(
            "company_id_resolver.async_enqueue.failed",
            error=str(e),
        )
        return 0


# Known empty placeholders in source data (Excel exports).
# These values indicate missing/unknown customer names and should return None
# instead of generating temp IDs. See Story 7.5-3 and INVALID_PLACEHOLDERS in normalizer.py.
#
# IMPORTANT: If adding new placeholders, also update:
# - src/work_data_hub/infrastructure/enrichment/normalizer.py INVALID_PLACEHOLDERS list
# - Test coverage in TestGenerateTempId class
#
# History:
# - Story 7.5-3 (2026-01-02): Initial constant with ("0", "空白")
# - CRITICAL-002 fix: Removed incorrect (空白) → 600866980 mapping from enrichment_index.csv
EMPTY_PLACEHOLDERS = ("0", "空白")


def generate_temp_id(customer_name: Optional[str], salt: str) -> Optional[str]:
    """
    Generate temporary company ID using HMAC-SHA1.

    Story 7.5-3: Returns None for empty customer names instead of
    a shared temp ID. This ensures proper semantics: temp IDs represent
    "unresolved but known company names", while NULL represents
    "no company information available".

    Args:
        customer_name: Customer name to generate ID for.
        salt: Salt for HMAC generation.

    Returns:
        Temporary ID in format "IN<16-char-Base32>", or None for empty names.
    """
    # Story 7.5-3: Return None for empty/unknown customer names
    if (
        customer_name is None
        or pd.isna(customer_name)
        or not str(customer_name).strip()
        or str(customer_name).strip() in EMPTY_PLACEHOLDERS
    ):
        return None

    return generate_temp_company_id(str(customer_name), salt)
