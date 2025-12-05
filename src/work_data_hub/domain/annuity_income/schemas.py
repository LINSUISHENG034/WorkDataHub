from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd
import pandera.pandas as pa

from work_data_hub.infrastructure.cleansing import get_cleansing_registry
from work_data_hub.infrastructure.cleansing.rules.numeric_rules import (
    clean_numeric_for_schema,
)
from work_data_hub.infrastructure.transforms.standard_steps import (
    coerce_numeric_columns,
)
from work_data_hub.infrastructure.validation.schema_helpers import (
    apply_schema_with_lazy_mode,
    ensure_non_null_columns,
    ensure_not_empty,
    ensure_required_columns,
    raise_schema_error,
    track_invalid_ratio,
)
from work_data_hub.utils.date_parser import parse_bronze_dates

# AnnuityIncome-specific column definitions
# Story 5.5.5: Corrected to match real data - four income fields instead of 收入金额
BRONZE_REQUIRED_COLUMNS: Sequence[str] = (
    "月度",
    "计划号",
    "客户名称",
    "业务类型",
    "固费",
    "浮费",
    "回补",
    "税",
)
BRONZE_NUMERIC_COLUMNS: Sequence[str] = ("固费", "浮费", "回补", "税")
GOLD_NUMERIC_COLUMNS: Sequence[str] = ("固费", "浮费", "回补", "税")
GOLD_REQUIRED_COLUMNS: Sequence[str] = (
    "月度",
    "计划号",
    "company_id",
    "客户名称",
    "固费",
    "浮费",
    "回补",
    "税",
)
# MVP Validation: Added 组合代码 to composite key to handle multiple portfolios per plan
GOLD_COMPOSITE_KEY: Sequence[str] = ("月度", "计划号", "组合代码", "company_id")

CLEANSING_DOMAIN = "annuity_income"

BronzeAnnuityIncomeSchema = pa.DataFrameSchema(  # type: ignore[no-untyped-call]
    columns={
        "月度": pa.Column(pa.DateTime, nullable=True, coerce=True),
        "机构代码": pa.Column(pa.String, nullable=True, coerce=True),
        "计划号": pa.Column(pa.String, nullable=True, coerce=True),
        "客户名称": pa.Column(pa.String, nullable=True, coerce=True),
        "业务类型": pa.Column(pa.String, nullable=True, coerce=True),
        # Story 5.5.5: Four income fields instead of 收入金额
        "固费": pa.Column(pa.Float, nullable=True, coerce=True),
        "浮费": pa.Column(pa.Float, nullable=True, coerce=True),
        "回补": pa.Column(pa.Float, nullable=True, coerce=True),
        "税": pa.Column(pa.Float, nullable=True, coerce=True),
    },
    strict=False,
    coerce=True,
)


GoldAnnuityIncomeSchema = pa.DataFrameSchema(  # type: ignore[no-untyped-call]
    columns={
        "月度": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "计划号": pa.Column(pa.String, nullable=False, coerce=True),
        "company_id": pa.Column(
            pa.String,
            nullable=False,
            coerce=True,
            checks=pa.Check.str_length(min_value=1),
        ),
        "客户名称": pa.Column(pa.String, nullable=False, coerce=True),
        "年金账户名": pa.Column(pa.String, nullable=True, coerce=True),
        "业务类型": pa.Column(pa.String, nullable=True, coerce=True),
        "计划类型": pa.Column(pa.String, nullable=True, coerce=True),
        "组合代码": pa.Column(pa.String, nullable=True, coerce=True),
        "产品线代码": pa.Column(pa.String, nullable=True, coerce=True),
        "机构代码": pa.Column(pa.String, nullable=True, coerce=True),
        # Story 5.5.5: Four income fields instead of 收入金额
        "固费": pa.Column(pa.Float, nullable=False, coerce=True),
        "浮费": pa.Column(pa.Float, nullable=False, coerce=True),
        "回补": pa.Column(pa.Float, nullable=False, coerce=True),
        "税": pa.Column(pa.Float, nullable=False, coerce=True),
    },
    strict=True,
    coerce=True,
    # No unique constraint - business detail data can have duplicate composite keys
)


@dataclass
class BronzeValidationSummary:
    """Summary of bronze layer validation results."""

    row_count: int
    invalid_date_rows: List[int] = field(default_factory=list)
    numeric_error_rows: Dict[str, List[int]] = field(default_factory=dict)
    empty_columns: List[str] = field(default_factory=list)


@dataclass
class GoldValidationSummary:
    """Summary of gold layer validation results."""

    row_count: int
    removed_columns: List[str] = field(default_factory=list)
    duplicate_keys: List[Tuple[str, str, str]] = field(default_factory=list)


def validate_bronze_dataframe(dataframe: pd.DataFrame, failure_threshold: float = 0.10) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    """Validate bronze layer DataFrame against schema."""
    working_df = dataframe.copy(deep=True)
    ensure_not_empty(GoldAnnuityIncomeSchema, working_df, schema_name="Gold")
    ensure_not_empty(BronzeAnnuityIncomeSchema, working_df, schema_name="Bronze")
    ensure_required_columns(BronzeAnnuityIncomeSchema, working_df, BRONZE_REQUIRED_COLUMNS, schema_name="Bronze")

    registry = get_cleansing_registry()
    numeric_invalid_rows = coerce_numeric_columns(
        working_df,
        BRONZE_NUMERIC_COLUMNS,
        cleaner=lambda value, field: clean_numeric_for_schema(
            value,
            field,
            domain=CLEANSING_DOMAIN,
            registry=registry,
        ),
    )

    parsed_dates, invalid_date_rows = parse_bronze_dates(working_df["月度"])
    working_df["月度"] = parsed_dates

    empty_columns = ensure_non_null_columns(BronzeAnnuityIncomeSchema, working_df, BRONZE_REQUIRED_COLUMNS)

    for column, rows in numeric_invalid_rows.items():
        track_invalid_ratio(
            column,
            rows,
            working_df,
            BronzeAnnuityIncomeSchema,
            failure_threshold,
            "Bronze validation failed: non-numeric values exceed threshold",
        )

    track_invalid_ratio(
        "月度",
        invalid_date_rows,
        working_df,
        BronzeAnnuityIncomeSchema,
        failure_threshold,
        "Bronze validation failed: unparseable dates exceed threshold",
    )

    validated_df = apply_schema_with_lazy_mode(BronzeAnnuityIncomeSchema, working_df)
    summary = BronzeValidationSummary(
        row_count=len(validated_df),
        invalid_date_rows=invalid_date_rows,
        numeric_error_rows=numeric_invalid_rows,
        empty_columns=empty_columns,
    )
    return validated_df, summary


def validate_gold_dataframe(
    dataframe: pd.DataFrame,
    project_columns: bool = True,
) -> Tuple[pd.DataFrame, GoldValidationSummary]:
    """Validate gold layer DataFrame against schema.

    Note: Duplicate composite keys are allowed since this is business detail data.
    Each record represents a real transaction and should be preserved.

    Args:
        dataframe: Input DataFrame to validate
        project_columns: Whether to project columns to Gold schema
    """
    working_df = dataframe.copy(deep=True)
    removed_columns: List[str] = []

    if project_columns:
        gold_cols = GoldAnnuityIncomeSchema.columns
        removed_columns = [column for column in working_df.columns if column not in gold_cols]
        if removed_columns:
            working_df = working_df.drop(columns=removed_columns, errors="ignore")

    ensure_required_columns(GoldAnnuityIncomeSchema, working_df, GOLD_REQUIRED_COLUMNS, schema_name="Gold")

    # Log duplicate keys for informational purposes only - do not reject or aggregate
    duplicate_mask = working_df.duplicated(subset=GOLD_COMPOSITE_KEY, keep=False)
    duplicate_keys: List[Tuple[str, str, str, str]] = []
    if duplicate_mask.any():
        duplicate_count = duplicate_mask.sum()
        # Just log, don't fail - business detail data can have duplicate composite keys

    validated_df = apply_schema_with_lazy_mode(GoldAnnuityIncomeSchema, working_df)

    summary = GoldValidationSummary(
        row_count=len(validated_df),
        removed_columns=removed_columns,
        duplicate_keys=duplicate_keys,
    )
    return validated_df, summary


def bronze_summary_to_dict(summary: BronzeValidationSummary) -> Dict[str, Any]:
    """Convert BronzeValidationSummary to dictionary."""
    return asdict(summary)


def gold_summary_to_dict(summary: GoldValidationSummary) -> Dict[str, Any]:
    """Convert GoldValidationSummary to dictionary."""
    return asdict(summary)


__all__ = [
    "BronzeAnnuityIncomeSchema",
    "GoldAnnuityIncomeSchema",
    "BronzeValidationSummary",
    "GoldValidationSummary",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    "bronze_summary_to_dict",
    "gold_summary_to_dict",
]
