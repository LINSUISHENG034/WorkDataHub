"""Unit tests for Dagster sensors (Story 6.7)."""

import sys
from types import SimpleNamespace

from dagster import RunRequest, SkipReason
from dagster import build_sensor_context

from src.work_data_hub.orchestration import sensors


class DummySettings:
    def __init__(self, enabled: bool, threshold: int = 10, batch_size: int = 99):
        self.enrichment_sensor_enabled = enabled
        self.enrichment_queue_threshold = threshold
        self.enrichment_batch_size = batch_size

    def get_database_connection_string(self) -> str:  # pragma: no cover - trivial
        return "postgresql://dummy"


class DummyConn:
    def cursor(self):  # pragma: no cover - context manager protocol
        return self

    def __enter__(self):  # pragma: no cover - context manager protocol
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - context manager
        return False

    def close(self):  # pragma: no cover - context manager
        return None


def test_enrichment_queue_sensor_disabled(monkeypatch):
    """Sensor should SkipReason when feature flag is off (AC5)."""

    monkeypatch.setattr(sensors, "get_settings", lambda: DummySettings(enabled=False))

    ctx = build_sensor_context()
    result = sensors.enrichment_queue_sensor(ctx)

    assert isinstance(result, SkipReason)
    assert "disabled" in result.skip_message.lower()


def test_enrichment_queue_sensor_triggers_when_threshold_exceeded(monkeypatch):
    """Sensor should trigger RunRequest using ready-only queue depth count."""

    dummy_settings = DummySettings(enabled=True, threshold=5, batch_size=77)
    monkeypatch.setattr(sensors, "get_settings", lambda: dummy_settings)

    # Stub psycopg2.connect
    class FakePsycopg2:
        @staticmethod
        def connect(_):  # pragma: no cover - trivial
            return DummyConn()

    # Ensure import psycopg2 inside sensor resolves to fake module
    sys.modules["psycopg2"] = FakePsycopg2

    # Capture ready_only usage
    class FakeQueue:
        last_ready_only = None

        def __init__(self, conn, plan_only=False):  # pragma: no cover - trivial
            self.conn = conn
            self.plan_only = plan_only

        def get_queue_depth(self, status="pending", ready_only=False):
            FakeQueue.last_ready_only = ready_only
            return 10  # Above threshold to trigger run

    monkeypatch.setattr(
        "work_data_hub.domain.company_enrichment.lookup_queue.LookupQueue",
        FakeQueue,
        raising=False,
    )

    ctx = build_sensor_context()
    result = sensors.enrichment_queue_sensor(ctx)

    assert isinstance(result, RunRequest)
    # Ensure we only counted entries whose backoff has elapsed
    assert FakeQueue.last_ready_only is True

    run_config = result.run_config["ops"]["process_company_lookup_queue_op"]["config"]
    assert run_config["batch_size"] == 77
    assert run_config["plan_only"] is False
