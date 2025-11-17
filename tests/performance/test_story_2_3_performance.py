"""Story 2.3 performance tests for cleansing registry."""

import time
from typing import List

import pytest

from src.work_data_hub.cleansing import get_cleansing_registry
from src.work_data_hub.domain.annuity_performance.models import (
    AnnuityPerformanceOut,
)

STRING_RULE_CHAIN = ["trim_whitespace", "normalize_company_name"]
NUMERIC_RULE_CHAIN = [
    "standardize_null_values",
    "remove_currency_symbols",
    "clean_comma_separated_number",
    {"name": "handle_percentage_conversion"},
]
DATASET_SIZE = 10_000


def _generate_company_names(count: int) -> List[str]:
    values = []
    patterns = [
        "「  公司　有限  ",
        "『企业　集团』",
        "  WorkDataHub　有限公司  ",
    ]
    for idx in range(count):
        base = patterns[idx % len(patterns)]
        values.append(f"{base}{idx:04d}")
    return values


def _generate_numeric_values(count: int) -> List[str]:
    values = []
    for idx in range(count):
        if idx % 4 == 0:
            values.append(f"¥{1_000_000 + idx:,}.50")
        elif idx % 4 == 1:
            values.append(f"{1_000_000 + idx:,}")
        elif idx % 4 == 2:
            values.append("5.5%")
        else:
            values.append("N/A")
    return values


@pytest.mark.performance
class TestStory23Performance:
    def setup_method(self):
        self.registry = get_cleansing_registry()

    def test_string_rule_throughput(self):
        dataset = _generate_company_names(DATASET_SIZE)

        # Warm-up
        for value in dataset[:100]:
            self.registry.apply_rules(value, STRING_RULE_CHAIN)

        start = time.perf_counter()
        for value in dataset:
            self.registry.apply_rules(value, STRING_RULE_CHAIN)
        duration = time.perf_counter() - start

        rows_per_second = len(dataset) / duration
        assert rows_per_second >= 1000, (
            f"AC-PERF-1 FAILED: string cleansing throughput {rows_per_second:.0f} rows/s < 1000"
        )

    def test_numeric_rule_overhead_below_threshold(self):
        numeric_values = _generate_numeric_values(DATASET_SIZE)
        output_rows = _generate_output_rows(DATASET_SIZE)

        start = time.perf_counter()
        for value in numeric_values:
            self.registry.apply_rules(value, NUMERIC_RULE_CHAIN, field_name="年化收益率")
        cleansing_duration = time.perf_counter() - start

        start = time.perf_counter()
        for row in output_rows:
            AnnuityPerformanceOut(**row)
        pipeline_duration = time.perf_counter() - start

        rows_per_second = len(numeric_values) / cleansing_duration
        overhead_pct = (
            (cleansing_duration / pipeline_duration) * 100 if pipeline_duration else 0
        )

        assert rows_per_second >= 1000, (
            f"AC-PERF-1 FAILED: numeric cleansing throughput {rows_per_second:.0f} rows/s < 1000"
        )
        assert overhead_pct < 20, (
            f"AC-PERF-2 FAILED: numeric cleansing overhead {overhead_pct:.1f}% >= 20%"
        )
def _generate_output_rows(count: int) -> List[dict]:
    values = _generate_numeric_values(count)
    rate_patterns = ["5.5%", "0.75%", "0.0%"]
    rows: List[dict] = []
    for idx, raw in enumerate(values):
        rows.append(
            {
                "计划代码": f"PLAN{idx:05d}",
                "company_id": f"COMP{idx:05d}",
                "期末资产规模": raw,
                "年化收益率": rate_patterns[idx % len(rate_patterns)],
            }
        )
    return rows
