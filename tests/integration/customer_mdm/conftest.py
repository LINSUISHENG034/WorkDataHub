"""Test fixtures for Customer MDM integration tests.

Story 7.6-10: Integration Testing & Documentation
Story 7.6-11: Customer Status Field Enhancement

Provides deterministic test data and database fixtures for Customer MDM tests.

Fixture hierarchy:
- postgres_db_with_migrations (from tests/conftest.py) → base fixture
- customer_mdm_test_db → extends base with Customer MDM test data
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator
from unittest.mock import patch

import psycopg2
import pytest


@contextmanager
def use_test_database(dsn: str):
    """Context manager to set test DATABASE_URL and prevent load_dotenv override.

    The Customer MDM service functions call load_dotenv(".wdh_env", override=True)
    internally, which would override our test DATABASE_URL. This context manager:
    1. Sets DATABASE_URL environment variable
    2. Patches load_dotenv in all service modules to prevent override

    Args:
        dsn: Database connection string for test database

    Yields:
        None - use within 'with' block
    """
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = dsn

    with (
        patch("work_data_hub.customer_mdm.contract_sync.load_dotenv"),
        patch("work_data_hub.customer_mdm.snapshot_refresh.load_dotenv"),
        patch("work_data_hub.customer_mdm.year_init.load_dotenv"),
    ):
        try:
            yield
        finally:
            if original_url is not None:
                os.environ["DATABASE_URL"] = original_url
            else:
                os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def customer_mdm_test_db(
    postgres_db_with_migrations: str,
) -> Generator[str, None, None]:
    """Extend base fixture with Customer MDM test data.

    Creates deterministic test data in the following tables:
    - customer."客户明细" (customer dimension, appended to seed data)
    - business.规模明细 (source AUM data)
    - customer."中标客户明细" (annual awards)
    - customer."流失客户明细" (annual churn)

    Note: mapping."产品线" already has seed data (PL201-PL204 etc.)
    Note: customer."客户明细" already has seed data, test IDs use TEST_ prefix

    Yields:
        str: DSN for test database with Customer MDM data populated
    """
    conn = psycopg2.connect(postgres_db_with_migrations)
    conn.autocommit = True

    try:
        with conn.cursor() as cur:
            # 1. Create business schema and table for source data
            # Story 7.6-11: Added 供款 and 机构代码 columns
            cur.execute("CREATE SCHEMA IF NOT EXISTS business")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS business."规模明细" (
                    id SERIAL PRIMARY KEY,
                    company_id VARCHAR(32),
                    "计划代码" VARCHAR(20),
                    "产品线代码" VARCHAR(20),
                    "业务类型" VARCHAR(50),
                    "机构代码" VARCHAR(20),
                    "月度" DATE,
                    "期末资产规模" NUMERIC(20, 2) DEFAULT 0,
                    "供款" NUMERIC(20, 2) DEFAULT 0
                )
                """
            )

            # 2. Insert test customers into customer."客户明细"
            # Uses TEST_ prefix to avoid collision with seed data
            cur.execute(
                """
                INSERT INTO customer."客户明细" (
                    company_id, "客户名称", "年金客户类型"
                ) VALUES
                    ('TEST_C001', '测试公司A', '企业年金'),
                    ('TEST_C002', '测试公司B', '职业年金'),
                    ('TEST_C003', '测试公司C', '企业年金'),
                    ('TEST_C004', '测试公司D', '企业年金')
                ON CONFLICT (company_id) DO NOTHING
                """
            )

            # 3. Insert test data into business.规模明细 (source data)
            # Story 7.6-11: Added 供款, 机构代码, and prior year December data
            # Note: 产品线代码 must match seed data in mapping.产品线
            cur.execute(
                """
                INSERT INTO business."规模明细" (
                    company_id, "计划代码", "产品线代码", "业务类型",
                    "机构代码", "月度", "期末资产规模", "供款"
                ) VALUES
                    -- Prior year December data (for is_existing test)
                    ('TEST_C001', 'P001', 'PL202', '企年受托', 'BR01',
                     '2025-12-01', 900000.00, 50000.00),
                    ('TEST_C002', 'P003', 'PL203', '职年投资', 'BR02',
                     '2025-12-01', 1800000.00, 100000.00),
                    -- TEST_C003 has NO prior year data (new customer)
                    -- Current year January data
                    ('TEST_C001', 'P001', 'PL202', '企年受托', 'BR01',
                     '2026-01-01', 1000000.00, 50000.00),
                    ('TEST_C001', 'P002', 'PL201', '企年投资', 'BR01',
                     '2026-01-01', 500000.00, 25000.00),
                    ('TEST_C002', 'P003', 'PL203', '职年投资', 'BR02',
                     '2026-01-01', 2000000.00, 100000.00),
                    -- TEST_C003: Inactive (AUM = 0), no contribution
                    ('TEST_C003', 'P004', 'PL202', '企年受托', 'BR01',
                     '2026-01-01', 0.00, 0.00),
                    -- TEST_C004: Active with contribution
                    ('TEST_C004', 'P005', 'PL202', '企年受托', 'BR01',
                     '2026-01-01', 750000.00, 30000.00),
                    ('TEST_C004', 'P006', 'PL202', '企年受托', 'BR01',
                     '2026-01-01', 250000.00, 0.00)
                """
            )

            # 4. Insert annual award data (中标客户明细)
            # Required NOT NULL columns: 上报月份, 业务类型, 上报客户名称
            cur.execute(
                """
                INSERT INTO customer."中标客户明细" (
                    company_id, "产品线代码", "上报月份",
                    "业务类型", "上报客户名称"
                ) VALUES
                    ('TEST_C001', 'PL202', '2026-01-01',
                     '企年受托', '测试公司A')
                """
            )

            # 5. Insert annual churn data (流失客户明细)
            # Required NOT NULL columns: 上报月份, 业务类型, 上报客户名称
            cur.execute(
                """
                INSERT INTO customer."流失客户明细" (
                    company_id, "产品线代码", "上报月份",
                    "业务类型", "上报客户名称"
                ) VALUES
                    ('TEST_C003', 'PL202', '2026-01-01',
                     '企年受托', '测试公司C')
                """
            )

        yield postgres_db_with_migrations

    finally:
        conn.close()


@pytest.fixture
def test_period() -> str:
    """Provide a deterministic test period.

    Returns:
        str: Test period in YYYYMM format
    """
    return "202601"


@pytest.fixture
def test_snapshot_month() -> str:
    """Provide the expected snapshot month date string.

    Returns:
        str: End-of-month date for test period (2026-01-31)
    """
    return "2026-01-31"
