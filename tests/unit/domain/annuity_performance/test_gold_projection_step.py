import logging
from typing import List

import pandas as pd
import pytest
from pandera.errors import SchemaError

from work_data_hub.domain.annuity_performance.constants import (
    DEFAULT_ALLOWED_GOLD_COLUMNS,
)
from work_data_hub.domain.annuity_performance.pipeline_steps import (
    GoldProjectionStep,
)
from work_data_hub.domain.annuity_performance.schemas import GoldAnnuitySchema
from work_data_hub.domain.pipelines.types import PipelineContext

GOLD_SCHEMA_COLUMNS = list(GoldAnnuitySchema.columns.keys())


def _build_context() -> PipelineContext:
    return PipelineContext(
        pipeline_name="test",
        execution_id="exec",
        timestamp=pd.Timestamp.utcnow(),
        config={},
        metadata={},
    )


def _build_gold_df(extra_columns: List[str] | None = None) -> pd.DataFrame:
    base_row = {
        "月度": pd.Timestamp("2025-01-01"),
        "业务类型": "企业年金",
        "计划类型": "单一计划",
        "计划代码": "PLAN001",
        "计划名称": "测试计划",
        "组合类型": "稳健型",
        "组合代码": "COMBO001",
        "组合名称": "稳健组合",
        "company_id": "COMP001",
        "客户名称": "公司A",
        "期初资产规模": 1000.0,
        "期末资产规模": 2000.0,
        "投资收益": 500.0,
        "供款": 100.0,
        "流失_含待遇支付": 0.0,
        "流失": 0.0,
        "待遇支付": 0.0,
        "年化收益率": 0.05,
        "机构代码": "G00",
        "机构名称": "总部",
        "产品线代码": "PROD001",
        "年金账户号": "ACC001",
        "年金账户名": "公司A年金账户",
    }
    if extra_columns:
        for column in extra_columns:
            base_row[column] = f"extra-{column}"
    return pd.DataFrame([base_row])


@pytest.mark.unit
class TestGoldProjectionStep:
    def test_projection_filters_to_allowed_columns(self):
        allowed = GOLD_SCHEMA_COLUMNS
        step = GoldProjectionStep(allowed_columns_provider=lambda: allowed)
        df = _build_gold_df(extra_columns=["temp_field"])
        result = step.execute(df, _build_context())

        assert list(result.columns) == allowed

    def test_removed_columns_logged(self, caplog: pytest.LogCaptureFixture):
        allowed = GOLD_SCHEMA_COLUMNS
        step = GoldProjectionStep(allowed_columns_provider=lambda: allowed)
        df = _build_gold_df(extra_columns=["intermediate_calc"])

        with caplog.at_level(logging.INFO):
            step.execute(df, _build_context())

        assert any(
            "gold_projection.removed_columns" in record.message
            for record in caplog.records
        )

    def test_provider_called_once(self):
        calls = {"count": 0}

        def provider() -> List[str]:
            calls["count"] += 1
            return GOLD_SCHEMA_COLUMNS

        step = GoldProjectionStep(allowed_columns_provider=provider)
        df = _build_gold_df(extra_columns=["tmp"])
        context = _build_context()

        step.execute(df, context)
        step.execute(df, context)

        assert calls["count"] == 1

    def test_schema_validation_applied(self):
        allowed = GOLD_SCHEMA_COLUMNS
        step = GoldProjectionStep(allowed_columns_provider=lambda: allowed)
        df = _build_gold_df()
        df.loc[0, "期末资产规模"] = -1.0

        with pytest.raises(SchemaError):
            step.execute(df, _build_context())

    def test_legacy_columns_removed(self):
        allowed = GOLD_SCHEMA_COLUMNS
        step = GoldProjectionStep(allowed_columns_provider=lambda: allowed)
        df = _build_gold_df(
            extra_columns=[
                "备注",
                "子企业号",
                "集团企业客户号",
            ]
        )

        result = step.execute(df, _build_context())

        assert "备注" not in result.columns
        assert "子企业号" not in result.columns
        assert "集团企业客户号" not in result.columns

    def test_metadata_written_to_context(self):
        allowed = GOLD_SCHEMA_COLUMNS
        step = GoldProjectionStep(allowed_columns_provider=lambda: allowed)
        df = _build_gold_df(extra_columns=["intermediate_calc"])
        context = _build_context()

        step.execute(df, context)

        assert "gold_projection" in context.metadata
        removed = context.metadata["gold_projection"]["removed_columns"]
        assert "intermediate_calc" in removed
        assert "gold_schema_validation" in context.metadata
        assert context.metadata["gold_schema_validation"]["row_count"] == 1

    def test_default_allowed_columns_fallback(self):
        step = GoldProjectionStep()
        df = _build_gold_df()
        result = step.execute(df, _build_context())
        assert not result.empty

    def test_creates_annualized_return_from_current_rate(self):
        allowed = GOLD_SCHEMA_COLUMNS
        step = GoldProjectionStep(allowed_columns_provider=lambda: allowed)
        df = _build_gold_df()

        result = step.execute(df, _build_context())

        assert "年化收益率" in result.columns
        assert pytest.approx(result["年化收益率"].iloc[0]) == 0.05
