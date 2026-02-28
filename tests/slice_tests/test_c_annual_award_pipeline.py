"""Phase C: annual_award Bronze→Silver pipeline tests (domain-specific only).

Covers steps unique to annual_award:
- C-1: ColumnMapping (annual_award COLUMN_MAPPING)
- C-6: AwardDateParsing (中标日期)
- C-8: CustomerNameCleansing
- C-9: CleansingStep (domain="annual_award")
- C-11: PlanCodeEnrichment (annual_award pipeline_builder)
- C-13: DropColumns (insert_sql via annual_award COLUMNS_TO_DROP)

Shared steps (2,3,4,5,7,10,12) are in test_cd_shared_pipeline.py.
"""

from __future__ import annotations

import pandas as pd
import pytest

from work_data_hub.domain.annual_award.constants import COLUMN_MAPPING, COLUMNS_TO_DROP
from work_data_hub.domain.annual_award.pipeline_builder import PlanCodeEnrichmentStep
from work_data_hub.infrastructure.cleansing import normalize_customer_name
from work_data_hub.infrastructure.transforms import CleansingStep, DropStep, MappingStep
from work_data_hub.utils.date_parser import parse_chinese_date

pytestmark = pytest.mark.slice_test


# ===================================================================
# C-1: Column name standardization
# ===================================================================
class TestC1ColumnMapping:
    """客户全称→上报客户名称, 受托人→原受托人, 机构→机构名称."""

    def test_mapping_renames(self, annual_award_slice_df, make_pipeline_context):
        step = MappingStep(COLUMN_MAPPING)
        result = step.apply(
            annual_award_slice_df, make_pipeline_context("annual_award")
        )
        for old, new in COLUMN_MAPPING.items():
            if old in annual_award_slice_df.columns:
                assert old not in result.columns
                assert new in result.columns


# ===================================================================
# C-6: 中标日期 parsing (blank/space→None)
# ===================================================================
class TestC6AwardDateParsing:
    """Parse 中标日期, blank/space values→None."""

    def test_blank_date_returns_none(self):
        assert parse_chinese_date("") is None
        assert parse_chinese_date("   ") is None
        assert parse_chinese_date(None) is None

    def test_valid_date_parses(self):
        result = parse_chinese_date("2025-03-15")
        assert result is not None


# ===================================================================
# C-8: Customer name cleansing (上报客户名称→客户名称)
# ===================================================================
class TestC8CustomerNameCleansing:
    """normalize_customer_name applied to 上报客户名称."""

    def test_normalize_strips_and_cleans(self):
        result = normalize_customer_name("  测试公司（北京）  ")
        assert result is not None
        assert "测试" in result

    def test_non_string_returns_empty_or_none(self):
        result_none = normalize_customer_name(None)
        result_empty = normalize_customer_name("")
        assert not result_none
        assert not result_empty


# ===================================================================
# C-9: Domain cleansing rules (CleansingStep domain="annual_award")
# ===================================================================
class TestC9CleansingStep:
    """CleansingStep with domain='annual_award'."""

    def test_cleansing_runs(self, annual_award_slice_df, make_pipeline_context):
        step = CleansingStep(domain="annual_award")
        result = step.apply(
            annual_award_slice_df.copy(), make_pipeline_context("annual_award")
        )
        assert len(result) == len(annual_award_slice_df)


# ===================================================================
# C-11: Plan code enrichment (mock in-memory)
# ===================================================================
class TestC11PlanCodeEnrichment:
    """PlanCodeEnrichmentStep P/S prefix selection logic."""

    def test_collective_prefers_p_prefix(self):
        step = PlanCodeEnrichmentStep(db_connection=None)
        result = step._select_plan_code(["S0100", "P0200", "X0300"], "集合计划")
        assert result == "P0200"

    def test_single_prefers_s_prefix(self):
        step = PlanCodeEnrichmentStep(db_connection=None)
        result = step._select_plan_code(["P0100", "S0200", "X0300"], "单一计划")
        assert result == "S0200"


# ===================================================================
# C-13: Drop excluded columns
# ===================================================================
class TestC13DropColumns:
    """Drop 区域, 年金中心, 上报人, insert_sql, etc."""

    def test_drop_step(self, make_pipeline_context):
        cols = {c: ["val"] for c in COLUMNS_TO_DROP}
        cols["月度"] = ["202510"]
        df = pd.DataFrame(cols)
        step = DropStep(list(COLUMNS_TO_DROP))
        result = step.apply(df, make_pipeline_context("annual_award"))
        for c in COLUMNS_TO_DROP:
            assert c not in result.columns
        assert "月度" in result.columns
