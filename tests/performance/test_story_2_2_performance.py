"""
Story 2.2 Performance Tests (Bronze/Gold Pandera Schemas)
"""

import time
from datetime import datetime
from typing import List

import pandas as pd
import pytest

from work_data_hub.domain.annuity_performance.schemas import (
    validate_bronze_dataframe,
    validate_gold_dataframe,
)


def _generate_bronze_rows(num_rows: int = 10_000) -> List[dict]:
    rows = []
    for i in range(num_rows):
        month = (i % 12) + 1
        rows.append(
            {
                "月度": f"2025年{month}月" if i % 2 == 0 else f"2025-{month:02d}",
                "计划代码": f"PLAN{i:05d}",
                "客户名称": f"公司{i}",
                "期初资产规模": f"{1_000_000 + i:,}.00",
                "期末资产规模": 2_000_000 + i,
                "投资收益": 500_000 + i,
                "年化收益率": "5.5%" if i % 3 == 0 else 0.04,
            }
        )
    return rows


def _generate_gold_rows(num_rows: int = 10_000) -> List[dict]:
    rows = []
    base = pd.Timestamp(datetime(2025, 1, 1))
    for i in range(num_rows):
        rows.append(
            {
                "月度": base + pd.DateOffset(months=i % 12),
                "计划代码": f"PLAN{i:05d}",
                "company_id": f"COMP{i:05d}",
                "客户名称": f"公司{i}",
                "期初资产规模": float(1_000_000 + i),
                "期末资产规模": float(2_000_000 + i),
                "投资收益": float(500_000 + i),
                "供款": float(100_000 + i),
                "流失_含待遇支付": 10.0,
                "流失": 5.0,
                "待遇支付": 2.0,
                "年化收益率": 0.05,
            }
        )
    return rows


@pytest.fixture(scope="module")
def bronze_dataframe() -> pd.DataFrame:
    return pd.DataFrame(_generate_bronze_rows())


@pytest.fixture(scope="module")
def gold_dataframe() -> pd.DataFrame:
    return pd.DataFrame(_generate_gold_rows())


@pytest.mark.performance
class TestStory22Performance:
    def test_bronze_validation_throughput(self, bronze_dataframe: pd.DataFrame):
        start = time.time()
        validate_bronze_dataframe(bronze_dataframe)
        duration = time.time() - start
        rows_per_second = len(bronze_dataframe) / duration
        assert rows_per_second >= 5_000, (
            f"Bronze validation throughput {rows_per_second:.0f} rows/s "
            "does not meet ≥5000 rows/s target"
        )

    def test_gold_validation_throughput(self, gold_dataframe: pd.DataFrame):
        start = time.time()
        validate_gold_dataframe(gold_dataframe)
        duration = time.time() - start
        rows_per_second = len(gold_dataframe) / duration
        assert rows_per_second >= 3_000, (
            f"Gold validation throughput {rows_per_second:.0f} rows/s "
            "does not meet ≥3000 rows/s target"
        )

    def test_validation_overhead_budget(self, bronze_dataframe: pd.DataFrame):
        start_validation = time.time()
        validate_bronze_dataframe(bronze_dataframe)
        validation_duration = time.time() - start_validation

        start_pipeline = time.time()
        df = bronze_dataframe.copy()
        df["月度"] = pd.to_datetime(
            df["月度"].str.replace("年", "-").str.replace("月", ""),
            format="mixed"
        )
        df = df.dropna().reset_index(drop=True)
        time.sleep(0.5)
        simulated_load = df.head(1000).to_dict("records")
        _ = len(simulated_load)
        time.sleep(0.2)
        pipeline_duration = time.time() - start_pipeline

        overhead_pct = (validation_duration / (validation_duration + pipeline_duration)) * 100
        assert overhead_pct < 20.0, (
            f"Validation overhead {overhead_pct:.1f}% exceeds 20% budget "
            "(simulated pipeline)."
        )
