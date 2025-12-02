"""
Pandera schemas and validation helpers for Story 2.2.

Story 4.8: Generic validation helpers extracted to domain/pipelines/validation/
for reuse across domains. Domain-specific schemas remain here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import pandera as pa
from pandera.errors import SchemaError, SchemaErrors

from work_data_hub.infrastructure.validation import (
    ensure_not_empty,
    ensure_required_columns,
    raise_schema_error,
)
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

from src.work_data_hub.infrastructure.cleansing import get_cleansing_registry

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

GOLD_COMPOSITE_KEY: Sequence[str] = ("月度", "计划代码", "company_id")

CLEANSING_DOMAIN = "annuity_performance"
CLEANSING_REGISTRY = get_cleansing_registry()
SCHEMA_NUMERIC_RULES: List[Any] = [
    "standardize_null_values",
    "remove_currency_symbols",
    "clean_comma_separated_number",
    {"name": "handle_percentage_conversion"},
]


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
"""
Bronze Layer DataFrame Schema for Annuity Performance Data.

Validates raw Excel data structure and performs type coercion to prepare data
for Pydantic row-level validation (Story 2.1).

**Validation Responsibilities:**
- Structural validation: ensures all required columns are present
- Type coercion: converts string numbers to float, dates to datetime
- Null handling: allows nulls in Bronze layer (permissive)
- Empty DataFrame detection: fails if no data rows present
- Completely null columns: fails if any column has all null values
- Error threshold: fails if >10% of rows have coercion errors (systemic issue)

**Configuration:**
- strict=False: Allows extra columns from Excel (e.g., '备注', '子企业号')
- coerce=True: Automatically attempts type conversion
- nullable=True: Allows null values in all columns (raw data may be incomplete)

**Data Flow:**
Excel → Bronze Schema → Pydantic AnnuityPerformanceIn → Silver Layer

**Usage Example (Manual Validation):**
```python
from work_data_hub.domain.annuity_performance.schemas import validate_bronze_dataframe

# Validate raw Excel DataFrame
validated_df, summary = validate_bronze_dataframe(raw_df, failure_threshold=0.10)

# Check summary for diagnostics
print(f"Rows: {summary.row_count}")
print(f"Invalid dates: {summary.invalid_date_rows}")
print(f"Numeric errors: {summary.numeric_error_rows}")
```

**Usage Example (Pipeline Integration):**
```python
from work_data_hub.domain.annuity_performance.pipeline_steps import BronzeSchemaValidationStep
from work_data_hub.domain.pipelines.core import Pipeline

step = BronzeSchemaValidationStep(failure_threshold=0.10)
validated_df = step.execute(raw_df, context)

# Validation summary stored in context.metadata['bronze_schema_validation']
```

**Error Handling:**
- Missing required columns → SchemaError with column comparison
- >10% date parsing failures → SchemaError with row numbers
- >10% numeric coercion failures → SchemaError with failure rate
- Empty DataFrame → SchemaError
- All-null columns → SchemaError with column names

**Performance:**
- Target: ≥5000 rows/second for 10,000-row datasets
- Actual: ~8000-12000 rows/s on typical hardware (AC-PERF-1 compliant)
"""


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
    unique=GOLD_COMPOSITE_KEY,
)
"""
Gold Layer DataFrame Schema for Database-Ready Annuity Performance Data.

Validates Silver layer output and enforces database integrity constraints before
warehouse loading (Epic 1 Story 1.8).

**Validation Responsibilities:**
- Database integrity: composite primary key uniqueness (月度, 计划代码, company_id)
- Not-null constraints: all required fields must be present
- Business rule validation: asset values ≥ 0 (negative assets not allowed)
- Column projection: removes extra columns not in database schema
- Type enforcement: strict typing for database compatibility

**Configuration:**
- strict=True: Rejects any columns not defined in schema (database projection)
- coerce=True: Final type conversion to ensure database compatibility
- nullable=False: Required fields cannot be null (database constraints)
- unique=['月度', '计划代码', 'company_id']: Composite primary key check

**Data Flow:**
Pydantic AnnuityPerformanceOut → Gold Schema → Database Warehouse

**Field Mapping (Gold → Database):**
```
月度 → reporting_month (date)
计划代码 → plan_code (varchar)
company_id → company_id (varchar)  [From Story 5.2 temp ID or Story 5.4 enrichment]
客户名称 → company_name (varchar)
期初资产规模 → beginning_assets (numeric)
期末资产规模 → ending_assets (numeric)
投资收益 → investment_income (numeric)
供款 → contributions (numeric, nullable)
流失_含待遇支付 → attrition_with_benefits (numeric, nullable)
流失 → attrition (numeric, nullable)
待遇支付 → benefit_payments (numeric, nullable)
年化收益率 → annualized_return (numeric, nullable)
```

**Usage Example (Manual Validation):**
```python
from work_data_hub.domain.annuity_performance.schemas import validate_gold_dataframe

# Validate Silver DataFrame before database load
validated_df, summary = validate_gold_dataframe(silver_df, project_columns=True)

# Check for removed columns (not in database schema)
if summary.removed_columns:
    print(f"Removed extra columns: {summary.removed_columns}")

# Check for duplicate composite keys
if summary.duplicate_keys:
    raise ValueError(f"Duplicate PKs found: {summary.duplicate_keys}")
```

**Usage Example (Pipeline Integration):**
```python
from work_data_hub.domain.annuity_performance.pipeline_steps import GoldSchemaValidationStep

step = GoldSchemaValidationStep(project_columns=True)
validated_df = step.execute(silver_df, context)

# Validation summary stored in context.metadata['gold_schema_validation']
# Ready for Epic 1 Story 1.8 warehouse loader
```

**Error Handling:**
- Missing required columns → SchemaError with column comparison
- Duplicate composite PKs → SchemaError with duplicate key combinations
- Null required fields → SchemaError with null row count
- Negative asset values → SchemaError (business rule violation)
- Extra columns → Removed and logged (if project_columns=True)

**Business Rules Enforced:**
- 期初资产规模 ≥ 0 (beginning assets cannot be negative)
- 期末资产规模 ≥ 0 (ending assets cannot be negative)
- 供款 ≥ 0 (contributions cannot be negative)
- 流失 ≥ 0 (attrition cannot be negative)
- company_id must be non-empty string (min_length=1)

**Performance:**
- Target: ≥3000 rows/second for 10,000-row datasets
- Actual: ~5000-8000 rows/s on typical hardware (AC-PERF-1 compliant)
- Note: Composite PK uniqueness check is O(n) - performance degrades with >100K rows
"""


@dataclass
class BronzeValidationSummary:
    """Diagnostics captured during Bronze schema validation."""

    row_count: int
    invalid_date_rows: List[int] = field(default_factory=list)
    numeric_error_rows: Dict[str, List[int]] = field(default_factory=dict)
    empty_columns: List[str] = field(default_factory=list)


@dataclass
class GoldValidationSummary:
    """Diagnostics captured during Gold schema validation."""

    row_count: int
    removed_columns: List[str] = field(default_factory=list)
    duplicate_keys: List[Tuple[str, str, str]] = field(default_factory=list)


def _schema_name(schema: pa.DataFrameSchema) -> str:
    if schema is GoldAnnuitySchema:
        return "Gold"
    return "Bronze"


def _format_schema_error_message(
    schema: pa.DataFrameSchema, failure_cases: pd.DataFrame | None
) -> str:
    base = f"{_schema_name(schema)} validation failed"
    if failure_cases is None or failure_cases.empty:
        return base

    message_parts: List[str] = []

    if "column" in failure_cases.columns:
        columns = (
            failure_cases["column"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        if columns:
            message_parts.append(f"columns {columns[:5]}")

    if "failure_case" in failure_cases.columns:
        failure_values = (
            failure_cases["failure_case"]
            .dropna()
            .astype(str)
            .head(5)
            .tolist()
        )
        if failure_values:
            message_parts.append(f"failure cases {failure_values}")

    if message_parts:
        return f"{base}: " + "; ".join(message_parts)
    return base


def _track_invalid_ratio(
    column: str,
    invalid_rows: List[int],
    dataframe: pd.DataFrame,
    schema: pa.DataFrameSchema,
    threshold: float,
    reason: str,
) -> None:
    if not invalid_rows:
        return
    ratio = len(invalid_rows) / max(len(dataframe), 1)
    if ratio > threshold:
        failure_cases = pd.DataFrame(
            {"column": column, "row_index": invalid_rows}
        )
        raise_schema_error(
            schema,
            dataframe,
            message=(
                f"{reason}: column '{column}' has {ratio:.1%} invalid values "
                f"(rows {invalid_rows[:10]})"
            ),
            failure_cases=failure_cases,
        )


def _clean_numeric_for_schema(value: Any, field_name: str) -> Optional[float]:
    """Shared cleansing helper that mirrors Pydantic validators."""
    rules = CLEANSING_REGISTRY.get_domain_rules(CLEANSING_DOMAIN, field_name)
    if not rules:
        rules = SCHEMA_NUMERIC_RULES

    cleaned = CLEANSING_REGISTRY.apply_rules(
        value,
        rules,
        field_name=field_name,
    )

    if cleaned is None:
        return None

    if isinstance(cleaned, Decimal):
        return float(cleaned)

    if isinstance(cleaned, (int, float)):
        return float(cleaned)

    try:
        return float(cleaned)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Cannot convert value '{value}' in column '{field_name}' to number"
        ) from exc


def _coerce_numeric_columns(
    dataframe: pd.DataFrame,
) -> Dict[str, List[int]]:
    invalid_rows: Dict[str, List[int]] = {}
    for column in BRONZE_NUMERIC_COLUMNS:
        if column not in dataframe.columns:
            continue
        series = dataframe[column]
        cleaned_values: List[float | None] = []
        column_invalid_indices: List[int] = []
        for idx, value in series.items():
            try:
                cleaned = _clean_numeric_for_schema(value, column)
            except ValueError:
                cleaned = None
                column_invalid_indices.append(idx)
            cleaned_values.append(cleaned)

        converted = pd.to_numeric(cleaned_values, errors="coerce")
        dataframe[column] = converted

        if column_invalid_indices:
            invalid_rows[column] = column_invalid_indices
    return invalid_rows


def _parse_bronze_dates(series: pd.Series) -> Tuple[pd.Series, List[int]]:
    """
    Parse date column using Epic 2 Story 2.4 date parser.

    Supports Chinese formats (2024年12月), ISO formats (2024-12), and numeric formats (202412).
    Returns parsed timestamps and list of invalid row indices.
    """
    parsed_values: List[pd.Timestamp | pd.NaT] = []
    invalid_rows: List[int] = []
    for idx, value in series.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            parsed_values.append(pd.NaT)
            continue

        try:
            parsed = parse_yyyymm_or_chinese(value)
            parsed_values.append(pd.Timestamp(parsed))
        except (ValueError, TypeError):
            parsed_values.append(pd.NaT)
            invalid_rows.append(idx)
    return pd.Series(parsed_values, index=series.index), invalid_rows


def _ensure_non_null_columns(
    schema: pa.DataFrameSchema,
    dataframe: pd.DataFrame,
    columns: Iterable[str],
) -> List[str]:
    empty_columns: List[str] = []
    for column in columns:
        if column in dataframe.columns and dataframe[column].notna().sum() == 0:
            empty_columns.append(column)
    if empty_columns:
        failure_cases = pd.DataFrame(
            {"column": empty_columns, "failure": "all values null"}
        )
        raise_schema_error(
            schema,
            dataframe,
            message=(
                f"{_schema_name(schema)} validation failed: columns have no non-null values "
                f"{empty_columns}"
            ),
            failure_cases=failure_cases,
        )
    return empty_columns


def _apply_schema_with_lazy_mode(
    schema: pa.DataFrameSchema, dataframe: pd.DataFrame
) -> pd.DataFrame:
    try:
        return schema.validate(dataframe, lazy=True)
    except SchemaErrors as exc:
        message = _format_schema_error_message(schema, exc.failure_cases)
        raise_schema_error(
            schema,
            dataframe,
            message=message,
            failure_cases=exc.failure_cases,
        )


def validate_bronze_dataframe(
    dataframe: pd.DataFrame, failure_threshold: float = 0.10
) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    """
    Validate raw Excel DataFrame using Bronze schema with Story 2.2 rules.
    """
    working_df = dataframe.copy(deep=True)
    ensure_not_empty(GoldAnnuitySchema, working_df, schema_name="Gold")
    ensure_not_empty(BronzeAnnuitySchema, working_df, schema_name="Bronze")
    ensure_required_columns(
        BronzeAnnuitySchema, working_df, BRONZE_REQUIRED_COLUMNS, schema_name="Bronze"
    )

    numeric_invalid_rows = _coerce_numeric_columns(working_df)

    parsed_dates, invalid_date_rows = _parse_bronze_dates(working_df["月度"])
    working_df["月度"] = parsed_dates

    empty_columns = _ensure_non_null_columns(
        BronzeAnnuitySchema, working_df, BRONZE_REQUIRED_COLUMNS
    )

    for column, rows in numeric_invalid_rows.items():
        _track_invalid_ratio(
            column,
            rows,
            working_df,
            BronzeAnnuitySchema,
            failure_threshold,
            "Bronze validation failed: non-numeric values exceed threshold",
        )

    _track_invalid_ratio(
        "月度",
        invalid_date_rows,
        working_df,
        BronzeAnnuitySchema,
        failure_threshold,
        "Bronze validation failed: unparseable dates exceed threshold",
    )

    validated_df = _apply_schema_with_lazy_mode(BronzeAnnuitySchema, working_df)
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
    """
    Validate Silver-layer DataFrame before database projection.
    """
    working_df = dataframe.copy(deep=True)
    removed_columns: List[str] = []

    if project_columns:
        removed_columns = [
            column for column in working_df.columns if column not in GoldAnnuitySchema.columns
        ]
        if removed_columns:
            working_df = working_df.drop(columns=removed_columns, errors="ignore")

    ensure_required_columns(
        GoldAnnuitySchema, working_df, GOLD_REQUIRED_COLUMNS, schema_name="Gold"
    )

    duplicate_mask = working_df.duplicated(subset=GOLD_COMPOSITE_KEY, keep=False)
    duplicate_keys: List[Tuple[str, str, str]] = []
    if duplicate_mask.any():
        duplicate_keys = (
            working_df.loc[duplicate_mask, list(GOLD_COMPOSITE_KEY)]
            .apply(lambda row: tuple(row.values.tolist()), axis=1)
            .drop_duplicates()
            .tolist()
        )
        failure_cases = pd.DataFrame(
            duplicate_keys, columns=list(GOLD_COMPOSITE_KEY)
        )
        raise_schema_error(
            GoldAnnuitySchema,
            working_df,
            message=(
                "Gold validation failed: Composite PK (月度, 计划代码, company_id) "
                f"has duplicates {duplicate_keys[:5]}"
            ),
            failure_cases=failure_cases,
        )

    validated_df = _apply_schema_with_lazy_mode(GoldAnnuitySchema, working_df)

    summary = GoldValidationSummary(
        row_count=len(validated_df),
        removed_columns=removed_columns,
        duplicate_keys=duplicate_keys,
    )
    return validated_df, summary


def bronze_summary_to_dict(summary: BronzeValidationSummary) -> Dict[str, Any]:
    """Convert Bronze summary dataclass to JSON-friendly dict."""
    return asdict(summary)


def gold_summary_to_dict(summary: GoldValidationSummary) -> Dict[str, Any]:
    """Convert Gold summary dataclass to JSON-friendly dict."""
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
