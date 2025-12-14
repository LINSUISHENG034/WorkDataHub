"""Unit tests for EqcDataRefreshService (Story 6.2-P5)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from work_data_hub.infrastructure.enrichment.data_refresh_service import EqcDataRefreshService


class DummySettings:
    eqc_token = "token"
    eqc_timeout = 5
    eqc_retry_max = 1
    eqc_base_url = "https://example.invalid"
    eqc_data_refresh_rate_limit = 1.0
    eqc_data_freshness_threshold_days = 90
    eqc_data_refresh_batch_size = 100


@pytest.mark.unit
class TestEqcDataRefreshService:
    def test_get_all_companies_orders_and_limits(self):
        mock_connection = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            SimpleNamespace(
                company_id="A",
                company_full_name="A Co",
                updated_at=None,
                days_since_update=None,
            ),
            SimpleNamespace(
                company_id="B",
                company_full_name="B Co",
                updated_at="2025-12-14T00:00:00+00:00",
                days_since_update=1,
            ),
        ]
        mock_connection.execute.return_value = mock_result

        with patch(
            "work_data_hub.infrastructure.enrichment.data_refresh_service.get_settings",
            return_value=DummySettings(),
        ):
            service = EqcDataRefreshService(mock_connection, eqc_client=MagicMock())
            companies = service.get_all_companies(limit=10)

        assert [c.company_id for c in companies] == ["A", "B"]
        assert companies[0].updated_at is None
        assert companies[1].days_since_update == 1

        call_args = mock_connection.execute.call_args
        sql_text = str(call_args[0][0])
        params = call_args[0][1]
        assert "ORDER BY company_id" in sql_text
        assert params["limit"] == 10

