from unittest.mock import MagicMock, patch

import pandas as pd

from work_data_hub.domain.protocols import ProcessingContext


def _context() -> ProcessingContext:
    return ProcessingContext(
        data_source="test.xlsx",
        session_id="test-session",
        plan_only=True,
        enrichment_service=None,
        eqc_config=None,
        export_unknown_names=True,
    )


def test_annual_award_adapter_always_passes_eqc_config_to_pipeline() -> None:
    from work_data_hub.domain.annual_award.adapter import AnnualAwardService

    service = AnnualAwardService()
    assert service.requires_backfill is True

    pipeline = MagicMock()
    pipeline.execute.return_value = pd.DataFrame()

    with (
        patch(
            "work_data_hub.domain.annual_award.pipeline_builder.build_bronze_to_silver_pipeline",
            return_value=pipeline,
        ) as mock_build,
        patch(
            "work_data_hub.domain.annual_award.helpers.convert_dataframe_to_models",
            return_value=([], 0),
        ),
    ):
        service = AnnualAwardService()
        service.process([{"客户全称": "测试公司"}], _context())

    eqc_config = mock_build.call_args.kwargs["eqc_config"]
    assert eqc_config is not None
    assert eqc_config.enabled is False


def test_annual_loss_adapter_always_passes_eqc_config_to_pipeline() -> None:
    from work_data_hub.domain.annual_loss.adapter import AnnualLossService

    service = AnnualLossService()
    assert service.requires_backfill is True

    pipeline = MagicMock()
    pipeline.execute.return_value = pd.DataFrame()

    with (
        patch(
            "work_data_hub.domain.annual_loss.pipeline_builder.build_bronze_to_silver_pipeline",
            return_value=pipeline,
        ) as mock_build,
        patch(
            "work_data_hub.domain.annual_loss.helpers.convert_dataframe_to_models",
            return_value=([], 0),
        ),
    ):
        service.process([{"客户全称": "测试公司"}], _context())

    eqc_config = mock_build.call_args.kwargs["eqc_config"]
    assert eqc_config is not None
    assert eqc_config.enabled is False
