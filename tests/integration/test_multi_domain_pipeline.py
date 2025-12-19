"""Multi-domain integration test for annuity_performance and annuity_income.

Story 5.5.4: Validates that both domains can process data independently
without cross-contamination, and records performance baseline metrics.

Test Coverage:
- AC7: Integration test with real/declared fixture paths + CLI-overridable month
- AC8: Single run covering both domains with output validation (rows/keys)
- AC9: Domain isolation assertions (no cross-pollution)
- AC10: Performance baseline recording (processing_time_ms, memory_mb_peak, etc.)
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

from work_data_hub.domain.annuity_income.service import process_annuity_income
from work_data_hub.domain.annuity_performance.service import process_annuity_performance
from work_data_hub.io.connectors.file_connector import DataDiscoveryResult
from work_data_hub.io.loader.warehouse_loader import LoadResult
from tests.fixtures.test_data_factory import AnnuityTestDataFactory

# Performance monitoring
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# Default test configuration
DEFAULT_MONTH = os.getenv("ANN_TEST_MONTH", "202412")
DEFAULT_FIXTURE_PATH = (
    "tests/fixtures/real_data/202412/收集数据/数据采集/V2/"
    "【for年金分战区经营分析】24年12月年金终稿数据0109采集-补充企年投资收入.xlsx"
)
DEFAULT_SHEET = "收入明细"
PERFORMANCE_BASELINE_PATH = Path("tests/fixtures/performance_baseline.json")


def _safe_platform_string() -> str:
    try:
        return platform.platform()
    except Exception:
        return sys.platform


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single domain processing run."""

    domain: str
    processing_time_ms: float
    memory_mb_peak: float
    rows_processed: int
    throughput_rows_per_sec: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EnvironmentInfo:
    """Environment information for performance baseline."""

    python_version: str = field(default_factory=lambda: sys.version)
    platform: str = field(default_factory=_safe_platform_string)
    cpu_count: int = field(default_factory=lambda: os.cpu_count() or 0)
    pandas_version: str = field(default_factory=lambda: pd.__version__)

    @classmethod
    def capture(cls) -> "EnvironmentInfo":
        """Capture current environment information."""
        info = cls()
        try:
            import pandera

            info.pandera_version = pandera.__version__
        except ImportError:
            info.pandera_version = "unknown"
        try:
            import pydantic

            info.pydantic_version = pydantic.__version__
        except ImportError:
            info.pydantic_version = "unknown"
        return info

    pandera_version: str = "unknown"
    pydantic_version: str = "unknown"


class MockFileDiscovery:
    """Mock file discovery for integration testing."""

    def __init__(self, data: Dict[str, pd.DataFrame]):
        self._data = data

    def discover_and_load(self, *, domain: str, month: str) -> Any:
        """Return mock data for the specified domain."""
        key = f"{domain}_{month}"
        if key not in self._data:
            raise FileNotFoundError(f"No mock data for {domain} month {month}")
        return self._data[key]


class StubDiscoveryService:
    """Stubbed file discovery that returns normalized DataFrames in DataDiscoveryResult."""

    def __init__(
        self,
        dataframe: pd.DataFrame,
        *,
        version: str = "V1",
        sheet: str = DEFAULT_SHEET,
    ) -> None:
        self._df = dataframe
        self.version = version
        self.sheet = sheet
        self.calls: List[dict[str, str]] = []

    def discover_and_load(
        self, domain: str, month: str, **_: str
    ) -> DataDiscoveryResult:  # type: ignore[override]
        self.calls.append({"domain": domain, "month": month})
        df_copy = self._df.copy(deep=True)
        return DataDiscoveryResult(
            df=df_copy,
            file_path=Path(DEFAULT_FIXTURE_PATH),
            version=self.version,
            sheet_name=self.sheet,
            row_count=len(df_copy.index),
            column_count=len(df_copy.columns),
            duration_ms=15,
            columns_renamed={},
            stage_durations={"version_detection": 5, "excel_reading": 10},
        )


class StubWarehouseLoader:
    """Minimal warehouse loader used to capture outputs."""

    def __init__(self) -> None:
        self.calls: List[dict[str, Any]] = []

    def load_dataframe(  # type: ignore[override]
        self,
        df: pd.DataFrame,
        table: str,
        schema: str = "public",
        upsert_keys: Optional[List[str]] = None,
    ) -> LoadResult:
        self.calls.append(
            {
                "table": table,
                "schema": schema,
                "upsert_keys": upsert_keys or [],
                "df": df.copy(deep=True),
            }
        )
        return LoadResult(
            success=True,
            rows_inserted=len(df.index),
            rows_updated=0,
            duration_ms=12.5,
            execution_id=f"exec-{table}",
        )

    def load_with_refresh(  # type: ignore[override]
        self,
        df: pd.DataFrame,
        table: str,
        schema: str = "public",
        refresh_keys: Optional[List[str]] = None,
    ) -> LoadResult:
        # Reuse load_dataframe semantics for refresh mode
        return self.load_dataframe(
            df, table=table, schema=schema, upsert_keys=refresh_keys
        )


def create_mock_annuity_performance_data(
    month: str = DEFAULT_MONTH, rows: int = 1000
) -> pd.DataFrame:
    """Create mock data for annuity_performance domain using factory."""
    factory = AnnuityTestDataFactory()
    df = factory.create_valid_sample(n=rows)
    df["月度"] = int(month)
    # Ensure domain specific columns exist
    if "计划代码" not in df.columns:
        df["计划代码"] = [f"P{i}" for i in range(rows)]

    # Avoid duplicate columns after MappingStep ("机构" -> "机构名称")
    if "机构" in df.columns and "机构名称" in df.columns:
        df = df.drop(columns=["机构名称"])

    return df


def create_mock_annuity_income_data(
    month: str = DEFAULT_MONTH, rows: int = 1000
) -> pd.DataFrame:
    """Create mock data for annuity_income domain using factory."""
    factory = AnnuityTestDataFactory()
    df = factory.create_annuity_income_sample(n=rows, month=month)

    # Avoid duplicate columns that could interfere with MappingStep
    if "机构代码" in df.columns:
        df = df.drop(columns=["机构代码"])

    return df


def measure_performance(
    func: Any, *args: Any, **kwargs: Any
) -> tuple[Any, PerformanceMetrics]:
    """Measure performance of a function call."""
    domain = kwargs.get("domain", "unknown")

    # Get initial memory
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
    else:
        initial_memory = 0.0

    # Time the execution
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()

    # Get peak memory
    if PSUTIL_AVAILABLE:
        peak_memory = process.memory_info().rss / (1024 * 1024)  # MB
    else:
        peak_memory = 0.0

    processing_time_ms = (end_time - start_time) * 1000
    rows_processed = len(result) if hasattr(result, "__len__") else 0
    throughput = (
        rows_processed / (processing_time_ms / 1000) if processing_time_ms > 0 else 0
    )

    metrics = PerformanceMetrics(
        domain=domain,
        processing_time_ms=processing_time_ms,
        memory_mb_peak=max(peak_memory - initial_memory, 0),
        rows_processed=rows_processed,
        throughput_rows_per_sec=throughput,
    )

    return result, metrics


def save_performance_baseline(
    metrics: List[PerformanceMetrics],
    env_info: EnvironmentInfo,
    output_path: Path = PERFORMANCE_BASELINE_PATH,
) -> None:
    """Save performance baseline to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    baseline = {
        "generated_at": datetime.now().isoformat(),
        "environment": {
            "python_version": env_info.python_version,
            "platform": env_info.platform,
            "cpu_count": env_info.cpu_count,
            "pandas_version": env_info.pandas_version,
            "pandera_version": env_info.pandera_version,
            "pydantic_version": env_info.pydantic_version,
        },
        "metrics": [
            {
                "domain": m.domain,
                "processing_time_ms": m.processing_time_ms,
                "memory_mb_peak": m.memory_mb_peak,
                "rows_processed": m.rows_processed,
                "throughput_rows_per_sec": m.throughput_rows_per_sec,
                "timestamp": m.timestamp,
            }
            for m in metrics
        ],
        "regression_threshold_percent": 10,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)


def check_performance_regression(
    current_metrics: List[PerformanceMetrics],
    baseline_path: Path = PERFORMANCE_BASELINE_PATH,
    threshold_percent: float = 10.0,
) -> List[str]:
    """Check for performance regressions against baseline."""
    warnings = []

    if not baseline_path.exists():
        return warnings

    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    baseline_metrics = {m["domain"]: m for m in baseline.get("metrics", [])}

    for current in current_metrics:
        if current.domain not in baseline_metrics:
            continue

        baseline_time = baseline_metrics[current.domain]["processing_time_ms"]
        if baseline_time > 0:
            regression_percent = (
                (current.processing_time_ms - baseline_time) / baseline_time
            ) * 100
            if regression_percent > threshold_percent:
                warnings.append(
                    f"Performance regression in {current.domain}: "
                    f"{regression_percent:.1f}% slower than baseline "
                    f"(current: {current.processing_time_ms:.1f}ms, baseline: {baseline_time:.1f}ms)"
                )

    return warnings


class TestMultiDomainPipeline:
    """Integration tests for multi-domain pipeline processing."""

    @pytest.fixture
    def mock_data(self) -> Dict[str, pd.DataFrame]:
        """Create mock data for both domains."""
        return {
            f"annuity_performance_{DEFAULT_MONTH}": create_mock_annuity_performance_data(
                rows=1000
            ),
            f"annuity_income_{DEFAULT_MONTH}": create_mock_annuity_income_data(
                rows=1000
            ),
        }

    @pytest.fixture
    def file_discovery(self, mock_data: Dict[str, pd.DataFrame]) -> MockFileDiscovery:
        """Create mock file discovery service."""
        return MockFileDiscovery(mock_data)

    @pytest.mark.integration
    def test_end_to_end_services_use_shared_infrastructure(self) -> None:
        """AC7/AC8: Run both domain services end-to-end with stubs and validate outputs."""
        month = DEFAULT_MONTH

        perf_df = create_mock_annuity_performance_data(month, rows=1000)
        income_df = create_mock_annuity_income_data(month, rows=1000)

        perf_discovery = StubDiscoveryService(perf_df, sheet="规模明细")
        income_discovery = StubDiscoveryService(income_df, sheet=DEFAULT_SHEET)
        loader = StubWarehouseLoader()

        perf_result = process_annuity_performance(
            month,
            file_discovery=perf_discovery,
            warehouse_loader=loader,
            export_unknown_names=False,
        )
        income_result = process_annuity_income(
            month,
            file_discovery=income_discovery,
            warehouse_loader=loader,
            export_unknown_names=False,
        )

        # Domain outputs should load rows >0
        assert perf_result.success is True
        assert income_result.success is True
        assert perf_result.rows_loaded > 0
        assert income_result.rows_loaded > 0

        # Loader captured two distinct tables with domain-specific upsert keys
        assert loader.calls[0]["table"] == "annuity_performance_NEW"
        assert loader.calls[0]["upsert_keys"] == ["月度", "业务类型", "计划类型"]
        assert loader.calls[1]["table"] == "annuity_income_NEW"
        assert loader.calls[1]["upsert_keys"] == ["月度", "业务类型", "计划类型"]

        # Column sets remain domain-specific
        perf_columns = set(loader.calls[0]["df"].columns)
        income_columns = set(loader.calls[1]["df"].columns)
        assert "计划代码" in perf_columns
        # annuity_income keeps both plan columns normalized for parity checks
        assert {"计划号", "计划代码"} <= income_columns

    @pytest.mark.integration
    def test_shared_mappings_are_consistent(self) -> None:
        """AC2-4: Verify shared mappings are imported correctly in both domains."""
        from work_data_hub.domain.annuity_income.constants import (
            BUSINESS_TYPE_CODE_MAPPING as AI_MAPPING,
        )
        from work_data_hub.domain.annuity_performance.constants import (
            BUSINESS_TYPE_CODE_MAPPING as AP_MAPPING,
        )
        from work_data_hub.infrastructure.mappings import BUSINESS_TYPE_CODE_MAPPING

        # All three should reference the same object
        assert AI_MAPPING is BUSINESS_TYPE_CODE_MAPPING
        assert AP_MAPPING is BUSINESS_TYPE_CODE_MAPPING

    @pytest.mark.integration
    def test_shared_helpers_are_consistent(self) -> None:
        """AC3-4: Verify shared helpers are imported correctly in both domains."""
        from work_data_hub.domain.annuity_income.helpers import (
            normalize_month as ai_normalize,
        )
        from work_data_hub.domain.annuity_performance.helpers import (
            normalize_month as ap_normalize,
        )
        from work_data_hub.infrastructure.helpers import normalize_month

        # All three should reference the same function
        assert ai_normalize is normalize_month
        assert ap_normalize is normalize_month

        # Verify functionality
        assert normalize_month("202412") == "202412"

    @pytest.mark.integration
    def test_domain_isolation_no_shared_mutable_state(self) -> None:
        """AC9: Verify domains don't share mutable global state."""
        from work_data_hub.domain.annuity_income import constants as ai_constants
        from work_data_hub.domain.annuity_performance import constants as ap_constants

        # Domain-specific constants should be different objects
        assert (
            ai_constants.COLUMN_ALIAS_MAPPING is not ap_constants.COLUMN_ALIAS_MAPPING
        )
        assert (
            ai_constants.LEGACY_COLUMNS_TO_DELETE
            is not ap_constants.LEGACY_COLUMNS_TO_DELETE
        )
        assert (
            ai_constants.DEFAULT_ALLOWED_GOLD_COLUMNS
            is not ap_constants.DEFAULT_ALLOWED_GOLD_COLUMNS
        )

    @pytest.mark.integration
    def test_domain_output_schemas_are_distinct(self) -> None:
        """AC9: Verify domain output schemas don't overlap incorrectly."""
        from work_data_hub.domain.annuity_income.constants import (
            DEFAULT_ALLOWED_GOLD_COLUMNS as AI_COLS,
        )
        from work_data_hub.domain.annuity_performance.constants import (
            DEFAULT_ALLOWED_GOLD_COLUMNS as AP_COLS,
        )

        ai_cols_set = set(AI_COLS)
        ap_cols_set = set(AP_COLS)

        # Some columns should be shared (common fields)
        common_cols = ai_cols_set & ap_cols_set
        assert "月度" in common_cols
        assert "company_id" in common_cols

        # Some columns should be domain-specific
        ai_only = ai_cols_set - ap_cols_set
        ap_only = ap_cols_set - ai_cols_set

        # annuity_income specific
        assert "计划号" in ai_only
        assert {"固费", "浮费", "回补", "税"} <= ai_only

        # annuity_performance specific
        assert "计划代码" in ap_only
        assert "期初资产规模" in ap_only

    @pytest.mark.integration
    def test_normalize_month_validation(self) -> None:
        """Test normalize_month from shared infrastructure."""
        from work_data_hub.infrastructure.helpers import normalize_month

        # Valid cases
        assert normalize_month("202412") == "202412"
        assert normalize_month("  202401  ") == "202401"

        # Invalid cases
        with pytest.raises(ValueError):
            normalize_month("2024")  # Too short

        with pytest.raises(ValueError):
            normalize_month("202413")  # Invalid month

    @pytest.mark.integration
    def test_company_branch_mapping_includes_legacy_overrides(self) -> None:
        """AC2: Verify COMPANY_BRANCH_MAPPING includes legacy overrides."""
        from work_data_hub.infrastructure.mappings import COMPANY_BRANCH_MAPPING

        # Standard mappings
        assert COMPANY_BRANCH_MAPPING["北京"] == "G01"
        assert COMPANY_BRANCH_MAPPING["上海"] == "G02"

        # Legacy overrides (from annuity_income)
        assert COMPANY_BRANCH_MAPPING["内蒙"] == "G31"
        assert COMPANY_BRANCH_MAPPING["战略"] == "G37"
        assert COMPANY_BRANCH_MAPPING["济南"] == "G21"
        assert COMPANY_BRANCH_MAPPING["北分"] == "G37"


class TestPerformanceBaseline:
    """Tests for performance baseline recording (AC10)."""

    @pytest.mark.integration
    def test_performance_metrics_capture(self) -> None:
        """Test that performance metrics can be captured."""

        def sample_operation(domain: str = "test") -> List[int]:
            return list(range(1000))

        result, metrics = measure_performance(sample_operation, domain="test")

        assert len(result) == 1000
        assert metrics.domain == "test"
        assert metrics.processing_time_ms >= 0
        assert metrics.rows_processed == 1000
        assert metrics.throughput_rows_per_sec > 0

    @pytest.mark.integration
    def test_environment_info_capture(self) -> None:
        """Test that environment info can be captured."""
        env_info = EnvironmentInfo.capture()

        assert env_info.python_version is not None
        assert env_info.platform is not None
        assert env_info.cpu_count > 0
        assert env_info.pandas_version is not None

    @pytest.mark.integration
    def test_performance_baseline_save_and_load(self, tmp_path: Path) -> None:
        """Test saving and loading performance baseline."""
        baseline_path = tmp_path / "test_baseline.json"

        metrics = [
            PerformanceMetrics(
                domain="test_domain",
                processing_time_ms=100.0,
                memory_mb_peak=50.0,
                rows_processed=1000,
                throughput_rows_per_sec=10000.0,
            )
        ]
        env_info = EnvironmentInfo.capture()

        save_performance_baseline(metrics, env_info, baseline_path)

        assert baseline_path.exists()

        with open(baseline_path, encoding="utf-8") as f:
            loaded = json.load(f)

        assert "environment" in loaded
        assert "metrics" in loaded
        assert len(loaded["metrics"]) == 1
        assert loaded["metrics"][0]["domain"] == "test_domain"

    @pytest.mark.integration
    def test_performance_regression_detection(self, tmp_path: Path) -> None:
        """Test performance regression detection."""
        baseline_path = tmp_path / "baseline.json"

        # Create baseline
        baseline_metrics = [
            PerformanceMetrics(
                domain="test",
                processing_time_ms=100.0,
                memory_mb_peak=50.0,
                rows_processed=1000,
                throughput_rows_per_sec=10000.0,
            )
        ]
        save_performance_baseline(
            baseline_metrics, EnvironmentInfo.capture(), baseline_path
        )

        # Test with no regression
        current_metrics = [
            PerformanceMetrics(
                domain="test",
                processing_time_ms=105.0,  # 5% slower - within threshold
                memory_mb_peak=50.0,
                rows_processed=1000,
                throughput_rows_per_sec=9523.8,
            )
        ]
        warnings = check_performance_regression(
            current_metrics, baseline_path, threshold_percent=10.0
        )
        assert len(warnings) == 0

        # Test with regression
        regressed_metrics = [
            PerformanceMetrics(
                domain="test",
                processing_time_ms=150.0,  # 50% slower - exceeds threshold
                memory_mb_peak=50.0,
                rows_processed=1000,
                throughput_rows_per_sec=6666.7,
            )
        ]
        warnings = check_performance_regression(
            regressed_metrics, baseline_path, threshold_percent=10.0
        )
        assert len(warnings) == 1
        assert "regression" in warnings[0].lower()

    @pytest.mark.integration
    def test_baseline_file_exists_and_has_expected_structure(self) -> None:
        """AC10: Ensure committed baseline file is present and well-formed."""
        assert PERFORMANCE_BASELINE_PATH.exists(), "performance_baseline.json missing"
        with PERFORMANCE_BASELINE_PATH.open(encoding="utf-8") as f:
            data = json.load(f)

        assert "environment" in data
        assert "metrics" in data
        assert isinstance(data["metrics"], list)
        assert all(
            {"domain", "processing_time_ms", "rows_processed"} <= set(m.keys())
            for m in data["metrics"]
        )


# Parallel execution note (AC9):
# Parallel test execution is N/A for this test suite because:
# 1. The domains share infrastructure modules (mappings, helpers) which are immutable
# 2. No global mutable state is used between domains
# 3. Each test uses isolated mock data
# If pytest-xdist is used, tests can run in parallel safely.
