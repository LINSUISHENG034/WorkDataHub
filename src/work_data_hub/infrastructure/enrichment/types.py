"""
Type definitions for Company ID Resolution.

This module defines the configuration and result types used by the CompanyIdResolver
for batch company ID resolution with hierarchical strategy support.

Architecture Reference:
- AD-002: Temporary Company ID Generation
- AD-010: Infrastructure Layer

Story 6.4: Extended with multi-tier lookup statistics and backflow tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

import pandas as pd


class ResolutionSource(Enum):
    """Source of company ID resolution."""

    PLAN_OVERRIDE = "plan_override"
    YAML_OVERRIDE = "yaml_override"
    DB_CACHE = "db_cache"
    EXISTING_COLUMN = "existing_column"
    EQC_SYNC = "eqc_sync"
    ENRICHMENT_SERVICE = "enrichment_service"
    TEMP_ID = "temp_id"
    UNRESOLVED = "unresolved"


class MatchTypePriority(Enum):
    """
    Match type priority levels for company ID resolution.

    Lower number = higher priority.
    """

    PLAN = 1
    ACCOUNT = 2
    HARDCODE = 3
    NAME = 4
    ACCOUNT_NAME = 5
    EQC = 6
    TEMP = 7


@dataclass
class ResolutionStrategy:
    """
    Configuration for company ID resolution behavior.

    This dataclass defines which columns to use for resolution and what
    strategies to apply during the batch resolution process.

    Attributes:
        plan_code_column: Column name for plan codes (override lookup).
        customer_name_column: Column name for customer names (temp ID).
        account_name_column: Column name for account names (enrichment hint).
        account_number_column: Column name for account numbers (Story 6.4).
        company_id_column: Column name for existing company IDs to preserve.
        output_column: Column name for the resolved company ID output.
        use_enrichment_service: Whether to use enrichment service.
        sync_lookup_budget: Maximum synchronous API lookups allowed.
        generate_temp_ids: Whether to generate temp IDs for unresolved.
        enable_backflow: Whether to backflow new mappings to database (Story 6.4).
    """

    plan_code_column: str = "计划代码"
    customer_name_column: str = "客户名称"
    account_name_column: str = "年金账户名"
    account_number_column: str = "年金账户号"
    company_id_column: str = "公司代码"
    output_column: str = "company_id"
    use_enrichment_service: bool = False
    sync_lookup_budget: int = 0
    generate_temp_ids: bool = True
    enable_backflow: bool = True


@dataclass
class ResolutionStatistics:
    """
    Statistics from a batch resolution operation.

    Provides insight into how company IDs were resolved across the batch,
    useful for monitoring and debugging resolution effectiveness.

    Attributes:
        total_rows: Total number of rows processed.
        plan_override_hits: DEPRECATED - Use yaml_hits["plan"] instead.
        existing_column_hits: Rows resolved from existing company_id column.
        enrichment_service_hits: Rows resolved via enrichment service.
        temp_ids_generated: Rows that received temporary IDs.
        unresolved: Rows that could not be resolved (0 if generate_temp_ids=True).
        yaml_hits: Breakdown of hits by YAML priority level (Story 6.4).
        db_cache_hits: Rows resolved via database cache (Story 6.4).
        eqc_sync_hits: Rows resolved via EQC sync lookup (Story 6.4).
        budget_consumed: Number of EQC lookups consumed (Story 6.4).
        budget_remaining: Remaining EQC lookup budget (Story 6.4).
        backflow_stats: Backflow operation statistics (Story 6.4).
    """

    total_rows: int = 0
    plan_override_hits: int = 0
    existing_column_hits: int = 0
    enrichment_service_hits: int = 0
    temp_ids_generated: int = 0
    unresolved: int = 0

    # Story 6.4: Multi-tier lookup statistics
    yaml_hits: Dict[str, int] = field(default_factory=dict)
    db_cache_hits: int = 0
    eqc_sync_hits: int = 0
    budget_consumed: int = 0
    budget_remaining: int = 0
    backflow_stats: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary for logging."""
        return {
            "total_rows": self.total_rows,
            "yaml_hits": self.yaml_hits,
            "yaml_hits_total": sum(self.yaml_hits.values()),
            "db_cache_hits": self.db_cache_hits,
            "eqc_sync_hits": self.eqc_sync_hits,
            "budget_consumed": self.budget_consumed,
            "budget_remaining": self.budget_remaining,
            "existing_column_hits": self.existing_column_hits,
            "enrichment_service_hits": self.enrichment_service_hits,
            "temp_ids_generated": self.temp_ids_generated,
            "unresolved": self.unresolved,
            "backflow": self.backflow_stats,
            # Backward compatibility
            "plan_override_hits": self.yaml_hits.get("plan", self.plan_override_hits),
        }


@dataclass
class ResolutionResult:
    """
    Result of a batch resolution operation.

    Contains the resolved DataFrame along with statistics about the resolution process.

    Attributes:
        data: The DataFrame with resolved company IDs.
        statistics: Resolution statistics for the batch.
        resolution_sources: Optional mapping of row index to resolution source.
    """

    data: pd.DataFrame
    statistics: ResolutionStatistics = field(default_factory=ResolutionStatistics)
    resolution_sources: Optional[Dict[int, ResolutionSource]] = None
