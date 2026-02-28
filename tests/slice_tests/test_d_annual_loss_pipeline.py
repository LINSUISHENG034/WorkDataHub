"""Phase D: annual_loss Bronze→Silver pipeline tests (domain-specific only).

Covers steps unique to annual_loss:
- D-1: ColumnMapping (annual_loss COLUMN_MAPPING)
- D-6: LossDateParsing (流失日期)
- D-8: CustomerNameCleansing
- D-9: CleansingStep (domain="annual_loss")
- D-11: PlanCodeEnrichment (annual_loss pipeline_builder)
- D-13: DropColumns (考核标签 via annual_loss COLUMNS_TO_DROP)

Shared steps (2,3,4,5,7,10,12) are in test_cd_shared_pipeline.py.
"""

from __future__ import annotations

import pandas as pd
import pytest

from work_data_hub.domain.annual_loss.constants import COLUMN_MAPPING, COLUMNS_TO_DROP
from work_data_hub.domain.annual_loss.pipeline_builder import PlanCodeEnrichmentStep
from work_data_hub.infrastructure.cleansing import normalize_customer_name
from work_data_hub.infrastructure.transforms import CleansingStep, DropStep, MappingStep
from work_data_hub.utils.date_parser import parse_chinese_date

pytestmark = pytest.mark.slice_test


# ===================================================================
# D-1: Column name standardization
# ===================================================================
class TestD1ColumnMapping:
    def test_mapping_renames(self, annual_loss_slice_df, make_pipeline_context):
        step = MappingStep(COLUMN_MAPPING)
        result = step.apply(annual_loss_slice_df, make_pipeline_context("annual_loss"))
        for old, new in COLUMN_MAPPING.items():
            if old in annual_loss_slice_df.columns:
                assert old not in result.columns
                assert new in result.columns


# ===================================================================
# D-6: 流失日期 parsing (KEY DIFFERENCE: 流失日期 not 中标日期)
# ===================================================================
class TestD6LossDateParsing:
    """Parse 流失日期, blank→None."""

    def test_blank_loss_date(self):
        assert parse_chinese_date("") is None
        assert parse_chinese_date(None) is None

    def test_valid_loss_date(self):
        assert parse_chinese_date("2025-06-30") is not None


# ===================================================================
# D-8: Customer name cleansing
# ===================================================================
class TestD8CustomerNameCleansing:
    def test_normalize(self):
        result = normalize_customer_name("  测试公司  ")
        assert result is not None


# ===================================================================
# D-9: Domain cleansing rules (domain="annual_loss")
# ===================================================================
class TestD9CleansingStep:
    def test_cleansing_runs(self, annual_loss_slice_df, make_pipeline_context):
        step = CleansingStep(domain="annual_loss")
        result = step.apply(
            annual_loss_slice_df.copy(), make_pipeline_context("annual_loss")
        )
        assert len(result) == len(annual_loss_slice_df)


# ===================================================================
# D-11: Plan code enrichment (annual_loss pipeline_builder)
# ===================================================================
class TestD11PlanCodeEnrichment:
    def test_p_prefix_for_collective(self):
        step = PlanCodeEnrichmentStep(db_connection=None)
        result = step._select_plan_code(["S01", "P02"], "集合计划")
        assert result == "P02"


# ===================================================================
# D-13: Drop excluded columns (考核标签 via annual_loss COLUMNS_TO_DROP)
# ===================================================================
class TestD13DropColumns:
    def test_drop_step(self, make_pipeline_context):
        cols = {c: ["val"] for c in COLUMNS_TO_DROP}
        cols["月度"] = ["202510"]
        df = pd.DataFrame(cols)
        step = DropStep(list(COLUMNS_TO_DROP))
        result = step.apply(df, make_pipeline_context("annual_loss"))
        for c in COLUMNS_TO_DROP:
            assert c not in result.columns
        assert "月度" in result.columns
