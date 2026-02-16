-- ============================================================
-- Story 7.6-19: 年金客户表重命名迁移脚本
-- Rename: customer."年金客户" → customer."年金关联公司"
-- Date: 2026-02-15
--
-- Purpose: Rename for semantic clarity - the table contains
--          companies associated with annuity business, not customers.
-- ============================================================

-- 预检查：记录迁移前行数
DO $$
DECLARE
    row_count_before INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count_before FROM customer."年金客户";
    RAISE NOTICE '迁移前行数: %', row_count_before;
END $$;

BEGIN;

-- ============================================================
-- Step 1: Drop existing triggers on the table
-- ============================================================
-- These triggers reference customer."年金客户" and must be
-- dropped before rename, then recreated on the new table name.

DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
    ON customer."年金客户";

DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
    ON customer."年金客户";

-- ============================================================
-- Step 2: Drop FK constraints referencing the table
-- ============================================================

ALTER TABLE customer.customer_plan_contract
    DROP CONSTRAINT IF EXISTS fk_contract_company;

ALTER TABLE customer.fct_customer_plan_monthly
    DROP CONSTRAINT IF EXISTS fk_fct_plan_company;

ALTER TABLE customer.fct_customer_product_line_monthly
    DROP CONSTRAINT IF EXISTS fk_snapshot_company;

-- ============================================================
-- Step 3: Drop existing backward compatibility views
-- ============================================================
-- mapping."年金客户" view was created during schema migration
-- (mapping → customer). It must be dropped before rename
-- because the view references the old table name.

DROP VIEW IF EXISTS mapping."年金客户";

-- ============================================================
-- Step 4: Rename table
-- ============================================================

ALTER TABLE customer."年金客户" RENAME TO "年金关联公司";

-- ============================================================
-- Step 5: Recreate FK constraints pointing to new table name
-- ============================================================

ALTER TABLE customer.customer_plan_contract
    ADD CONSTRAINT fk_contract_company
    FOREIGN KEY (company_id) REFERENCES customer."年金关联公司"(company_id);

ALTER TABLE customer.fct_customer_plan_monthly
    ADD CONSTRAINT fk_fct_plan_company
    FOREIGN KEY (company_id) REFERENCES customer."年金关联公司"(company_id);

ALTER TABLE customer.fct_customer_product_line_monthly
    ADD CONSTRAINT fk_snapshot_company
    FOREIGN KEY (company_id) REFERENCES customer."年金关联公司"(company_id);

-- ============================================================
-- Step 6: Recreate triggers on renamed table
-- ============================================================

CREATE TRIGGER trg_sync_fct_pl_customer_name
    AFTER UPDATE OF 客户名称 ON customer."年金关联公司"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_pl_customer_name();

CREATE TRIGGER trg_sync_fct_plan_customer_name
    AFTER UPDATE OF 客户名称 ON customer."年金关联公司"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_plan_customer_name();

-- ============================================================
-- Step 7: Create backward compatibility views
-- ============================================================

CREATE OR REPLACE VIEW customer."年金客户" AS
SELECT * FROM customer."年金关联公司";

CREATE OR REPLACE VIEW mapping."年金客户" AS
SELECT * FROM customer."年金关联公司";

COMMIT;

-- ============================================================
-- 后检查：验证迁移结果
-- ============================================================
DO $$
DECLARE
    row_count_after INTEGER;
    table_schema_result TEXT;
BEGIN
    -- 验证表位置
    SELECT schemaname INTO table_schema_result
    FROM pg_tables WHERE tablename = '年金关联公司' AND schemaname = 'customer';

    IF table_schema_result IS NULL THEN
        RAISE EXCEPTION '迁移失败: 表 年金关联公司 未在 customer schema 中找到';
    END IF;

    -- 验证行数
    SELECT COUNT(*) INTO row_count_after FROM customer."年金关联公司";
    RAISE NOTICE '迁移后行数: %', row_count_after;

    -- 验证兼容性视图
    PERFORM COUNT(*) FROM customer."年金客户";
    RAISE NOTICE '兼容性视图 customer."年金客户" 可用 ✓';

    PERFORM COUNT(*) FROM mapping."年金客户";
    RAISE NOTICE '兼容性视图 mapping."年金客户" 可用 ✓';

    RAISE NOTICE '迁移成功！表已重命名为 customer."年金关联公司"';
END $$;
