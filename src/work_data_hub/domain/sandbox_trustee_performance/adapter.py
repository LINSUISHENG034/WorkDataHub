"""Sandbox Trustee Performance Domain Service Adapter.

实现 DomainServiceProtocol，包装现有的 process 函数。
"""

import time
from typing import Any, Dict, List

from work_data_hub.domain.protocols import (
    DomainProcessingResult,
    ProcessingContext,
)


class SandboxTrusteePerformanceService:
    """Sandbox Trustee Performance 领域服务适配器."""

    @property
    def domain_name(self) -> str:
        return "sandbox_trustee_performance"

    @property
    def requires_enrichment(self) -> bool:
        return False

    @property
    def requires_backfill(self) -> bool:
        return False

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult:
        """委托给现有的 process 函数."""
        from work_data_hub.domain.sandbox_trustee_performance.service import (
            process,
        )

        start = time.perf_counter()

        records = process(rows, data_source=context.data_source)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return DomainProcessingResult(
            records=records,
            total_input=len(rows),
            total_output=len(records),
            failed_count=len(rows) - len(records),
            processing_time_ms=elapsed_ms,
        )
