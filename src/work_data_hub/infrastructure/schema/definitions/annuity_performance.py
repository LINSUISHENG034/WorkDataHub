"""Annuity Performance domain schema definition.

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
        domain_name="annuity_performance",
        pg_schema="business",
        pg_table="规模明细",
        sheet_name="规模明细",
        primary_key="id",
        delete_scope_key=["月度", "业务类型", "计划类型"],
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
            # Story 7.3-5: Add 4 missing fields for enterprise hierarchy
            ColumnDef("子企业号", ColumnType.STRING, max_length=50),
            ColumnDef("子企业名称", ColumnType.STRING, max_length=255),
            ColumnDef("集团企业客户号", ColumnType.STRING, max_length=50),
            ColumnDef("集团企业客户名称", ColumnType.STRING, max_length=255),
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
