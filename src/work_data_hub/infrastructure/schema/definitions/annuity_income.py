"""Annuity Income domain schema definition.

Story 7.5: Domain Registry Pre-modularization
Extracted from domain_registry.py for isolation and maintainability.
"""

from work_data_hub.infrastructure.schema.core import (
    ColumnDef,
    ColumnType,
    DomainSchema,
    IndexDef,
)
from work_data_hub.infrastructure.schema.registry import register_domain

register_domain(
    DomainSchema(
        domain_name="annuity_income",
        pg_schema="business",
        pg_table="收入明细",
        sheet_name="收入明细",
        primary_key="id",
        delete_scope_key=["月度", "计划代码", "company_id"],
        composite_key=["月度", "计划代码", "组合代码", "company_id"],
        bronze_required=[
            "月度",
            "计划代码",
            "客户名称",
            "业务类型",
            "固费",
            "浮费",
            "回补",
            "税",
        ],
        gold_required=[
            "月度",
            "计划代码",
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
            ColumnDef("计划代码", ColumnType.STRING, nullable=False, max_length=255),
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
            IndexDef(["计划代码"]),
            IndexDef(["company_id"]),
            IndexDef(["月度", "计划代码", "company_id"]),
        ],
    )
)
