"""Date cleansing rules (Story 6.2-P5)."""

from __future__ import annotations

from datetime import date
from typing import Any

from work_data_hub.infrastructure.cleansing.registry import RuleCategory, rule
from work_data_hub.utils.date_parser import parse_chinese_date


@rule(
    name="parse_chinese_date_value",
    category=RuleCategory.DATE,
    description="解析中文/数字日期为 Python date（解析失败则返回原值）",
)
def parse_chinese_date_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, date):
        return value

    parsed = parse_chinese_date(value)
    return parsed if parsed is not None else value


__all__ = ["parse_chinese_date_value"]
