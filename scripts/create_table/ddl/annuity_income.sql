-- DDL for domain: annuity_income

DROP TABLE IF EXISTS business."收入明细" CASCADE;

-- Table: business."收入明细"
CREATE TABLE business."收入明细" (
  "id" INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

  -- Business columns
  "月度" DATE NOT NULL,
  "计划代码" VARCHAR(255) NOT NULL,
  "company_id" VARCHAR(50),
  "客户名称" VARCHAR(255),
  "年金账户名" VARCHAR(255),
  "业务类型" VARCHAR(255),
  "计划类型" VARCHAR(255),
  "组合代码" VARCHAR(255),
  "产品线代码" VARCHAR(255),
  "机构代码" VARCHAR(255),
  "计划名称" VARCHAR(255),
  "组合类型" VARCHAR(255),
  "组合名称" VARCHAR(255),
  "机构名称" VARCHAR(255),
  "固费" DECIMAL(18, 4) NOT NULL,
  "浮费" DECIMAL(18, 4) NOT NULL,
  "回补" DECIMAL(18, 4) NOT NULL,
  "税" DECIMAL(18, 4) NOT NULL,

  -- Audit columns
  "created_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  "updated_at" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "idx_收入明细_月度" ON business."收入明细" ("月度");
CREATE INDEX IF NOT EXISTS "idx_收入明细_计划代码" ON business."收入明细" ("计划代码");
CREATE INDEX IF NOT EXISTS "idx_收入明细_company_id" ON business."收入明细" ("company_id");
CREATE INDEX IF NOT EXISTS "idx_收入明细_月度_计划代码_company_id" ON business."收入明细" ("月度", "计划代码", "company_id");

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_annuity_income_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trigger_update_annuity_income_updated_at
    BEFORE UPDATE ON business."收入明细"
    FOR EACH ROW
    EXECUTE FUNCTION update_annuity_income_updated_at();