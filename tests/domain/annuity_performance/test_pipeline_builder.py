from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from work_data_hub.domain.annuity_performance.pipeline_builder import (
    build_bronze_to_silver_pipeline,
)
from work_data_hub.domain.pipelines.types import PipelineContext


def test_pipeline_handles_missing_month_column() -> None:
    pipeline = build_bronze_to_silver_pipeline(
        enrichment_service=None,
        plan_override_mapping={},
        sync_lookup_budget=0,
        mapping_repository=None,
    )

    df = pd.DataFrame(
        {
            "业务类型": ["企业年金受托"],
            "计划类型": ["集合计划"],
            "客户名称": ["测试公司"],
        }
    )
    context = PipelineContext(
        pipeline_name="test_missing_month",
        execution_id="test-missing-month",
        timestamp=datetime.now(timezone.utc),
        config={},
        domain="annuity_performance",
    )

    result = pipeline.execute(df, context)
    assert "月度" in result.columns
    assert result["月度"].isna().all()
