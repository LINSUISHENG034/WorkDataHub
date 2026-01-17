-- ============================================================
-- 年金客户表 Schema 迁移脚本
-- From: mapping."年金客户" → To: customer."年金客户"
-- Date: 2026-01-17
-- 
-- Purpose: Migrate existing 年金客户 table from mapping schema
--          to customer schema for Customer MDM consistency.
-- ============================================================

-- 预检查：记录迁移前行数
DO $$
DECLARE
    row_count_before INTEGER;
BEGIN
    SELECT COUNT(*) INTO row_count_before FROM mapping."年金客户";
    RAISE NOTICE '迁移前行数: %', row_count_before;
END $$;

BEGIN;

-- Step 1: 确保 customer schema 存在
CREATE SCHEMA IF NOT EXISTS customer;

-- Step 2: 将表从 mapping 移动到 customer schema
ALTER TABLE mapping."年金客户" SET SCHEMA customer;

-- Step 3: 在 mapping schema 创建兼容性视图
CREATE OR REPLACE VIEW mapping."年金客户" AS
SELECT * FROM customer."年金客户";

COMMIT;

-- 后检查：验证迁移结果
DO $$
DECLARE
    row_count_after INTEGER;
    table_schema_result TEXT;
BEGIN
    -- 验证表位置
    SELECT schemaname INTO table_schema_result
    FROM pg_tables WHERE tablename = '年金客户' AND schemaname = 'customer';

    IF table_schema_result IS NULL THEN
        RAISE EXCEPTION '迁移失败: 表未在 customer schema 中找到';
    END IF;

    -- 验证行数
    SELECT COUNT(*) INTO row_count_after FROM customer."年金客户";
    RAISE NOTICE '迁移后行数: %', row_count_after;
    RAISE NOTICE '迁移成功！表现在位于 customer schema';
END $$;

-- 验证视图
SELECT schemaname, viewname FROM pg_views WHERE viewname = '年金客户';
