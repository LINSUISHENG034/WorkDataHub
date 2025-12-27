from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd
import structlog

from work_data_hub.config import get_domain_output_config
from work_data_hub.domain.pipelines.types import DomainPipelineResult, PipelineContext
from work_data_hub.infrastructure.constants import DROP_RATE_THRESHOLD
from work_data_hub.infrastructure.validation import export_error_csv

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

# =============================================================================
# Data Loading Configuration
# =============================================================================
# This domain uses REFRESH mode (DELETE + INSERT) because it contains detail
# records (明细数据) where the same key combination can have multiple rows.
#
# UPSERT mode (ON CONFLICT DO UPDATE) is NOT suitable for detail tables.
# UPSERT is only appropriate for aggregate tables with unique key combinations.
#
# Legacy equivalent: annuity_mapping.update_based_on_field = "月度"
# Updated to: "月度+业务类型+计划类型" per Sprint Change Proposal 2025-12-06
# =============================================================================

# Enable/disable UPSERT mode (requires UNIQUE constraint on upsert_keys)
ENABLE_UPSERT_MODE = False  # Detail table - use refresh mode instead

# UPSERT keys (only used when ENABLE_UPSERT_MODE = True)
# For aggregate tables with unique records per key combination
DEFAULT_UPSERT_KEYS: Optional[List[str]] = [
    "月度",
    "计划代码",
    "组合代码",
    "company_id",
]

# REFRESH keys (used when ENABLE_UPSERT_MODE = False)
# Defines scope for DELETE before INSERT (Legacy: update_based_on_field)
DEFAULT_REFRESH_KEYS = ["月度", "业务类型", "计划类型"]


def process_annuity_income(
    month: str,
    *,
    file_discovery: FileDiscoveryProtocol,
    warehouse_loader: Any,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    domain: str = "annuity_income",
    table_name: Optional[str] = None,
    schema: Optional[str] = None,
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
    upsert_keys: Optional[List[str]] = None,
    refresh_keys: Optional[List[str]] = None,
    is_validation_mode: bool = True,
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
        upsert_keys: Columns for upsert operation (default: 月度, 计划代码, company_id)

    Expected Inputs:
        Bronze DataFrame from discovered Excel file (sheet: 收入明细)
        Required columns: 月度, 机构/机构代码, 机构名称, 计划代码, 客户名称,
        业务类型, 计划类型, 组合代码, 固费, 浮费, 回补, 税

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
        All errors logged with domain tag 'annuity_income', PII (客户名称) scrubbed
        outside debug level.

    Returns:
        DomainPipelineResult with processing metrics and status
    """
    # Load output configuration from data_sources.yml if not explicitly provided
    if table_name is None or schema is None:
        config_table, config_schema = get_domain_output_config(
            domain,
            is_validation_mode=is_validation_mode,
        )
        if table_name is None:
            table_name = config_table
        if schema is None:
            schema = config_schema

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
        logger.bind(domain="annuity_income", step="process_with_enrichment").info(
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
        execution_id=f"annuity_income-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_income", "data_source": data_source},
        domain="annuity_income",
        run_id=f"annuity_income-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        extra={"data_source": data_source},
    )
    start_time = time.perf_counter()
    input_df = pd.DataFrame(rows)
    result_df = pipeline.execute(input_df.copy(), context)

    # Story 5.5.5: Enforce Gold schema validation (checks uniqueness of composite key)
    # This catches issues that Pydantic row-by-row validation misses
    result_df, _ = validate_gold_dataframe(result_df)

    records, unknown_names = convert_dataframe_to_models(result_df)
    dropped_count = len(rows) - len(records)
    if dropped_count > 0:
        drop_rate = dropped_count / len(rows) if rows else 0
        if drop_rate > DROP_RATE_THRESHOLD:
            logger.bind(
                domain="annuity_income", step="process_with_enrichment"
            ).warning(
                "High row drop rate during processing",
                dropped=dropped_count,
                total=len(rows),
                rate=drop_rate,
            )
        # Export failed rows to CSV for debugging (Story 5.6.1)
        success_pairs = {(r.计划代码, getattr(r, "组合代码", None)) for r in records}
        if {"计划代码", "组合代码"}.issubset(input_df.columns):
            key_series = pd.Series(
                list(zip(input_df["计划代码"], input_df["组合代码"]))
            )
            failed_df = input_df[~key_series.isin(success_pairs)]
        elif "计划代码" in input_df.columns:
            success_codes = {pair[0] for pair in success_pairs}
            failed_df = input_df[~input_df["计划代码"].isin(success_codes)]
        else:
            failed_df = input_df
        if not failed_df.empty:
            error_csv_path = export_error_csv(
                failed_df,
                filename_prefix=f"failed_records_{Path(data_source).stem}",
                output_dir=Path("logs"),
            )
            logger.bind(domain="annuity_income", step="process_with_enrichment").info(
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


def _records_to_dataframe(records: List[AnnuityIncomeOut]) -> pd.DataFrame:
    """Convert list of AnnuityIncomeOut models to DataFrame for warehouse loading."""
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(
        [r.model_dump(mode="json", by_alias=True, exclude_none=True) for r in records]
    )
    # Now 计划代码 is the standard column name (no need for legacy conversion)
    return df
