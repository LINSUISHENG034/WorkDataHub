"""
Base classes for validation summary dataclasses.

Story 4.8: Provides base patterns for validation summaries that can be
extended by domain-specific implementations (annuity_performance, Epic 9, etc.).

These base classes ensure consistent validation reporting across all domains.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class ValidationSummaryBase:
    """
    Base class for validation summary dataclasses.

    Provides common fields and methods that all domain-specific validation
    summaries should include. Domain implementations can extend this with
    additional fields specific to their validation needs.

    Attributes:
        row_count: Number of rows processed during validation
        warnings: List of non-fatal warning messages
        errors: List of error messages (may not cause validation failure)
    """

    row_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to JSON-friendly dictionary."""
        return asdict(self)

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were recorded."""
        return len(self.warnings) > 0

    @property
    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def add_warning(self, message: str) -> None:
        """Add a warning message to the summary."""
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        """Add an error message to the summary."""
        self.errors.append(message)


__all__ = [
    "ValidationSummaryBase",
]
