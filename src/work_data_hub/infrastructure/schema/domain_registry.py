"""Domain schema registry (Single Source of Truth) for WorkDataHub.

Story 6.2-P13: Unified Domain Schema Management Architecture

Note on layering:
This module lives under `work_data_hub.infrastructure` so other layers can
import schema definitions without importing `work_data_hub.io`, preserving
Clean Architecture boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from work_data_hub.infrastructure.sql.core.identifier import (
    qualify_table,
    quote_identifier,
)


class ColumnType(Enum):
    """Supported column types for domain schemas."""

    STRING = "string"
    DATE = "date"
    DATETIME = "datetime"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    TEXT = "text"


@dataclass
class ColumnDef:
    """Definition of a single column in a domain schema."""

    name: str
    column_type: ColumnType
    nullable: bool = True
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    description: str = ""
    is_primary_key: bool = False


@dataclass
class IndexDef:
    """Definition of a database index."""

    columns: List[str]
    unique: bool = False
    name: Optional[str] = None
    method: Optional[str] = None
    where: Optional[str] = None


@dataclass
class DomainSchema:
    """Complete schema definition for a domain."""

    domain_name: str
    pg_schema: str
    pg_table: str
    sheet_name: str
    primary_key: str = "id"
    delete_scope_key: List[str] = field(default_factory=list)
    composite_key: List[str] = field(default_factory=list)
    columns: List[ColumnDef] = field(default_factory=list)
    indexes: List[IndexDef] = field(default_factory=list)
    bronze_required: List[str] = field(default_factory=list)
    gold_required: List[str] = field(default_factory=list)
    numeric_columns: List[str] = field(default_factory=list)


_DOMAIN_REGISTRY: Dict[str, DomainSchema] = {}


def register_domain(schema: DomainSchema) -> None:
    if schema.domain_name in _DOMAIN_REGISTRY:
        raise ValueError(
            f"Domain '{schema.domain_name}' is already registered. "
            "Use a different domain_name or unregister first."
        )
    _DOMAIN_REGISTRY[schema.domain_name] = schema


def get_domain(name: str) -> DomainSchema:
    if name not in _DOMAIN_REGISTRY:
        available = list(_DOMAIN_REGISTRY.keys())
        raise KeyError(f"Domain '{name}' not found in registry. Available: {available}")
    return _DOMAIN_REGISTRY[name]


def list_domains() -> List[str]:
    return sorted(_DOMAIN_REGISTRY.keys())


def get_composite_key(domain_name: str) -> List[str]:
    return get_domain(domain_name).composite_key


def get_delete_scope_key(domain_name: str) -> List[str]:
    return get_domain(domain_name).delete_scope_key


def _column_type_to_sql(col: ColumnDef) -> str:
    if col.column_type == ColumnType.STRING:
        length = col.max_length or 255
        return f"VARCHAR({length})"
    if col.column_type == ColumnType.DATE:
        return "DATE"
    if col.column_type == ColumnType.DATETIME:
        return "TIMESTAMP WITH TIME ZONE"
    if col.column_type == ColumnType.DECIMAL:
        precision = col.precision or 18
        scale = col.scale or 4
        return f"DECIMAL({precision}, {scale})"
    if col.column_type == ColumnType.INTEGER:
        return "INTEGER"
    if col.column_type == ColumnType.BOOLEAN:
        return "BOOLEAN"
    if col.column_type == ColumnType.TEXT:
        return "TEXT"
    return "VARCHAR(255)"


def generate_create_table_sql(domain_name: str) -> str:
    """Generate deterministic CREATE TABLE SQL for a domain."""

    schema = get_domain(domain_name)
    qualified_table = qualify_table(schema.pg_table, schema.pg_schema)
    quoted_pk = quote_identifier(schema.primary_key)

    lines: List[str] = []
    lines.append(f"-- DDL for domain: {domain_name}")
    lines.append(f"-- Table: {qualified_table}")
    lines.append("")
    lines.append(f"DROP TABLE IF EXISTS {qualified_table} CASCADE;")
    lines.append("")
    lines.append(f"CREATE TABLE {qualified_table} (")
    lines.append(f"  {quoted_pk} INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,")
    lines.append("")
    lines.append("  -- Business columns")
    for col in schema.columns:
        quoted_name = quote_identifier(col.name)
        sql_type = _column_type_to_sql(col)
        nullable_str = "" if col.nullable else " NOT NULL"
        lines.append(f"  {quoted_name} {sql_type}{nullable_str},")
    lines.append("")
    lines.append("  -- Audit columns")
    lines.append('  "created_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,')
    lines.append('  "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP')
    lines.append(");")
    lines.append("")

    if schema.indexes:
        lines.append("-- Indexes")
        for idx in schema.indexes:
            cols_str = ", ".join(quote_identifier(c) for c in idx.columns)
            idx_name = idx.name or f"idx_{schema.pg_table}_{'_'.join(idx.columns)}"
            quoted_idx_name = quote_identifier(idx_name)
            unique_str = "UNIQUE " if idx.unique else ""
            method_str = f" USING {idx.method}" if idx.method else ""
            where_str = f" WHERE {idx.where}" if idx.where else ""
            lines.append(
                f"CREATE {unique_str}INDEX IF NOT EXISTS {quoted_idx_name} "
                f"ON {qualified_table}{method_str} ({cols_str}){where_str};"
            )
        lines.append("")

    func_name = f"update_{domain_name}_updated_at"
    lines.append("-- Trigger for updated_at")
    lines.append(f"CREATE OR REPLACE FUNCTION {func_name}()")
    lines.append("RETURNS TRIGGER AS $$")
    lines.append("BEGIN")
    lines.append("    NEW.updated_at = CURRENT_TIMESTAMP;")
    lines.append("    RETURN NEW;")
    lines.append("END;")
    lines.append("$$ LANGUAGE plpgsql;")
    lines.append("")

    trigger_name = f"trigger_{func_name}"
    lines.append(f"CREATE TRIGGER {trigger_name}")
    lines.append(f"    BEFORE UPDATE ON {qualified_table}")
    lines.append("    FOR EACH ROW")
    lines.append(f"    EXECUTE FUNCTION {func_name}();")

    return "\n".join(lines)


# =============================================================================
# Domain Registrations
# =============================================================================

register_domain(
    DomainSchema(
        domain_name="annuity_performance",
        pg_schema="business",
        pg_table="规模明细",
        sheet_name="规模明细",
        primary_key="annuity_performance_id",
        delete_scope_key=["月度", "计划代码", "company_id"],
        composite_key=["月度", "计划代码", "组合代码", "company_id"],
        bronze_required=[
            "月度",
            "计划代码",
            "客户名称",
            "期初资产规模",
            "期末资产规模",
            "投资收益",
            "当期收益率",
        ],
        gold_required=[
            "月度",
            "计划代码",
            "company_id",
            "客户名称",
            "期初资产规模",
            "期末资产规模",
            "投资收益",
        ],
        numeric_columns=[
            "期初资产规模",
            "期末资产规模",
            "供款",
            "流失_含待遇支付",
            "流失",
            "待遇支付",
            "投资收益",
            "当期收益率",
            "年化收益率",
        ],
        columns=[
            ColumnDef("月度", ColumnType.DATE, nullable=False),
            ColumnDef("业务类型", ColumnType.STRING, max_length=255),
            ColumnDef("计划类型", ColumnType.STRING, max_length=255),
            ColumnDef("计划代码", ColumnType.STRING, nullable=False, max_length=255),
            ColumnDef("计划名称", ColumnType.STRING, max_length=255),
            ColumnDef("组合类型", ColumnType.STRING, max_length=255),
            ColumnDef("组合代码", ColumnType.STRING, max_length=255),
            ColumnDef("组合名称", ColumnType.STRING, max_length=255),
            ColumnDef("客户名称", ColumnType.STRING, max_length=255),
            ColumnDef("期初资产规模", ColumnType.DECIMAL, precision=18, scale=4),
            ColumnDef("期末资产规模", ColumnType.DECIMAL, precision=18, scale=4),
            ColumnDef("供款", ColumnType.DECIMAL, precision=18, scale=4),
            ColumnDef("流失_含待遇支付", ColumnType.DECIMAL, precision=18, scale=4),
            ColumnDef("流失", ColumnType.DECIMAL, precision=18, scale=4),
            ColumnDef("待遇支付", ColumnType.DECIMAL, precision=18, scale=4),
            ColumnDef("投资收益", ColumnType.DECIMAL, precision=18, scale=4),
            ColumnDef("当期收益率", ColumnType.DECIMAL, precision=10, scale=6),
            ColumnDef("年化收益率", ColumnType.DECIMAL, precision=10, scale=6),
            ColumnDef("机构代码", ColumnType.STRING, max_length=255),
            ColumnDef("机构名称", ColumnType.STRING, max_length=255),
            ColumnDef("产品线代码", ColumnType.STRING, max_length=255),
            ColumnDef("年金账户号", ColumnType.STRING, max_length=50),
            ColumnDef("年金账户名", ColumnType.STRING, max_length=255),
            ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),
        ],
        indexes=[
            IndexDef(["月度"]),
            IndexDef(["计划代码"]),
            IndexDef(["company_id"]),
            IndexDef(["机构代码"]),
            IndexDef(["产品线代码"]),
            IndexDef(["年金账户号"]),
            IndexDef(["月度", "计划代码"]),
            IndexDef(["月度", "company_id"]),
            IndexDef(["月度", "计划代码", "company_id"]),
        ],
    )
)

register_domain(
    DomainSchema(
        domain_name="annuity_income",
        pg_schema="business",
        pg_table="收入明细",
        sheet_name="收入明细",
        primary_key="annuity_income_id",
        delete_scope_key=["月度", "计划号", "company_id"],
        composite_key=["月度", "计划号", "组合代码", "company_id"],
        bronze_required=[
            "月度",
            "计划号",
            "客户名称",
            "业务类型",
            "固费",
            "浮费",
            "回补",
            "税",
        ],
        gold_required=[
            "月度",
            "计划号",
            "company_id",
            "客户名称",
            "固费",
            "浮费",
            "回补",
            "税",
        ],
        numeric_columns=["固费", "浮费", "回补", "税"],
        columns=[
            ColumnDef("月度", ColumnType.DATE, nullable=False),
            ColumnDef("计划号", ColumnType.STRING, nullable=False, max_length=255),
            ColumnDef("company_id", ColumnType.STRING, nullable=False, max_length=50),
            ColumnDef("客户名称", ColumnType.STRING, nullable=False, max_length=255),
            ColumnDef("年金账户名", ColumnType.STRING, max_length=255),
            ColumnDef("业务类型", ColumnType.STRING, max_length=255),
            ColumnDef("计划类型", ColumnType.STRING, max_length=255),
            ColumnDef("组合代码", ColumnType.STRING, max_length=255),
            ColumnDef("产品线代码", ColumnType.STRING, max_length=255),
            ColumnDef("机构代码", ColumnType.STRING, max_length=255),
            ColumnDef(
                "固费",
                ColumnType.DECIMAL,
                nullable=False,
                precision=18,
                scale=4,
            ),
            ColumnDef(
                "浮费",
                ColumnType.DECIMAL,
                nullable=False,
                precision=18,
                scale=4,
            ),
            ColumnDef(
                "回补",
                ColumnType.DECIMAL,
                nullable=False,
                precision=18,
                scale=4,
            ),
            ColumnDef(
                "税",
                ColumnType.DECIMAL,
                nullable=False,
                precision=18,
                scale=4,
            ),
        ],
        indexes=[
            IndexDef(["月度"]),
            IndexDef(["计划号"]),
            IndexDef(["company_id"]),
            IndexDef(["月度", "计划号", "company_id"]),
        ],
    )
)

register_domain(
    DomainSchema(
        domain_name="annuity_plans",
        pg_schema="mapping",
        pg_table="年金计划",
        sheet_name="年金计划",
        primary_key="annuity_plans_id",
        delete_scope_key=["年金计划号", "company_id"],
        composite_key=["年金计划号", "company_id"],
        bronze_required=["年金计划号"],
        gold_required=["年金计划号", "company_id"],
        numeric_columns=["组合数", "是否统括"],
        columns=[
            ColumnDef("年金计划号", ColumnType.STRING, nullable=False, max_length=255),
            ColumnDef("计划简称", ColumnType.STRING, max_length=255),
            ColumnDef("计划全称", ColumnType.STRING, max_length=255),
            ColumnDef("主拓代码", ColumnType.STRING, max_length=10),
            ColumnDef("计划类型", ColumnType.STRING, max_length=255),
            ColumnDef("客户名称", ColumnType.STRING, max_length=255),
            ColumnDef("company_id", ColumnType.STRING, max_length=255),
            ColumnDef("管理资格", ColumnType.STRING, max_length=255),
            ColumnDef("计划状态", ColumnType.STRING, max_length=255),
            ColumnDef("主拓机构", ColumnType.STRING, max_length=10),
            ColumnDef("组合数", ColumnType.INTEGER),
            ColumnDef("是否统括", ColumnType.INTEGER),
            ColumnDef("备注", ColumnType.TEXT),
        ],
        indexes=[
            IndexDef(["company_id"]),
            IndexDef(["年金计划号"]),
            IndexDef(["年金计划号", "company_id"]),
        ],
    )
)

register_domain(
    DomainSchema(
        domain_name="portfolio_plans",
        pg_schema="mapping",
        pg_table="组合计划",
        sheet_name="组合计划",
        primary_key="portfolio_plans_id",
        delete_scope_key=["年金计划号", "组合代码"],
        composite_key=["年金计划号", "组合代码"],
        bronze_required=["组合代码"],
        gold_required=["年金计划号", "组合代码"],
        numeric_columns=["是否存款组合", "是否外部组合", "是否PK组合"],
        columns=[
            ColumnDef("年金计划号", ColumnType.STRING, max_length=255),
            ColumnDef("组合代码", ColumnType.STRING, nullable=False, max_length=255),
            ColumnDef("组合名称", ColumnType.STRING, max_length=255),
            ColumnDef("组合简称", ColumnType.STRING, max_length=255),
            ColumnDef("组合状态", ColumnType.STRING, max_length=255),
            ColumnDef("运作开始日", ColumnType.DATE),
            ColumnDef("组合类型", ColumnType.STRING, max_length=255),
            ColumnDef("子分类", ColumnType.STRING, max_length=255),
            ColumnDef("受托人", ColumnType.STRING, max_length=255),
            ColumnDef("是否存款组合", ColumnType.INTEGER),
            ColumnDef("是否外部组合", ColumnType.INTEGER),
            ColumnDef("是否PK组合", ColumnType.INTEGER),
            ColumnDef("投资管理人", ColumnType.STRING, max_length=255),
            ColumnDef("受托管理人", ColumnType.STRING, max_length=255),
            ColumnDef("投资组合代码", ColumnType.STRING, max_length=255),
            ColumnDef("投资组合名称", ColumnType.STRING, max_length=255),
            ColumnDef("备注", ColumnType.TEXT),
        ],
        indexes=[
            IndexDef(["年金计划号"]),
            IndexDef(["组合代码"]),
            IndexDef(["年金计划号", "组合代码"]),
        ],
    )
)

__all__ = [
    "ColumnType",
    "ColumnDef",
    "IndexDef",
    "DomainSchema",
    "register_domain",
    "get_domain",
    "list_domains",
    "get_composite_key",
    "get_delete_scope_key",
    "generate_create_table_sql",
]
