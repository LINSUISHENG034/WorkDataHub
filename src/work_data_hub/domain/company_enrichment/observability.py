"""
Enrichment observability module for metrics collection and unknown company tracking.

This module provides comprehensive observability for the company enrichment pipeline,
including metrics collection, unknown company tracking, and CSV export capabilities.

Story 6.8: Enrichment Observability and Export
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class EnrichmentStats:
    """
    Comprehensive enrichment metrics for pipeline observability.

    Tracks all enrichment operations during a pipeline run for
    monitoring effectiveness and identifying optimization opportunities.

    Attributes:
        total_lookups: Total number of company ID resolution attempts
        cache_hits: Number of successful internal mapping hits
        temp_ids_generated: Number of temporary IDs generated for unknown companies
        api_calls: Number of EQC API calls made
        sync_budget_used: Number of synchronous lookup budget consumed
        async_queued: Number of requests queued for async processing
        queue_depth_after: Queue depth after pipeline completion

    Examples:
        >>> stats = EnrichmentStats(total_lookups=100, cache_hits=85)
        >>> stats.cache_hit_rate
        0.85
        >>> stats.to_dict()["cache_hit_rate"]
        0.85
    """

    total_lookups: int = 0
    cache_hits: int = 0
    temp_ids_generated: int = 0
    api_calls: int = 0
    sync_budget_used: int = 0
    async_queued: int = 0
    queue_depth_after: int = 0
    hit_type_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def cache_hit_rate(self) -> float:
        """
        Calculate cache hit rate as decimal (0.0-1.0).

        Returns:
            Cache hit rate, or 0.0 if no lookups performed
        """
        if self.total_lookups == 0:
            return 0.0
        return self.cache_hits / self.total_lookups

    @property
    def temp_id_rate(self) -> float:
        """
        Calculate temporary ID generation rate as decimal (0.0-1.0).

        Returns:
            Temp ID rate, or 0.0 if no lookups performed
        """
        if self.total_lookups == 0:
            return 0.0
        return self.temp_ids_generated / self.total_lookups

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON logging.

        Returns:
            Dictionary with all metrics including computed rates
        """
        return {
            "total_lookups": self.total_lookups,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "temp_ids_generated": self.temp_ids_generated,
            "temp_id_rate": round(self.temp_id_rate, 4),
            "api_calls": self.api_calls,
            "sync_budget_used": self.sync_budget_used,
            "async_queued": self.async_queued,
            "queue_depth_after": self.queue_depth_after,
            "hit_type_counts": self.hit_type_counts,
            # Compatibility fields for ResolutionStatistics-style breakdowns
            "yaml_hits": self.hit_type_counts,
            "db_cache_hits": self.cache_hits,
            "existing_column_hits": 0,
            "eqc_sync_hits": self.api_calls,
            "backflow": {},
        }

    def merge(self, other: "EnrichmentStats") -> "EnrichmentStats":
        """
        Merge stats from another run (for aggregation).

        Args:
            other: Another EnrichmentStats instance to merge

        Returns:
            New EnrichmentStats with combined metrics
        """
        # Merge hit type counts
        merged_counts = self.hit_type_counts.copy()
        for k, v in other.hit_type_counts.items():
            merged_counts[k] = merged_counts.get(k, 0) + v

        return EnrichmentStats(
            total_lookups=self.total_lookups + other.total_lookups,
            cache_hits=self.cache_hits + other.cache_hits,
            temp_ids_generated=self.temp_ids_generated + other.temp_ids_generated,
            api_calls=self.api_calls + other.api_calls,
            sync_budget_used=self.sync_budget_used + other.sync_budget_used,
            async_queued=self.async_queued + other.async_queued,
            queue_depth_after=other.queue_depth_after,  # Take latest
            hit_type_counts=merged_counts,
        )


@dataclass
class UnknownCompanyRecord:
    """
    Record of an unknown company for CSV export.

    Tracks companies that received temporary IDs for manual backfill review.

    Attributes:
        company_name: Original company name that couldn't be resolved
        temporary_id: Generated temporary ID (IN_* format)
        first_seen: Timestamp of first occurrence
        occurrence_count: Number of times this company appeared
    """

    company_name: str
    temporary_id: str
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    occurrence_count: int = 1

    @staticmethod
    def csv_headers() -> List[str]:
        """Return CSV column headers."""
        return ["company_name", "temporary_id", "first_seen", "occurrence_count"]

    def to_csv_row(self) -> List[str]:
        """Convert to CSV row values."""
        return [
            self.company_name,
            self.temporary_id,
            self.first_seen.isoformat(),
            str(self.occurrence_count),
        ]


class EnrichmentObserver:
    """
    Observer for tracking enrichment metrics during pipeline execution.

    Thread-safe metrics collection with support for unknown company
    tracking and CSV export data generation.

    Examples:
        >>> observer = EnrichmentObserver()
        >>> observer.record_lookup()
        >>> observer.record_cache_hit("exact_match")
        >>> observer.record_temp_id("Unknown Corp", "IN_ABC123")
        >>> stats = observer.get_stats()
        >>> stats.total_lookups
        1
        >>> unknown = observer.get_unknown_companies()
        >>> len(unknown)
        1
    """

    def __init__(self) -> None:
        """Initialize observer with empty stats and unknown company tracking."""
        self._stats = EnrichmentStats()
        self._unknown_companies: Dict[str, UnknownCompanyRecord] = {}
        self._lock = threading.Lock()

    def record_lookup(self) -> None:
        """Record a lookup attempt."""
        with self._lock:
            self._stats.total_lookups += 1

    def record_cache_hit(self, match_type: str = "unknown") -> None:
        """
        Record a successful cache hit (internal mapping).

        Args:
            match_type: Type of match (e.g., 'plan', 'name', 'account')
        """
        with self._lock:
            self._stats.cache_hits += 1
            self._stats.hit_type_counts[match_type] = (
                self._stats.hit_type_counts.get(match_type, 0) + 1
            )

    def record_temp_id(self, company_name: str, temp_id: str) -> None:
        """
        Record temporary ID generation for unknown company.

        Args:
            company_name: Original company name
            temp_id: Generated temporary ID
        """
        with self._lock:
            self._stats.temp_ids_generated += 1

            # Track unknown company with occurrence count
            if company_name in self._unknown_companies:
                self._unknown_companies[company_name].occurrence_count += 1
            else:
                self._unknown_companies[company_name] = UnknownCompanyRecord(
                    company_name=company_name,
                    temporary_id=temp_id,
                    first_seen=datetime.now(timezone.utc),
                    occurrence_count=1,
                )

    def record_api_call(self) -> None:
        """Record an EQC API call."""
        with self._lock:
            self._stats.api_calls += 1
            self._stats.sync_budget_used += 1

    def record_async_queued(self) -> None:
        """Record a request queued for async processing."""
        with self._lock:
            self._stats.async_queued += 1

    def set_queue_depth(self, depth: int) -> None:
        """
        Set final queue depth after processing.

        Args:
            depth: Current queue depth
        """
        with self._lock:
            self._stats.queue_depth_after = depth

    def get_stats(self) -> EnrichmentStats:
        """
        Get current enrichment statistics.

        Returns:
            Copy of current EnrichmentStats
        """
        with self._lock:
            return EnrichmentStats(
                total_lookups=self._stats.total_lookups,
                cache_hits=self._stats.cache_hits,
                temp_ids_generated=self._stats.temp_ids_generated,
                api_calls=self._stats.api_calls,
                sync_budget_used=self._stats.sync_budget_used,
                async_queued=self._stats.async_queued,
                queue_depth_after=self._stats.queue_depth_after,
                hit_type_counts=self._stats.hit_type_counts.copy(),
            )

    def get_unknown_companies(self) -> List[UnknownCompanyRecord]:
        """
        Get unknown companies sorted by occurrence count DESC.

        Returns:
            List of UnknownCompanyRecord sorted by occurrence_count descending
        """
        with self._lock:
            return sorted(
                list(self._unknown_companies.values()),
                key=lambda x: x.occurrence_count,
                reverse=True,
            )

    def get_unknown_company_rows(self) -> List[List[str]]:
        """
        Get unknown company data as CSV rows (sorted by occurrence_count DESC).

        Domain-side method that produces sorted rows for CSV export without file I/O.

        Returns:
            List of CSV row values, sorted by occurrence count descending
        """
        records = self.get_unknown_companies()
        return [record.to_csv_row() for record in records]

    def has_unknown_companies(self) -> bool:
        """
        Check if any unknown companies were recorded.

        Returns:
            True if unknown companies exist
        """
        with self._lock:
            return len(self._unknown_companies) > 0

    def reset(self) -> None:
        """Reset all statistics for new run."""
        with self._lock:
            self._stats = EnrichmentStats()
            self._unknown_companies.clear()


def build_unknown_company_rows(observer: EnrichmentObserver) -> List[List[str]]:
    """
    Build sorted rows for CSV export from observer (no file I/O).

    Convenience function for orchestration layer to get export data.

    Args:
        observer: EnrichmentObserver instance

    Returns:
        List of CSV row values sorted by occurrence count descending
    """
    return observer.get_unknown_company_rows()
