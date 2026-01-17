-- ============================================================
-- 年金客户表 Schema 迁移回滚脚本
-- Rollback: customer."年金客户" → mapping."年金客户"
-- Date: 2026-01-17
-- 
-- Purpose: Rollback the 年金客户 table migration if needed.
-- WARNING: This will reverse the schema migration.
-- ============================================================

BEGIN;

-- 删除视图
DROP VIEW IF EXISTS mapping."年金客户";

-- 将表移回 mapping schema
ALTER TABLE customer."年金客户" SET SCHEMA mapping;

COMMIT;

-- 验证回滚
SELECT schemaname, tablename FROM pg_tables WHERE tablename = '年金客户';
