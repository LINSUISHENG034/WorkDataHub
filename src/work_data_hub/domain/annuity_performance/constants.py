"""Shared constants for the annuity performance domain."""

from __future__ import annotations

from typing import Sequence

# Columns that exist in the annuity performance gold table. This mirrors the
# structure enforced by Story 4.4 and is reused by both the legacy service path
# and the pipeline-based Gold projection step.
DEFAULT_ALLOWED_GOLD_COLUMNS: Sequence[str] = (
    "月度",
    "业务类型",
    "计划类型",
    "计划代码",
    "计划名称",
    "组合类型",
    "组合代码",
    "组合名称",
    "客户名称",
    "期初资产规模",
    "期末资产规模",
    "供款",
    "流失_含待遇支付",
    "流失",
    "待遇支付",
    "投资收益",
    "年化收益率",
    "机构代码",
    "机构名称",
    "产品线代码",
    "年金账户号",
    "年金账户名",
    "company_id",
)
