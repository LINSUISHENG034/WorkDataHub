# INITIAL.md — C-024..C-027：规模明细（真实样本）首轮试点

目的：以真实业务样本“规模明细（AnnuityPerformance）”为试点，完成端到端闭环（发现→读取→清洗/校验→装载），验证新架构对legacy流程的承载能力，尽快暴露关键问题并指导后续修复。

## 任务
- ROADMAP：
  - C-024：E2E骨架与标记（legacy_data）
  - C-025：数据发现配置（正则与V*版本选择）
  - C-026：Postgres最小DDL（scripts/dev/annuity_performance.sql）
  - C-027：E2E（plan-only/execute，本地样本）
- 范围：仅“规模明细”一个域；不修改CI默认行为（本地opt-in）。

## 输入与定位
- 真实样本路径（本地）：`reference/monthly/数据采集/V*/【for年金分战区经营分析】24年11月年金终稿数据1209采集.xlsx`
- 目录特征：位于`数据采集`目录，采集版本目录形如`V1`/`V2`/...；同一`数据采集`下取`V*`最大的为最终版本。
- sheet 名：`规模明细`

## 交付物
1) data_sources.yml 新增域：`annuity_performance`（规模明细）
   - pattern（Unicode-aware）：
     - `(?P<year>20\d{2}|\d{2})年(?P<month>0?[1-9]|1[0-2])月.*年金.*终稿数据.*\.(xlsx|xlsm)$`
     - 说明：两位年（如`24`）按`2000+year`转换；保留月份回退修正逻辑（10/11/12）。
   - select：新增策略`latest_by_year_month_and_version`
     - 语义：先按(year, month)分组，再在同组内比较版本目录`V(?P<version>\d+)`取最大；若version不存在，回退mtime。
   - sheet：`规模明细`
   - table/pk：
     - `table: "annuity_performance"`
     - `pk: ["report_date", "plan_code", "company_code", "portfolio_code"]`

2) DataSourceConnector 增强（C-025）
   - 支持新select策略`latest_by_year_month_and_version`：
     - 在`_scan_directory_for_domain`中，除从文件名提取year/month外，增加从路径父目录提取版本：
       - 若父目录名匹配`^V(?P<version>\d+)`且父目录上一级名为`数据采集`，则记录`version=int(...)`；
     - `_apply_selection_strategies`：对同域文件按(year,month)分组；若组内存在version，按(version, mtime)排序取最大；否则按mtime。
   - 兼容性：若pattern未捕获year/month，仍可回退mtime；若路径不存在`V*`与`数据采集`，不影响其他域的选择逻辑。

3) DDL（C-026）：`scripts/dev/annuity_performance.sql`
   - 表：`annuity_performance`（英文列名；可选中文视图`"规模明细"`辅助核对）
   - 字段（建议）：
     - 键：`report_date DATE NOT NULL`，`plan_code VARCHAR(50) NOT NULL`，`company_code VARCHAR(20) NOT NULL`，`portfolio_code VARCHAR(50) NOT NULL`，`portfolio_name VARCHAR(255)`
     - 规模流量：`scale_open NUMERIC(18,2)`，`scale_close NUMERIC(18,2)`，`contribution NUMERIC(18,2)`，`outflow NUMERIC(18,2)`，`benefit_payment NUMERIC(18,2)`，`investment_return NUMERIC(18,2)`
     - 比率：`period_return NUMERIC(8,6)`
     - 标志：`assess_valid BOOLEAN DEFAULT FALSE`
     - 元数据：`data_source TEXT NOT NULL`，`processed_at TIMESTAMP DEFAULT now()`，`validation_warnings JSONB DEFAULT '[]'::jsonb`，`metadata JSONB DEFAULT NULL`
     - 约束：`PRIMARY KEY (report_date, plan_code, company_code, portfolio_code)`
   - 注：精度与后续领域模型保持一致；JSONB用于沉淀校验/清洗warning与上下文。

4) E2E（C-024/C-027）：`tests/legacy/test_annuity_performance_smoke.py`
   - 标记：`@pytest.mark.legacy_data`（在`pyproject.toml`配置markers）
   - 用例：
     - 发现：`WDH_DATA_BASE_DIR=./reference/monthly`时，能在`数据采集`下发现`V*`最大版本的规模明细文件；
     - plan-only：读取`sheet="规模明细"`，生成DELETE+INSERT计划；
     - execute（可选）：小规模执行（限制`--max-files 1`）；
     - 跳过策略：当本地无样本/无Postgres/无psycopg2时跳过。

## 清洗与校验（领域服务要点，后续扩展）
- 列映射（示例，按样本列头调整）：
  - 年/月→report_date（拼接当月1日）；计划/公司/组合代码与名称；
  - 期初/期末规模、供款、流失、待遇支付、投资收益、当期收益率。
- 数值清洗：货币符号/千分位/空白剔除；空值占位转None；
- 比率处理：字符串`%`→/100；数值>1且≤100按百分比解释（仅收益率）；
- 交叉校验（可选，容差±0.01）：`scale_close ≈ scale_open + contribution + investment_return - outflow - benefit_payment`；超出容差写入`validation_warnings`。

## 文档与安全
- README 新增“真实样本Smoke（规模明细）”段落：
  - 环境变量：
    - `export WDH_DATA_BASE_DIR=./reference/monthly`
    - `export WDH_DATABASE__URI=postgresql://wdh_user:changeme@localhost:5432/wdh_local`
  - 建表示例：
    - `uv run python -m scripts.create_table.apply_sql --sql scripts/dev/annuity_performance.sql`
  - 执行：
    - 计划：`uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only --max-files 1`
    - 执行：`uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --execute --max-files 1`
- 安全：不提交任何PII；`reference/monthly`为本地资源；CI默认跳过`legacy_data`测试。

## 验证命令（本地）
- 基线：
  - `uv run ruff check src/ --fix`
  - `uv run mypy src/`
- E2E（opt-in）：
  - `export WDH_DATA_BASE_DIR=./reference/monthly`
  - `uv run pytest -m legacy_data -v`
  - 计划/执行命令见上。

## 验收标准
- 在`reference/monthly/数据采集/V*/`存在规模明细样本时：
  - 发现器能识别并仅选择同目录下`V*`最大的文件；
  - `sheet="规模明细"`读取成功；
  - plan-only 产生合理的DELETE+INSERT计划；
  - execute模式可写入最小DDL表，打印删除/插入/批次数；
  - README包含“规模明细Smoke”指引；
  - 不影响既有CI（默认跳过）。

## 风险与回退
- 文件命名差异：pattern匹配失败时回退mtime；必要时增补别名正则。
- 目录层级差异：若不存在`数据采集/V*`，不启用版本优先策略。
- 数值偏差：以容差写warning；不阻断装载（除非人为设置阈值）。
