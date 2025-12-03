"""Lightweight helpers for annuity performance processing (Story 5.7 refactor)."""

from __future__ import annotations

from typing import List, Optional, Tuple

import structlog

import pandas as pd
from pydantic import ValidationError

from work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceOut,
    EnrichmentStats,
)
from work_data_hub.utils.date_parser import parse_chinese_date

logger = structlog.get_logger(__name__)


class AnnuityPerformanceTransformationError(Exception):
    """Raised when annuity performance data transformation fails."""


def convert_dataframe_to_models(
    df: pd.DataFrame,
) -> Tuple[List[AnnuityPerformanceOut], List[str]]:
    """
    Convert a transformed DataFrame into validated domain models.

    Unknown companies are inferred via IN_* temporary IDs emitted by CompanyIdResolver.
    """
    records: List[AnnuityPerformanceOut] = []
    unknown_names: List[str] = []

    for idx, row in df.iterrows():
        try:
            row_dict = {
                key: (None if pd.isna(val) else val) for key, val in row.to_dict().items()
            }

            # Require minimal fields (plan code + month) to build a record
            if not row_dict.get("计划代码") or row_dict.get("月度") is None:
                continue

            record = AnnuityPerformanceOut(**row_dict)
            records.append(record)

            if record.company_id and record.company_id.startswith("IN"):
                customer_name = row_dict.get("客户名称")
                if customer_name:
                    unknown_names.append(str(customer_name))
        except ValidationError as exc:
            logger.bind(domain="annuity_performance", step="convert_to_models").debug(
                "Row validation failed", row_index=idx, error=str(exc)
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.bind(domain="annuity_performance", step="convert_to_models").warning(
                "Row unexpected error", row_index=idx, error=str(exc)
            )

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

    from work_data_hub.infrastructure.validation import export_error_csv

    try:
        df = pd.DataFrame({"unknown_company_name": unknown_names})
        csv_path = export_error_csv(
            df,
            filename_prefix=f"unknown_companies_{data_source}",
            output_dir=Path("logs"),
        )
        logger.bind(domain="annuity_performance", step="export_unknown_names").info(
            "Exported unknown company names", count=len(unknown_names), path=str(csv_path)
        )
        return str(csv_path)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.bind(domain="annuity_performance", step="export_unknown_names").warning(
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


def parse_report_period(report_period: str) -> Optional[Tuple[int, int]]:
    """
    Parse year and month from common report period formats.
    """
    if not report_period:
        return None

    from re import search

    patterns = [
        r"(\d{4})[年\-/](\d{1,2})",  # 2024年11月 / 2024-11 / 2024/11
        r"(\d{4})(\d{2})",  # 202411
        r"(\d{2})年(\d{1,2})",  # 24年11月
    ]

    for pattern in patterns:
        match = search(pattern, report_period)
        if not match:
            continue
        try:
            year, month = int(match.group(1)), int(match.group(2))
            if year < 50:
                year += 2000
            elif 50 <= year < 100:
                year += 1900
            return (year, month)
        except ValueError:
            continue

    return None


def parse_report_date(value: str) -> Optional[pd.Timestamp]:
    """
    Parse a single value into a date using the shared Chinese date parser.
    """
    if value is None:
        return None

    try:
        parsed = parse_chinese_date(value)
        if hasattr(parsed, "date"):
            return parsed.date()
        return parsed
    except Exception:  # pragma: no cover - defensive logging
        logger.bind(domain="annuity_performance", step="parse_report_date").debug(
            "Unable to parse report date value", value=value
        )
        return None


__all__ = [
    "AnnuityPerformanceTransformationError",
    "convert_dataframe_to_models",
    "export_unknown_names_csv",
    "summarize_enrichment",
    "parse_report_period",
    "parse_report_date",
]
