"""
Domain-agnostic validation functions for bronze and gold layers.

Story 6.2-P13: Unified Domain Schema Management Architecture

This module provides registry-driven validation functions that work with
any domain's configuration from domain_registry. Domain-specific schemas.py
files can use these generalized functions via thin wrappers.

Usage:
    from work_data_hub.infrastructure.validation.domain_validators import (
        validate_bronze_layer,
        validate_gold_layer,
    )
    from work_data_hub.io.schema.domain_registry import get_domain

    config = get_domain("annuity_performance")
    validated_df, summary = validate_bronze_layer(
        df, config, bronze_schema, "月度"
    )
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import pandera.pandas as pa

from work_data_hub.infrastructure.cleansing import get_cleansing_registry
from work_data_hub.infrastructure.cleansing.rules.numeric_rules import (
    clean_numeric_for_schema,
)
from work_data_hub.infrastructure.models.shared import (
    BronzeValidationSummary,
    GoldValidationSummary,
)
from work_data_hub.infrastructure.transforms.standard_steps import (
    coerce_numeric_columns,
)
from work_data_hub.infrastructure.validation.schema_helpers import (
    apply_schema_with_lazy_mode,
    ensure_non_null_columns,
    ensure_not_empty,
    ensure_required_columns,
    track_invalid_ratio,
)
from work_data_hub.utils.date_parser import parse_bronze_dates

if TYPE_CHECKING:
    from work_data_hub.infrastructure.schema.domain_registry import DomainSchema


_DOMAIN_SCHEMA_OVERRIDES: Dict[str, Tuple[str, str, str]] = {
    "annuity_performance": (
        "work_data_hub.domain.annuity_performance.schemas",
        "BronzeAnnuitySchema",
        "GoldAnnuitySchema",
    ),
    "annuity_income": (
        "work_data_hub.domain.annuity_income.schemas",
        "BronzeAnnuityIncomeSchema",
        "GoldAnnuityIncomeSchema",
    ),
}


def _try_load_schema_override(
    domain_name: str, layer: str
) -> Optional["pa.DataFrameSchema"]:
    override = _DOMAIN_SCHEMA_OVERRIDES.get(domain_name)
    if not override:
        return None

    module_path, bronze_attr, gold_attr = override
    attr = bronze_attr if layer == "bronze" else gold_attr
    try:
        module = importlib.import_module(module_path)
    except Exception:
        return None

    schema = getattr(module, attr, None)
    return schema if isinstance(schema, pa.DataFrameSchema) else None


def _build_schema_from_domain_config(
    domain_config: "DomainSchema",
    *,
    strict: bool,
) -> "pa.DataFrameSchema":
    columns: Dict[str, pa.Column] = {}

    for col in domain_config.columns:
        col_type = getattr(col.column_type, "name", str(col.column_type)).upper()
        if col_type in {"STRING", "TEXT"}:
            dtype = pa.String
        elif col_type == "DATE":
            dtype = pa.DateTime
        elif col_type == "DATETIME":
            dtype = pa.DateTime
        elif col_type == "DECIMAL":
            dtype = pa.Float
        elif col_type == "INTEGER":
            dtype = pa.Int
        elif col_type == "BOOLEAN":
            dtype = pa.Bool
        else:
            dtype = pa.String

        columns[col.name] = pa.Column(
            dtype,
            nullable=col.nullable,
            coerce=True,
        )

    return pa.DataFrameSchema(
        columns=columns,
        strict=strict,
        coerce=True,
    )


def validate_bronze_dataframe(
    df: pd.DataFrame,
    domain_name: str,
    failure_threshold: float = 0.10,
) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    """Registry-driven bronze validation (Story 6.2-P13 AC-2.1).

    Notes:
    - Loads DomainSchema via get_domain(domain_name)
    - Uses existing per-domain Pandera schema when available; otherwise builds a
      minimal schema from DomainSchema columns.
    """
    from work_data_hub.infrastructure.schema.domain_registry import get_domain

    domain_config = get_domain(domain_name)
    bronze_schema = _try_load_schema_override(domain_name, "bronze") or (
        _build_schema_from_domain_config(domain_config, strict=False)
    )
    date_column = "月度"
    if date_column not in df.columns:
        for col in domain_config.columns:
            col_type = getattr(col.column_type, "name", str(col.column_type)).upper()
            if col_type in {"DATE", "DATETIME"} and col.name in df.columns:
                date_column = col.name
                break
    return validate_bronze_layer(
        df,
        domain_config,
        bronze_schema,
        date_column=date_column,
        failure_threshold=failure_threshold,
    )


def validate_gold_dataframe(
    df: pd.DataFrame,
    domain_name: str,
    project_columns: bool = True,
    aggregate_duplicates: bool = False,
) -> Tuple[pd.DataFrame, GoldValidationSummary]:
    """Registry-driven gold validation (Story 6.2-P13 AC-2.1).

    Notes:
    - Loads DomainSchema via get_domain(domain_name)
    - Uses existing per-domain Pandera schema when available; otherwise builds a
      minimal schema from DomainSchema columns.
    """
    from work_data_hub.infrastructure.schema.domain_registry import get_domain

    domain_config = get_domain(domain_name)
    gold_schema = _try_load_schema_override(domain_name, "gold") or (
        _build_schema_from_domain_config(domain_config, strict=project_columns)
    )
    return validate_gold_layer(
        df,
        domain_config,
        gold_schema,
        project_columns=project_columns,
        aggregate_duplicates=aggregate_duplicates,
    )


def validate_bronze_layer(
    dataframe: pd.DataFrame,
    domain_config: "DomainSchema",
    bronze_schema: "pa.DataFrameSchema",
    date_column: str = "月度",
    failure_threshold: float = 0.10,
    cleaner_override: Optional[Callable[[Any, str], Any]] = None,
) -> Tuple[pd.DataFrame, BronzeValidationSummary]:
    """Validate a DataFrame against bronze layer rules using domain configuration.

    This is a generalized version of domain-specific validate_bronze_dataframe
    functions.
    Domain layers can call this directly or wrap it for custom behavior.

    Args:
        dataframe: Input DataFrame to validate
        domain_config: DomainSchema from domain_registry with validation config
        bronze_schema: Pandera schema for bronze layer validation
        date_column: Name of the date column to parse (default: "月度")
        failure_threshold: Maximum ratio of invalid values before failing
            (default: 0.10)
        cleaner_override: Optional custom cleaner function; defaults to
            registry-based cleaning.

    Returns:
        Tuple of (validated_dataframe, BronzeValidationSummary)

    Raises:
        SchemaError: If validation fails beyond thresholds
    """
    working_df = dataframe.copy(deep=True)

    # Basic checks
    ensure_not_empty(bronze_schema, working_df, schema_name="Bronze")
    ensure_required_columns(
        bronze_schema,
        working_df,
        domain_config.bronze_required,
        schema_name="Bronze",
    )

    # Numeric column cleansing
    domain_name = domain_config.domain_name
    registry = get_cleansing_registry()

    if cleaner_override:
        cleaner = cleaner_override
    else:
        def cleaner(value: Any, field: str) -> Any:
            return clean_numeric_for_schema(
                value, field, domain=domain_name, registry=registry
            )

    # Get numeric columns that apply to Bronze:
    # - intersection with domain's numeric_columns
    # - and present in required cols or incoming dataframe
    bronze_numeric = [
        col for col in domain_config.numeric_columns
        if col in domain_config.bronze_required or col in dataframe.columns
    ]

    numeric_invalid_rows = coerce_numeric_columns(
        working_df,
        bronze_numeric,
        cleaner=cleaner,
    )

    # Date parsing
    invalid_date_rows: List[int] = []
    if date_column in working_df.columns:
        parsed_dates, invalid_date_rows = parse_bronze_dates(working_df[date_column])
        working_df[date_column] = parsed_dates

    # Non-null column check
    empty_columns = ensure_non_null_columns(
        bronze_schema, working_df, domain_config.bronze_required
    )

    # Track invalid ratios
    for column, rows in numeric_invalid_rows.items():
        track_invalid_ratio(
            column,
            rows,
            working_df,
            bronze_schema,
            failure_threshold,
            "Bronze validation failed: non-numeric values exceed threshold",
        )

    if invalid_date_rows:
        track_invalid_ratio(
            date_column,
            invalid_date_rows,
            working_df,
            bronze_schema,
            failure_threshold,
            "Bronze validation failed: unparseable dates exceed threshold",
        )

    # Final schema validation
    validated_df = apply_schema_with_lazy_mode(bronze_schema, working_df)

    summary = BronzeValidationSummary(
        row_count=len(validated_df),
        invalid_date_rows=invalid_date_rows,
        numeric_error_rows=numeric_invalid_rows,
        empty_columns=empty_columns,
    )
    return validated_df, summary


def validate_gold_layer(
    dataframe: pd.DataFrame,
    domain_config: "DomainSchema",
    gold_schema: "pa.DataFrameSchema",
    project_columns: bool = True,
    aggregate_duplicates: bool = False,
    enforce_unique: bool = False,
    custom_numeric_columns: Optional[Sequence[str]] = None,
) -> Tuple[pd.DataFrame, GoldValidationSummary]:
    """Validate a DataFrame against gold layer rules using domain configuration.

    This is a generalized version of domain-specific validate_gold_dataframe functions.
    Domain layers can call this directly or wrap it for custom behavior.

    Args:
        dataframe: Input DataFrame to validate
        domain_config: DomainSchema from domain_registry with validation config
        gold_schema: Pandera schema for gold layer validation
        project_columns: Whether to remove columns not in gold schema
            (default: True)
        aggregate_duplicates: If True, aggregate duplicate composite keys
            (default: False)
        enforce_unique: If True, raise on duplicate composite keys (default: False)
        custom_numeric_columns: Override numeric columns for aggregation (optional)

    Returns:
        Tuple of (validated_dataframe, GoldValidationSummary)

    Raises:
        SchemaError: If validation fails or a unique constraint is violated
            with enforce_unique=True
    """
    working_df = dataframe.copy(deep=True)
    removed_columns: List[str] = []

    # Column projection
    if project_columns:
        schema_cols = set(gold_schema.columns.keys())
        registry_cols = (
            [c.name for c in domain_config.columns] if domain_config.columns else []
        )
        allowed_cols = schema_cols
        if registry_cols:
            intersection = schema_cols & set(registry_cols)
            allowed_cols = intersection or schema_cols
        removed_columns = [
            column for column in working_df.columns if column not in allowed_cols
        ]
        if removed_columns:
            working_df = working_df.drop(columns=removed_columns, errors="ignore")

    # Ensure composite key columns exist
    composite_key = domain_config.composite_key
    for key_col in composite_key:
        if key_col not in working_df.columns:
            working_df[key_col] = None

    # Required columns check
    ensure_required_columns(
        gold_schema,
        working_df,
        domain_config.gold_required,
        schema_name="Gold",
    )

    # Duplicate detection
    duplicate_mask = working_df.duplicated(subset=composite_key, keep=False)
    duplicate_keys: List[Tuple[Any, ...]] = []

    if duplicate_mask.any():
        duplicate_keys = (
            working_df.loc[duplicate_mask, list(composite_key)]
            .apply(lambda row: tuple(row.values.tolist()), axis=1)
            .drop_duplicates()
            .tolist()
        )

        if enforce_unique:
            from work_data_hub.infrastructure.validation.schema_helpers import (
                raise_schema_error,
            )
            failure_cases = pd.DataFrame(duplicate_keys, columns=list(composite_key))
            raise_schema_error(
                gold_schema,
                working_df,
                message="Gold validation failed: Composite PK has duplicates",
                failure_cases=failure_cases,
            )

        if aggregate_duplicates:
            # Aggregate duplicates by summing numeric fields
            numeric_cols = list(custom_numeric_columns or domain_config.numeric_columns)
            non_numeric_cols = [c for c in working_df.columns if c not in numeric_cols]

            agg_dict: Dict[str, str] = {}
            for col in numeric_cols:
                if col in working_df.columns:
                    agg_dict[col] = "sum"
            for col in non_numeric_cols:
                if col not in composite_key:
                    agg_dict[col] = "first"

            working_df = working_df.groupby(
                list(composite_key), as_index=False
            ).agg(agg_dict)

    # Final schema validation
    validated_df = apply_schema_with_lazy_mode(gold_schema, working_df)

    summary = GoldValidationSummary(
        row_count=len(validated_df),
        removed_columns=removed_columns,
        duplicate_keys=duplicate_keys,
    )
    return validated_df, summary


__all__ = [
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    "validate_bronze_layer",
    "validate_gold_layer",
]
