from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import DomainPipelineResult, PipelineContext

from .helpers import (
    FileDiscoveryProtocol,
    convert_dataframe_to_models,
    export_unknown_names_csv,
    normalize_month,
    run_discovery,
    summarize_enrichment,
)
from .models import AnnuityIncomeOut, ProcessingResultWithEnrichment
from .pipeline_builder import (
    build_bronze_to_silver_pipeline,
    load_plan_override_mapping,
)
from .schemas import validate_gold_dataframe

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = structlog.get_logger(__name__)


def process_annuity_income(
    month: str,
    *,
    file_discovery: FileDiscoveryProtocol,
    warehouse_loader: Any,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    domain: str = "annuity_income",
    table_name: str = "annuity_income_NEW",
    schema: str = "public",
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
    upsert_keys: Optional[List[str]] = None,
) -> DomainPipelineResult:
    """
    Process AnnuityIncome domain data from bronze to gold layer.

    Service API Contract:
    ---------------------
    Parameters:
        month: Report month in YYYYMM format (e.g., "202412")
        file_discovery: FileDiscoveryProtocol implementation for locating source files
        warehouse_loader: Data warehouse loader for persisting results
        enrichment_service: Optional CompanyEnrichmentService for external ID resolution
        domain: Domain identifier (default: "annuity_income")
        table_name: Target database table name
        schema: Database schema name
        sync_lookup_budget: Maximum synchronous EQC lookups allowed
        export_unknown_names: Whether to export unresolved company names to CSV
        upsert_keys: Columns for upsert operation (default: 月度, 计划号, company_id)

    Expected Inputs:
        Bronze DataFrame from discovered Excel file (sheet: 收入明细)
        Required columns: 月度, 机构/机构代码, 机构名称, 计划号/计划代码, 客户名称, 业务类型,
        计划类型, 组合代码, 固费, 浮费, 回补, 税

    Outputs:
        DomainPipelineResult containing:
        - success: bool
        - rows_loaded: int
        - rows_failed: int
        - duration_ms: float
        - file_path: Path
        - version: str
        - metrics: Dict with discovery, processing, loading details

    Failure Modes:
        - FileNotFoundError: Source file not discovered
        - ValidationError: Schema validation failures
        - DatabaseError: Warehouse loading failures
        All errors logged with domain tag 'annuity_income', PII (客户名称) scrubbed outside debug level.

    Returns:
        DomainPipelineResult with processing metrics and status
    """
    normalized_month = normalize_month(month)
    start_time = time.perf_counter()
    logger.bind(domain=domain, step="pipeline_start").info(
        "annuity_income.pipeline.start",
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
    load_result = warehouse_loader.load_dataframe(
        dataframe,
        table=table_name,
        schema=schema,
        upsert_keys=upsert_keys or ["月度", "计划号", "组合代码", "company_id"],
    )
    duration_ms = (time.perf_counter() - start_time) * 1000
    rows_failed = max(discovery_result.row_count - len(processing.records), 0)
    rows_loaded = load_result.rows_inserted + load_result.rows_updated
    logger.bind(domain=domain, step="pipeline_completed").info(
        "annuity_income.pipeline.completed",
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
    """
    Process raw rows through the bronze-to-silver pipeline with optional enrichment.

    This is the core processing function that:
    1. Builds the transformation pipeline
    2. Executes all pipeline steps (mapping, cleansing, ID resolution)
    3. Converts results to validated Pydantic models
    4. Exports unknown company names for manual review

    Parameters:
        rows: List of dictionaries from bronze layer (Excel rows)
        data_source: Source file identifier for logging/tracking
        enrichment_service: Optional external enrichment service
        sync_lookup_budget: Max synchronous lookups for enrichment
        export_unknown_names: Whether to export unresolved names to CSV

    Returns:
        ProcessingResultWithEnrichment containing validated records and stats
    """
    if not rows:
        logger.bind(domain="annuity_income", step="process_with_enrichment").info("No rows provided for processing")
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
        execution_id=f"annuity_income-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_income", "data_source": data_source},
        domain="annuity_income",
        run_id=f"annuity_income-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        extra={"data_source": data_source},
    )
    start_time = time.perf_counter()
    result_df = pipeline.execute(pd.DataFrame(rows), context)

    # Story 5.5.5: Enforce Gold schema validation (checks uniqueness of composite key)
    # This catches issues that Pydantic row-by-row validation misses
    result_df, _ = validate_gold_dataframe(result_df)

    records, unknown_names = convert_dataframe_to_models(result_df)
    dropped_count = len(rows) - len(records)
    if dropped_count > 0:
        drop_rate = dropped_count / len(rows) if rows else 0
        if drop_rate > 0.5:
            logger.bind(domain="annuity_income", step="process_with_enrichment").warning(
                "High row drop rate during processing",
                dropped=dropped_count,
                total=len(rows),
                rate=drop_rate,
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


def _records_to_dataframe(records: List[AnnuityIncomeOut]) -> pd.DataFrame:
    """Convert list of AnnuityIncomeOut models to DataFrame for warehouse loading."""
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame([r.model_dump(mode="json", by_alias=True, exclude_none=True) for r in records])
    # Keep both plan columns for parity with annuity_performance
    if "计划代码" not in df.columns and "计划号" in df.columns:
        df["计划代码"] = df["计划号"]
    return df
