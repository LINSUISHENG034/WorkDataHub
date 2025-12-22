"""
Result dataclasses for repository operations.

This module contains the result types returned by repository methods.

Story 7.3: Infrastructure Layer Decomposition
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MatchResult:
    """
    Result of a company mapping lookup.

    Attributes:
        company_id: The resolved canonical company ID.
        match_type: Type of match (plan/account/hardcode/name/account_name).
        priority: Priority level (1-5, lower is higher priority).
        source: Source of the mapping (internal/eqc/pipeline_backflow).
    """

    company_id: str
    match_type: str
    priority: int
    source: str


@dataclass
class InsertBatchResult:
    """
    Result of a batch insert operation with conflict detection.

    Attributes:
        inserted_count: Number of rows successfully inserted.
        skipped_count: Number of rows skipped due to existing entries.
        conflicts: List of conflicts where alias_name exists but company_id differs.
    """

    inserted_count: int
    skipped_count: int
    conflicts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EnqueueResult:
    """
    Result of an async enrichment queue operation (Story 6.5).

    Attributes:
        queued_count: Number of requests actually enqueued.
        skipped_count: Number of requests skipped (duplicates via partial unique index).
    """

    queued_count: int
    skipped_count: int
