-- ============================================================
-- Story 7.6-19: 客户明细表回滚/修复脚本（幂等）
-- Target state:
--   - Canonical table: customer."客户明细"
--   - Mapping view:    mapping."客户明细"
-- Date: 2026-02-15
--
-- Purpose: Recover from partially applied rename scripts and normalize
--          customer schema objects to canonical names.
-- ============================================================

BEGIN;

-- Step 1: Normalize customer master table name (legacy -> canonical)
DO $$
BEGIN
    IF to_regclass('customer."客户明细"') IS NULL THEN
        IF to_regclass('mapping."年金关联公司"') IS NOT NULL THEN
            ALTER TABLE mapping."年金关联公司" RENAME TO "客户明细";
            ALTER TABLE mapping."客户明细" SET SCHEMA customer;
        ELSIF to_regclass('mapping."年金客户"') IS NOT NULL THEN
            ALTER TABLE mapping."年金客户" RENAME TO "客户明细";
            ALTER TABLE mapping."客户明细" SET SCHEMA customer;
        ELSIF to_regclass('mapping."客户明细"') IS NOT NULL THEN
            ALTER TABLE mapping."客户明细" SET SCHEMA customer;
        ELSIF to_regclass('customer."年金关联公司"') IS NOT NULL THEN
            ALTER TABLE customer."年金关联公司" RENAME TO "客户明细";
        ELSIF to_regclass('customer."年金客户"') IS NOT NULL THEN
            ALTER TABLE customer."年金客户" RENAME TO "客户明细";
        ELSE
            RAISE EXCEPTION
                '修复失败: 未找到客户主表 (customer."客户明细"/"年金关联公司"/"年金客户")';
        END IF;
    END IF;
END $$;

-- Step 2: Drop legacy mapping views and recreate canonical mapping view
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'mapping'
          AND c.relname = '年金客户'
          AND c.relkind IN ('v', 'm')
    ) THEN
        EXECUTE 'DROP VIEW mapping."年金客户"';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'mapping'
          AND c.relname = '客户明细'
          AND c.relkind IN ('v', 'm')
    ) THEN
        EXECUTE 'DROP VIEW mapping."客户明细"';
    END IF;
END $$;

DO $$
DECLARE
    relkind "char";
BEGIN
    SELECT c.relkind
    INTO relkind
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'mapping'
      AND c.relname = '客户明细'
    LIMIT 1;

    IF relkind IS NOT NULL AND relkind NOT IN ('v', 'm') THEN
        RAISE EXCEPTION
            '修复失败: mapping."客户明细" 已存在且不是视图，请先清理冲突对象';
    END IF;
END $$;

CREATE OR REPLACE VIEW mapping."客户明细" AS
SELECT * FROM customer."客户明细";

-- Step 3: Rebuild FK constraints to canonical customer table
DO $$
BEGIN
    IF to_regclass('customer."客户年金计划"') IS NOT NULL THEN
        ALTER TABLE customer."客户年金计划"
            DROP CONSTRAINT IF EXISTS fk_contract_company;
        ALTER TABLE customer."客户年金计划"
            ADD CONSTRAINT fk_contract_company
            FOREIGN KEY (company_id) REFERENCES customer."客户明细"(company_id);
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('customer."客户计划月度快照"') IS NOT NULL THEN
        ALTER TABLE customer."客户计划月度快照"
            DROP CONSTRAINT IF EXISTS fk_fct_plan_company;
        ALTER TABLE customer."客户计划月度快照"
            ADD CONSTRAINT fk_fct_plan_company
            FOREIGN KEY (company_id) REFERENCES customer."客户明细"(company_id);
    END IF;
END $$;

DO $$
BEGIN
    IF to_regclass('customer."客户业务月度快照"') IS NOT NULL THEN
        ALTER TABLE customer."客户业务月度快照"
            DROP CONSTRAINT IF EXISTS fk_snapshot_company;
        ALTER TABLE customer."客户业务月度快照"
            DROP CONSTRAINT IF EXISTS fk_fct_pl_company;
        ALTER TABLE customer."客户业务月度快照"
            ADD CONSTRAINT fk_fct_pl_company
            FOREIGN KEY (company_id) REFERENCES customer."客户明细"(company_id);
    END IF;
END $$;

-- Step 4: Recreate sync triggers with canonical trigger/function names
DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
    ON customer."客户明细";
DROP TRIGGER IF EXISTS trg_sync_fct_pl_customer_name
    ON customer."客户明细";

CREATE TRIGGER trg_sync_fct_pl_customer_name
    AFTER UPDATE OF 客户名称 ON customer."客户明细"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_pl_customer_name();

DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
    ON customer."客户明细";
DROP TRIGGER IF EXISTS trg_sync_fct_plan_customer_name
    ON customer."客户明细";

CREATE TRIGGER trg_sync_fct_plan_customer_name
    AFTER UPDATE OF 客户名称 ON customer."客户明细"
    FOR EACH ROW
    EXECUTE FUNCTION customer.sync_fct_plan_customer_name();

COMMIT;

-- 验证结果
SELECT schemaname, tablename FROM pg_tables WHERE tablename = '客户明细';
SELECT schemaname, viewname FROM pg_views WHERE viewname = '客户明细';
