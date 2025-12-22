"""Unit tests for Dagster schedules (Story 6.7)."""

from datetime import datetime

from dagster import RunRequest
from dagster import build_schedule_context

from src.work_data_hub.orchestration import schedules


class DummySettings:
    def __init__(self, enabled: bool = True, batch_size: int = 50):
        self.async_enrichment_enabled = enabled
        self.enrichment_batch_size = batch_size


def test_async_enrichment_schedule_disabled(monkeypatch):
    """Schedule should skip when feature flag is off (AC9)."""

    monkeypatch.setattr(schedules, "get_settings", lambda: DummySettings(enabled=False))

    ctx = build_schedule_context(scheduled_execution_time=None)
    result = schedules.async_enrichment_schedule(ctx)

    assert result is None


def test_async_enrichment_schedule_builds_run_request(monkeypatch):
    """Schedule should emit RunRequest with configured batch size and run key."""

    monkeypatch.setattr(
        schedules, "get_settings", lambda: DummySettings(enabled=True, batch_size=123)
    )

    scheduled_time = datetime(2025, 1, 1, 12, 0, 0)
    ctx = build_schedule_context(scheduled_execution_time=scheduled_time)

    result = schedules.async_enrichment_schedule(ctx)

    assert isinstance(result, RunRequest)
    assert "async_enrichment_" in result.run_key
    assert str(scheduled_time.isoformat()) in result.run_key

    run_config = result.run_config["ops"]["process_company_lookup_queue_op"]["config"]
    assert run_config["batch_size"] == 123
    assert run_config["plan_only"] is False
