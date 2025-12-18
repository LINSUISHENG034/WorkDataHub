"""
Base Domain Comparison Configuration.

Defines the abstract base class that all domain-specific comparison configs
must implement. This enables a configuration-driven, domain-agnostic approach
to cleaner comparison.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional, Type

if TYPE_CHECKING:
    import pandas as pd


class DomainComparisonConfig(ABC):
    """
    Abstract base class for domain-specific comparison configurations.

    Each domain (e.g., annuity_performance, annuity_income) must implement
    a subclass that defines:
    - Field configurations (numeric, derived, upgrade)
    - Legacy cleaner accessor
    - New pipeline builder

    Example:
        class AnnuityPerformanceConfig(DomainComparisonConfig):
            domain_name = "annuity_performance"
            sheet_name = "规模明细"
            numeric_fields = ["期初资产规模", "期末资产规模", ...]
            ...
    """

    # ==========================================================================
    # Abstract Properties (MUST be overridden)
    # ==========================================================================

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """Unique domain identifier (e.g., 'annuity_performance')."""
        ...

    @property
    @abstractmethod
    def sheet_name(self) -> str:
        """Default Excel sheet name for this domain."""
        ...

    @property
    @abstractmethod
    def numeric_fields(self) -> List[str]:
        """
        Fields requiring zero-tolerance numeric comparison.
        NULL and 0 are treated as equivalent.
        """
        ...

    @property
    @abstractmethod
    def derived_fields(self) -> List[str]:
        """
        Fields computed from source via mappings/transformations.
        (e.g., 月度, 机构代码, 计划代码)
        """
        ...

    # ==========================================================================
    # Default Properties (CAN be overridden)
    # ==========================================================================

    @property
    def upgrade_fields(self) -> List[str]:
        """
        Fields intentionally enhanced in New Pipeline.
        Default: ["company_id"]
        """
        return ["company_id"]

    @property
    def column_name_mapping(self) -> Dict[str, str]:
        """
        Column name mapping: Legacy -> New Pipeline.
        Default: empty (no mapping needed)
        """
        return {}

    # ==========================================================================
    # Abstract Methods (MUST be implemented)
    # ==========================================================================

    @abstractmethod
    def get_legacy_cleaner(self) -> Type:
        """
        Get the Legacy cleaner class for this domain.

        Uses lazy import to avoid import errors when Legacy dependencies
        are not installed (enables --new-only mode).

        Returns:
            Legacy cleaner class (e.g., AnnuityPerformanceCleaner)

        Raises:
            ImportError: If Legacy dependencies are not available
        """
        ...

    @abstractmethod
    def build_new_pipeline(
        self,
        excel_path: str,
        sheet_name: str,
        row_limit: Optional[int],
        enable_enrichment: bool,
        sync_lookup_budget: int,
    ) -> "pd.DataFrame":
        """
        Build and execute the New Pipeline for this domain.

        Uses lazy import to keep module lightweight.

        Args:
            excel_path: Path to Excel file
            sheet_name: Sheet name to process
            row_limit: Optional row limit (None or 0 = no limit)
            enable_enrichment: Whether to enable EQC enrichment
            sync_lookup_budget: Budget for EQC sync lookups

        Returns:
            Cleaned DataFrame from New Pipeline
        """
        ...

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    def get_column_mapping(self, legacy_col: str) -> str:
        """
        Get the New Pipeline column name for a Legacy column.

        Args:
            legacy_col: Legacy column name

        Returns:
            New Pipeline column name (same as legacy_col if no mapping)
        """
        return self.column_name_mapping.get(legacy_col, legacy_col)
