-- PostgreSQL DDL for table: 规模明细
-- Generated from: reference\db_migration\db_structure.json
-- Generation time: 2025-09-11 00:50:30
-- Configuration: without foreign keys
--
-- IMPORTANT: Chinese identifiers are properly quoted for PostgreSQL compatibility
-- IMPORTANT: MySQL COLLATE clauses have been stripped during conversion
-- IMPORTANT: Primary key inferred from unique indexes in source schema
--


CREATE TABLE IF NOT EXISTS "规模明细" (
  "id"                      INTEGER NOT NULL,
  "月度"                      DATE,
  "业务类型"                    VARCHAR(255),
  "计划类型"                    VARCHAR(255),
  "计划代码"                    VARCHAR(255),
  "计划名称"                    VARCHAR(255),
  "组合类型"                    VARCHAR(255),
  "组合代码"                    VARCHAR(255),
  "组合名称"                    VARCHAR(255),
  "客户名称"                    VARCHAR(255),
  "期初资产规模"                  double precision,
  "期末资产规模"                  double precision,
  "供款"                      double precision,
  "流失(含待遇支付)"               double precision,
  "流失"                      double precision,
  "待遇支付"                    double precision,
  "投资收益"                    double precision,
  "当期收益率"                   double precision,
  "机构代码"                    VARCHAR(255),
  "机构名称"                    VARCHAR(255),
  "产品线代码"                   VARCHAR(255),
  "年金账户号"                   VARCHAR(50),
  "年金账户名"                   VARCHAR(255),
  "company_id"              VARCHAR(50),
  CONSTRAINT pk_规模明细 PRIMARY KEY ("id")
);

-- Indexes
CREATE INDEX IF NOT EXISTS "FK_产品线_规模明细" ON "规模明细" ("产品线代码");
CREATE INDEX IF NOT EXISTS "FK_年金计划_规模明细" ON "规模明细" ("计划代码");
CREATE INDEX IF NOT EXISTS "FK_组合计划_规模明细" ON "规模明细" ("组合代码");
CREATE INDEX IF NOT EXISTS "FK_组织架构_规模明细" ON "规模明细" ("机构代码");
CREATE INDEX IF NOT EXISTS "KY_客户代码" ON "规模明细" ("company_id");
CREATE INDEX IF NOT EXISTS "KY_客户名称" ON "规模明细" ("客户名称");
CREATE INDEX IF NOT EXISTS "KY_年金账户号" ON "规模明细" ("年金账户号");

-- Table and Column Comments
COMMENT ON TABLE "规模明细" IS '规模明细 (Generated from MySQL JSON schema)';
COMMENT ON COLUMN "规模明细"."id" IS 'id';
COMMENT ON COLUMN "规模明细"."月度" IS '月度';
COMMENT ON COLUMN "规模明细"."业务类型" IS '业务类型';
COMMENT ON COLUMN "规模明细"."计划类型" IS '计划类型';
COMMENT ON COLUMN "规模明细"."计划代码" IS '计划代码';
COMMENT ON COLUMN "规模明细"."计划名称" IS '计划名称';
COMMENT ON COLUMN "规模明细"."组合类型" IS '组合类型';
COMMENT ON COLUMN "规模明细"."组合代码" IS '组合代码';
COMMENT ON COLUMN "规模明细"."组合名称" IS '组合名称';
COMMENT ON COLUMN "规模明细"."客户名称" IS '客户名称';
COMMENT ON COLUMN "规模明细"."期初资产规模" IS '期初资产规模';
COMMENT ON COLUMN "规模明细"."期末资产规模" IS '期末资产规模';
COMMENT ON COLUMN "规模明细"."供款" IS '供款';
COMMENT ON COLUMN "规模明细"."流失(含待遇支付)" IS '流失(含待遇支付)';
COMMENT ON COLUMN "规模明细"."流失" IS '流失';
COMMENT ON COLUMN "规模明细"."待遇支付" IS '待遇支付';
COMMENT ON COLUMN "规模明细"."投资收益" IS '投资收益';
COMMENT ON COLUMN "规模明细"."当期收益率" IS '当期收益率';
COMMENT ON COLUMN "规模明细"."机构代码" IS '机构代码';
COMMENT ON COLUMN "规模明细"."机构名称" IS '机构名称';
COMMENT ON COLUMN "规模明细"."产品线代码" IS '产品线代码';
COMMENT ON COLUMN "规模明细"."年金账户号" IS '年金账户号';
COMMENT ON COLUMN "规模明细"."年金账户名" IS '年金账户名';
COMMENT ON COLUMN "规模明细"."company_id" IS 'company_id';