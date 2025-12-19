from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Sequence, Tuple

import pandas as pd
import pandera.pandas as pa

# Story 6.2-P13: Import shared models from infrastructure layer
from work_data_hub.infrastructure.models.shared import (
    BronzeValidationSummary,
    GoldValidationSummary,
)
from work_data_hub.infrastructure.validation.domain_validators import (
    validate_bronze_dataframe as _validate_bronze,
)
from work_data_hub.infrastructure.validation.domain_validators import (
    validate_gold_dataframe as _validate_gold,
)

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

BronzeAnnuitySchema = pa.DataFrameSchema(
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


GoldAnnuitySchema = pa.DataFrameSchema(
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
        "期初资产规模": pa.Column(
            pa.Float, nullable=False, coerce=True, checks=pa.Check.ge(0)
        ),
        "期末资产规模": pa.Column(
            pa.Float, nullable=False, coerce=True, checks=pa.Check.ge(0)
        ),
        "投资收益": pa.Column(pa.Float, nullable=False, coerce=True),
        "供款": pa.Column(pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)),
        "流失_含待遇支付": pa.Column(
            pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)
        ),
        "流失": pa.Column(pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)),
        "待遇支付": pa.Column(
            pa.Float, nullable=True, coerce=True, checks=pa.Check.ge(0)
        ),
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


# Story 6.2-P13: BronzeValidationSummary and GoldValidationSummary are now imported
# from work_data_hub.infrastructure.models.shared and re-exported for backward compatibility
# See: src/work_data_hub/infrastructure/models/shared.py



def validate_bronze_dataframe(
    dataframe: pd.DataFrame, failure_threshold: float = 0.10
) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    return _validate_bronze(
        dataframe,
        domain_name="annuity_performance",
        failure_threshold=failure_threshold,
    )


def validate_gold_dataframe(
    dataframe: pd.DataFrame,
    project_columns: bool = True,
    aggregate_duplicates: bool = False,
) -> Tuple[pd.DataFrame, GoldValidationSummary]:
    return _validate_gold(
        dataframe,
        domain_name="annuity_performance",
        project_columns=project_columns,
        aggregate_duplicates=aggregate_duplicates,
    )


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
