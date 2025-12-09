from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import DomainPipelineResult, PipelineContext
from work_data_hub.infrastructure.validation import export_error_csv

from .helpers import (
    FileDiscoveryProtocol,
    convert_dataframe_to_models,
    export_unknown_names_csv,
    normalize_month,
    run_discovery,
    summarize_enrichment,
)
from .models import AnnuityPerformanceOut, ProcessingResultWithEnrichment
from .pipeline_builder import (
    build_bronze_to_silver_pipeline,
    load_plan_override_mapping,
)
from .constants import DEFAULT_REFRESH_KEYS, DEFAULT_UPSERT_KEYS

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)

# =============================================================================
# Data Loading Configuration
# =============================================================================
# This domain uses REFRESH mode (DELETE + INSERT) because it contains detail
# records (明细数据) where the same key combination can have multiple rows.
#
# UPSERT mode (ON CONFLICT DO UPDATE) is NOT suitable for detail tables.
# UPSERT is only appropriate for aggregate tables with unique key combinations.
#
# Legacy equivalent: annuity_mapping.update_based_on_field = "月度+业务类型"
# Updated to: "月度+业务类型+计划类型" per Sprint Change Proposal 2025-12-06
# Keys are imported from constants.py
# =============================================================================

# Enable/disable UPSERT mode (requires UNIQUE constraint on upsert_keys)
ENABLE_UPSERT_MODE = False  # Detail table - use refresh mode instead


def process_annuity_performance(
    month: str,
    *,
    file_discovery: FileDiscoveryProtocol,
    warehouse_loader: Any,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    domain: str = "annuity_performance",
    table_name: str = "annuity_performance_NEW",
    schema: str = "public",
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
    upsert_keys: Optional[List[str]] = None,
    refresh_keys: Optional[List[str]] = None,
) -> DomainPipelineResult:
    normalized_month = normalize_month(month)
    start_time = time.perf_counter()
    logger.bind(domain=domain, step="pipeline_start").info(
        "annuity.pipeline.start",
        month=normalized_month,
        table=table_name,
    )
    discovery_result = run_discovery(
        file_discovery=file_discovery,
        domain=domain,
        month=normalized_month,
    )
    processing = process_with_enrichment(
        discovery_result.df.to_dict(orient="records"),
        data_source=str(discovery_result.file_path),
        enrichment_service=enrichment_service,
        sync_lookup_budget=sync_lookup_budget,
        export_unknown_names=export_unknown_names,
    )
    dataframe = _records_to_dataframe(processing.records)

    # Choose loading mode based on configuration
    if ENABLE_UPSERT_MODE:
        # UPSERT mode: ON CONFLICT DO UPDATE (for aggregate tables)
        actual_upsert_keys = (
            upsert_keys if upsert_keys is not None else DEFAULT_UPSERT_KEYS
        )
        load_result = warehouse_loader.load_dataframe(
            dataframe,
            table=table_name,
            schema=schema,
            upsert_keys=actual_upsert_keys,
        )
    else:
        # REFRESH mode: DELETE + INSERT (for detail tables)
        actual_refresh_keys = (
            refresh_keys if refresh_keys is not None else DEFAULT_REFRESH_KEYS
        )
        load_result = warehouse_loader.load_with_refresh(
            dataframe,
            table=table_name,
            schema=schema,
            refresh_keys=actual_refresh_keys,
        )
    duration_ms = (time.perf_counter() - start_time) * 1000
    rows_failed = max(discovery_result.row_count - len(processing.records), 0)
    rows_loaded = load_result.rows_inserted + load_result.rows_updated
    logger.bind(domain=domain, step="pipeline_completed").info(
        "annuity.pipeline.completed",
        month=normalized_month,
        rows_loaded=rows_loaded,
        rows_failed=rows_failed,
        duration_ms=duration_ms,
    )

    def _to_dict(obj: Any) -> Dict[str, Any]:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # type: ignore[no-any-return]
        return getattr(obj, "__dict__", obj)  # type: ignore[no-any-return]

    metrics = {
        "parameters": {
            "month": normalized_month,
            "domain": domain,
            "table": table_name,
            "schema": schema,
        },
        "discovery": _to_dict(discovery_result),
        "processing": _to_dict(processing),
        "loading": _to_dict(load_result),
    }
    return DomainPipelineResult(
        success=True,
        rows_loaded=rows_loaded,
        rows_failed=rows_failed,
        duration_ms=duration_ms,
        file_path=Path(discovery_result.file_path),
        version=discovery_result.version,
        metrics=metrics,
    )


def process_with_enrichment(
    rows: List[Dict[str, Any]],
    data_source: str = "unknown",
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
) -> ProcessingResultWithEnrichment:
    if not rows:
        logger.bind(domain="annuity_performance", step="process_with_enrichment").info(
            "No rows provided for processing"
        )
        return ProcessingResultWithEnrichment(
            records=[],
            data_source=data_source,
            unknown_names_csv=None,
            processing_time_ms=0,
        )

    plan_overrides = load_plan_override_mapping()
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=enrichment_service,
        plan_override_mapping=plan_overrides,
        sync_lookup_budget=sync_lookup_budget,
    )
    context = PipelineContext(
        pipeline_name="bronze_to_silver",
        execution_id=f"annuity-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_performance", "data_source": data_source},
        domain="annuity_performance",
        run_id=f"annuity-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        extra={"data_source": data_source},
    )
    start_time = time.perf_counter()
    input_df = pd.DataFrame(rows)
    result_df = pipeline.execute(input_df.copy(), context)
    # Keep all original records - no aggregation for business detail data
    records, unknown_names = convert_dataframe_to_models(result_df)
    dropped_count = len(rows) - len(records)
    if dropped_count > 0:
        drop_rate = dropped_count / len(rows) if rows else 0
        if drop_rate > 0.5:
            logger.bind(
                domain="annuity_performance", step="process_with_enrichment"
            ).warning(
                "High row drop rate during processing",
                dropped=dropped_count,
                total=len(rows),
                rate=drop_rate,
            )
        # Export failed rows to CSV for debugging (Story 5.6.1)
        success_codes = {r.计划代码 for r in records}
        if "计划代码" in input_df.columns:
            failed_df = input_df[~input_df["计划代码"].isin(success_codes)]
        else:
            failed_df = input_df
        if not failed_df.empty:
            error_csv_path = export_error_csv(
                failed_df,
                filename_prefix=f"failed_records_{Path(data_source).stem}",
                output_dir=Path("logs"),
            )
            logger.bind(
                domain="annuity_performance", step="process_with_enrichment"
            ).info(
                "Exported failed records to CSV",
                csv_path=str(error_csv_path),
                count=len(failed_df),
            )
    csv_path = export_unknown_names_csv(
        unknown_names,
        data_source,
        export_enabled=export_unknown_names,
    )
    processing_time_ms = int((time.perf_counter() - start_time) * 1000)
    enrichment_stats = summarize_enrichment(
        total_rows=len(rows),
        temp_ids=len(unknown_names),
        processing_time_ms=processing_time_ms,
    )

    return ProcessingResultWithEnrichment(
        records=records,
        enrichment_stats=enrichment_stats,
        unknown_names_csv=csv_path,
        data_source=data_source,
        processing_time_ms=processing_time_ms,
    )


def _records_to_dataframe(records: List[AnnuityPerformanceOut]) -> pd.DataFrame:
    return (
        pd.DataFrame(
            [
                r.model_dump(mode="json", by_alias=True, exclude_none=True)
                for r in records
            ]
        )
        if records
        else pd.DataFrame()
    )
