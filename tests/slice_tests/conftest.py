"""Shared fixtures for slice tests.

Provides:
- Slice data loading fixtures (per domain)
- On-demand fallback fixture generation (when local slice Excel files are absent)
- Mock CompanyIdResolver (skips DB/EQC, uses YAML + temp ID only)
- Mock PlanCodeEnrichment (in-memory DataFrame)
- pytest marker registration
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "slice_data" / "202510"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"


# ---------------------------------------------------------------------------
# Fallback slice fixture generation
# ---------------------------------------------------------------------------
def _fallback_annuity_df() -> pd.DataFrame:
    """Build deterministic annuity_performance slice rows."""
    return pd.DataFrame(
        [
            {
                "月度": "2025年10月",
                "业务类型": "企年受托",
                "计划类型": "集合计划",
                "机构": "北京",
                "计划号": "P1001",
                "计划名称": "共享客户计划A",
                "组合类型": "受托组合",
                "组合代码": "F001",
                "组合名称": "组合A",
                "客户名称": "共享客户",
                "期初资产规模": 90.0,
                "期末资产规模": 100.0,
                "供款": 10.0,
                "流失(含待遇支付)": 0.0,
                "流失": 0.0,
                "待遇支付": 0.0,
                "投资收益": 1.0,
                "当期收益率": "1.5%",
                "集团企业客户号": "C10001",
                "公司代码": "COMP_SHARED",
                "备注": "keep-for-drop-step",
                "id": 1,
            },
            {
                "月度": "202510",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "机构": "上海",
                "计划号": "P1002",
                "计划名称": "共享客户计划B",
                "组合类型": "投资组合",
                "组合代码": "",
                "组合名称": "组合B",
                "客户名称": "共享客户",
                "期初资产规模": 250.0,
                "期末资产规模": 300.0,
                "供款": 12.0,
                "流失(含待遇支付)": 0.0,
                "流失": 0.0,
                "待遇支付": 0.0,
                "投资收益": 2.0,
                "当期收益率": "2.0%",
                "集团企业客户号": "C10001",
                "公司代码": "COMP_SHARED",
                "备注": "",
                "id": 2,
            },
            {
                "月度": "2025-10",
                "业务类型": "企年受托",
                "计划类型": "集合计划",
                "机构": "(空白)",
                "计划号": "",
                "计划名称": "默认计划-集合",
                "组合类型": "受托组合",
                "组合代码": None,
                "组合名称": "组合C",
                "客户名称": "缺计划集合",
                "期初资产规模": 40.0,
                "期末资产规模": 50.0,
                "供款": 5.0,
                "流失(含待遇支付)": 0.0,
                "流失": 0.0,
                "待遇支付": 0.0,
                "投资收益": 0.5,
                "当期收益率": "1.0%",
                "集团企业客户号": "nan",
                "公司代码": None,
                "备注": "",
                "id": 3,
            },
            {
                "月度": "202510",
                "业务类型": "企年投资",
                "计划类型": "单一计划",
                "机构": "不存在机构",
                "计划号": None,
                "计划名称": "默认计划-单一",
                "组合类型": "投资组合",
                "组合代码": "F009",
                "组合名称": "组合D",
                "客户名称": "缺计划单一",
                "期初资产规模": 55.0,
                "期末资产规模": 60.0,
                "供款": 6.0,
                "流失(含待遇支付)": 0.0,
                "流失": 0.0,
                "待遇支付": 0.0,
                "投资收益": 0.6,
                "当期收益率": "1.2%",
                "集团企业客户号": None,
                "公司代码": None,
                "备注": "",
                "id": 4,
            },
        ]
    )


def _fallback_award_sheets() -> dict[str, pd.DataFrame]:
    """Build deterministic annual_award two-sheet slice rows."""
    trustee = pd.DataFrame(
        [
            {
                "上报月份": "202510",
                "业务类型": "受托",
                "计划类型": "集合",
                "客户全称": "共享客户（中标）",
                "机构": "北京",
                "年金计划号": "",
                "中标日期": "",
                "计划规模": 100.0,
                "受托人": "原受托机构A",
                "company_id": "COMP_SHARED",
                "区域": "华北",
                "年金中心": "中心A",
                "上报人": "测试",
                "insert_sql": "drop-me",
            },
            {
                "上报月份": "202510",
                "业务类型": "投管",
                "计划类型": "单一",
                "客户全称": "共享客户（中标）",
                "机构": "上海",
                "年金计划号": None,
                "中标日期": "2025-10-10",
                "计划规模": 300.0,
                "受托人": "原受托机构B",
                "company_id": "COMP_SHARED",
                "区域": "华东",
                "年金中心": "中心B",
                "上报人": "测试",
                "insert_sql": "drop-me",
            },
        ]
    )
    investee = pd.DataFrame(
        [
            {
                "上报月份": "202510",
                "业务类型": "投资",
                "计划类型": "集合",
                "客户全称": "新客中标",
                "机构": "未知机构",
                "年金计划号": "P9001",
                "中标日期": "2025年10月",
                "计划规模": 50.0,
                "受托人": "原受托机构C",
                "company_id": "",
                "区域": "华南",
                "年金中心": "中心C",
                "上报人": "测试",
                "insert_sql": "drop-me",
            }
        ]
    )
    return {"企年受托中标(空白)": trustee, "企年投资中标(空白)": investee}


def _fallback_loss_sheets() -> dict[str, pd.DataFrame]:
    """Build deterministic annual_loss two-sheet slice rows."""
    trustee = pd.DataFrame(
        [
            {
                "上报月份": "202510",
                "业务类型": "受托",
                "计划类型": "集合",
                "客户全称": "共享客户（流失）",
                "机构": "北京",
                "年金计划号": "",
                "流失日期": "",
                "计划规模": 80.0,
                "受托人": "原受托机构A",
                "company_id": "COMP_SHARED",
                "区域": "华北",
                "年金中心": "中心A",
                "上报人": "测试",
                "考核标签": "drop-me",
            },
            {
                "上报月份": "202510",
                "业务类型": "投资",
                "计划类型": "单一",
                "客户全称": "共享客户（流失）",
                "机构": "上海",
                "年金计划号": None,
                "流失日期": "2025-10-11",
                "计划规模": 280.0,
                "受托人": "原受托机构B",
                "company_id": "COMP_SHARED",
                "区域": "华东",
                "年金中心": "中心B",
                "上报人": "测试",
                "考核标签": "drop-me",
            },
        ]
    )
    investee = pd.DataFrame(
        [
            {
                "上报月份": "202510",
                "业务类型": "投管",
                "计划类型": "集合",
                "客户全称": "新客流失",
                "机构": "未知机构",
                "年金计划号": "P9101",
                "流失日期": "2025年10月",
                "计划规模": 60.0,
                "受托人": "原受托机构C",
                "company_id": "",
                "区域": "华南",
                "年金中心": "中心C",
                "上报人": "测试",
                "考核标签": "drop-me",
            }
        ]
    )
    return {"企年受托流失(解约)": trustee, "企年投资流失(解约)": investee}


def _ensure_excel_file(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    """Create a fallback Excel fixture file only when it does not exist.

    Note: path.exists() + write is a TOCTOU race under pytest-xdist,
    but acceptable for single-process test runs.
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)


def _ensure_slice_fixtures() -> None:
    """Ensure local slice fixture files are available for non-skip test execution."""
    _ensure_excel_file(
        FIXTURE_ROOT / "annuity_performance" / "slice_规模收入数据.xlsx",
        {"规模明细": _fallback_annuity_df()},
    )
    _ensure_excel_file(
        FIXTURE_ROOT / "annual_award" / "slice_中标台账.xlsx",
        _fallback_award_sheets(),
    )
    _ensure_excel_file(
        FIXTURE_ROOT / "annual_loss" / "slice_流失台账.xlsx",
        _fallback_loss_sheets(),
    )


# ---------------------------------------------------------------------------
# pytest markers
# ---------------------------------------------------------------------------
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slice_test: real-data slice verification test")


@pytest.fixture(scope="session", autouse=True)
def _ensure_fixtures():
    """Ensure fallback Excel fixtures exist before any test runs."""
    _ensure_slice_fixtures()


# ---------------------------------------------------------------------------
# Slice data loading fixtures (session-scoped — data is read-only)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def annuity_performance_slice_df() -> pd.DataFrame:
    """Load annuity_performance slice data (sheet '规模明细')."""
    path = FIXTURE_ROOT / "annuity_performance" / "slice_规模收入数据.xlsx"
    return pd.read_excel(path, sheet_name="规模明细", engine="openpyxl")


@pytest.fixture(scope="session")
def annual_award_slice_df() -> pd.DataFrame:
    """Load annual_award slice data (merged from two sheets)."""
    path = FIXTURE_ROOT / "annual_award" / "slice_中标台账.xlsx"
    sheets = ["企年受托中标(空白)", "企年投资中标(空白)"]
    frames = []
    for s in sheets:
        try:
            frames.append(pd.read_excel(path, sheet_name=s, engine="openpyxl"))
        except ValueError:
            pass  # sheet not found
    if not frames:
        pytest.fail("No sheets found in annual_award slice fixture")
    return pd.concat(frames, ignore_index=True)


@pytest.fixture(scope="session")
def annual_loss_slice_df() -> pd.DataFrame:
    """Load annual_loss slice data (merged from two sheets)."""
    path = FIXTURE_ROOT / "annual_loss" / "slice_流失台账.xlsx"
    sheets = ["企年受托流失(解约)", "企年投资流失(解约)"]
    frames = []
    for s in sheets:
        try:
            frames.append(pd.read_excel(path, sheet_name=s, engine="openpyxl"))
        except ValueError:
            pass  # sheet not found
    if not frames:
        pytest.fail("No sheets found in annual_loss slice fixture")
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Mock CompanyIdResolver — YAML overrides + temp ID only, no DB/EQC
# ---------------------------------------------------------------------------
@pytest.fixture
def disabled_eqc_config():
    """EqcLookupConfig with all external lookups disabled."""
    from work_data_hub.infrastructure.enrichment import EqcLookupConfig

    return EqcLookupConfig.disabled()


@pytest.fixture
def mock_company_id_resolver(disabled_eqc_config):
    """CompanyIdResolver that only uses YAML overrides + temp ID generation."""
    from work_data_hub.infrastructure.enrichment import CompanyIdResolver

    return CompanyIdResolver(
        eqc_config=disabled_eqc_config,
        enrichment_service=None,
        yaml_overrides=None,
        mapping_repository=None,
    )


# ---------------------------------------------------------------------------
# Mock PlanCodeEnrichment — in-memory DataFrame instead of DB query
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_plan_code_df() -> pd.DataFrame:
    """In-memory 客户年金计划 table for PlanCodeEnrichment testing."""
    return pd.DataFrame(
        {
            "company_id": ["COMP001", "COMP001", "COMP002", "COMP002"],
            "product_line_code": ["PL202", "PL201", "PL202", "PL201"],
            "plan_code": ["P0100", "S0200", "P0300", "S0400"],
        }
    )


# ---------------------------------------------------------------------------
# PipelineContext factory
# ---------------------------------------------------------------------------
@pytest.fixture
def make_pipeline_context():
    """Factory fixture for creating PipelineContext instances."""
    from datetime import datetime

    from work_data_hub.domain.pipelines.types import PipelineContext

    def _factory(domain: str = "test", **kwargs):
        defaults = {
            "pipeline_name": f"{domain}_bronze_to_silver",
            "execution_id": "slice-test-001",
            "timestamp": datetime(2025, 10, 1),
            "config": {"domain": domain},
            "domain": domain,
        }
        defaults.update(kwargs)
        return PipelineContext(**defaults)

    return _factory
