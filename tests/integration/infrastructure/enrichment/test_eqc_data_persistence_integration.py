"""Integration tests for Story 6.2-P5 EQC persistence + refresh + cleansing.

These tests require a PostgreSQL DATABASE_URL/WDH_TEST_DATABASE_URI.
They do NOT require live EQC connectivity (EQC client is faked).
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from work_data_hub.domain.company_enrichment.models import CompanySearchResult
from work_data_hub.infrastructure.enrichment.data_refresh_service import EqcDataRefreshService


class FakeEqcClient:
    def __init__(self, company_id: str):
        self.company_id = company_id

    def search_company_with_raw(self, name: str):
        result = CompanySearchResult(
            company_id=self.company_id,
            official_name=name,
            unite_code="TEST_UCC",
            match_score=0.9,
        )
        raw_json = {
            "list": [{"companyId": self.company_id, "companyFullName": name}],
            "total": 1,
        }
        return [result], raw_json


@pytest.mark.integration
@pytest.mark.postgres
def test_refresh_updates_base_info_and_cleanses_business_info():
    # Explicit opt-in to avoid accidental runs against non-test databases.
    url = os.environ.get("WDH_TEST_DATABASE_URI")
    if not url or not url.startswith("postgres"):
        pytest.skip("Set WDH_TEST_DATABASE_URI to run postgres-backed integration tests")

    engine = create_engine(url)
    company_id = "CID_TEST_001"
    company_name = "中国平安"

    try:
        conn_ctx = engine.connect()
    except OperationalError:
        pytest.skip("PostgreSQL not reachable or invalid WDH_TEST_DATABASE_URI")

    with conn_ctx as conn:
        # Ensure schema exists (migrations should create it, but keep test robust)
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS enterprise"))

        # Ensure minimal legacy tables/columns exist for this test (idempotent).
        conn.execute(text("CREATE TABLE IF NOT EXISTS enterprise.base_info (company_id VARCHAR(255) PRIMARY KEY)"))
        conn.execute(text('ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS search_key_word VARCHAR(255)'))
        conn.execute(text('ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS "companyFullName" VARCHAR(255)'))
        conn.execute(text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS unite_code VARCHAR(255)"))
        conn.execute(text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS raw_data JSONB"))
        conn.execute(text("ALTER TABLE enterprise.base_info ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ"))

        conn.execute(text("CREATE TABLE IF NOT EXISTS enterprise.business_info (company_id VARCHAR(255) PRIMARY KEY)"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS registered_date TEXT"))
        conn.execute(text('ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS "registerCaptial" TEXT'))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS registered_status TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS legal_person_name TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS address TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS company_name TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS credit_code TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS company_type TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS industry_name TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS business_scope TEXT"))
        conn.execute(text("ALTER TABLE enterprise.business_info ADD COLUMN IF NOT EXISTS _cleansing_status JSONB"))
        conn.commit()

        # Seed base_info row (refresh reads companyFullName)
        conn.execute(
            text("""
                INSERT INTO enterprise.base_info (company_id, "companyFullName", updated_at)
                VALUES (:company_id, :company_full_name, NOW() - INTERVAL '100 days')
                ON CONFLICT (company_id) DO UPDATE
                SET "companyFullName" = EXCLUDED."companyFullName"
            """),
            {"company_id": company_id, "company_full_name": company_name},
        )
        # Seed business_info row (refresh should cleanse it best-effort)
        conn.execute(
            text("""
                INSERT INTO enterprise.business_info (company_id, "registerCaptial", company_name)
                VALUES (:company_id, :cap, :name)
                ON CONFLICT (company_id) DO UPDATE
                SET "registerCaptial" = EXCLUDED."registerCaptial",
                    company_name = EXCLUDED.company_name
            """),
            {"company_id": company_id, "cap": "1,000万元", "name": "「  测试公司  」"},
        )
        conn.commit()

        service = EqcDataRefreshService(conn, eqc_client=FakeEqcClient(company_id))
        result = service.refresh_by_company_ids([company_id], rate_limit=0.0)
        conn.commit()

        assert result.successful == 1
        assert result.failed == 0

        base_row = conn.execute(
            text("""
                SELECT raw_data, updated_at
                FROM enterprise.base_info
                WHERE company_id = :company_id
            """),
            {"company_id": company_id},
        ).fetchone()
        assert base_row is not None
        assert base_row[0] is not None  # raw_data
        assert base_row[1] is not None  # updated_at

        biz_row = conn.execute(
            text("""
                SELECT "registerCaptial", _cleansing_status, company_name
                FROM enterprise.business_info
                WHERE company_id = :company_id
            """),
            {"company_id": company_id},
        ).fetchone()
        assert biz_row is not None
        assert biz_row[1] is not None  # _cleansing_status should be populated
        assert float(biz_row[0]) == 1000 * 10_000.0
        assert biz_row[2] == "测试公司"
