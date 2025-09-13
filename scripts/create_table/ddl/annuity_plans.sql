-- Auto-generated baseline DDL (initial seed).
-- Entity: annuity_plans | Table: 年金计划

DROP TABLE IF EXISTS "年金计划" CASCADE;

CREATE TABLE "年金计划" (
  "annuity_plans_id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "年金计划号" VARCHAR(255) NOT NULL,
  "计划简称" VARCHAR(255),
  "计划全称" VARCHAR(255),
  "主拓代码" VARCHAR(10),
  "计划类型" VARCHAR(255),
  "客户名称" VARCHAR(255),
  "company_id" VARCHAR(255),
  "管理资格" VARCHAR(255),
  "计划状态" VARCHAR(255),
  "主拓机构" VARCHAR(10),
  "组合数" INTEGER,
  "是否统括" SMALLINT,
  "备注" TEXT,
  "created_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "idx_年金计划_company_id" ON "年金计划" ("company_id");
CREATE INDEX IF NOT EXISTS "idx_年金计划_年金计划号" ON "年金计划" ("年金计划号");
CREATE INDEX IF NOT EXISTS "idx_年金计划_年金计划号_company_id" ON "年金计划" ("年金计划号", "company_id");
CREATE INDEX IF NOT EXISTS "idx_年金计划_年金计划号_company_id" ON "年金计划" ("年金计划号", "company_id");

CREATE OR REPLACE FUNCTION update_annuity_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_annuity_plans_updated_at
    BEFORE UPDATE ON "年金计划"
    FOR EACH ROW
    EXECUTE FUNCTION update_annuity_plans_updated_at();

DO $$
BEGIN
    RAISE NOTICE '=== 年金计划 Table Creation Complete ===';
    RAISE NOTICE 'Primary Key: annuity_plans_id (GENERATED ALWAYS AS IDENTITY)';
    RAISE NOTICE 'Delete Scope Key (non-unique): 年金计划号, company_id';
    RAISE NOTICE 'Audit Fields: created_at, updated_at with auto-update trigger';
    RAISE NOTICE 'Indexes: Performance indexes created for common query patterns';
END $$ LANGUAGE plpgsql;
