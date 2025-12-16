-- Auto-generated baseline DDL (initial seed).
-- Entity: annuity_performance | Table: business.规模明细

DROP TABLE IF EXISTS business."规模明细" CASCADE;

CREATE TABLE business."规模明细" (
  "annuity_performance_id"    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- Core business fields (normalized)
  "月度"                      DATE NOT NULL,
  "业务类型"                    VARCHAR(255),
  "计划类型"                    VARCHAR(255),
  "计划代码"                    VARCHAR(255) NOT NULL,
  "计划名称"                    VARCHAR(255),
  "组合类型"                    VARCHAR(255),
  "组合代码"                    VARCHAR(255),
  "组合名称"                    VARCHAR(255),
  "客户名称"                    VARCHAR(255),
  "期初资产规模"                  double precision,
  "期末资产规模"                  double precision,
  "供款"                      double precision,
  "流失_含待遇支付"               double precision,
  "流失"                      double precision,
  "待遇支付"                    double precision,
  "投资收益"                    double precision,
  "当期收益率"                   double precision,
  "机构代码"                    VARCHAR(255),
  "机构名称"                    VARCHAR(255),
  "产品线代码"                   VARCHAR(255),
  "年金账户号"                   VARCHAR(50),
  "年金账户名"                   VARCHAR(255),
  "company_id"              VARCHAR(50) NOT NULL,

  -- Audit fields
  "created_at"              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  "updated_at"              TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度" ON business."规模明细" ("月度");
CREATE INDEX IF NOT EXISTS "idx_规模明细_计划代码" ON business."规模明细" ("计划代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_company_id" ON business."规模明细" ("company_id");
CREATE INDEX IF NOT EXISTS "idx_规模明细_机构代码" ON business."规模明细" ("机构代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_产品线代码" ON business."规模明细" ("产品线代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_年金账户号" ON business."规模明细" ("年金账户号");

CREATE INDEX IF NOT EXISTS "idx_规模明细_月度_计划代码" ON business."规模明细" ("月度", "计划代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度_company_id" ON business."规模明细" ("月度", "company_id");
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度_计划代码_company_id" ON business."规模明细" ("月度", "计划代码", "company_id");

-- Trigger function
CREATE OR REPLACE FUNCTION update_annuity_performance_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger
CREATE TRIGGER trigger_update_annuity_performance_updated_at
    BEFORE UPDATE ON business."规模明细"
    FOR EACH ROW
    EXECUTE FUNCTION update_annuity_performance_updated_at();

-- Notices
DO $$
BEGIN
    RAISE NOTICE '=== 规模明细 Table Creation Complete ===';
    RAISE NOTICE 'Primary Key: annuity_performance_id (GENERATED ALWAYS AS IDENTITY)';
    RAISE NOTICE 'Delete Scope Key (non-unique): 月度, 计划代码, company_id';
    RAISE NOTICE 'Audit Fields: created_at, updated_at with auto-update trigger';
    RAISE NOTICE 'Indexes: Performance indexes created for common query patterns';
END $$ LANGUAGE plpgsql;

