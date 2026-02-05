"""Seed customer_plan_contract table from business.规模明细 for testing.

This script creates the customer.customer_plan_contract table and populates it
with test data derived from business.规模明细 for the 202510 period.

Usage:
    PYTHONPATH=src uv run scripts/seed_data/seed_customer_plan_contract.py
    python scripts/seed_data/seed_customer_plan_contract.py
"""

import logging

import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "Post.169828",
    "database": "postgres",
}

# Target period for data extraction
TARGET_PERIOD = "2025-10-01"
STATUS_YEAR = 2025

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def execute_sql(conn, sql: str, params=None) -> None:
    """Execute SQL statement."""
    with conn.cursor() as cursor:
        cursor.execute(sql, params or ())
    conn.commit()


def table_exists(conn, table_name: str, schema: str = "customer") -> bool:
    """Check if table exists."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
            """,
            (schema, table_name),
        )
        return cursor.fetchone()[0]


def create_table(conn) -> None:
    """Create customer.customer_plan_contract table."""
    logger.info("Creating customer.customer_plan_contract table...")

    # Create schema if not exists
    execute_sql(conn, "CREATE SCHEMA IF NOT EXISTS customer")

    # Drop table if exists (for clean re-run)
    if table_exists(conn, "customer_plan_contract"):
        logger.info("  Dropping existing table...")
        execute_sql(conn, "DROP TABLE customer.customer_plan_contract CASCADE")

    # Create table
    create_table_sql = """
    CREATE TABLE customer.customer_plan_contract (
        -- Primary key
        contract_id SERIAL PRIMARY KEY,

        -- Business dimension (compound business key)
        company_id VARCHAR NOT NULL,
        plan_code VARCHAR NOT NULL,
        product_line_code VARCHAR(20) NOT NULL,

        -- Redundant fields (for query convenience)
        product_line_name VARCHAR(50) NOT NULL,
        customer_name VARCHAR(200),             -- From customer.年金客户.客户名称
        plan_name VARCHAR(200),                 -- From mapping.年金计划.计划全称

        -- Annual initialization status (updated every January)
        is_strategic BOOLEAN DEFAULT FALSE,
        is_existing BOOLEAN DEFAULT FALSE,
        status_year INTEGER NOT NULL,

        -- Monthly update status
        contract_status VARCHAR(20) NOT NULL,

        -- SCD Type 2 time dimension (end of month)
        valid_from DATE NOT NULL,
        valid_to DATE DEFAULT '9999-12-31',

        -- Audit fields
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

        -- Foreign key constraints (optional, can be disabled for testing)
        CONSTRAINT fk_contract_product_line FOREIGN KEY (product_line_code)
            REFERENCES mapping.产品线(产品线代码),

        -- Compound unique constraint (business key + time)
        CONSTRAINT uq_active_contract UNIQUE (
            company_id, plan_code, product_line_code, valid_to
        )
    );
    """
    execute_sql(conn, create_table_sql)

    # Create indexes
    indexes = [
        """CREATE INDEX idx_contract_company
            ON customer.customer_plan_contract(company_id)""",
        """CREATE INDEX idx_contract_plan
            ON customer.customer_plan_contract(plan_code)""",
        """CREATE INDEX idx_contract_product_line
            ON customer.customer_plan_contract(product_line_code)""",
        """CREATE INDEX idx_contract_strategic
            ON customer.customer_plan_contract(is_strategic)
            WHERE is_strategic = TRUE""",
        """CREATE INDEX idx_contract_status_year
            ON customer.customer_plan_contract(status_year)""",
        """CREATE INDEX idx_active_contracts
            ON customer.customer_plan_contract(
                company_id, plan_code, product_line_code
            ) WHERE valid_to = '9999-12-31'""",
        """CREATE INDEX idx_contract_valid_from_brin
            ON customer.customer_plan_contract USING BRIN (valid_from)""",
        """CREATE INDEX idx_contract_customer_name
            ON customer.customer_plan_contract(customer_name)""",
        """CREATE INDEX idx_contract_plan_name
            ON customer.customer_plan_contract(plan_name)""",
    ]

    for idx_sql in indexes:
        execute_sql(conn, idx_sql)

    # Create trigger for updated_at
    trigger_sql = """
    CREATE OR REPLACE FUNCTION update_contract_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER trg_contract_updated_at
    BEFORE UPDATE ON customer.customer_plan_contract
    FOR EACH ROW EXECUTE FUNCTION update_contract_updated_at();
    """
    execute_sql(conn, trigger_sql)

    logger.info("  Table created successfully")


def seed_data(conn) -> None:
    """Populate table with data from business.规模明细 for 202510."""
    logger.info(f"Seeding data from business.规模明细 for period {TARGET_PERIOD}...")

    # Insert SQL - derive contract records from 规模明细
    insert_sql = """
    INSERT INTO customer.customer_plan_contract (
        company_id,
        plan_code,
        product_line_code,
        product_line_name,
        customer_name,
        plan_name,
        is_strategic,
        is_existing,
        status_year,
        contract_status,
        valid_from,
        valid_to
    )
    SELECT DISTINCT
        s.company_id,
        s.计划代码 as plan_code,
        s.产品线代码 as product_line_code,
        COALESCE(p.产品线, s.业务类型) as product_line_name,
        cust.客户名称 as customer_name,
        plan.计划全称 as plan_name,
        FALSE as is_strategic,  -- Default
        FALSE as is_existing,   -- Default
        %s as status_year,
        CASE
            WHEN s.期末资产规模 > 0 THEN '正常'
            ELSE '停缴'
        END as contract_status,
        (date_trunc('month', %s::date) + interval '1 month - 1 day')::date
            as valid_from,
        '9999-12-31'::date as valid_to
    FROM business.规模明细 s
    LEFT JOIN mapping.产品线 p ON s.产品线代码 = p.产品线代码
    LEFT JOIN customer."年金客户" cust ON s.company_id = cust.company_id
    LEFT JOIN mapping."年金计划" plan ON s.计划代码 = plan.年金计划号
    WHERE s.月度 = %s
      AND s.company_id IS NOT NULL
      AND s.产品线代码 IS NOT NULL
      AND s.计划代码 IS NOT NULL
    ON CONFLICT (company_id, plan_code, product_line_code, valid_to)
    DO NOTHING;
    """

    with conn.cursor() as cursor:
        cursor.execute(insert_sql, (STATUS_YEAR, TARGET_PERIOD, TARGET_PERIOD))
        inserted = cursor.rowcount

    conn.commit()
    logger.info(f"  Inserted {inserted:,} contract records")


def verify_data(conn) -> None:
    """Verify seeded data."""
    logger.info("Verifying seeded data...")

    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        # Total count
        cursor.execute("SELECT COUNT(*) as total FROM customer.customer_plan_contract")
        total = cursor.fetchone()["total"]
        logger.info(f"  Total records: {total:,}")

        # By product line
        cursor.execute("""
            SELECT product_line_code, product_line_name, COUNT(*) as count
            FROM customer.customer_plan_contract
            GROUP BY product_line_code, product_line_name
            ORDER BY count DESC
        """)
        logger.info("  By product line:")
        for row in cursor.fetchall():
            code = row["product_line_code"]
            name = row["product_line_name"]
            count = row["count"]
            logger.info(f"    {code} ({name}): {count:,}")

        # By contract status
        cursor.execute("""
            SELECT contract_status, COUNT(*) as count
            FROM customer.customer_plan_contract
            GROUP BY contract_status
            ORDER BY contract_status
        """)
        logger.info("  By contract status:")
        for row in cursor.fetchall():
            logger.info(f"    {row['contract_status']}: {row['count']:,}")

        # Sample records
        cursor.execute("""
            SELECT cpc.company_id, cpc.plan_code, cpc.product_line_name,
                   cpc.customer_name, cpc.plan_name,
                   cpc.contract_status, cpc.valid_from
            FROM customer.customer_plan_contract cpc
            ORDER BY cpc.contract_id
            LIMIT 5
        """)
        logger.info("  Sample records:")
        for row in cursor.fetchall():
            cid = row["company_id"]
            pcode = row["plan_code"]
            pln = row["product_line_name"]
            cname = row["customer_name"]
            pname = row["plan_name"]
            status = row["contract_status"]
            logger.info(f"    {cid} | {pcode} | {pln} | {cname} | {pname} | {status}")


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Seeding customer_plan_contract table")
    logger.info("=" * 60)

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        # Create table
        create_table(conn)

        # Seed data
        seed_data(conn)

        # Verify
        verify_data(conn)

        logger.info("=" * 60)
        logger.info("Seed completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
