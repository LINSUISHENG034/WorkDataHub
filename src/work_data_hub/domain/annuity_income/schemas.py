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
from work_data_hub.infrastructure.schema.domain_registry import get_domain
from work_data_hub.infrastructure.validation.domain_validators import (
    validate_bronze_dataframe as _validate_bronze,
)
from work_data_hub.infrastructure.validation.domain_validators import (
    validate_gold_layer as _validate_gold_layer,
)

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

BronzeAnnuityIncomeSchema = pa.DataFrameSchema(
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


GoldAnnuityIncomeSchema = pa.DataFrameSchema(
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


# Story 6.2-P13: BronzeValidationSummary and GoldValidationSummary are now imported
# from work_data_hub.infrastructure.models.shared and re-exported for backward
# compatibility
# See: src/work_data_hub/infrastructure/models/shared.py


def validate_bronze_dataframe(
    dataframe: pd.DataFrame, failure_threshold: float = 0.10
) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    return _validate_bronze(
        dataframe,
        domain_name="annuity_income",
        failure_threshold=failure_threshold,
    )


def validate_gold_dataframe(
    dataframe: pd.DataFrame,
    project_columns: bool = True,
    enforce_unique: bool = False,
) -> Tuple[pd.DataFrame, GoldValidationSummary]:
    domain_config = get_domain("annuity_income")
    return _validate_gold_layer(
        dataframe,
        domain_config,
        GoldAnnuityIncomeSchema,
        project_columns=project_columns,
        aggregate_duplicates=False,
        enforce_unique=enforce_unique,
    )


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
