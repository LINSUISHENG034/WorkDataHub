from __future__ import annotations

import logging
from typing import Any, List, Optional, Protocol, Tuple

import pandas as pd
import structlog
from pydantic import ValidationError

from work_data_hub.domain.annuity_income.models import (
    AnnuityIncomeOut,
    EnrichmentStats,
)
from work_data_hub.domain.pipelines.types import ErrorContext

# Shared helper imported from infrastructure (Story 5.5.4 extraction)
from work_data_hub.infrastructure.helpers import normalize_month
from work_data_hub.infrastructure.validation import export_error_csv
from work_data_hub.utils.date_parser import (
    parse_chinese_date,
    parse_report_date,
    parse_report_period,
)

logger = logging.getLogger(__name__)
event_logger = structlog.get_logger(__name__)


class FileDiscoveryProtocol(Protocol):
    """Protocol for file discovery services."""

    def discover_and_load(self, *, domain: str, month: str) -> Any: ...


def run_discovery(
    *, file_discovery: FileDiscoveryProtocol, domain: str, month: str
) -> Any:
    """Run file discovery for the specified domain and month."""
    try:
        return file_discovery.discover_and_load(domain=domain, month=month)
    except Exception as exc:  # noqa: BLE001
        error_ctx = ErrorContext(
            error_type="discovery_error",
            operation="file_discovery",
            domain=domain,
            stage="discovery",
            error_message=f"Failed to discover file for {domain} month {month}",
            details={"month": month, "exception": str(exc)},
        )
        logger.error("annuity_income.discovery.failed", extra=error_ctx.to_log_dict())
        raise


# NOTE(5.5.4-deferred): Extraction deferred to Epic 6
# Reason: Requires generic factory pattern with type parameters (model class +
# required keys)
# See: docs/sprint-artifacts/epic-5.5-optimization-recommendations.md "Reuse Candidates"
# table
# Duplicated from: annuity_performance/helpers.py (with model type change)
# Reuse potential: MEDIUM - Epic 6 will implement generic version
def convert_dataframe_to_models(
    df: pd.DataFrame,
) -> Tuple[List[AnnuityIncomeOut], List[str]]:
    """Convert DataFrame rows to AnnuityIncomeOut models."""
    records: List[AnnuityIncomeOut] = []
    unknown_names: List[str] = []
    allowed_fields = set(AnnuityIncomeOut.model_fields.keys())

    for idx, row in df.iterrows():
        try:
            row_dict = {
                key: (None if pd.isna(val) else val)
                for key, val in row.to_dict().items()
            }
            row_dict = {k: v for k, v in row_dict.items() if k in allowed_fields}
            if not row_dict.get("计划号") or row_dict.get("月度") is None:
                continue

            # type ignore: Dynamic dictionary unpacking for Pydantic model
            record = AnnuityIncomeOut(**row_dict)  # type: ignore[arg-type]
            records.append(record)

            if record.company_id and record.company_id.startswith("IN"):
                customer_name = row_dict.get("客户名称")
                if customer_name:
                    unknown_names.append(str(customer_name))
        except ValidationError as exc:
            event_logger.bind(domain="annuity_income", step="convert_to_models").debug(
                "Row validation failed", row_index=idx, error=str(exc)
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            event_logger.bind(
                domain="annuity_income", step="convert_to_models"
            ).warning("Row unexpected error", row_index=idx, error=str(exc))

    return records, unknown_names


def export_unknown_names_csv(
    unknown_names: List[str],
    data_source: str,
    *,
    export_enabled: bool = True,
) -> Optional[str]:
    """
    Export unknown company names to CSV using infrastructure validation utilities.
    """
    if not export_enabled or not unknown_names:
        return None

    from pathlib import Path

    try:
        df = pd.DataFrame({"unknown_company_name": unknown_names})
        csv_path = export_error_csv(
            df,
            filename_prefix=f"unknown_companies_{data_source}",
            output_dir=Path("logs"),
        )
        event_logger.bind(domain="annuity_income", step="export_unknown_names").info(
            "Exported unknown company names",
            count=len(unknown_names),
            path=str(csv_path),
        )
        return str(csv_path)
    except Exception as exc:  # pragma: no cover - defensive logging
        event_logger.bind(domain="annuity_income", step="export_unknown_names").warning(
            "Failed to export unknown names CSV", error=str(exc)
        )
        return None


def summarize_enrichment(
    total_rows: int,
    temp_ids: int,
    processing_time_ms: int,
) -> EnrichmentStats:
    """Build enrichment statistics object."""
    return EnrichmentStats(
        total_records=total_rows,
        temp_assigned=temp_ids,
        processing_time_ms=processing_time_ms,
    )


__all__ = [
    "FileDiscoveryProtocol",
    "convert_dataframe_to_models",
    "export_unknown_names_csv",
    "normalize_month",
    "parse_report_date",
    "parse_report_period",
    "run_discovery",
    "summarize_enrichment",
    "parse_chinese_date",
]
