"""
EQC sync resolution strategies.

This module handles Step 4 of the resolution priority: EQC sync lookup
with budget management, caching, and error handling.

Story 7.3: Infrastructure Layer Decomposition
"""

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import pandas as pd

from work_data_hub.infrastructure.cleansing import normalize_company_name
from work_data_hub.utils.logging import get_logger

from ..eqc_lookup_config import EqcLookupConfig
from ..normalizer import normalize_for_temp_id
from ..types import ResolutionStrategy

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
    from work_data_hub.infrastructure.enrichment.eqc_provider import EqcProvider
    from work_data_hub.infrastructure.enrichment.mapping_repository import (
        CompanyMappingRepository,
    )

logger = get_logger(__name__)


def resolve_via_eqc_sync(
    df: pd.DataFrame,
    mask_unresolved: pd.Series,
    strategy: ResolutionStrategy,
    eqc_config: EqcLookupConfig,
    eqc_provider: Optional["EqcProvider"],
    enrichment_service: Optional["CompanyEnrichmentService"],
    mapping_repository: Optional["CompanyMappingRepository"],
) -> Tuple[pd.Series, int, int]:
    """
    Resolve via EQC within budget; cache results to enrichment_index.

    Note: company_mapping table removed in Story 7.1-4 (Zero Legacy).
    All EQC results now cached to enrichment_index (Story 6.1.1).

    Story 6.6: Supports both EqcProvider (preferred) and legacy enrichment_service.

    Args:
        df: Input DataFrame.
        mask_unresolved: Boolean mask of unresolved rows.
        strategy: Resolution strategy configuration.
        eqc_config: EQC lookup configuration.
        eqc_provider: Optional EqcProvider for API lookups.
        enrichment_service: Optional legacy enrichment service.
        mapping_repository: Optional repository for caching results.

    Returns:
        Tuple of (resolved_series, eqc_hits, budget_remaining)
    """
    # Story 6.6: Use EqcProvider if available, otherwise fall back to enrichment_service
    use_eqc_provider = eqc_provider is not None and eqc_provider.is_available
    use_enrichment_service = enrichment_service is not None and not use_eqc_provider

    # Story 6.2-P17: Budget is controlled by eqc_config, not strategy.
    if not (use_eqc_provider or use_enrichment_service) or eqc_config.sync_budget <= 0:
        return (
            pd.Series(pd.NA, index=df.index, dtype=object),
            0,
            eqc_config.sync_budget,
        )

    # Story 6.6: Use EqcProvider path if available
    if use_eqc_provider:
        return _resolve_via_eqc_provider(
            df, mask_unresolved, strategy, eqc_config, eqc_provider
        )

    # Legacy path using enrichment_service
    return _resolve_via_enrichment_service(
        df,
        mask_unresolved,
        strategy,
        eqc_config,
        enrichment_service,
        mapping_repository,
    )


def _resolve_via_eqc_provider(
    df: pd.DataFrame,
    mask_unresolved: pd.Series,
    strategy: ResolutionStrategy,
    eqc_config: EqcLookupConfig,
    eqc_provider: "EqcProvider",
) -> Tuple[pd.Series, int, int]:
    """
    Resolve via EqcProvider (Story 6.6).

    Uses the new EqcProvider adapter for EQC API lookups with built-in
    budget management, caching, and error handling.

    Args:
        df: Input DataFrame.
        mask_unresolved: Boolean mask of unresolved rows.
        strategy: Resolution strategy configuration.
        eqc_config: EQC lookup configuration.
        eqc_provider: EqcProvider for API lookups.

    Returns:
        Tuple of (resolved_series, eqc_hits, budget_remaining)
    """
    resolved = pd.Series(pd.NA, index=df.index, dtype=object)
    eqc_hits = 0

    # EqcProvider manages its own budget internally
    # Story 6.2-P17: Set provider budget to match EqcLookupConfig budget (SSOT).
    if eqc_provider.budget != eqc_config.sync_budget:
        eqc_provider.budget = eqc_config.sync_budget
        eqc_provider.remaining_budget = eqc_config.sync_budget

    # Deduplicate by normalized customer name so budget is consumed per-unique name
    # (not per-row), and apply a successful hit to all matching rows.
    unresolved_name_series = df.loc[mask_unresolved, strategy.customer_name_column]
    indices_by_name: Dict[str, List[int]] = {}
    exemplar_raw_by_name: Dict[str, str] = {}
    for idx, raw_name in unresolved_name_series.items():
        if pd.isna(raw_name):
            continue
        raw_text = str(raw_name).strip()
        if not raw_text:
            continue
        normalized_name = normalize_for_temp_id(raw_text) or raw_text
        indices_by_name.setdefault(normalized_name, []).append(idx)
        exemplar_raw_by_name.setdefault(normalized_name, raw_text)

    for normalized_name, indices in indices_by_name.items():
        # Check if provider still has budget
        if not eqc_provider.is_available:
            break

        try:
            # EqcProvider.lookup() handles budget, caching, and errors internally
            result = eqc_provider.lookup(exemplar_raw_by_name[normalized_name])

            if result:
                for idx in indices:
                    resolved.loc[idx] = result.company_id
                eqc_hits += len(indices)

        except Exception as e:
            logger.warning(
                "company_id_resolver.eqc_provider_lookup_failed",
                error_type=type(e).__name__,
            )
            # Continue to next name - don't block pipeline

    budget_remaining = eqc_provider.remaining_budget

    logger.info(
        "company_id_resolver.eqc_provider_completed",
        eqc_hits=eqc_hits,
        budget_remaining=budget_remaining,
    )

    return resolved, eqc_hits, budget_remaining


def _resolve_via_enrichment_service(
    df: pd.DataFrame,
    mask_unresolved: pd.Series,
    strategy: ResolutionStrategy,
    eqc_config: EqcLookupConfig,
    enrichment_service: "CompanyEnrichmentService",
    mapping_repository: Optional["CompanyMappingRepository"],
) -> Tuple[pd.Series, int, int]:
    """
    Legacy path: resolve via enrichment_service.

    Args:
        df: Input DataFrame.
        mask_unresolved: Boolean mask of unresolved rows.
        strategy: Resolution strategy configuration.
        eqc_config: EQC lookup configuration.
        enrichment_service: Legacy enrichment service.
        mapping_repository: Optional repository for caching results.

    Returns:
        Tuple of (resolved_series, eqc_hits, budget_remaining)
    """
    budget_remaining = eqc_config.sync_budget
    resolved = pd.Series(pd.NA, index=df.index, dtype=object)
    eqc_hits = 0

    cache_payloads: List[Dict[str, Any]] = []

    # Deduplicate by normalized customer name so budget is consumed per-unique name
    # (not per-row), and apply a successful hit to all matching rows.
    unresolved_name_series = df.loc[mask_unresolved, strategy.customer_name_column]
    indices_by_name: Dict[str, List[int]] = {}
    exemplar_row_by_name: Dict[str, pd.Series] = {}
    for idx, raw_name in unresolved_name_series.items():
        if pd.isna(raw_name):
            continue
        raw_text = str(raw_name).strip()
        if not raw_text:
            continue
        normalized_name = normalize_for_temp_id(raw_text) or raw_text
        indices_by_name.setdefault(normalized_name, []).append(idx)
        exemplar_row_by_name.setdefault(normalized_name, df.loc[idx])

    for normalized_name, indices in indices_by_name.items():
        if budget_remaining <= 0:
            break

        row = exemplar_row_by_name[normalized_name]
        customer_name = row.get(strategy.customer_name_column)
        if pd.isna(customer_name):
            continue

        try:
            result = enrichment_service.resolve_company_id(
                plan_code=row.get(strategy.plan_code_column)
                if pd.notna(row.get(strategy.plan_code_column))
                else None,
                customer_name=str(customer_name),
                account_name=row.get(strategy.account_name_column)
                if pd.notna(row.get(strategy.account_name_column))
                else None,
                sync_lookup_budget=1,
            )
            budget_remaining -= 1

            if result and result.company_id:
                for idx in indices:
                    resolved.loc[idx] = result.company_id
                eqc_hits += len(indices)

                cache_payloads.append(
                    {
                        # Align EQC cache entries with P4 normalization so lookups hit
                        "alias_name": normalize_company_name(str(customer_name))
                        or str(customer_name).strip(),
                        "canonical_id": result.company_id,
                        "match_type": "eqc",
                        "priority": 6,
                        "source": "eqc_sync",
                    }
                )

        except Exception as e:
            budget_remaining -= 1
            logger.warning(
                "company_id_resolver.eqc_lookup_failed",
                error=str(e),
            )
            # Continue to next name - don't block pipeline

    if cache_payloads and mapping_repository:
        # Deduplicate by alias_name/match_type to avoid redundant inserts
        deduped: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for payload in cache_payloads:
            key = (payload["alias_name"], payload["match_type"])
            deduped.setdefault(key, payload)

        try:
            mapping_repository.insert_batch_with_conflict_check(list(deduped.values()))
        except Exception as cache_err:
            logger.warning(
                "company_id_resolver.eqc_cache_failed",
                error=str(cache_err),
            )

    return resolved, eqc_hits, budget_remaining
