"""
Type definitions for Company ID Resolution.

This module defines the configuration and result types used by the CompanyIdResolver
for batch company ID resolution with hierarchical strategy support.

Architecture Reference:
- AD-002: Temporary Company ID Generation
- AD-010: Infrastructure Layer

Story 6.4: Extended with multi-tier lookup statistics and backflow tracking.
Story 6.1.1: Added LookupType, SourceType enums and EnrichmentIndexRecord for enrichment_index table.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
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
        enable_async_queue: Whether to enqueue unresolved names for async
            enrichment when generating temp IDs (Story 6.5).
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
    enable_async_queue: bool = True


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
        async_queued: Number of requests enqueued for async enrichment (Story 6.5).
    """

    total_rows: int = 0
    plan_override_hits: int = 0
    existing_column_hits: int = 0
    enrichment_service_hits: int = 0
    temp_ids_generated: int = 0
    unresolved: int = 0

    # Story 6.4: Multi-tier lookup statistics
    yaml_hits: Dict[str, int] = field(default_factory=dict)
    db_cache_hits: Dict[str, int] = field(
        default_factory=lambda: {
            "plan_code": 0,
            "account_name": 0,
            "account_number": 0,
            "customer_name": 0,
            "plan_customer": 0,
            "legacy": 0,  # Legacy fallback (company_mapping) for backward compatibility
        }
    )
    db_decision_path_counts: Dict[str, int] = field(default_factory=dict)
    eqc_sync_hits: int = 0
    budget_consumed: int = 0
    budget_remaining: int = 0
    backflow_stats: Dict[str, int] = field(default_factory=dict)

    # Story 6.5: Async queue statistics
    async_queued: int = 0

    # Story 6.1.3: Domain learning statistics
    domain_learning_stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def db_cache_hits_total(self) -> int:
        """Total DB cache hits across all priorities (compatibility helper)."""
        return sum(self.db_cache_hits.values())

    def ensure_db_cache_keys(self) -> None:
        """Ensure db_cache_hits contains all expected keys."""
        defaults = {
            "plan_code": 0,
            "account_name": 0,
            "account_number": 0,
            "customer_name": 0,
            "plan_customer": 0,
            "legacy": 0,
        }
        for key, value in defaults.items():
            self.db_cache_hits.setdefault(key, value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert statistics to dictionary for logging."""
        self.ensure_db_cache_keys()
        return {
            "total_rows": self.total_rows,
            "yaml_hits": self.yaml_hits,
            "yaml_hits_total": sum(self.yaml_hits.values()),
            "db_cache_hits": self.db_cache_hits,
            "db_cache_hits_total": self.db_cache_hits_total,
            "db_decision_path_counts": self.db_decision_path_counts,
            "eqc_sync_hits": self.eqc_sync_hits,
            "budget_consumed": self.budget_consumed,
            "budget_remaining": self.budget_remaining,
            "existing_column_hits": self.existing_column_hits,
            "enrichment_service_hits": self.enrichment_service_hits,
            "temp_ids_generated": self.temp_ids_generated,
            "unresolved": self.unresolved,
            "backflow": self.backflow_stats,
            "async_queued": self.async_queued,
            "domain_learning": self.domain_learning_stats,
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


# =============================================================================
# Story 6.1.1: Enrichment Index Types
# =============================================================================


class LookupType(Enum):
    """
    Lookup type for enrichment_index table (Story 6.1.1).

    Maps to DB-P1 through DB-P5 priority levels in Layer 2 cache.

    Attributes:
        PLAN_CODE: DB-P1 - Plan code lookup (highest priority)
        ACCOUNT_NAME: DB-P2 - Annuity account name lookup
        ACCOUNT_NUMBER: DB-P3 - Annuity account number lookup (集团企业客户号)
        CUSTOMER_NAME: DB-P4 - Customer name lookup (normalized)
        PLAN_CUSTOMER: DB-P5 - Plan + Customer combo lookup (lowest priority)
    """

    PLAN_CODE = "plan_code"
    ACCOUNT_NAME = "account_name"
    ACCOUNT_NUMBER = "account_number"
    CUSTOMER_NAME = "customer_name"
    PLAN_CUSTOMER = "plan_customer"


class SourceType(Enum):
    """
    Source type for enrichment_index records (Story 6.1.1).

    Indicates how the mapping was created/discovered.

    Attributes:
        YAML: Synced from YAML configuration (confidence: 1.00)
        EQC_API: EQC API query result (confidence: 1.00)
        MANUAL: Manually added mapping (confidence: 1.00)
        BACKFLOW: Layer 3 backflow from existing data (confidence: 1.00)
        DOMAIN_LEARNING: Learned from domain data processing (confidence: 0.85-0.95)
        LEGACY_MIGRATION: Migrated from legacy system (confidence: 0.90-1.00)
    """

    YAML = "yaml"
    EQC_API = "eqc_api"
    MANUAL = "manual"
    BACKFLOW = "backflow"
    DOMAIN_LEARNING = "domain_learning"
    LEGACY_MIGRATION = "legacy_migration"


@dataclass
class EnrichmentIndexRecord:
    """
    Record for enrichment_index table (Story 6.1.1).

    Represents a single lookup mapping in the Layer 2 database cache.
    Used for batch insert/update operations.

    Attributes:
        lookup_key: The lookup key value. For customer_name and plan_customer,
            this should be normalized using the shared normalizer.
            Format for plan_customer: "{plan_code}|{normalized_customer_name}"
        lookup_type: Type of lookup (plan_code, account_name, etc.)
        company_id: Resolved company ID (aligned with enterprise.company_master)
        confidence: Confidence score (0.00-1.00), default 1.00
        source: Source of the mapping (yaml, eqc_api, etc.)
        source_domain: Optional domain that learned this mapping
        source_table: Optional table that provided this mapping
        hit_count: Number of cache hits (default 0)
        last_hit_at: Timestamp of last cache hit
        created_at: Record creation timestamp
        updated_at: Record last update timestamp

    Example:
        >>> from work_data_hub.infrastructure.enrichment.normalizer import normalize_for_temp_id
        >>> # Plan code lookup (DB-P1)
        >>> record = EnrichmentIndexRecord(
        ...     lookup_key="FP0001",
        ...     lookup_type=LookupType.PLAN_CODE,
        ...     company_id="614810477",
        ...     source=SourceType.YAML,
        ... )
        >>> # Customer name lookup (DB-P4) - normalized
        >>> normalized = normalize_for_temp_id("中国平安")
        >>> record = EnrichmentIndexRecord(
        ...     lookup_key=normalized,
        ...     lookup_type=LookupType.CUSTOMER_NAME,
        ...     company_id="614810477",
        ...     source=SourceType.EQC_API,
        ... )
        >>> # Plan + Customer combo (DB-P5)
        >>> plan_customer_key = f"FP0001|{normalized}"
        >>> record = EnrichmentIndexRecord(
        ...     lookup_key=plan_customer_key,
        ...     lookup_type=LookupType.PLAN_CUSTOMER,
        ...     company_id="614810477",
        ...     source=SourceType.DOMAIN_LEARNING,
        ...     confidence=Decimal("0.90"),
        ...     source_domain="annuity_performance",
        ... )
    """

    lookup_key: str
    lookup_type: LookupType
    company_id: str
    source: SourceType
    confidence: Decimal = field(default_factory=lambda: Decimal("1.00"))
    source_domain: Optional[str] = None
    source_table: Optional[str] = None
    hit_count: int = 0
    last_hit_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for database operations."""
        return {
            "lookup_key": self.lookup_key,
            "lookup_type": self.lookup_type.value,
            "company_id": self.company_id,
            "confidence": float(self.confidence),
            "source": self.source.value,
            "source_domain": self.source_domain,
            "source_table": self.source_table,
            "hit_count": self.hit_count,
            "last_hit_at": self.last_hit_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnrichmentIndexRecord":
        """Create record from dictionary (e.g., database row)."""
        return cls(
            lookup_key=data["lookup_key"],
            lookup_type=LookupType(data["lookup_type"]),
            company_id=data["company_id"],
            confidence=Decimal(str(data.get("confidence", "1.00"))),
            source=SourceType(data["source"]),
            source_domain=data.get("source_domain"),
            source_table=data.get("source_table"),
            hit_count=data.get("hit_count", 0),
            last_hit_at=data.get("last_hit_at"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


# =============================================================================
# Story 6.1.3: Domain Learning Types
# =============================================================================


@dataclass
class DomainLearningConfig:
    """
    Configuration for domain learning mechanism (Story 6.1.3).

    Controls which domains and lookup types are enabled for learning,
    confidence levels, and thresholds.

    Attributes:
        enabled_domains: List of domains enabled for learning.
        confidence_levels: Confidence level per lookup type.
        enabled_lookup_types: Enable/disable per lookup type.
        min_records_for_learning: Minimum records required to trigger learning.
        min_confidence_for_cache: Minimum confidence for cache writes.
        column_mappings: Domain-specific column name mappings.
    """

    enabled_domains: list = field(
        default_factory=lambda: ["annuity_performance", "annuity_income"]
    )
    confidence_levels: Dict[str, float] = field(
        default_factory=lambda: {
            "plan_code": 0.95,
            "account_name": 0.90,
            "account_number": 0.95,
            "customer_name": 0.85,
            "plan_customer": 0.90,
        }
    )
    enabled_lookup_types: Dict[str, bool] = field(
        default_factory=lambda: {
            "plan_code": True,
            "account_name": True,
            "account_number": True,
            "customer_name": True,
            "plan_customer": True,
        }
    )
    min_records_for_learning: int = 10
    min_confidence_for_cache: float = 0.80
    column_mappings: Dict[str, Dict[str, str]] = field(
        default_factory=lambda: {
            "annuity_performance": {
                "plan_code": "计划代码",
                "account_name": "年金账户名",
                "account_number": "年金账户号",
                "customer_name": "客户名称",
                "company_id": "company_id",
            },
            "annuity_income": {
                "plan_code": "计划代码",
                "account_name": "年金账户名",
                "account_number": "年金账户号",
                "customer_name": "客户名称",
                "company_id": "company_id",
            },
        }
    )


@dataclass
class DomainLearningResult:
    """
    Result of domain learning operation (Story 6.1.3).

    Tracks statistics from a learning run including extracted, inserted,
    updated, and skipped counts.

    Attributes:
        domain_name: Name of the domain (e.g., 'annuity_performance').
        table_name: Name of the source table.
        total_records: Total records in the input DataFrame.
        valid_records: Records with non-null, non-temp company_id.
        extracted: Count of mappings extracted per lookup type.
        inserted: Number of new mappings inserted.
        updated: Number of existing mappings updated.
        skipped: Number of mappings skipped (null, temp ID, low confidence).
        skipped_by_reason: Breakdown of skipped counts by reason.
    """

    domain_name: str
    table_name: str
    total_records: int = 0
    valid_records: int = 0
    extracted: Dict[str, int] = field(default_factory=dict)
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    skipped_by_reason: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for logging/reporting."""
        return {
            "domain_name": self.domain_name,
            "table_name": self.table_name,
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "extracted": self.extracted,
            "extracted_total": sum(self.extracted.values()),
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "skipped_by_reason": self.skipped_by_reason,
        }
