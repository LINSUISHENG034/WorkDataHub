"""
Annuity Performance Domain Configuration.

Migrated from guimo_iter_config.py to enable config-driven comparison.
Contains all domain-specific values for the 规模明细 (annuity_performance) domain.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Type

from .base import DomainComparisonConfig

if TYPE_CHECKING:
    import pandas as pd


class AnnuityPerformanceConfig(DomainComparisonConfig):
    """Configuration for annuity_performance (规模明细) domain comparison."""

    # ==========================================================================
    # Required Properties (from guimo_iter_config.py)
    # ==========================================================================

    @property
    def domain_name(self) -> str:
        return "annuity_performance"

    @property
    def sheet_name(self) -> str:
        return "规模明细"

    @property
    def numeric_fields(self) -> List[str]:
        """Numeric fields requiring zero-tolerance comparison."""
        return [
            "期初资产规模",
            "期末资产规模",
            "供款",
            "流失(含待遇支付)",  # Legacy column name
            "流失",
            "待遇支付",
        ]

    @property
    def derived_fields(self) -> List[str]:
        """Fields computed from source via mappings/transformations."""
        return [
            "月度",
            "机构代码",
            "计划代码",
            "组合代码",
            "产品线代码",
        ]

    # ==========================================================================
    # Optional Properties (overriding defaults)
    # ==========================================================================

    @property
    def upgrade_fields(self) -> List[str]:
        """Fields intentionally enhanced in New Pipeline."""
        return ["company_id", "客户名称"]

    @property
    def column_name_mapping(self) -> Dict[str, str]:
        """Column name mapping: Legacy -> New Pipeline."""
        return {
            "流失(含待遇支付)": "流失_含待遇支付",
        }

    # ==========================================================================
    # Abstract Method Implementations
    # ==========================================================================

    def get_legacy_cleaner(self) -> Type:
        """
        Get Legacy AnnuityPerformanceCleaner class.

        Uses lazy import to enable --new-only mode without Legacy dependencies.
        """
        # Lazy import to avoid import errors when Legacy is not installed
        from annuity_hub.data_handler.data_cleaner import AnnuityPerformanceCleaner

        return AnnuityPerformanceCleaner

    def build_new_pipeline(
        self,
        excel_path: str,
        sheet_name: str,
        row_limit: Optional[int],
        enable_enrichment: bool,
        sync_lookup_budget: int,
    ) -> "pd.DataFrame":
        """
        Build and execute New Pipeline for annuity_performance domain.

        This is a thin wrapper around the existing pipeline builder logic,
        migrated from guimo_iter_cleaner_compare.py run_new_pipeline().
        """
        import pandas as pd

        from work_data_hub.config.settings import get_settings
        from work_data_hub.domain.annuity_performance.pipeline_builder import (
            build_bronze_to_silver_pipeline,
            load_plan_override_mapping,
        )
        from work_data_hub.domain.pipelines.types import PipelineContext

        # Load raw data (same as Legacy cleaner input)
        raw_df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)

        if row_limit and row_limit > 0:
            raw_df = raw_df.head(row_limit)

        # Load plan override mapping from YAML
        plan_override_mapping = load_plan_override_mapping()

        # Enable DB cache lookups whenever possible
        settings = get_settings()
        engine = None

        try:
            from sqlalchemy import create_engine

            engine = create_engine(settings.get_database_connection_string())
        except Exception as e:
            print(f"   ⚠️ Database engine init failed (DB cache disabled): {e}")

        if engine is None:
            # Run without database mapping repository
            pipeline = build_bronze_to_silver_pipeline(
                enrichment_service=None,
                plan_override_mapping=plan_override_mapping,
                sync_lookup_budget=sync_lookup_budget if enable_enrichment else 0,
                mapping_repository=None,
            )

            context = PipelineContext(
                pipeline_name="cleaner_comparison",
                execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(timezone.utc),
                config={},
                domain=self.domain_name,
                run_id="compare",
                extra={},
            )

            return pipeline.execute(raw_df.copy(), context)

        # Run with database mapping repository
        from work_data_hub.infrastructure.enrichment.mapping_repository import (
            CompanyMappingRepository,
        )

        with engine.connect() as conn:
            mapping_repository = CompanyMappingRepository(conn)
            print("   ✓ Database mapping repository enabled (enterprise.enrichment_index)")

            pipeline = build_bronze_to_silver_pipeline(
                enrichment_service=None,
                plan_override_mapping=plan_override_mapping,
                sync_lookup_budget=sync_lookup_budget if enable_enrichment else 0,
                mapping_repository=mapping_repository,
            )

            context = PipelineContext(
                pipeline_name="cleaner_comparison",
                execution_id=f"compare-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(timezone.utc),
                config={},
                domain=self.domain_name,
                run_id="compare",
                extra={},
            )

            result_df = pipeline.execute(raw_df.copy(), context)

            # CRITICAL: Commit to persist EQC cache writes to database
            conn.commit()

            return result_df


# Register this config when module is imported
# This is done via the register_config decorator in __init__.py
# But we also need to update the registry directly here for robustness
def _register():
    from . import DOMAIN_CONFIGS
    DOMAIN_CONFIGS["annuity_performance"] = AnnuityPerformanceConfig


_register()
