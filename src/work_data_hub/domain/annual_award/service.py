"""Annual Award (当年中标) domain - Business Service Layer.

Main entry point for processing annual award data.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Literal, Optional

import pandas as pd
import structlog

from work_data_hub.config import get_domain_output_config
from work_data_hub.domain.pipelines.types import DomainPipelineResult, PipelineContext

from .helpers import (
    FileDiscoveryProtocol,
    convert_dataframe_to_models,
    export_failed_records_csv,
    normalize_month,
    run_discovery,
)
from .models import AnnualAwardOut, AnnualAwardProcessingResult
from .pipeline_builder import build_bronze_to_silver_pipeline
from .schemas import validate_gold_dataframe

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# =============================================================================
# Data Loading Configuration
# =============================================================================
# This domain uses REFRESH mode (DELETE + INSERT) because it contains detail
# records where the same key combination can have multiple rows.
# =============================================================================

# Enable/disable UPSERT mode (requires UNIQUE constraint on upsert_keys)
ENABLE_UPSERT_MODE = False  # Detail table - use refresh mode

# REFRESH keys (used when ENABLE_UPSERT_MODE = False)
# Defines scope for DELETE before INSERT
DEFAULT_REFRESH_KEYS = ["上报月份", "业务类型"]


def process_annual_award(
    month: str,
    *,
    file_discovery: FileDiscoveryProtocol,
    warehouse_loader: Any,
    source_type: Literal["trustee", "investee", "both"] = "both",
    domain: str = "annual_award",
    table_name: Optional[str] = None,
    schema: Optional[str] = None,
    refresh_keys: Optional[List[str]] = None,
    is_validation_mode: bool = True,
) -> DomainPipelineResult:
    """Process Annual Award (当年中标) domain data.

    Service API Contract:
    ---------------------
    Parameters:
        month: Report month in YYYYMM format (e.g., "202501")
        file_discovery: FileDiscoveryProtocol implementation for locating source files
        warehouse_loader: Data warehouse loader for persisting results
        source_type: Which source sheet(s) to process:
            - "trustee": Only 企年受托中标 sheet
            - "investee": Only 企年投资中标 sheet
            - "both": Process both sheets (default)
        domain: Domain identifier (default: "annual_award")
        table_name: Target database table name
        schema: Database schema name
        refresh_keys: Columns for refresh scope (default: ["上报月份", "业务类型"])
        is_validation_mode: Whether running in validation mode

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
            table_name = config_table or "当年中标"
        if schema is None:
            schema = config_schema or "customer"

    normalized_month = normalize_month(month)
    start_time = time.perf_counter()

    logger.bind(domain=domain, step="pipeline_start").info(
        "annual_award.pipeline.start",
        month=normalized_month,
        source_type=source_type,
        table=table_name,
    )

    # Process based on source type
    all_records: List[AnnualAwardOut] = []
    total_failed = 0
    file_paths: List[Path] = []

    if source_type in ("trustee", "both"):
        trustee_result = _process_source_sheet(
            month=normalized_month,
            file_discovery=file_discovery,
            sheet_type="trustee",
            domain=domain,
        )
        all_records.extend(trustee_result.records)
        total_failed += trustee_result.failed_count
        if trustee_result.data_source != "unknown":
            file_paths.append(Path(trustee_result.data_source))

    if source_type in ("investee", "both"):
        investee_result = _process_source_sheet(
            month=normalized_month,
            file_discovery=file_discovery,
            sheet_type="investee",
            domain=domain,
        )
        all_records.extend(investee_result.records)
        total_failed += investee_result.failed_count
        if investee_result.data_source != "unknown":
            file_paths.append(Path(investee_result.data_source))

    # Convert to DataFrame for loading
    if all_records:
        dataframe = pd.DataFrame([r.model_dump() for r in all_records])
    else:
        dataframe = pd.DataFrame()

    # Load to warehouse using REFRESH mode
    actual_refresh_keys = (
        refresh_keys if refresh_keys is not None else DEFAULT_REFRESH_KEYS
    )

    if not dataframe.empty:
        load_result = warehouse_loader.load_with_refresh(
            dataframe,
            table=table_name,
            schema=schema,
            refresh_keys=actual_refresh_keys,
        )
        rows_loaded = load_result.rows_inserted + load_result.rows_updated
    else:
        rows_loaded = 0

    duration_ms = (time.perf_counter() - start_time) * 1000

    logger.bind(domain=domain, step="pipeline_completed").info(
        "annual_award.pipeline.completed",
        month=normalized_month,
        source_type=source_type,
        rows_loaded=rows_loaded,
        rows_failed=total_failed,
        duration_ms=duration_ms,
    )

    metrics = {
        "parameters": {
            "month": normalized_month,
            "domain": domain,
            "source_type": source_type,
            "table": table_name,
            "schema": schema,
        },
        "processing": {
            "total_records": len(all_records),
            "failed_records": total_failed,
        },
    }

    return DomainPipelineResult(
        success=True,
        rows_loaded=rows_loaded,
        rows_failed=total_failed,
        duration_ms=duration_ms,
        file_path=file_paths[0] if file_paths else Path("."),
        version="unknown",
        metrics=metrics,
    )


def _process_source_sheet(
    month: str,
    file_discovery: FileDiscoveryProtocol,
    sheet_type: Literal["trustee", "investee"],
    domain: str,
) -> AnnualAwardProcessingResult:
    """Process a single source sheet (trustee or investee)."""
    # Use correct product line names per mapping."产品线" table
    business_type = "企年受托" if sheet_type == "trustee" else "企年投资"

    try:
        # Try to discover and load the file
        discovery_result = run_discovery(
            file_discovery=file_discovery,
            domain=domain,
            month=month,
        )

        df = discovery_result.df.copy()
        data_source = str(discovery_result.file_path)

    except Exception as e:
        logger.bind(domain=domain, step="discovery").warning(
            f"Failed to discover {sheet_type} sheet",
            error=str(e),
        )
        return AnnualAwardProcessingResult(
            records=[],
            source_type=sheet_type,
            total_count=0,
            success_count=0,
            failed_count=0,
            processing_time_ms=0,
            data_source="unknown",
        )

    start_time = time.perf_counter()

    # Ensure business type is set
    df["业务类型"] = business_type

    # Build and execute pipeline
    pipeline = build_bronze_to_silver_pipeline()
    context = PipelineContext(
        pipeline_name="bronze_to_silver",
        execution_id=f"annual_award-{sheet_type}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=datetime.now(timezone.utc),
        config={"domain": domain, "sheet_type": sheet_type},
        domain=domain,
        run_id=f"annual_award-{sheet_type}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        extra={"sheet_type": sheet_type},
    )

    result_df = pipeline.execute(df, context)

    # Validate Gold layer
    result_df, _ = validate_gold_dataframe(result_df)

    # Convert to models
    records, failed_count = convert_dataframe_to_models(result_df)

    processing_time_ms = int((time.perf_counter() - start_time) * 1000)

    # Export failed records if any
    if failed_count > 0:
        failed_df = df.iloc[len(records) :]  # Simple approximation
        if not failed_df.empty:
            export_failed_records_csv(failed_df, f"{sheet_type}_{month}")

    return AnnualAwardProcessingResult(
        records=records,
        source_type=sheet_type,
        total_count=len(df),
        success_count=len(records),
        failed_count=failed_count,
        processing_time_ms=processing_time_ms,
        data_source=data_source,
    )


__all__ = [
    "process_annual_award",
    "ENABLE_UPSERT_MODE",
    "DEFAULT_REFRESH_KEYS",
]
