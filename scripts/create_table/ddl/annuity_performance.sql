-- DDL for domain: annuity_performance

DROP TABLE IF EXISTS business."规模明细" CASCADE;

-- Table: business."规模明细"
CREATE TABLE business."规模明细" (
  "id" INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- Business columns
  "月度" DATE NOT NULL,
  "业务类型" VARCHAR(255),
  "计划类型" VARCHAR(255),
  "计划代码" VARCHAR(255) NOT NULL,
  "计划名称" VARCHAR(255),
  "组合类型" VARCHAR(255),
  "组合代码" VARCHAR(255),
  "组合名称" VARCHAR(255),
  "客户名称" VARCHAR(255),
  "期初资产规模" DECIMAL(18, 4),
  "期末资产规模" DECIMAL(18, 4),
  "供款" DECIMAL(18, 4),
  "流失_含待遇支付" DECIMAL(18, 4),
  "流失" DECIMAL(18, 4),
  "待遇支付" DECIMAL(18, 4),
  "投资收益" DECIMAL(18, 4),
  "当期收益率" DECIMAL(10, 6),
  "年化收益率" DECIMAL(10, 6),
  "机构代码" VARCHAR(255),
  "机构名称" VARCHAR(255),
  "产品线代码" VARCHAR(255),
  "年金账户号" VARCHAR(50),
  "年金账户名" VARCHAR(255),
  "company_id" VARCHAR(50) NOT NULL,
  "子企业号" VARCHAR(50),
  "子企业名称" VARCHAR(255),
  "集团企业客户号" VARCHAR(50),
  "集团企业客户名称" VARCHAR(255),

  -- Audit columns
  "created_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "idx_规模明细_月度" ON business."规模明细" ("月度");
CREATE INDEX IF NOT EXISTS "idx_规模明细_计划代码" ON business."规模明细" ("计划代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_company_id" ON business."规模明细" ("company_id");
CREATE INDEX IF NOT EXISTS "idx_规模明细_机构代码" ON business."规模明细" ("机构代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_产品线代码" ON business."规模明细" ("产品线代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_年金账户号" ON business."规模明细" ("年金账户号");
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度_计划代码" ON business."规模明细" ("月度", "计划代码");
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度_company_id" ON business."规模明细" ("月度", "company_id");
CREATE INDEX IF NOT EXISTS "idx_规模明细_月度_计划代码_company_id" ON business."规模明细" ("月度", "计划代码", "company_id");

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_annuity_performance_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trigger_update_annuity_performance_updated_at
    BEFORE UPDATE ON business."规模明细"
    FOR EACH ROW
    EXECUTE FUNCTION update_annuity_performance_updated_at();