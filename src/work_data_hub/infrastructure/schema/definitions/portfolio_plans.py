"""Portfolio Plans domain schema definition.

Story 7.5: Domain Registry Pre-modularization
Extracted from domain_registry.py for isolation and maintainability.
"""

from ..core import ColumnDef, ColumnType, DomainSchema, IndexDef
from ..registry import register_domain

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
            IndexDef(["组合代码"], unique=True),  # UNIQUE for ON CONFLICT FK backfill
            IndexDef(["年金计划号", "组合代码"]),
        ],
    )
)
