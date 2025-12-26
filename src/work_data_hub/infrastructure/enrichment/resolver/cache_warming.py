"""
Cache warming for CompanyIdResolver.

This module provides pre-batch cache warming functionality to optimize
EQC API performance by reducing cache misses through proactive enrichment_index
lookups.

Story 7.1-14: EQC API Performance Optimization
Task 2: Cache Optimization (AC-2) - Highest ROI

The cache warming strategy:
1. Extract all unique company names from input DataFrame before processing
2. Batch query enrichment_index once (single SQL round-trip)
3. Build in-memory cache for all strategies to share
4. Only cache misses trigger EQC API calls

Expected Impact: >80% cache hit rate for repeated company names
"""

from typing import TYPE_CHECKING, Dict, List

import pandas as pd

from work_data_hub.utils.logging import get_logger

from ..normalizer import normalize_for_temp_id
from ..types import LookupType

if TYPE_CHECKING:
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

logger = get_logger(__name__)


def extract_unique_customer_names(
    df: pd.DataFrame,
    customer_name_column: str,
) -> List[str]:
    """
    Extract unique customer names from DataFrame for cache warming.

    Args:
        df: Input DataFrame.
        customer_name_column: Name of the column containing customer names.

    Returns:
        List of unique customer names (normalized for cache lookup).
    """
    if customer_name_column not in df.columns:
        return []

    # Get unique non-null customer names
    unique_names = df[customer_name_column].dropna().unique().tolist()

    # Normalize for cache lookup (P4 uses normalized values)
    normalized_names = [
        normalize_for_temp_id(str(name))
        for name in unique_names
        if name and pd.notna(name)
    ]

    # Remove duplicates after normalization
    unique_normalized = list(set(normalized_names))

    logger.debug(
        "company_id_resolver.extracted_unique_names",
        total_rows=len(df),
        unique_names_raw=len(unique_names),
        unique_names_normalized=len(unique_normalized),
    )

    return unique_normalized


def warm_cache_with_customer_names(
    unique_customer_names: List[str],
    mapping_repository: "CompanyMappingRepository",
) -> Dict[str, str]:
    """
    Warm cache by pre-fetching enrichment_index entries for all customer names.

    This performs a single SQL batch query to fetch all known company_ids
    for the given customer names, building an in-memory cache to avoid
    repeated database lookups during row-by-row resolution.

    Args:
        unique_customer_names: List of normalized customer names to lookup.
        mapping_repository: Repository for database lookups.

    Returns:
        Dictionary mapping {customer_name: company_id} for cache hits.
    """
    if not unique_customer_names:
        logger.debug("company_id_resolver.cache_warming_skipped", reason="no_names")
        return {}

    # Build lookup keys for enrichment_index (P4: customer_name)
    keys_by_type = {
        LookupType.CUSTOMER_NAME: set(unique_customer_names),
    }

    try:
        # Single SQL batch query for all names
        # Returns Dict[tuple[LookupType, str], EnrichmentIndexRecord]
        results = mapping_repository.lookup_enrichment_index_batch(keys_by_type)

        # Build in-memory cache: {customer_name: company_id}
        # Fix: iterate over .values() to get records, not dict keys (tuples)
        cache = {
            record.lookup_key: record.company_id
            for record in results.values()
            if record.lookup_type == LookupType.CUSTOMER_NAME
        }

        cache_hits = len(cache)
        cache_misses = len(unique_customer_names) - cache_hits
        cache_hit_rate = (
            cache_hits / len(unique_customer_names) if unique_customer_names else 0
        )

        logger.info(
            "company_id_resolver.cache_warming_complete",
            total_names=len(unique_customer_names),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_hit_rate=f"{cache_hit_rate:.1%}",
        )

        return cache

    except Exception as e:
        logger.warning(
            "company_id_resolver.cache_warming_failed",
            error=str(e),
            msg="Cache warming failed, will fall back to on-demand lookups",
        )
        return {}


class CacheWarmer:
    """
    Cache warming manager for CompanyIdResolver.

    Provides pre-batch cache warming to reduce EQC API calls by proactively
    populating an in-memory cache from enrichment_index before resolution begins.

    Usage:
        >>> warmer = CacheWarmer(mapping_repository)
        >>> cache = warmer.warm_cache(df, customer_name_column="客户名称")
        >>> # cache is now available for all resolution strategies
    """

    def __init__(
        self,
        mapping_repository: "CompanyMappingRepository",
    ) -> None:
        """
        Initialize cache warmer.

        Args:
            mapping_repository: Repository for database lookups.
        """
        self.mapping_repository = mapping_repository
        self._cache: Dict[str, str] = {}

    def warm_cache(
        self,
        df: pd.DataFrame,
        customer_name_column: str,
    ) -> Dict[str, str]:
        """
        Warm cache with unique customer names from DataFrame.

        Performs cache warming in two steps:
        1. Extract unique customer names from DataFrame
        2. Batch query enrichment_index for all names

        The resulting cache can be accessed via the `.cache` property.

        Args:
            df: Input DataFrame.
            customer_name_column: Name of the column containing customer names.

        Returns:
            Dictionary mapping {customer_name: company_id} for cache hits.
        """
        # Step 1: Extract unique names
        unique_names = extract_unique_customer_names(df, customer_name_column)

        # Step 2: Batch query enrichment_index
        self._cache = warm_cache_with_customer_names(
            unique_names,
            self.mapping_repository,
        )

        return self._cache

    @property
    def cache(self) -> Dict[str, str]:
        """Get the in-memory cache dictionary."""
        return self._cache

    def lookup(self, customer_name: str) -> str | None:
        """
        Lookup customer name in warmed cache.

        Args:
            customer_name: Normalized customer name to lookup.

        Returns:
            company_id if found in cache, None otherwise.
        """
        normalized = normalize_for_temp_id(str(customer_name))
        return self._cache.get(normalized)

    def cache_hit_rate(self, total_names: int) -> float:
        """
        Calculate cache hit rate.

        Args:
            total_names: Total number of unique names processed.

        Returns:
            Cache hit rate as a percentage (0.0 to 1.0).
        """
        if total_names == 0:
            return 0.0
        return len(self._cache) / total_names
