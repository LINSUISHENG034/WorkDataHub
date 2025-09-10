-- Test schema setup for local testing with reference/monthly data
-- This extends the production schema with the metadata column required by INITIAL.md
-- Used for smoke tests and local development validation

-- Create test table (drop if exists for clean slate)
DROP TABLE IF EXISTS trustee_performance CASCADE;

CREATE TABLE trustee_performance (
    report_date          DATE         NOT NULL,
    plan_code            VARCHAR(50)  NOT NULL,
    company_code         VARCHAR(20)  NOT NULL,
    return_rate          NUMERIC(8,6),         -- CRITICAL: 6 decimal places
    net_asset_value      NUMERIC(18,4),        -- CRITICAL: 4 decimal places
    fund_scale           NUMERIC(18,2),        -- CRITICAL: 2 decimal places
    data_source          VARCHAR(255) NOT NULL,
    processed_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    has_performance_data BOOLEAN      NOT NULL DEFAULT FALSE,
    validation_warnings  JSONB        NOT NULL DEFAULT '[]'::jsonb,
    metadata             JSONB        DEFAULT NULL,  -- NEW: Required by INITIAL.md
    CONSTRAINT pk_trustee_performance PRIMARY KEY (report_date, plan_code, company_code)
);

-- Comments for clarity
COMMENT ON TABLE trustee_performance IS 'Test schema for trustee performance data with metadata column';
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
COMMENT ON COLUMN trustee_performance.metadata             IS '元数据（扩展信息，JSON 对象）';

-- Indexes for common queries (optional for testing but useful for performance)
CREATE INDEX IF NOT EXISTS idx_trustee_performance_report_date ON trustee_performance(report_date);
CREATE INDEX IF NOT EXISTS idx_trustee_performance_plan_code   ON trustee_performance(plan_code);