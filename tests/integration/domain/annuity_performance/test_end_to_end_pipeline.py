"""End-to-end tests for process_annuity_performance (Story 4.5)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pytest

from work_data_hub.domain.annuity_performance.service import (
    PipelineResult,
    process_annuity_performance,
)
from work_data_hub.io.connectors.exceptions import DiscoveryError
from work_data_hub.io.connectors.file_connector import DataDiscoveryResult
from work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    LoadResult,
)


class StubFileDiscoveryService:
    """Minimal FileDiscoveryService replacement for integration tests."""

    def __init__(self, dataframe: pd.DataFrame, *, version: str = "V1") -> None:
        self._dataframe = dataframe
        self.version = version
        self.calls: List[dict[str, str]] = []
        self.file_path = Path("tests/fixtures/excel/annuity_sample.xlsx")

    def discover_and_load(self, domain: str, month: str, **_) -> DataDiscoveryResult:  # type: ignore[override]
        self.calls.append({"domain": domain, "month": month})
        df_copy = self._dataframe.copy(deep=True)
        return DataDiscoveryResult(
            df=df_copy,
            file_path=self.file_path,
            version=self.version,
            sheet_name="规模明细",
            row_count=len(df_copy.index),
            column_count=len(df_copy.columns),
            duration_ms=15,
            columns_renamed={},
            stage_durations={"version_detection": 5, "excel_reading": 10},
        )


@dataclass
class StubWarehouseLoader:
    """Test double implementing the WarehouseLoader interface."""

    results: List[LoadResult]
    fail_call: Optional[int] = None

    def __post_init__(self) -> None:
        self.calls: List[dict[str, object]] = []

    def load_dataframe(  # type: ignore[override]
        self,
        df: pd.DataFrame,
        table: str,
        schema: str = "public",
        upsert_keys: Optional[List[str]] = None,
    ) -> LoadResult:
        call_index = len(self.calls) + 1
        self.calls.append(
            {
                "table": table,
                "schema": schema,
                "upsert_keys": upsert_keys,
                "df": df.copy(deep=True),
            }
        )
        if self.fail_call and call_index == self.fail_call:
            raise DataWarehouseLoaderError("forced failure")
        result_idx = min(call_index - 1, len(self.results) - 1)
        return self.results[result_idx]


def _build_source_dataframe(valid: int = 4, invalid: int = 1) -> pd.DataFrame:
    """Create a deterministic DataFrame resembling normalized Excel rows."""
    rows = []
    for i in range(valid):
        rows.append(
            {
                "年": "2024",
                "月": "11",
                "月度": "202411",
                "计划代码": f"PLAN{i+1:03d}",
                "客户名称": f"公司{i+1}",
                "公司代码": f"COMP{i+1:03d}",
                "期初资产规模": "1000",
                "期末资产规模": "1500",
                "投资收益": "500",
                "年金账户名": f"账户{i+1}",
            }
        )
    for j in range(invalid):
        rows.append(
            {
                "年": "2024",
                "月": "11",
                "月度": None,
                "计划代码": None,  # Missing identifiers -> filtered out
                "客户名称": f"缺失{j}",
                "期初资产规模": "0",
                "期末资产规模": "0",
            }
        )
    return pd.DataFrame(rows)


def _default_loader(result_rows: int) -> StubWarehouseLoader:
    load_result = LoadResult(
        success=True,
        rows_inserted=result_rows,
        rows_updated=0,
        duration_ms=12.5,
        execution_id="exec-001",
    )
    return StubWarehouseLoader(results=[load_result])


@pytest.mark.integration
class TestProcessAnnuityPerformance:
    """Integration-style tests exercising the new orchestration entry point."""

    def test_successful_pipeline_returns_metrics(self):
        df = _build_source_dataframe()
        discovery = StubFileDiscoveryService(df)
        loader = _default_loader(result_rows=4)

        result = process_annuity_performance(
            "202501",
            file_discovery=discovery,
            warehouse_loader=loader,
        )

        assert isinstance(result, PipelineResult)
        assert result.success is True
        assert result.rows_loaded == 4
        assert result.rows_failed == 1  # One intentionally invalid row
        assert result.metrics["discovery"]["row_count"] == len(df.index)
        assert loader.calls[0]["table"] == "annuity_performance_NEW"
        assert loader.calls[0]["upsert_keys"] == ["月度", "计划代码", "company_id"]

    def test_idempotent_re_run_tracks_updates(self):
        df = _build_source_dataframe()
        discovery = StubFileDiscoveryService(df)
        loader = StubWarehouseLoader(
            results=[
                LoadResult(True, 4, 0, 10.0, "exec-first"),
                LoadResult(True, 0, 4, 8.0, "exec-second"),
            ]
        )

        first = process_annuity_performance(
            "202404",
            file_discovery=discovery,
            warehouse_loader=loader,
        )
        second = process_annuity_performance(
            "202404",
            file_discovery=discovery,
            warehouse_loader=loader,
        )

        assert first.rows_loaded == 4
        assert second.rows_loaded == 4  # Updated rows count as loaded
        assert loader.calls[1]["schema"] == "public"
        assert loader.calls[1]["df"].shape[0] == 4

    def test_invalid_month_rejected(self):
        df = _build_source_dataframe()
        discovery = StubFileDiscoveryService(df)
        loader = _default_loader(result_rows=2)

        with pytest.raises(ValueError):
            process_annuity_performance(
                "20251",  # malformed
                file_discovery=discovery,
                warehouse_loader=loader,
                )

    def test_discovery_failure_bubbles_up(self):
        class FailingDiscovery:
            def discover_and_load(self, domain: str, month: str, **_: str) -> DataDiscoveryResult:
                raise DiscoveryError("annuity", "file_matching", RuntimeError("boom"), "boom")

        loader = _default_loader(result_rows=0)

        with pytest.raises(DiscoveryError):
            process_annuity_performance(
                "202501",
                file_discovery=FailingDiscovery(),  # type: ignore[arg-type]
                warehouse_loader=loader,
                )

    def test_loader_failure_propagates(self):
        df = _build_source_dataframe()
        discovery = StubFileDiscoveryService(df)
        loader = StubWarehouseLoader(
            results=[
                LoadResult(True, 0, 0, 0.0, "exec"),
            ],
            fail_call=1,
        )

        with pytest.raises(DataWarehouseLoaderError):
            process_annuity_performance(
                "202501",
                file_discovery=discovery,
                warehouse_loader=loader,
                )
