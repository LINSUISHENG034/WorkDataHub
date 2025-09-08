-- 受托业绩表（English table name to match loader; Chinese-friendly metadata and view）
-- 说明：
-- - 本脚本创建应用当前流水线所需的目标表：trustee_performance（英文表名匹配代码与配置）。
-- - 字段命名保持与代码输出一致，以便无缝装载。
-- - 通过 COMMENT 与中文视图暴露中文语义，方便中文用户与下游消费。

-- 创建表（若不存在）
CREATE TABLE IF NOT EXISTS trustee_performance (
  report_date          DATE        NOT NULL,
  plan_code            VARCHAR(50) NOT NULL,
  company_code         VARCHAR(20) NOT NULL,
  return_rate          NUMERIC(8,6),
  net_asset_value      NUMERIC(18,4),
  fund_scale           NUMERIC(18,2),
  data_source          TEXT        NOT NULL,
  processed_at         TIMESTAMP   NOT NULL DEFAULT now(),
  has_performance_data BOOLEAN     NOT NULL DEFAULT FALSE,
  validation_warnings  JSONB       NOT NULL DEFAULT '[]'::jsonb,
  CONSTRAINT pk_trustee_performance PRIMARY KEY (report_date, plan_code, company_code)
);

-- 中文注释（有助于中文用户理解字段语义）
COMMENT ON TABLE trustee_performance IS '受托业绩（流水线装载目标表）';
COMMENT ON COLUMN trustee_performance.report_date          IS '报告日期';
COMMENT ON COLUMN trustee_performance.plan_code            IS '计划代码';
COMMENT ON COLUMN trustee_performance.company_code         IS '公司代码';
COMMENT ON COLUMN trustee_performance.return_rate          IS '收益率（小数，例如 0.055 表示 5.5%）';
COMMENT ON COLUMN trustee_performance.net_asset_value      IS '净值';
COMMENT ON COLUMN trustee_performance.fund_scale           IS '规模';
COMMENT ON COLUMN trustee_performance.data_source          IS '数据来源（文件路径或来源系统）';
COMMENT ON COLUMN trustee_performance.processed_at         IS '处理时间（记录入库时间戳）';
COMMENT ON COLUMN trustee_performance.has_performance_data IS '是否包含业绩指标数据';
COMMENT ON COLUMN trustee_performance.validation_warnings  IS '校验警告（JSON 数组）';

-- 可选：为常用查询加索引（根据实际使用场景再调整）
-- CREATE INDEX IF NOT EXISTS idx_trustee_performance_report_date ON trustee_performance(report_date);
-- CREATE INDEX IF NOT EXISTS idx_trustee_performance_plan_code   ON trustee_performance(plan_code);
-- CREATE INDEX IF NOT EXISTS idx_trustee_performance_company     ON trustee_performance(company_code);

-- 中文视图（仅供使用者友好查询，不影响装载逻辑）
-- 视图名和列名使用中文，便于中文环境核对与下游消费。
CREATE OR REPLACE VIEW "受托业绩" AS
SELECT
  report_date          AS "报告日期",
  plan_code            AS "计划代码",
  company_code         AS "公司代码",
  return_rate          AS "收益率",
  net_asset_value      AS "净值",
  fund_scale           AS "规模",
  data_source          AS "数据来源",
  processed_at         AS "处理时间",
  has_performance_data AS "有业绩数据",
  validation_warnings  AS "校验警告"
FROM trustee_performance;

