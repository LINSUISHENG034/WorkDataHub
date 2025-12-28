from __future__ import annotations

import importlib.util
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "io"
    / "schema"
    / "migrations"
    / "versions"
    / "001_initial_infrastructure.py"
)


def _extract_table_columns(text: str, table_name: str) -> list[str]:
    match = re.search(rf'op\.create_table\(\s*\n\s*"{re.escape(table_name)}"\s*,', text)
    if not match:
        raise AssertionError(f"op.create_table('{table_name}') not found")

    sliced = text[match.start() :]
    depth = 0
    end = None
    for i, ch in enumerate(sliced):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise AssertionError(f"Could not parse create_table() call for '{table_name}'")

    block = sliced[:end]
    return re.findall(r'sa\.Column\(\s*"([^"]+)"', block)


def test_migration_module_imports() -> None:
    assert MIGRATION_PATH.exists(), f"Missing migration file: {MIGRATION_PATH}"
    spec = importlib.util.spec_from_file_location(
        "enterprise_schema_migration", MIGRATION_PATH
    )
    assert spec and spec.loader, "Failed to build import spec for migration file"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def test_migration_uses_valid_sqlalchemy_types() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "sa.DoublePrecision" not in text, (
        "Invalid SQLAlchemy type (sa.DoublePrecision) should not be used"
    )


def test_enterprise_schema_column_contract() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")

    base_info_cols = _extract_table_columns(text, "base_info")
    business_info_cols = _extract_table_columns(text, "business_info")
    biz_label_cols = _extract_table_columns(text, "biz_label")

    assert len(base_info_cols) == 41, (
        f"base_info expected 41 columns (37 legacy + 4 canonical), got {len(base_info_cols)}"
    )
    assert len(business_info_cols) == 43, (
        f"business_info expected 43 columns, got {len(business_info_cols)}"
    )
    assert len(biz_label_cols) == 9, (
        f"biz_label expected 9 columns, got {len(biz_label_cols)}"
    )

    base_info_required = {
        "company_id",
        "search_key_word",
        "unite_code",
        "raw_data",
        "raw_business_info",
        "raw_biz_label",
        "api_fetched_at",
        "updated_at",
    }
    assert base_info_required.issubset(set(base_info_cols)), (
        f"base_info missing required columns: {base_info_required - set(base_info_cols)}"
    )

    business_info_required = {
        "company_id",
        "registered_date",
        "registered_capital",
        "created_at",
        "updated_at",
    }
    assert business_info_required.issubset(set(business_info_cols)), (
        f"business_info missing required columns: {business_info_required - set(business_info_cols)}"
    )

    biz_label_required = {
        "company_id",
        "type",
        "lv1_name",
        "lv2_name",
        "lv3_name",
        "lv4_name",
    }
    assert biz_label_required.issubset(set(biz_label_cols)), (
        f"biz_label missing required columns: {biz_label_required - set(biz_label_cols)}"
    )
