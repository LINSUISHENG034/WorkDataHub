"""Generic Domain Processing Op (Phase 3).

Story: Orchestration Layer Refactor
Location: orchestration/ops/generic_ops.py

使用 DomainServiceProtocol 统一处理所有 domain。
"""

from typing import Any, Dict, List, Optional

from dagster import Config, OpExecutionContext, op


class GenericDomainOpConfig(Config):
    """Generic Op 配置."""

    domain: str
    plan_only: bool = True
    session_id: Optional[str] = None


@op
def process_domain_op_v2(
    context: OpExecutionContext,
    config: GenericDomainOpConfig,
    rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """Generic domain processing using Protocol.

    Args:
        context: Dagster execution context
        config: Op configuration
        rows: Input data rows
        file_paths: Source file paths

    Returns:
        Processed records as dicts
    """
    import uuid

    from work_data_hub.domain.protocols import ProcessingContext
    from work_data_hub.domain.registry import DOMAIN_SERVICE_REGISTRY
    from work_data_hub.infrastructure.enrichment.factory import (
        EnrichmentServiceFactory,
    )

    domain = config.domain
    file_path = file_paths[0] if file_paths else "unknown"

    # Get service from Protocol registry
    service = DOMAIN_SERVICE_REGISTRY.get(domain)
    if service is None:
        raise ValueError(f"Unknown domain: {domain}")

    # Create enrichment context using Factory
    enrichment_ctx = None
    if service.requires_enrichment:
        enrichment_ctx = EnrichmentServiceFactory.create(
            plan_only=config.plan_only,
        )

    try:
        # Build ProcessingContext
        processing_context = ProcessingContext(
            data_source=file_path,
            session_id=config.session_id or str(uuid.uuid4()),
            plan_only=config.plan_only,
            enrichment_service=(enrichment_ctx.service if enrichment_ctx else None),
        )

        # Call unified interface
        result = service.process(rows, processing_context)

        context.log.info(
            f"domain_processing.completed domain={domain} "
            f"input={result.total_input} output={result.total_output}"
        )

        return result.to_dicts()

    finally:
        if enrichment_ctx:
            enrichment_ctx.cleanup()
