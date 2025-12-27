-- Auto-generated baseline DDL (initial seed).
-- Entity: portfolio_plans | Table: 组合计划

DROP TABLE IF EXISTS "组合计划" CASCADE;

CREATE TABLE "组合计划" (
  "id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  "年金计划号" VARCHAR(255),
  "组合代码" VARCHAR(255) NOT NULL,
  "组合名称" VARCHAR(255),
  "组合简称" VARCHAR(255),
  "组合状态" VARCHAR(255),
  "运作开始日" DATE,
  "组合类型" VARCHAR(255),
  "子分类" VARCHAR(255),
  "受托人" VARCHAR(255),
  "是否存款组合" SMALLINT,
  "是否外部组合" SMALLINT,
  "是否PK组合" SMALLINT,
  "投资管理人" VARCHAR(255),
  "受托管理人" VARCHAR(255),
  "投资组合代码" VARCHAR(255),
  "投资组合名称" VARCHAR(255),
  "备注" TEXT,
  "created_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "idx_组合计划_年金计划号" ON "组合计划" ("年金计划号");
CREATE INDEX IF NOT EXISTS "idx_组合计划_组合代码" ON "组合计划" ("组合代码");
CREATE INDEX IF NOT EXISTS "idx_组合计划_年金计划号_组合代码" ON "组合计划" ("年金计划号", "组合代码");
CREATE INDEX IF NOT EXISTS "idx_组合计划_年金计划号_组合代码" ON "组合计划" ("年金计划号", "组合代码");

CREATE OR REPLACE FUNCTION update_portfolio_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_portfolio_plans_updated_at
    BEFORE UPDATE ON "组合计划"
    FOR EACH ROW
    EXECUTE FUNCTION update_portfolio_plans_updated_at();

DO $$
BEGIN
    RAISE NOTICE '=== 组合计划 Table Creation Complete ===';
    RAISE NOTICE 'Primary Key: id (GENERATED ALWAYS AS IDENTITY)';
    RAISE NOTICE 'Delete Scope Key (non-unique): 年金计划号, 组合代码';
    RAISE NOTICE 'Audit Fields: created_at, updated_at with auto-update trigger';
    RAISE NOTICE 'Indexes: Performance indexes created for common query patterns';
END $$ LANGUAGE plpgsql;
