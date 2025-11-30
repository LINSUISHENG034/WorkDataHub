"""
Pure transformation service for annuity performance data.

This module provides pure functions for transforming raw Excel data from
"规模明细" sheets into validated annuity performance domain objects. All
functions are side-effect free and fully testable. Includes column projection
to prevent SQL column mismatch errors.

Story 4.8: Refactored for maintainability:
- ErrorContext and PipelineResult moved to domain/pipelines/types.py
- Discovery helpers moved to discovery_helpers.py
- Processing helpers moved to processing_helpers.py
- Re-exports maintained for backward compatibility
"""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import pandas as pd

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
    from work_data_hub.io.connectors.file_connector import (
        DataDiscoveryResult,
        FileDiscoveryService,
    )
    from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

from work_data_hub.domain.pipelines.types import (
    DomainPipelineResult,
    ErrorContext,
)

from .constants import DEFAULT_ALLOWED_GOLD_COLUMNS
from .discovery_helpers import normalize_month, run_discovery
from .models import (
    AnnuityPerformanceOut,
    EnrichmentStats,
    ProcessingResultWithEnrichment,
)
from .processing_helpers import (
    AnnuityPerformanceTransformationError,
    export_unknown_names_csv,
    extract_company_code,
    extract_plan_code,
    extract_report_date,
    log_enrichment_stats,
    process_rows_via_pipeline,
    validate_processing_results,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Story 4.8: Re-exports for backward compatibility
# =============================================================================

# PipelineResult is now DomainPipelineResult in types.py
PipelineResult = DomainPipelineResult

# Re-export discovery helpers (were private functions)
_run_discovery = run_discovery
_normalize_month = normalize_month

# Re-export processing helpers (were private functions)
from .processing_helpers import (
    extract_financial_metrics,
    extract_metadata_fields,
    transform_single_row,
    pipeline_row_to_model,
    apply_enrichment_integration,
)

_process_rows_via_pipeline = process_rows_via_pipeline
_validate_processing_results = validate_processing_results
_export_unknown_names_csv = export_unknown_names_csv
_log_enrichment_stats = log_enrichment_stats
_extract_report_date = extract_report_date
_extract_plan_code = extract_plan_code
_extract_company_code = extract_company_code
_extract_financial_metrics = extract_financial_metrics
_extract_metadata_fields = extract_metadata_fields
_transform_single_row = transform_single_row
_pipeline_row_to_model = pipeline_row_to_model
_apply_enrichment_integration = apply_enrichment_integration


# =============================================================================
# Public API Functions
# =============================================================================


def get_allowed_columns() -> List[str]:
    """
    Return the canonical list of columns allowed in the gold table.

    This list mirrors the database schema and is shared across the legacy
    service path and the pipeline-based Gold projection step so that column
    projection stays consistent regardless of execution mode.
    """
    return list(DEFAULT_ALLOWED_GOLD_COLUMNS)


def project_columns(
    rows: List[Dict[str, Any]], allowed_cols: List[str]
) -> List[Dict[str, Any]]:
    """
    Filter dictionary keys to only allowed columns for safe SQL loading.

    This prevents column-not-found errors when Excel files contain more
    columns than the database schema expects.

    Args:
        rows: List of row dictionaries from Excel
        allowed_cols: List of column names allowed in database

    Returns:
        List of dictionaries with only allowed columns
    """
    if not rows:
        return []

    logger.debug(
        f"Projecting {len(rows)} rows to allowed columns: {len(allowed_cols)} columns"
    )

    # Use dictionary comprehension for memory efficiency
    projected_rows = [{k: row.get(k) for k in allowed_cols if k in row} for row in rows]

    if projected_rows:
        original_cols = set(rows[0].keys()) if rows else set()
        projected_cols = set(projected_rows[0].keys()) if projected_rows else set()
        removed_cols = original_cols - projected_cols
        if removed_cols:
            logger.debug(f"Removed columns during projection: {sorted(removed_cols)}")

    return projected_rows


def process_annuity_performance(
    month: str,
    *,
    file_discovery: "FileDiscoveryService",
    warehouse_loader: "WarehouseLoader",
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    domain: str = "annuity_performance",
    table_name: str = "annuity_performance_NEW",
    schema: str = "public",
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
    upsert_keys: Optional[List[str]] = None,
) -> PipelineResult:
    """
    Execute the complete annuity performance pipeline for the requested month.

    Flow:
        1. Discover and load the Excel file via FileDiscoveryService
        2. Transform + validate rows using process_with_enrichment()
        3. Load the resulting DataFrame to PostgreSQL through WarehouseLoader

    Story 4.9: Simplified to use pipeline-only path (legacy path removed).

    Args:
        month: Target reporting month in YYYYMM format
        file_discovery: Injected FileDiscoveryService (Epic 3)
        warehouse_loader: Injected WarehouseLoader (Epic 1 Story 1.8)
        enrichment_service: Optional enrichment dependency (Epic 5 stub)
        domain: Domain identifier used in discovery config
        table_name: Warehouse table (shadow table for MVP)
        schema: Warehouse schema name
        sync_lookup_budget: Budget passed to enrichment for sync lookups
        export_unknown_names: Whether to export unknown companies CSV
        upsert_keys: Override composite key list (defaults to 月度/计划代码/company_id)

    Returns:
        PipelineResult metadata object

    Raises:
        DiscoveryError: Source file could not be located
        AnnuityPerformanceTransformationError: Validation failed catastrophically
        DataWarehouseLoaderError: Database load failed
        ValueError: Invalid month parameter
    """
    normalized_month = normalize_month(month)
    start_time = time.perf_counter()
    metrics: Dict[str, Any] = {
        "parameters": {
            "month": normalized_month,
            "domain": domain,
            "table": table_name,
            "schema": schema,
        }
    }

    logger.info(
        "annuity.pipeline.start",
        extra={"month": normalized_month, "domain": domain, "table": table_name},
    )

    discovery_result = run_discovery(
        file_discovery=file_discovery,
        domain=domain,
        month=normalized_month,
    )
    metrics["discovery"] = {
        "row_count": discovery_result.row_count,
        "column_count": discovery_result.column_count,
        "duration_ms": discovery_result.duration_ms,
        "stage_durations": discovery_result.stage_durations,
    }

    raw_rows = discovery_result.df.to_dict(orient="records")
    processing_result = process_with_enrichment(
        raw_rows,
        data_source=str(discovery_result.file_path),
        enrichment_service=enrichment_service,
        sync_lookup_budget=sync_lookup_budget,
        export_unknown_names=export_unknown_names,
    )

    metrics["processing"] = {
        "input_rows": len(raw_rows),
        "output_rows": len(processing_result.records),
        "processing_time_ms": processing_result.processing_time_ms,
        "enrichment": processing_result.enrichment_stats.model_dump(),
        "unknown_names_csv": processing_result.unknown_names_csv,
    }

    dataframe = _records_to_dataframe(processing_result.records)
    load_result = warehouse_loader.load_dataframe(
        dataframe,
        table=table_name,
        schema=schema,
        upsert_keys=upsert_keys or ["月度", "计划代码", "company_id"],
    )

    metrics["loading"] = {
        "rows_inserted": load_result.rows_inserted,
        "rows_updated": load_result.rows_updated,
        "duration_ms": load_result.duration_ms,
        "execution_id": load_result.execution_id,
    }

    rows_failed = max(len(raw_rows) - len(processing_result.records), 0)
    rows_loaded = load_result.rows_inserted + load_result.rows_updated
    duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "annuity.pipeline.completed",
        extra={
            "month": normalized_month,
            "rows_loaded": rows_loaded,
            "rows_failed": rows_failed,
            "duration_ms": duration_ms,
        },
    )

    return PipelineResult(
        success=True,
        rows_loaded=rows_loaded,
        rows_failed=rows_failed,
        duration_ms=duration_ms,
        file_path=Path(discovery_result.file_path),
        version=discovery_result.version,
        metrics=metrics,
    )


def _records_to_dataframe(records: List[AnnuityPerformanceOut]) -> pd.DataFrame:
    """Convert processed Pydantic models into a pandas DataFrame for loading."""
    if not records:
        return pd.DataFrame()

    serialized = [
        record.model_dump(mode="json", by_alias=True, exclude_none=True)
        for record in records
    ]
    return pd.DataFrame(serialized)


def process_with_enrichment(
    rows: List[Dict[str, Any]],
    data_source: str = "unknown",
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
) -> ProcessingResultWithEnrichment:
    """
    Process raw Excel rows into validated annuity performance output models
    with optional enrichment.

    This is the full-featured entry point for the annuity performance domain
    service. It transforms raw dictionary data from "规模明细" Excel sheets into
    fully validated AnnuityPerformanceOut models ready for warehouse loading.

    When enrichment_service is provided, performs company ID resolution using
    internal mappings, EQC lookups, and async queue processing according to the
    configured budget and export settings.

    Story 4.9: Simplified to use pipeline-only path (legacy path removed).

    Args:
        rows: List of dictionaries representing Excel rows
        data_source: Identifier for the source file or system
        enrichment_service: Optional CompanyEnrichmentService for company ID
            resolution
        sync_lookup_budget: Budget for synchronous EQC lookups per processing
            session
        export_unknown_names: Whether to export unknown company names to CSV

    Returns:
        ProcessingResultWithEnrichment with processed records, statistics, and
        optional CSV export

    Raises:
        AnnuityPerformanceTransformationError: If transformation fails
        ValueError: If input data is invalid or cannot be processed
    """
    # Early return for empty input
    if not rows:
        logger.info("No rows provided for processing")
        return ProcessingResultWithEnrichment(
            records=[],
            data_source=data_source,
            unknown_names_csv=None,
            processing_time_ms=0,
        )

    if not isinstance(rows, list):
        raise ValueError("Rows must be provided as a list")

    logger.info(f"Processing {len(rows)} rows from data source: {data_source}")

    # Initialize tracking variables
    start_time = time.time()
    stats = EnrichmentStats()
    unknown_names: List[str] = []

    # Process rows using pipeline (Story 4.9: single execution path)
    processed_records, processing_errors = process_rows_via_pipeline(
        rows, data_source, enrichment_service, sync_lookup_budget,
        stats, unknown_names
    )

    # Validate results
    validate_processing_results(processed_records, processing_errors, len(rows))

    # Export unknown names if requested
    csv_path = export_unknown_names_csv(unknown_names, data_source, export_unknown_names)

    # Calculate final metrics
    processing_time_ms = int((time.time() - start_time) * 1000)
    stats.processing_time_ms = processing_time_ms

    # Log enrichment statistics
    log_enrichment_stats(
        enrichment_service, stats, processing_time_ms,
        len(unknown_names), bool(csv_path)
    )

    return ProcessingResultWithEnrichment(
        records=processed_records,
        enrichment_stats=stats,
        unknown_names_csv=csv_path,
        data_source=data_source,
        processing_time_ms=processing_time_ms,
    )


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    # Main entry points
    "process_annuity_performance",
    "process_with_enrichment",
    # Utility functions
    "get_allowed_columns",
    "project_columns",
    # Re-exported types (backward compatibility)
    "PipelineResult",
    "ErrorContext",
    "AnnuityPerformanceTransformationError",
]
