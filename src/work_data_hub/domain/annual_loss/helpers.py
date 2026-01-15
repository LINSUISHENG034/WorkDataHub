"""Annual Loss (当年流失) domain - Helper functions.

Data transformation utilities for the annual loss domain.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional, Protocol, Tuple

import pandas as pd
import structlog
from pydantic import ValidationError

from work_data_hub.domain.annual_loss.models import AnnualLossOut
from work_data_hub.domain.pipelines.types import ErrorContext
from work_data_hub.infrastructure.helpers import normalize_month
from work_data_hub.infrastructure.validation import export_error_csv
from work_data_hub.utils.date_parser import parse_chinese_date

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
    except Exception as exc:
        error_ctx = ErrorContext(
            error_type="discovery_error",
            operation="file_discovery",
            domain=domain,
            stage="discovery",
            error_message=f"Failed to discover file for {domain} month {month}",
            details={"month": month, "exception": str(exc)},
        )
        logger.error("annual_loss.discovery.failed", extra=error_ctx.to_log_dict())
        raise


def rename_customer_name_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Rename 客户全称 → 上报客户名称 and generate cleaned 客户名称.

    This implements requirement #5 from the proposal:
    - Original 客户名称 renamed to 上报客户名称
    - Clean using customer_name_normalize module to generate 客户名称
    """
    from work_data_hub.infrastructure.cleansing import clean_company_name

    df = df.copy()

    # Rename original customer name field
    if "客户全称" in df.columns:
        df = df.rename(columns={"客户全称": "上报客户名称"})

    # Generate cleaned customer name
    if "上报客户名称" in df.columns:
        df["客户名称"] = df["上报客户名称"].apply(
            lambda x: clean_company_name(x) if isinstance(x, str) and x else None
        )

    return df


def drop_excluded_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop excluded columns: 区域, 年金中心, 上报人, 考核标签.

    This implements requirement #1 from the proposal.
    """
    columns_to_drop = ["区域", "年金中心", "上报人", "考核标签"]
    existing_columns = [col for col in columns_to_drop if col in df.columns]
    if existing_columns:
        df = df.drop(columns=existing_columns)
    return df


def conditional_update_plan_and_company(df: pd.DataFrame) -> pd.DataFrame:
    """Conditionally update 年金计划号 and company_id only if original is empty.

    This implements requirement #4 from the proposal:
    - If original 年金计划号 and company_id are non-empty, keep original values
    - Otherwise, apply enrichment logic
    """
    # For now, just pass through - enrichment will be handled in pipeline
    return df


def map_branch_code(df: pd.DataFrame) -> pd.DataFrame:
    """Map 机构 to 机构代码 using branch mapping."""
    from work_data_hub.infrastructure.cleansing.mappings import (
        COMPANY_BRANCH_MAPPING,
    )

    df = df.copy()
    if "机构" in df.columns:
        df["机构代码"] = df["机构"].map(COMPANY_BRANCH_MAPPING)
        # Default to headquarters code if mapping fails
        df["机构代码"] = df["机构代码"].fillna("G00")
    return df


def convert_dataframe_to_models(
    df: pd.DataFrame,
) -> Tuple[List[AnnualLossOut], int]:
    """Convert DataFrame rows to AnnualLossOut models.

    Returns:
        Tuple of (list of valid records, count of failed records)
    """
    records: List[AnnualLossOut] = []
    failed_count = 0
    allowed_fields = set(AnnualLossOut.model_fields.keys())

    for idx, row in df.iterrows():
        try:
            row_dict = {
                key: (None if pd.isna(val) else val)
                for key, val in row.to_dict().items()
            }
            row_dict = {k: v for k, v in row_dict.items() if k in allowed_fields}

            # Required fields check
            if not row_dict.get("上报月份") or not row_dict.get("业务类型"):
                failed_count += 1
                continue
            if not row_dict.get("上报客户名称"):
                failed_count += 1
                continue

            record = AnnualLossOut(**row_dict)
            records.append(record)
        except ValidationError as exc:
            event_logger.bind(domain="annual_loss", step="convert_to_models").debug(
                "Row validation failed", row_index=idx, error=str(exc)
            )
            failed_count += 1
        except Exception as exc:
            event_logger.bind(domain="annual_loss", step="convert_to_models").warning(
                "Row unexpected error", row_index=idx, error=str(exc)
            )
            failed_count += 1

    return records, failed_count


def export_failed_records_csv(
    df: pd.DataFrame,
    data_source: str,
) -> Optional[str]:
    """Export failed records to CSV for debugging."""
    if df.empty:
        return None

    try:
        csv_path = export_error_csv(
            df,
            filename_prefix=f"failed_annual_loss_{data_source}",
            output_dir=Path("logs"),
        )
        event_logger.bind(domain="annual_loss", step="export_failed").info(
            "Exported failed records",
            count=len(df),
            path=str(csv_path),
        )
        return str(csv_path)
    except Exception as exc:
        event_logger.bind(domain="annual_loss", step="export_failed").warning(
            "Failed to export failed records CSV", error=str(exc)
        )
        return None


__all__ = [
    "FileDiscoveryProtocol",
    "convert_dataframe_to_models",
    "conditional_update_plan_and_company",
    "drop_excluded_columns",
    "export_failed_records_csv",
    "map_branch_code",
    "normalize_month",
    "parse_chinese_date",
    "rename_customer_name_fields",
    "run_discovery",
]
