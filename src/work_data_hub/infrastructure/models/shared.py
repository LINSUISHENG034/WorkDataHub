"""
Shared models used across multiple domains.

Story 6.2-P13: Unified Domain Schema Management Architecture

This module provides centralized model definitions to eliminate code duplication
across domain layers. Domain-specific modules should import from here and
maintain backward-compatible aliases.

Extracted from:
- domain/annuity_performance/schemas.py
- domain/annuity_performance/models.py
- domain/annuity_income/schemas.py
- domain/annuity_income/models.py
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.models import ResolutionStatus


@dataclass
class BronzeValidationSummary:
    """Summary of bronze layer validation results.

    This is the canonical definition - domain layers should import this
    and maintain backward-compatible aliases.

    Attributes:
        row_count: Total number of rows processed
        invalid_date_rows: List of row indices with invalid dates
        numeric_error_rows: Dict mapping column names to lists of invalid row indices
        empty_columns: List of columns that are entirely empty
    """

    row_count: int
    invalid_date_rows: List[int] = field(default_factory=list)
    numeric_error_rows: Dict[str, List[int]] = field(default_factory=dict)
    empty_columns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class GoldValidationSummary:
    """Summary of gold layer validation results.

    This is the canonical definition - domain layers should import this
    and maintain backward-compatible aliases.

    Attributes:
        row_count: Total number of rows in validated data
        removed_columns: List of columns removed during projection
        duplicate_keys: List of duplicate composite key tuples found
    """

    row_count: int
    removed_columns: List[str] = field(default_factory=list)
    duplicate_keys: List[Tuple[Any, ...]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class EnrichmentStats(BaseModel):
    """Statistics for company ID enrichment process.

    This is the canonical definition - domain layers should import this
    and maintain backward-compatible aliases.

    Tracks resolution outcomes from the multi-tier company ID resolution:
    - Internal: Resolved via YAML/DB cache mappings
    - External: Resolved via EQC API lookup
    - Pending: Queued for async processing
    - Temp: Assigned temporary HMAC-based ID
    - Failed: Resolution failed completely
    """

    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )

    total_records: int = 0
    success_internal: int = 0  # Resolved via internal mappings
    success_external: int = 0  # Resolved via EQC lookup + cached
    pending_lookup: int = 0  # Queued for async processing
    temp_assigned: int = 0  # Assigned temporary ID
    failed: int = 0  # Resolution failed completely
    sync_budget_used: int = 0  # EQC lookups consumed from budget
    processing_time_ms: int = 0  # Total enrichment processing time

    def record(self, status: "ResolutionStatus", source: Optional[str] = None) -> None:
        """Record a resolution outcome.

        Args:
            status: Resolution status from company enrichment
            source: Optional source identifier for tracking
        """
        from work_data_hub.domain.company_enrichment.models import ResolutionStatus

        self.total_records += 1
        if status == ResolutionStatus.SUCCESS_INTERNAL:
            self.success_internal += 1
        elif status == ResolutionStatus.SUCCESS_EXTERNAL:
            self.success_external += 1
            self.sync_budget_used += 1
        elif status == ResolutionStatus.PENDING_LOOKUP:
            self.pending_lookup += 1
        elif status == ResolutionStatus.TEMP_ASSIGNED:
            self.temp_assigned += 1
        else:
            self.failed += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage of total records."""
        if self.total_records == 0:
            return 0.0
        return (self.success_internal + self.success_external) / self.total_records


__all__ = [
    "BronzeValidationSummary",
    "GoldValidationSummary",
    "EnrichmentStats",
]
