"""Annual Loss (流失客户明细) domain - Pandera schemas.

DataFrame-level validation schemas for Bronze and Gold layers.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Sequence, Tuple

import pandas as pd
import pandera.pandas as pa

from work_data_hub.infrastructure.models.shared import (
    BronzeValidationSummary,
    GoldValidationSummary,
)
from work_data_hub.infrastructure.validation.domain_validators import (
    validate_bronze_dataframe as _validate_bronze,
)

# AnnualLoss column definitions
BRONZE_REQUIRED_COLUMNS: Sequence[str] = (
    "上报月份",
    "业务类型",
    "客户全称",  # Will be renamed to 上报客户名称 in pipeline
)

GOLD_REQUIRED_COLUMNS: Sequence[str] = (
    "上报月份",
    "业务类型",
    "上报客户名称",
    "机构代码",
)

# Composite key for uniqueness check
GOLD_COMPOSITE_KEY: Sequence[str] = ("上报月份", "业务类型", "年金计划号", "company_id")

CLEANSING_DOMAIN = "annual_loss"


BronzeAnnualLossSchema = pa.DataFrameSchema(
    columns={
        "上报月份": pa.Column(pa.DateTime, nullable=True, coerce=True),
        "业务类型": pa.Column(pa.String, nullable=True, coerce=True),
        "客户全称": pa.Column(pa.String, nullable=True, coerce=True),
        "年金计划号": pa.Column(pa.String, nullable=True, coerce=True),
        "company_id": pa.Column(pa.String, nullable=True, coerce=True),
        "机构": pa.Column(pa.String, nullable=True, coerce=True),
        "机构名称": pa.Column(pa.String, nullable=True, coerce=True),
        "流失日期": pa.Column(pa.DateTime, nullable=True, coerce=True),
        "产品线代码": pa.Column(pa.String, nullable=True, coerce=True),
        "客户类型": pa.Column(pa.String, nullable=True, coerce=True),
        "原受托人": pa.Column(pa.String, nullable=True, coerce=True),
        "计划规模": pa.Column(pa.Float, nullable=True, coerce=True),
        "年缴规模": pa.Column(pa.Float, nullable=True, coerce=True),
        "计划类型": pa.Column(pa.String, nullable=True, coerce=True),
        "证明材料": pa.Column(pa.String, nullable=True, coerce=True),
        "考核有效": pa.Column(pa.Int, nullable=True, coerce=True),
        "备注": pa.Column(pa.String, nullable=True, coerce=True),
    },
    strict=False,  # Allow extra columns (will be dropped)
    coerce=True,
)


GoldAnnualLossSchema = pa.DataFrameSchema(
    columns={
        # Required fields
        "上报月份": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "业务类型": pa.Column(pa.String, nullable=False, coerce=True),
        "上报客户名称": pa.Column(pa.String, nullable=False, coerce=True),
        "机构代码": pa.Column(pa.String, nullable=False, coerce=True),
        # Transformed fields
        "客户名称": pa.Column(pa.String, nullable=True, coerce=True),
        "年金计划号": pa.Column(pa.String, nullable=True, coerce=True),
        "company_id": pa.Column(pa.String, nullable=True, coerce=True),
        # Optional fields
        "机构名称": pa.Column(pa.String, nullable=True, coerce=True),
        "产品线代码": pa.Column(pa.String, nullable=True, coerce=True),
        "流失日期": pa.Column(pa.DateTime, nullable=True, coerce=True),
        "客户类型": pa.Column(pa.String, nullable=True, coerce=True),
        "原受托人": pa.Column(pa.String, nullable=True, coerce=True),
        "计划规模": pa.Column(pa.Float, nullable=True, coerce=True),
        "年缴规模": pa.Column(pa.Float, nullable=True, coerce=True),
        "计划类型": pa.Column(pa.String, nullable=True, coerce=True),
        "证明材料": pa.Column(pa.String, nullable=True, coerce=True),
        "考核有效": pa.Column(pa.Int, nullable=True, coerce=True),
        "备注": pa.Column(pa.String, nullable=True, coerce=True),
    },
    strict=True,  # No extra columns allowed in Gold layer
    coerce=True,
)


def validate_bronze_dataframe(
    dataframe: pd.DataFrame, failure_threshold: float = 0.10
) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    """Validate dataframe against Bronze schema."""
    return _validate_bronze(
        dataframe,
        domain_name="annual_loss",
        failure_threshold=failure_threshold,
    )


def validate_gold_dataframe(
    dataframe: pd.DataFrame,
    enforce_unique: bool = False,
) -> Tuple[pd.DataFrame, GoldValidationSummary]:
    """Validate dataframe against Gold schema."""
    try:
        validated_df = GoldAnnualLossSchema.validate(dataframe)
        summary = GoldValidationSummary(
            total_rows=len(dataframe),
            valid_rows=len(validated_df),
            invalid_rows=0,
            validation_passed=True,
        )
        return validated_df, summary
    except pa.errors.SchemaError as e:
        summary = GoldValidationSummary(
            total_rows=len(dataframe),
            valid_rows=0,
            invalid_rows=len(dataframe),
            validation_passed=False,
            error_message=str(e),
        )
        return dataframe, summary


def bronze_summary_to_dict(summary: BronzeValidationSummary) -> Dict[str, Any]:
    """Convert BronzeValidationSummary to dictionary."""
    return asdict(summary)


def gold_summary_to_dict(summary: GoldValidationSummary) -> Dict[str, Any]:
    """Convert GoldValidationSummary to dictionary."""
    return asdict(summary)


__all__ = [
    "BronzeAnnualLossSchema",
    "GoldAnnualLossSchema",
    "BronzeValidationSummary",
    "GoldValidationSummary",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    "bronze_summary_to_dict",
    "gold_summary_to_dict",
    "BRONZE_REQUIRED_COLUMNS",
    "GOLD_REQUIRED_COLUMNS",
    "GOLD_COMPOSITE_KEY",
]
