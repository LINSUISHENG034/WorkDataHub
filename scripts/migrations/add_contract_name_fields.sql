-- Add customer_name and plan_name fields to customer."客户年金计划"
-- Story 7.6-13: Name Fields Enhancement
-- Date: 2026-02-05
--
-- Usage:
--   psql -h localhost -U postgres -d postgres -f scripts/migrations/add_contract_name_fields.sql

BEGIN;

-- 1. Add new columns
ALTER TABLE customer."客户年金计划"
    ADD COLUMN IF NOT EXISTS customer_name VARCHAR(200),
    ADD COLUMN IF NOT EXISTS plan_name VARCHAR(200);

-- 2. Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_contract_customer_name
    ON customer."客户年金计划"(customer_name);

CREATE INDEX IF NOT EXISTS idx_contract_plan_name
    ON customer."客户年金计划"(plan_name);

-- 3. Backfill existing data
UPDATE customer."客户年金计划" cpc
SET customer_name = c.客户名称
FROM customer."客户明细" c
WHERE cpc.company_id = c.company_id
  AND cpc.customer_name IS NULL;

UPDATE customer."客户年金计划" cpc
SET plan_name = p.计划全称
FROM mapping."年金计划" p
WHERE cpc.plan_code = p.年金计划号
  AND cpc.plan_name IS NULL;

-- 4. Create sync trigger for customer name changes
CREATE OR REPLACE FUNCTION customer.sync_contract_customer_name()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.客户名称 IS DISTINCT FROM NEW.客户名称 THEN
        UPDATE customer."客户年金计划"
        SET customer_name = NEW.客户名称,
            updated_at = CURRENT_TIMESTAMP
        WHERE company_id = NEW.company_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_contract_customer_name
    ON customer."客户明细";
DROP TRIGGER IF EXISTS trg_sync_contract_customer_name
    ON customer."客户明细";

CREATE TRIGGER trg_sync_contract_customer_name
    AFTER UPDATE OF 客户名称 ON customer."客户明细"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_contract_customer_name();

-- 5. Create sync trigger for plan name changes
CREATE OR REPLACE FUNCTION customer.sync_contract_plan_name()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.计划全称 IS DISTINCT FROM NEW.计划全称 THEN
        UPDATE customer."客户年金计划"
        SET plan_name = NEW.计划全称,
            updated_at = CURRENT_TIMESTAMP
        WHERE plan_code = NEW.年金计划号;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_contract_plan_name
    ON mapping."年金计划";
DROP TRIGGER IF EXISTS trg_sync_contract_plan_name
    ON mapping."年金计划";

CREATE TRIGGER trg_sync_contract_plan_name
    AFTER UPDATE OF 计划全称 ON mapping."年金计划"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_contract_plan_name();

COMMIT;

-- Verify results
SELECT
    'Total records' as metric,
    COUNT(*)::text as value
FROM customer."客户年金计划"
UNION ALL
SELECT
    'Records with customer_name',
    COUNT(*)::text
FROM customer."客户年金计划"
WHERE customer_name IS NOT NULL
UNION ALL
SELECT
    'Records with plan_name',
    COUNT(*)::text
FROM customer."客户年金计划"
WHERE plan_name IS NOT NULL;
