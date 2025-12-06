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

BRONZE_REQUIRED_COLUMNS: Sequence[str] = (
    "月度",
    "计划代码",
    "客户名称",
    "期初资产规模",
    "期末资产规模",
    "投资收益",
    "当期收益率",
)
BRONZE_NUMERIC_COLUMNS: Sequence[str] = (
    "期初资产规模",
    "期末资产规模",
    "投资收益",
    "当期收益率",
)
GOLD_NUMERIC_COLUMNS: Sequence[str] = (
    "期初资产规模",
    "期末资产规模",
    "供款",
    "流失_含待遇支付",
    "流失",
    "待遇支付",
    "投资收益",
    "年化收益率",
)
GOLD_REQUIRED_COLUMNS: Sequence[str] = (
    "月度",
    "计划代码",
    "company_id",
    "客户名称",
    "期初资产规模",
    "期末资产规模",
    "投资收益",
)
# MVP Validation: Added 组合代码 to composite key to handle multiple portfolios per plan
GOLD_COMPOSITE_KEY: Sequence[str] = ("月度", "计划代码", "组合代码", "company_id")

CLEANSING_DOMAIN = "annuity_performance"

BronzeAnnuitySchema = pa.DataFrameSchema(  # type: ignore[no-untyped-call]
    columns={
        "月度": pa.Column(pa.DateTime, nullable=True, coerce=True),
        "计划代码": pa.Column(pa.String, nullable=True, coerce=True),
        "客户名称": pa.Column(pa.String, nullable=True, coerce=True),
        "期初资产规模": pa.Column(pa.Float, nullable=True, coerce=True),
        "期末资产规模": pa.Column(pa.Float, nullable=True, coerce=True),
        "投资收益": pa.Column(pa.Float, nullable=True, coerce=True),
        "当期收益率": pa.Column(pa.Float, nullable=True, coerce=True),
    },
    strict=False,
    coerce=True,
)


GoldAnnuitySchema = pa.DataFrameSchema(  # type: ignore[no-untyped-call]
    columns={
        "月度": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "业务类型": pa.Column(pa.String, nullable=True, coerce=True),
        "计划类型": pa.Column(pa.String, nullable=True, coerce=True),
        "计划代码": pa.Column(pa.String, nullable=False, coerce=True),
        "计划名称": pa.Column(pa.String, nullable=True, coerce=True),
        "组合类型": pa.Column(pa.String, nullable=True, coerce=True),
        "组合代码": pa.Column(pa.String, nullable=True, coerce=True),
        "组合名称": pa.Column(pa.String, nullable=True, coerce=True),
        "company_id": pa.Column(
            pa.String,
            nullable=False,
            coerce=True,
            checks=pa.Check.str_length(min_value=1),
        ),
        "客户名称": pa.Column(pa.String, nullable=False, coerce=True),
        "期初资产规模": pa.Column(pa.Float, nullable=False, coerce=True, checks=pa.Check.ge(0)),
        "期末资产规模": pa.Column(pa.Float, nullable=False, coerce=True, checks=pa.Check.ge(0)),
        "投资收益": pa.Column(pa.Float, nullable=False, coerce=True),
        "供款": pa.Column(pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)),
        "流失_含待遇支付": pa.Column(pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)),
        "流失": pa.Column(pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)),
        "待遇支付": pa.Column(pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)),
        "年化收益率": pa.Column(pa.Float, nullable=True, coerce=True),
        "机构代码": pa.Column(pa.String, nullable=True, coerce=True),
        "机构名称": pa.Column(pa.String, nullable=True, coerce=True),
        "产品线代码": pa.Column(pa.String, nullable=True, coerce=True),
        "年金账户号": pa.Column(pa.String, nullable=True, coerce=True),
        "年金账户名": pa.Column(pa.String, nullable=True, coerce=True),
    },
    strict=True,
    coerce=True,
)


@dataclass
class BronzeValidationSummary:
    row_count: int
    invalid_date_rows: List[int] = field(default_factory=list)
    numeric_error_rows: Dict[str, List[int]] = field(default_factory=dict)
    empty_columns: List[str] = field(default_factory=list)


@dataclass
class GoldValidationSummary:
    row_count: int
    removed_columns: List[str] = field(default_factory=list)
    duplicate_keys: List[Tuple[str, str, str]] = field(default_factory=list)


def validate_bronze_dataframe(dataframe: pd.DataFrame, failure_threshold: float = 0.10) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    working_df = dataframe.copy(deep=True)
    ensure_not_empty(GoldAnnuitySchema, working_df, schema_name="Gold")
    ensure_not_empty(BronzeAnnuitySchema, working_df, schema_name="Bronze")
    ensure_required_columns(BronzeAnnuitySchema, working_df, BRONZE_REQUIRED_COLUMNS, schema_name="Bronze")

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

    empty_columns = ensure_non_null_columns(BronzeAnnuitySchema, working_df, BRONZE_REQUIRED_COLUMNS)

    for column, rows in numeric_invalid_rows.items():
        track_invalid_ratio(
            column,
            rows,
            working_df,
            BronzeAnnuitySchema,
            failure_threshold,
            "Bronze validation failed: non-numeric values exceed threshold",
        )

    track_invalid_ratio(
        "月度",
        invalid_date_rows,
        working_df,
        BronzeAnnuitySchema,
        failure_threshold,
        "Bronze validation failed: unparseable dates exceed threshold",
    )

    validated_df = apply_schema_with_lazy_mode(BronzeAnnuitySchema, working_df)
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
    aggregate_duplicates: bool = False,
) -> Tuple[pd.DataFrame, GoldValidationSummary]:
    """Validate gold layer DataFrame against schema.

    Args:
        dataframe: Input DataFrame to validate
        project_columns: Whether to project columns to Gold schema
        aggregate_duplicates: If True, aggregate duplicate keys by summing numeric fields.
                            If False, retain all detail rows (no aggregation, no error).
    """
    working_df = dataframe.copy(deep=True)
    removed_columns: List[str] = []

    if project_columns:
        gold_cols = GoldAnnuitySchema.columns
        removed_columns = [column for column in working_df.columns if column not in gold_cols]
        if removed_columns:
            working_df = working_df.drop(columns=removed_columns, errors="ignore")

    # Ensure composite key columns exist for duplicate detection
    if "组合代码" not in working_df.columns:
        working_df["组合代码"] = None

    ensure_required_columns(GoldAnnuitySchema, working_df, GOLD_REQUIRED_COLUMNS, schema_name="Gold")

    duplicate_mask = working_df.duplicated(subset=GOLD_COMPOSITE_KEY, keep=False)
    duplicate_keys: List[Tuple[str, str, str, str]] = []
    if duplicate_mask.any():
        duplicate_keys = (
            working_df.loc[duplicate_mask, list(GOLD_COMPOSITE_KEY)]
            .apply(lambda row: tuple(row.values.tolist()), axis=1)
            .drop_duplicates()
            .tolist()
        )

        if aggregate_duplicates:
            # MVP Validation: Aggregate duplicates by summing numeric fields
            numeric_cols = list(GOLD_NUMERIC_COLUMNS)
            non_numeric_cols = [c for c in working_df.columns if c not in numeric_cols]

            # Group by composite key and aggregate
            agg_dict = {col: "sum" for col in numeric_cols if col in working_df.columns}
            for col in non_numeric_cols:
                if col not in GOLD_COMPOSITE_KEY:
                    agg_dict[col] = "first"  # Take first value for non-numeric columns

            working_df = working_df.groupby(list(GOLD_COMPOSITE_KEY), as_index=False).agg(agg_dict)
        # When aggregate_duplicates is False, keep detail rows as-is (no error/aggregation)

    validated_df = apply_schema_with_lazy_mode(GoldAnnuitySchema, working_df)

    summary = GoldValidationSummary(
        row_count=len(validated_df),
        removed_columns=removed_columns,
        duplicate_keys=duplicate_keys,
    )
    return validated_df, summary


def bronze_summary_to_dict(summary: BronzeValidationSummary) -> Dict[str, Any]:
    return asdict(summary)


def gold_summary_to_dict(summary: GoldValidationSummary) -> Dict[str, Any]:
    return asdict(summary)


__all__ = [
    "BronzeAnnuitySchema",
    "GoldAnnuitySchema",
    "BronzeValidationSummary",
    "GoldValidationSummary",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    "bronze_summary_to_dict",
    "gold_summary_to_dict",
]
