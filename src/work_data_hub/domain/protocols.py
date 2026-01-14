"""Domain Service Protocol - 所有领域服务的统一接口契约.

Story: Orchestration Layer Refactor - Phase 0
Location: domain/protocols.py

Design Goals:
- 统一 process() 签名，消除 per-domain ops
- 通过 requires_* 属性声明依赖，编排层按需注入
- 返回标准化结果，便于通用处理
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService


@dataclass
class ProcessingContext:
    """运行时上下文 - 由编排层根据 requires_* 属性填充."""

    data_source: str
    session_id: str
    plan_only: bool = True

    # Optional injected services
    enrichment_service: Optional["CompanyEnrichmentService"] = None
    eqc_config: Optional[Any] = None

    # Runtime flags
    export_unknown_names: bool = True


@dataclass
class DomainProcessingResult:
    """统一的处理结果结构."""

    records: List[Any]  # Pydantic models
    total_input: int
    total_output: int
    failed_count: int
    processing_time_ms: float

    # Optional enrichment data
    enrichment_stats: Optional[Dict[str, Any]] = None
    unknown_names_csv: Optional[str] = None

    def to_dicts(self) -> List[Dict[str, Any]]:
        """Convert records to JSON-serializable dicts."""
        return [
            r.model_dump(mode="json", by_alias=True, exclude_none=True)
            for r in self.records
        ]


@runtime_checkable
class DomainServiceProtocol(Protocol):
    """所有 Domain 服务必须实现的接口."""

    @property
    def domain_name(self) -> str:
        """Registry 用于查找的唯一标识符."""
        ...

    @property
    def requires_enrichment(self) -> bool:
        """是否需要 CompanyEnrichmentService 注入."""
        ...

    @property
    def requires_backfill(self) -> bool:
        """是否需要 ReferenceBackfillService 注入."""
        ...

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult:
        """统一处理入口."""
        ...
