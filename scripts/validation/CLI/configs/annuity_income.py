"""
Annuity Income Domain Configuration.

Contains all domain-specific values for the 收入明细 (annuity_income) domain.
Integrates with the extracted legacy cleaner from run_legacy_annuity_income_cleaner.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Type

from .base import DomainComparisonConfig

if TYPE_CHECKING:
    import pandas as pd


class AnnuityIncomeConfig(DomainComparisonConfig):
    """Configuration for annuity_income (收入明细) domain comparison."""

    # ==========================================================================
    # Required Properties
    # ==========================================================================

    @property
    def domain_name(self) -> str:
        return "annuity_income"

    @property
    def sheet_name(self) -> str:
        return "收入明细"

    @property
    def numeric_fields(self) -> List[str]:
        """Numeric fields requiring zero-tolerance comparison.

        annuity_income schema uses: 固费, 浮费, 回补, 税
        (different from annuity_performance: 首年保费, 续期保费, 保费合计,
        受托规模, 投资规模)
        """
        return [
            "固费",
            "浮费",
            "回补",
            "税",
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
        # Legacy now outputs 计划代码 directly (unified with New Pipeline)
        return {}

    # ==========================================================================
    # Abstract Method Implementations
    # ==========================================================================

    def get_legacy_cleaner(self) -> Type:
        """
        Get Legacy AnnuityIncomeCleaner class wrapped in an adapter.

        Uses lazy import to enable --new-only mode without Legacy dependencies.
        Directly imports from legacy module to ensure complete MySQL mapping data.

        Note: AnnuityIncomeCleaner doesn't accept sheet_name parameter
        (hardcoded to "收入明细"), so we wrap it in an adapter for
        interface compatibility.
        """
        # Lazy import to avoid import errors when Legacy is not installed
        from annuity_hub.data_handler.data_cleaner import AnnuityIncomeCleaner

        class AnnuityIncomeCleanerAdapter(AnnuityIncomeCleaner):
            """Adapter to make AnnuityIncomeCleaner compatible with framework."""

            def __init__(self, path, sheet_name: str = "收入明细"):
                # AnnuityIncomeCleaner ignores sheet_name (hardcoded in _clean_method)
                # but we accept it for interface compatibility
                super().__init__(path)

        return AnnuityIncomeCleanerAdapter

    def build_new_pipeline(
        self,
        excel_path: str,
        sheet_name: str,
        row_limit: Optional[int],
        enable_enrichment: bool,
        sync_lookup_budget: int,
    ) -> "pd.DataFrame":
        """
        Build and execute New Pipeline for annuity_income domain.
        """
        import pandas as pd

        from work_data_hub.config.settings import get_settings
        from work_data_hub.domain.annuity_income.pipeline_builder import (
            build_bronze_to_silver_pipeline,
            load_plan_override_mapping,
        )
        from work_data_hub.domain.pipelines.types import PipelineContext
        from work_data_hub.infrastructure.enrichment.eqc_lookup_config import (
            EqcLookupConfig,
        )

        # Build EqcLookupConfig based on enable_enrichment flag
        if enable_enrichment:
            eqc_config = EqcLookupConfig(
                enabled=True,
                sync_budget=sync_lookup_budget,
                auto_create_provider=True,
            )
        else:
            eqc_config = EqcLookupConfig.disabled()

        # Load raw data
        raw_df = pd.read_excel(excel_path, sheet_name=sheet_name, dtype=str)

        if row_limit and row_limit > 0:
            raw_df = raw_df.head(row_limit)

        # Load plan override mapping from YAML
        plan_override_mapping = load_plan_override_mapping()

        # Suppress work_data_hub logs during pipeline execution for clean CLI output
        import logging
        import warnings

        for name in list(logging.Logger.manager.loggerDict):
            if name.startswith("work_data_hub"):
                logging.getLogger(name).setLevel(logging.ERROR)
        # Also suppress FutureWarning from pandas
        warnings.filterwarnings("ignore", category=FutureWarning)

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
                eqc_config=eqc_config,
                plan_override_mapping=plan_override_mapping,
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
            print(
                "   ✓ Database mapping repository enabled (enterprise.enrichment_index)"
            )

            pipeline = build_bronze_to_silver_pipeline(
                eqc_config=eqc_config,
                plan_override_mapping=plan_override_mapping,
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
def _register():
    from . import DOMAIN_CONFIGS

    DOMAIN_CONFIGS["annuity_income"] = AnnuityIncomeConfig


_register()
