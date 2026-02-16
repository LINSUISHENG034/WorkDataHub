-- ============================================================
-- Story 7.6-19: 年金关联公司表重命名回滚脚本
-- Rollback: customer."年金关联公司" → customer."年金客户"
-- Date: 2026-02-15
--
-- Purpose: Rollback the table rename if needed.
-- WARNING: This will reverse the rename migration.
-- ============================================================

BEGIN;

-- Step 1: Drop backward compatibility views
DROP VIEW IF EXISTS customer."年金客户";
DROP VIEW IF EXISTS mapping."年金客户";

-- Step 2: Drop triggers on renamed table
DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
    ON customer."年金关联公司";
DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
    ON customer."年金关联公司";

-- Step 3: Drop FK constraints
ALTER TABLE customer.customer_plan_contract
    DROP CONSTRAINT IF EXISTS fk_contract_company;
ALTER TABLE customer.fct_customer_plan_monthly
    DROP CONSTRAINT IF EXISTS fk_fct_plan_company;
ALTER TABLE customer.fct_customer_product_line_monthly
    DROP CONSTRAINT IF EXISTS fk_snapshot_company;

-- Step 4: Rename back
ALTER TABLE customer."年金关联公司" RENAME TO "年金客户";

-- Step 5: Recreate FK constraints pointing to original name
ALTER TABLE customer.customer_plan_contract
    ADD CONSTRAINT fk_contract_company
    FOREIGN KEY (company_id) REFERENCES customer."年金客户"(company_id);
ALTER TABLE customer.fct_customer_plan_monthly
    ADD CONSTRAINT fk_fct_plan_company
    FOREIGN KEY (company_id) REFERENCES customer."年金客户"(company_id);
ALTER TABLE customer.fct_customer_product_line_monthly
    ADD CONSTRAINT fk_snapshot_company
    FOREIGN KEY (company_id) REFERENCES customer."年金客户"(company_id);

-- Step 6: Recreate triggers on original table name
CREATE TRIGGER trg_sync_fct_pl_customer_name
    AFTER UPDATE OF 客户名称 ON customer."年金客户"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_pl_customer_name();

CREATE TRIGGER trg_sync_fct_plan_customer_name
    AFTER UPDATE OF 客户名称 ON customer."年金客户"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_plan_customer_name();

-- Step 7: Recreate mapping compatibility view (from original schema migration)
CREATE OR REPLACE VIEW mapping."年金客户" AS
SELECT * FROM customer."年金客户";

COMMIT;

-- 验证回滚
SELECT schemaname, tablename FROM pg_tables WHERE tablename = '年金客户';
