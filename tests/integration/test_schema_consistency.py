"""Schema consistency tests between Pydantic models and database tables.

This module validates that Pydantic domain models stay in sync with
database table definitions created by Alembic migrations.

Purpose:
- Detect field name mismatches between models and DB columns
- Detect type incompatibilities early in CI
- Prevent runtime errors from schema drift

Usage:
    pytest tests/integration/test_schema_consistency.py -v

Note:
    These tests require a PostgreSQL database with migrations applied.
    Skip if DATABASE_URL is not configured.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, get_args, get_origin

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from work_data_hub.config import get_settings


# =============================================================================
# Field Mapping: Pydantic model field -> DB column name
# =============================================================================
# Domain models use Chinese field names, DB uses English column names.
# This mapping defines the expected correspondence.

ANNUITY_PERFORMANCE_FIELD_MAP = {
    # Pydantic field -> DB column
    "月度": "reporting_month",
    "计划代码": "plan_code",
    "company_id": "company_id",
    "业务类型": "business_type",
    "计划类型": "plan_type",
    "计划名称": "plan_name",
    "组合类型": "portfolio_type",
    "组合代码": "portfolio_code",
    "组合名称": "portfolio_name",
    "客户名称": "customer_name",
    "期初资产规模": "starting_assets",
    "期末资产规模": "ending_assets",
    "供款": "contribution",
    "流失_含待遇支付": "loss_with_benefit",
    "流失": "loss",
    "待遇支付": "benefit_payment",
    "投资收益": "investment_return",
    "当期收益率": "annualized_return_rate",
    "机构代码": "institution_code",
    "机构名称": "institution_name",
    "产品线代码": "product_line_code",
    "年金账户号": "pension_account_number",
    "年金账户名": "pension_account_name",
    "子企业号": "sub_enterprise_number",
    "子企业名称": "sub_enterprise_name",
    "集团企业客户号": "group_customer_number",
    "集团企业客户名称": "group_customer_name",
}

# Fields in Pydantic model that are NOT in DB (handled separately)
ANNUITY_PERFORMANCE_MODEL_ONLY_FIELDS = {"id"}

# Columns in DB that are NOT in Pydantic model (audit columns, etc.)
ANNUITY_PERFORMANCE_DB_ONLY_COLUMNS = {
    "pipeline_run_id",
    "created_at",
    "updated_at",
}


# =============================================================================
# Type Compatibility Mapping
# =============================================================================


def _get_base_type(annotation: Any) -> type | None:
    """Extract base type from Optional, Union, etc."""
    origin = get_origin(annotation)
    if origin is None:
        return annotation if isinstance(annotation, type) else None

    # Handle Optional[X] which is Union[X, None]
    args = get_args(annotation)
    if type(None) in args:
        # Filter out NoneType
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return _get_base_type(non_none_args[0])
    return None


def _types_compatible(python_type: Any, sql_type_str: str) -> bool:
    """Check if Python type is compatible with SQL type.

    Args:
        python_type: Python type annotation from Pydantic model
        sql_type_str: SQL type string from database inspection

    Returns:
        True if types are compatible
    """
    base_type = _get_base_type(python_type)
    sql_lower = sql_type_str.lower()

    # String types
    if base_type is str:
        return any(t in sql_lower for t in ["varchar", "text", "char"])

    # Date types
    if base_type is date:
        return "date" in sql_lower

    # Numeric types
    if base_type in (int, float, Decimal):
        return any(
            t in sql_lower for t in ["numeric", "decimal", "integer", "float", "double"]
        )

    # If we can't determine, assume compatible (avoid false positives)
    return True


# =============================================================================
# Test Fixtures
# =============================================================================


def get_test_engine() -> Engine | None:
    """Get database engine for testing, or None if not available."""
    try:
        settings = get_settings()
        url = settings.get_database_connection_string()
        if "sqlite" in url.lower():
            return None
        return create_engine(url)
    except Exception:
        return None


@pytest.fixture(scope="module")
def db_engine():
    """Provide database engine, skip if not available."""
    engine = get_test_engine()
    if engine is None:
        pytest.skip("PostgreSQL database not available for schema consistency tests")
    return engine


# =============================================================================
# Test Classes
# =============================================================================


class TestAnnuityPerformanceSchemaConsistency:
    """Validate AnnuityPerformanceOut model matches annuity_performance_new table."""

    TABLE_NAME = "annuity_performance_new"

    def test_table_exists(self, db_engine: Engine):
        """Verify the target table exists in database."""
        inspector = inspect(db_engine)
        tables = [t.lower() for t in inspector.get_table_names()]
        assert self.TABLE_NAME in tables, (
            f"Table '{self.TABLE_NAME}' not found. Run migrations first."
        )

    def test_all_model_fields_have_db_columns(self, db_engine: Engine):
        """Every Pydantic model field should map to a DB column."""
        from work_data_hub.domain.annuity_performance.models import (
            AnnuityPerformanceOut,
        )

        inspector = inspect(db_engine)
        db_columns = {c["name"] for c in inspector.get_columns(self.TABLE_NAME)}

        model_fields = set(AnnuityPerformanceOut.model_fields.keys())
        mapped_fields = model_fields - ANNUITY_PERFORMANCE_MODEL_ONLY_FIELDS

        missing_in_db = []
        for field in mapped_fields:
            expected_column = ANNUITY_PERFORMANCE_FIELD_MAP.get(field, field)
            if expected_column not in db_columns:
                missing_in_db.append(f"{field} -> {expected_column}")

        assert not missing_in_db, f"Model fields missing in DB:\n" + "\n".join(
            f"  - {m}" for m in missing_in_db
        )

    def test_all_db_columns_have_model_fields(self, db_engine: Engine):
        """Every DB column should map to a Pydantic model field (except audit columns)."""
        from work_data_hub.domain.annuity_performance.models import (
            AnnuityPerformanceOut,
        )

        inspector = inspect(db_engine)
        db_columns = {c["name"] for c in inspector.get_columns(self.TABLE_NAME)}

        # Remove audit-only columns
        business_columns = db_columns - ANNUITY_PERFORMANCE_DB_ONLY_COLUMNS

        # Build reverse mapping: DB column -> Pydantic field
        reverse_map = {v: k for k, v in ANNUITY_PERFORMANCE_FIELD_MAP.items()}

        model_fields = set(AnnuityPerformanceOut.model_fields.keys())

        missing_in_model = []
        for col in business_columns:
            expected_field = reverse_map.get(col, col)
            if expected_field not in model_fields:
                missing_in_model.append(f"{col} -> {expected_field}")

        assert not missing_in_model, f"DB columns missing in model:\n" + "\n".join(
            f"  - {m}" for m in missing_in_model
        )

    def test_field_types_compatible(self, db_engine: Engine):
        """Pydantic field types should be compatible with DB column types."""
        from work_data_hub.domain.annuity_performance.models import (
            AnnuityPerformanceOut,
        )

        inspector = inspect(db_engine)
        db_columns = {c["name"]: c for c in inspector.get_columns(self.TABLE_NAME)}

        incompatible = []
        for field_name, field_info in AnnuityPerformanceOut.model_fields.items():
            if field_name in ANNUITY_PERFORMANCE_MODEL_ONLY_FIELDS:
                continue

            db_col_name = ANNUITY_PERFORMANCE_FIELD_MAP.get(field_name, field_name)
            if db_col_name not in db_columns:
                continue  # Already caught by other tests

            db_col = db_columns[db_col_name]
            sql_type = str(db_col["type"])

            if not _types_compatible(field_info.annotation, sql_type):
                incompatible.append(
                    f"{field_name} ({field_info.annotation}) vs "
                    f"{db_col_name} ({sql_type})"
                )

        assert not incompatible, f"Type incompatibilities found:\n" + "\n".join(
            f"  - {i}" for i in incompatible
        )

    def test_required_fields_not_nullable(self, db_engine: Engine):
        """Required Pydantic fields should map to NOT NULL DB columns."""
        from work_data_hub.domain.annuity_performance.models import (
            AnnuityPerformanceOut,
        )

        inspector = inspect(db_engine)
        db_columns = {c["name"]: c for c in inspector.get_columns(self.TABLE_NAME)}

        mismatches = []
        for field_name, field_info in AnnuityPerformanceOut.model_fields.items():
            if field_name in ANNUITY_PERFORMANCE_MODEL_ONLY_FIELDS:
                continue

            db_col_name = ANNUITY_PERFORMANCE_FIELD_MAP.get(field_name, field_name)
            if db_col_name not in db_columns:
                continue

            is_required = field_info.is_required()
            is_nullable = db_columns[db_col_name]["nullable"]

            # Required field should NOT be nullable in DB
            if is_required and is_nullable:
                mismatches.append(f"{field_name}: required in model but nullable in DB")

        assert not mismatches, f"Required/nullable mismatches:\n" + "\n".join(
            f"  - {m}" for m in mismatches
        )


class TestFieldMappingCompleteness:
    """Validate that field mapping dictionaries are complete."""

    def test_annuity_performance_mapping_covers_all_model_fields(self):
        """Field mapping should cover all non-excluded model fields."""
        from work_data_hub.domain.annuity_performance.models import (
            AnnuityPerformanceOut,
        )

        model_fields = set(AnnuityPerformanceOut.model_fields.keys())
        mapped_fields = model_fields - ANNUITY_PERFORMANCE_MODEL_ONLY_FIELDS

        unmapped = mapped_fields - set(ANNUITY_PERFORMANCE_FIELD_MAP.keys())
        assert not unmapped, (
            f"Model fields not in ANNUITY_PERFORMANCE_FIELD_MAP:\n"
            + "\n".join(f"  - {f}" for f in unmapped)
        )


class TestMigrationFieldMapSync:
    """Validate that migration comments match field mapping."""

    def test_migration_comments_match_mapping(self, db_engine: Engine):
        """DB column comments should reference correct Chinese field names."""
        # Get columns with comments using proper PostgreSQL query
        with db_engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT
                    a.attname as column_name,
                    col_description(a.attrelid, a.attnum) as comment
                FROM pg_attribute a
                JOIN pg_class c ON a.attrelid = c.oid
                WHERE c.relname = 'annuity_performance_new'
                AND a.attnum > 0
                AND NOT a.attisdropped
                AND col_description(a.attrelid, a.attnum) IS NOT NULL
            """)
            )
            columns_with_comments = {row[0]: row[1] for row in result}

        # Build reverse mapping
        reverse_map = {v: k for k, v in ANNUITY_PERFORMANCE_FIELD_MAP.items()}

        mismatches = []
        for col_name, comment in columns_with_comments.items():
            if col_name in ANNUITY_PERFORMANCE_DB_ONLY_COLUMNS:
                continue

            expected_chinese = reverse_map.get(col_name)
            if expected_chinese and expected_chinese not in comment:
                # Check if the Chinese name is in the comment
                # Comments format: "Description (中文名)"
                if f"({expected_chinese})" not in comment:
                    mismatches.append(
                        f"{col_name}: comment '{comment}' doesn't mention "
                        f"'{expected_chinese}'"
                    )

        # This is a soft check - just warn, don't fail
        if mismatches:
            import warnings

            warnings.warn(
                f"Column comments may be out of sync:\n"
                + "\n".join(f"  - {m}" for m in mismatches)
            )
