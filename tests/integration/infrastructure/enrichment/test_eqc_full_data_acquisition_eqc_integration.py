"""Live EQC integration test for Story 6.2-P8 full data acquisition.

This test is intentionally opt-in:
- Requires a real EQC token (`WDH_EQC_TOKEN`)
- Requires a PostgreSQL DSN (`WDH_TEST_DATABASE_URI`)
- Requires explicit enable flag (`RUN_EQC_INTEGRATION_TESTS=1`)

It verifies:
1) search + findDepart + findLabels endpoints are callable with the provided token
2) raw responses can be persisted to `enterprise.base_info` (raw_data/raw_business_info/raw_biz_label)
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
)
from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token
from work_data_hub.io.connectors.eqc_client import EQCClient


@pytest.mark.integration
@pytest.mark.postgres
@pytest.mark.eqc_integration
def test_eqc_full_acquisition_persists_raw_responses() -> None:
    if os.environ.get("RUN_EQC_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_EQC_INTEGRATION_TESTS=1 to enable live EQC integration test")

    token = os.environ.get("WDH_EQC_TOKEN")
    if not token:
        pytest.skip("Set WDH_EQC_TOKEN to run live EQC integration test")

    url = os.environ.get("WDH_TEST_DATABASE_URI") or os.environ.get("WDH_DATABASE__URI")
    if not url or not url.startswith("postgres"):
        pytest.skip(
            "Set WDH_TEST_DATABASE_URI (or WDH_DATABASE__URI) to a postgres DSN for this integration test"
        )
    # SQLAlchemy expects the canonical scheme name.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    base_url = os.environ.get("WDH_EQC_BASE_URL") or "https://eqc.pingan.com"
    keyword = os.environ.get("WDH_EQC_TEST_COMPANY_KEYWORD") or "中国平安"

    if not validate_eqc_token(token, base_url):
        pytest.fail(
            "EQC token rejected/expired. Refresh it and re-run:\n"
            "  python -m work_data_hub.cli auth refresh --env-file .wdh_env --timeout 300"
        )

    engine = create_engine(url)
    try:
        conn_ctx = engine.connect()
    except OperationalError:
        parsed = urlparse(url)
        redacted = f"{parsed.scheme}://[REDACTED]@{parsed.hostname}:{parsed.port}{parsed.path}"
        pytest.skip(f"PostgreSQL not reachable: {redacted}")

    with conn_ctx as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS enterprise"))

        # Keep the test robust even if migrations weren't applied (idempotent).
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS enterprise.base_info (
                    company_id VARCHAR(255) PRIMARY KEY
                )
                """
            )
        )
        conn.execute(
            text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS search_key_word VARCHAR(255)")
        )
        conn.execute(
            text('ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS "companyFullName" VARCHAR(255)')
        )
        conn.execute(
            text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS unite_code VARCHAR(255)")
        )
        conn.execute(
            text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS raw_data JSONB")
        )
        conn.execute(
            text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS raw_business_info JSONB")
        )
        conn.execute(
            text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS raw_biz_label JSONB")
        )
        conn.execute(
            text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS api_fetched_at TIMESTAMPTZ")
        )
        conn.execute(
            text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
        )
        conn.commit()

        client = EQCClient(token=token, base_url=base_url)

        results, raw_search = client.search_company_with_raw(keyword)
        assert results, "Expected at least one search result from EQC"

        top = results[0]
        company_id = str(top.company_id).strip()
        assert company_id, "Expected a non-empty company_id from EQC search"

        business_info, raw_business = client.get_business_info_with_raw(company_id)
        assert business_info.company_id, "Expected parsed business_info with company_id"
        assert isinstance(raw_business, dict) and raw_business, "Expected raw business JSON dict"
        assert "businessInfodto" in raw_business, "Expected findDepart raw to contain businessInfodto"

        labels, raw_labels = client.get_label_info_with_raw(company_id)
        assert isinstance(raw_labels, dict) and raw_labels, "Expected raw labels JSON dict"
        assert "labels" in raw_labels, "Expected findLabels raw to contain labels"

        repo = CompanyMappingRepository(conn)
        repo.upsert_base_info(
            company_id=company_id,
            search_key_word=keyword,
            company_full_name=top.official_name or keyword,
            unite_code=getattr(top, "unite_code", None),
            raw_data=raw_search,
            raw_business_info=raw_business,
            raw_biz_label=raw_labels,
        )
        conn.commit()

        row = conn.execute(
            text(
                """
                SELECT raw_data, raw_business_info, raw_biz_label, api_fetched_at
                FROM enterprise.base_info
                WHERE company_id = :company_id
                """
            ),
            {"company_id": company_id},
        ).fetchone()

        assert row is not None
        assert row[0] is not None  # raw_data
        assert row[1] is not None  # raw_business_info
        assert row[2] is not None  # raw_biz_label
        assert row[3] is not None  # api_fetched_at
