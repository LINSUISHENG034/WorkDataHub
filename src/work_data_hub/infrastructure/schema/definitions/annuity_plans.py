"""Annuity Plans domain schema definition.

Story 7.5: Domain Registry Pre-modularization
Extracted from domain_registry.py for isolation and maintainability.
"""

from ..core import ColumnDef, ColumnType, DomainSchema, IndexDef
from ..registry import register_domain

register_domain(
    DomainSchema(
        domain_name="annuity_plans",
        pg_schema="mapping",
        pg_table="年金计划",
        sheet_name="年金计划",
        primary_key="id",
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
            IndexDef(["年金计划号"], unique=True),
            IndexDef(["年金计划号", "company_id"]),
        ],
    )
)
