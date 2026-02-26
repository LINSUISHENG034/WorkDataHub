-- ============================================================
-- 客户明细表 Schema 迁移脚本（幂等）
-- From: mapping."年金客户"/mapping."客户明细"/customer."年金客户"
-- To:   customer."客户明细" + mapping."客户明细" view
-- Date: 2026-01-17
--
-- Purpose: Normalize legacy customer master table names and move
--          canonical table to customer schema.
-- ============================================================

-- 预检查：记录迁移前行数
DO $$
DECLARE
    row_count_before INTEGER := 0;
BEGIN
    IF to_regclass('mapping."年金客户"') IS NOT NULL THEN
        SELECT COUNT(*) INTO row_count_before FROM mapping."年金客户";
    ELSIF to_regclass('mapping."客户明细"') IS NOT NULL THEN
        SELECT COUNT(*) INTO row_count_before FROM mapping."客户明细";
    ELSIF to_regclass('customer."年金客户"') IS NOT NULL THEN
        SELECT COUNT(*) INTO row_count_before FROM customer."年金客户";
    ELSIF to_regclass('customer."客户明细"') IS NOT NULL THEN
        SELECT COUNT(*) INTO row_count_before FROM customer."客户明细";
    END IF;

    RAISE NOTICE '迁移前行数: %', row_count_before;
END $$;

BEGIN;

-- Step 1: 确保 customer schema 存在
CREATE SCHEMA IF NOT EXISTS customer;

-- Step 2: 规范化并迁移表到 customer schema
DO $$
BEGIN
    IF to_regclass('customer."客户明细"') IS NULL THEN
        IF to_regclass('mapping."年金客户"') IS NOT NULL THEN
            ALTER TABLE mapping."年金客户" RENAME TO "客户明细";
            ALTER TABLE mapping."客户明细" SET SCHEMA customer;
        ELSIF to_regclass('mapping."客户明细"') IS NOT NULL THEN
            ALTER TABLE mapping."客户明细" SET SCHEMA customer;
        ELSIF to_regclass('customer."年金客户"') IS NOT NULL THEN
            ALTER TABLE customer."年金客户" RENAME TO "客户明细";
        ELSE
            RAISE EXCEPTION
                '迁移失败: 未找到可迁移的客户表 (mapping."年金客户"/mapping."客户明细"/customer."年金客户")';
        END IF;
    END IF;
END $$;

-- Step 3: 清理旧视图并创建 mapping 兼容视图
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
            '迁移失败: mapping."客户明细" 已存在且不是视图，请先清理冲突对象';
    END IF;
END $$;

CREATE OR REPLACE VIEW mapping."客户明细" AS
SELECT * FROM customer."客户明细";

COMMIT;

-- 后检查：验证迁移结果
DO $$
DECLARE
    row_count_after INTEGER;
BEGIN
    IF to_regclass('customer."客户明细"') IS NULL THEN
        RAISE EXCEPTION '迁移失败: 表 customer."客户明细" 未找到';
    END IF;

    SELECT COUNT(*) INTO row_count_after FROM customer."客户明细";
    RAISE NOTICE '迁移后行数: %', row_count_after;
    RAISE NOTICE '迁移成功！规范表位于 customer."客户明细"';
END $$;

-- 验证视图
SELECT schemaname, viewname FROM pg_views WHERE viewname = '客户明细';
