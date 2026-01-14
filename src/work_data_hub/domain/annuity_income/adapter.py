"""Annuity Income Domain Service Adapter.

实现 DomainServiceProtocol，包装现有的 process_with_enrichment 函数。
"""

import time
from typing import Any, Dict, List

from work_data_hub.domain.protocols import (
    DomainProcessingResult,
    ProcessingContext,
)


class AnnuityIncomeService:
    """Annuity Income 领域服务适配器."""

    @property
    def domain_name(self) -> str:
        return "annuity_income"

    @property
    def requires_enrichment(self) -> bool:
        return True

    @property
    def requires_backfill(self) -> bool:
        return True

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult:
        """委托给现有的 process_with_enrichment."""
        from work_data_hub.domain.annuity_income.service import (
            process_with_enrichment,
        )

        start = time.perf_counter()

        result = process_with_enrichment(
            rows,
            data_source=context.data_source,
            enrichment_service=context.enrichment_service,
            export_unknown_names=context.export_unknown_names,
            session_id=context.session_id,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        return DomainProcessingResult(
            records=result.records,
            total_input=len(rows),
            total_output=len(result.records),
            failed_count=len(rows) - len(result.records),
            processing_time_ms=elapsed_ms,
            enrichment_stats=(
                result.enrichment_stats.to_dict()
                if hasattr(result, "enrichment_stats") and result.enrichment_stats
                else None
            ),
            unknown_names_csv=result.unknown_names_csv,
        )
