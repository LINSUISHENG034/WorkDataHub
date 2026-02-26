-- ============================================================================
-- Migration Script: Fact Table Refactoring (双表粒度分离)
-- Story: 7.6-16
-- Date: 2026-02-09
-- Purpose: Rename fct_customer_business_monthly_status to
--          "客户业务月度快照" and create "客户计划月度快照"
-- ============================================================================
-- IMPORTANT: This script is for EXISTING databases only.
--            New deployments should use Alembic migrations (009, 013).
-- ============================================================================

BEGIN;

-- ============================================================================
-- Part 1: Rename Table
-- ============================================================================

-- Rename main table (legacy -> canonical)
DO $$
BEGIN
    IF to_regclass('customer.fct_customer_business_monthly_status') IS NOT NULL
       AND to_regclass('customer."客户业务月度快照"') IS NULL THEN
        ALTER TABLE customer.fct_customer_business_monthly_status
            RENAME TO "客户业务月度快照";
    END IF;
END $$;

-- Rename foreign key constraints only when legacy names exist
DO $$
BEGIN
    IF to_regclass('customer."客户业务月度快照"') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM pg_constraint
           WHERE conname = 'fk_snapshot_company'
             AND conrelid = to_regclass('customer."客户业务月度快照"')
       ) THEN
        ALTER TABLE customer."客户业务月度快照"
            RENAME CONSTRAINT fk_snapshot_company TO fk_fct_pl_company;
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('customer."客户业务月度快照"') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM pg_constraint
           WHERE conname = 'fk_snapshot_product_line'
             AND conrelid = to_regclass('customer."客户业务月度快照"')
       ) THEN
        ALTER TABLE customer."客户业务月度快照"
            RENAME CONSTRAINT fk_snapshot_product_line TO fk_fct_pl_product_line;
    END IF;
END $$;

-- ============================================================================
-- Part 2: Rename Indexes
-- ============================================================================

ALTER INDEX IF EXISTS customer.idx_snapshot_month
    RENAME TO idx_fct_pl_snapshot_month;

ALTER INDEX IF EXISTS customer.idx_snapshot_company
    RENAME TO idx_fct_pl_company;

ALTER INDEX IF EXISTS customer.idx_snapshot_product_line
    RENAME TO idx_fct_pl_product_line;

ALTER INDEX IF EXISTS customer.idx_snapshot_month_product
    RENAME TO idx_fct_pl_month_product;

ALTER INDEX IF EXISTS customer.idx_snapshot_month_brin
    RENAME TO idx_fct_pl_month_brin;

ALTER INDEX IF EXISTS customer.idx_snapshot_strategic
    RENAME TO idx_fct_pl_strategic;

-- ============================================================================
-- Part 3: Add customer_name Column (Story 7.6-13 merged)
-- ============================================================================

ALTER TABLE customer."客户业务月度快照"
    ADD COLUMN IF NOT EXISTS customer_name VARCHAR(200);

CREATE INDEX IF NOT EXISTS idx_fct_pl_customer_name
    ON customer."客户业务月度快照"(customer_name);

-- ============================================================================
-- Part 4: Update Trigger Functions
-- ============================================================================

-- Drop old triggers
DROP TRIGGER IF EXISTS update_fct_customer_monthly_status_timestamp
    ON customer."客户业务月度快照";
DROP TRIGGER IF EXISTS update_fct_pl_monthly_timestamp
    ON customer."客户业务月度快照";
DROP TRIGGER IF EXISTS update_fct_pl_monthly_timestamp
    ON customer."客户业务月度快照";

-- Drop old functions
DROP FUNCTION IF EXISTS customer.update_fct_customer_monthly_status_timestamp();
DROP FUNCTION IF EXISTS customer.update_fct_pl_monthly_timestamp();
DROP FUNCTION IF EXISTS customer.update_fct_pl_monthly_timestamp();

-- Create canonical updated_at trigger function
CREATE OR REPLACE FUNCTION customer.update_fct_pl_monthly_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach canonical trigger
CREATE TRIGGER update_fct_pl_monthly_timestamp
    BEFORE UPDATE ON customer."客户业务月度快照"
    FOR EACH ROW
    EXECUTE FUNCTION customer.update_fct_pl_monthly_timestamp();

-- ============================================================================
-- Part 5: Create customer_name Sync Trigger for ProductLine Table
-- ============================================================================

DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
    ON customer."客户明细";
DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
    ON customer."客户明细";
DROP FUNCTION IF EXISTS customer.sync_fct_pl_customer_name();
DROP FUNCTION IF EXISTS customer.sync_fct_pl_customer_name();

CREATE OR REPLACE FUNCTION customer.sync_fct_pl_customer_name()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.客户名称 IS DISTINCT FROM NEW.客户名称 THEN
        UPDATE customer."客户业务月度快照"
        SET customer_name = NEW.客户名称,
            updated_at = CURRENT_TIMESTAMP
        WHERE company_id = NEW.company_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_fct_pl_customer_name
    AFTER UPDATE OF 客户名称 ON customer."客户明细"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_pl_customer_name();

-- ============================================================================
-- Part 6: Create "客户计划月度快照" Table
-- ============================================================================

CREATE TABLE IF NOT EXISTS customer."客户计划月度快照" (
    -- Composite primary key (Granularity: Customer + Plan + ProductLine)
    snapshot_month DATE NOT NULL,
    company_id VARCHAR NOT NULL,
    plan_code VARCHAR NOT NULL,
    product_line_code VARCHAR(20) NOT NULL,

    -- Redundant fields (for query convenience)
    customer_name VARCHAR(200),
    plan_name VARCHAR(200),
    product_line_name VARCHAR(50) NOT NULL,

    -- Status flags (Plan-level)
    is_churned_this_year BOOLEAN DEFAULT FALSE,
    contract_status VARCHAR(50),

    -- Measure (Plan-level)
    aum_balance DECIMAL(20,2) DEFAULT 0,

    -- Audit fields
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Primary key constraint
    PRIMARY KEY (snapshot_month, company_id, plan_code, product_line_code),

    -- Foreign key constraints
    CONSTRAINT fk_fct_plan_company FOREIGN KEY (company_id)
        REFERENCES customer."客户明细"(company_id),
    CONSTRAINT fk_fct_plan_product_line FOREIGN KEY (product_line_code)
        REFERENCES mapping."产品线"(产品线代码)
);

-- ============================================================================
-- Part 7: Create Indexes for Plan Table
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_fct_plan_snapshot_month
    ON customer."客户计划月度快照"(snapshot_month);

CREATE INDEX IF NOT EXISTS idx_fct_plan_company
    ON customer."客户计划月度快照"(company_id);

CREATE INDEX IF NOT EXISTS idx_fct_plan_plan_code
    ON customer."客户计划月度快照"(plan_code);

CREATE INDEX IF NOT EXISTS idx_fct_plan_product_line
    ON customer."客户计划月度快照"(product_line_code);

CREATE INDEX IF NOT EXISTS idx_fct_plan_month_brin
    ON customer."客户计划月度快照"
    USING BRIN (snapshot_month);

CREATE INDEX IF NOT EXISTS idx_fct_plan_churned
    ON customer."客户计划月度快照"(snapshot_month)
    WHERE is_churned_this_year = TRUE;

CREATE INDEX IF NOT EXISTS idx_fct_plan_customer_name
    ON customer."客户计划月度快照"(customer_name);

CREATE INDEX IF NOT EXISTS idx_fct_plan_plan_name
    ON customer."客户计划月度快照"(plan_name);

-- ============================================================================
-- Part 8: Create Triggers for Plan Table
-- ============================================================================

-- updated_at trigger function
DROP TRIGGER IF EXISTS update_fct_plan_monthly_timestamp
    ON customer."客户计划月度快照";
DROP TRIGGER IF EXISTS update_fct_plan_monthly_timestamp
    ON customer."客户计划月度快照";
DROP FUNCTION IF EXISTS customer.update_fct_plan_monthly_timestamp();
DROP FUNCTION IF EXISTS customer.update_fct_plan_monthly_timestamp();

CREATE OR REPLACE FUNCTION customer.update_fct_plan_monthly_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_fct_plan_monthly_timestamp
    BEFORE UPDATE ON customer."客户计划月度快照"
    FOR EACH ROW
    EXECUTE FUNCTION customer.update_fct_plan_monthly_timestamp();

-- ============================================================================
-- Part 9: Create Sync Triggers for Plan Table
-- ============================================================================

-- customer_name sync trigger
DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
    ON customer."客户明细";
DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
    ON customer."客户明细";
DROP FUNCTION IF EXISTS customer.sync_fct_plan_customer_name();
DROP FUNCTION IF EXISTS customer.sync_fct_plan_customer_name();

CREATE OR REPLACE FUNCTION customer.sync_fct_plan_customer_name()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.客户名称 IS DISTINCT FROM NEW.客户名称 THEN
        UPDATE customer."客户计划月度快照"
        SET customer_name = NEW.客户名称,
            updated_at = CURRENT_TIMESTAMP
        WHERE company_id = NEW.company_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_fct_plan_customer_name
    AFTER UPDATE OF 客户名称 ON customer."客户明细"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_plan_customer_name();

-- plan_name sync trigger
DROP TRIGGER IF EXISTS trg_sync_fct_plan_plan_name
    ON mapping."年金计划";
DROP TRIGGER IF EXISTS trg_sync_fct_plan_plan_name
    ON mapping."年金计划";
DROP FUNCTION IF EXISTS customer.sync_fct_plan_plan_name();
DROP FUNCTION IF EXISTS customer.sync_fct_plan_plan_name();

CREATE OR REPLACE FUNCTION customer.sync_fct_plan_plan_name()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.计划全称 IS DISTINCT FROM NEW.计划全称 THEN
        UPDATE customer."客户计划月度快照"
        SET plan_name = NEW.计划全称,
            updated_at = CURRENT_TIMESTAMP
        WHERE plan_code = NEW.年金计划号;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_fct_plan_plan_name
    AFTER UPDATE OF 计划全称 ON mapping."年金计划"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_plan_plan_name();

-- ============================================================================
-- Part 10: Backfill Plan Table from Existing Contract History
-- ============================================================================

INSERT INTO customer."客户计划月度快照" (
    snapshot_month,
    company_id,
    plan_code,
    product_line_code,
    customer_name,
    plan_name,
    product_line_name,
    is_churned_this_year,
    contract_status,
    aum_balance
)
SELECT
    pl.snapshot_month,
    c.company_id,
    c.plan_code,
    c.product_line_code,
    c.customer_name,
    c.plan_name,
    c.product_line_name,

    -- Plan-level churn (matches plan_code)
    EXISTS (
        SELECT 1 FROM customer."流失客户明细" l
        WHERE l.company_id = c.company_id
          AND l.年金计划号 = c.plan_code
          AND EXTRACT(YEAR FROM l.上报月份) = EXTRACT(YEAR FROM pl.snapshot_month)
    ) as is_churned_this_year,

    MAX(c.contract_status) as contract_status,

    -- Plan-level AUM
    COALESCE(SUM(s.期末资产规模), 0) as aum_balance

FROM customer."客户业务月度快照" pl
JOIN customer."客户年金计划" c
  ON c.company_id = pl.company_id
 AND c.product_line_code = pl.product_line_code
 AND c.valid_from <= pl.snapshot_month
 AND c.valid_to >= pl.snapshot_month
LEFT JOIN business.规模明细 s
  ON s.company_id = c.company_id
 AND s.计划代码 = c.plan_code
 AND s.产品线代码 = c.product_line_code
 AND s.月度 = DATE_TRUNC('month', pl.snapshot_month)
GROUP BY
    pl.snapshot_month,
    c.company_id,
    c.plan_code,
    c.product_line_code,
    c.customer_name,
    c.plan_name,
    c.product_line_name
ON CONFLICT (snapshot_month, company_id, plan_code, product_line_code)
DO UPDATE SET
    customer_name = EXCLUDED.customer_name,
    plan_name = EXCLUDED.plan_name,
    product_line_name = EXCLUDED.product_line_name,
    is_churned_this_year = EXCLUDED.is_churned_this_year,
    contract_status = EXCLUDED.contract_status,
    aum_balance = EXCLUDED.aum_balance,
    updated_at = CURRENT_TIMESTAMP;

-- ============================================================================
-- Part 11: Backfill customer_name in ProductLine Table
-- ============================================================================

UPDATE customer."客户业务月度快照" f
SET customer_name = c.客户名称
FROM customer."客户明细" c
WHERE f.company_id = c.company_id
  AND f.customer_name IS NULL;

COMMIT;

-- ============================================================================
-- Verification Queries (Run after migration)
-- ============================================================================
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'customer' AND table_name LIKE 'fct_%';
--
-- SELECT COUNT(*) FROM customer."客户业务月度快照"
-- WHERE customer_name IS NULL;
-- Expected: 0
