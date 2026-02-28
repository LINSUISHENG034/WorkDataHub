# 核心业务数据处理流程验证指南 (实盘数据版)

根据 `docs\domain_processing_flows.md` 文档中描述的 **6个核心流转阶段** 以及 **2个核心机制** (MDM企业标识解析与维度回填)，本文档提供了如何使用 `data\real_data` 目录下的真实账期数据 (如 `202509`, `202510`, `202511` 等) 进行代码运行和结果验证的详细步骤。

特别地，由于项目集成了高度复杂的 `foreign_keys.yml` 聚合回填逻辑、`customer_status_rules.yml` 状态推断逻辑以及基于 Post-ETL Hook 链的多阶段级联处理 (合约同步 → 年度初始化 → 快照刷新)，本文重点对各关键节点提供针对性极强的验证方式。

---

## 步骤一：环境与数据准备

在执行真实数据处理前，需先确保数据库表结构最新，并清理测试所需的环境：

1. **同步最新数据库结构**：
   ```bash
   uv run --env-file .wdh_env alembic upgrade head
   ```
2. **确认真实数据存在**：
   确保 `config/data_sources.yml` 中的 glob 配置能够正确指向 `data\real_data` 下的目录（例如 `data/real_data/202510/**/*.xlsx` 等）。
   *(注意：如果遇上"找不到文件"报错，大概率是原始数据存放到了像 `V1/` 这样的子目录中，建议在 yaml 中使用 `**/*...*.xlsx` 增加递归通配符)*

---

## 步骤二：执行全流程 ETL 及快照生成

项目提供了统一的 CLI 入口来触发 Dagster 的 `generic_domain_job`。
执行时，**3个 Post-ETL Hook** 已在 `cli/etl/hooks.py` 中按序注册，会在 `annuity_performance` 领域跑完后**自动依次执行**：

| 执行顺序 | Hook 名称 | 功能描述 |
|:---:|---|---|
| 1 | `contract_status_sync` | 从 `business.规模明细` 同步合约状态到 SCD2 维表 `customer."客户年金计划"` |
| 2 | `year_init` | 仅1月触发，初始化当年 `is_strategic` / `is_existing` 标识 |
| 3 | `snapshot_refresh` | 刷新两张月度快照宽表 (ProductLine粒度 + Plan粒度) |

> **注意**：Hook 仅对 `annuity_performance` 领域触发。建议先跑 `annual_award` 和 `annual_loss`，最后跑 `annuity_performance`，以确保快照刷新时中标/流失事实已入库。

请依次执行各大领域（以 `202510` 账期为例）：

```bash
# 推荐按此顺序执行，确保快照刷新时所有事实表数据已就绪
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annual_award --period 202510 --file-selection newest --execute
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annual_loss --period 202510 --file-selection newest --execute
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annuity_performance --period 202510 --file-selection newest --execute

# 或：一次性执行所有受支持领域 (--all-domains) 触发完整的处理流水线
uv run --env-file .wdh_env python -m work_data_hub.cli etl --all-domains --period 202510 --file-selection newest --execute
```
*注：如果在内网测试无法连通 EQC(天眼查) 接口，可附带 `--no-enrichment` 参数跳过外部网络解析，系统将自动降级使用本地规则或生成 `IN*` 临时 ID，不影响核心逻辑验证。*

---

## 步骤三：验证 ETL 管线基础阶段 (阶段 1-3)

这些基础清理和加工的体现可以在日志和 UI 中直观地找到。
**验证方式：通过 Dagster UI 可视化查验。**

1. 启动 Dagster Webserver：`uv run --env-file .wdh_env dagster dev`
2. 打开 `http://localhost:3000` 进入对应的 Run。
3. **查验文件发现与合并 (阶段 1-2)**：点开 `read_data_op` 的 Compute Logs，检查 `annual_award` 等领域是否成功将受托和投资多个 sheet 的数据合并读取。
4. **查验补全插值 `PlanCodeEnrichmentStep` (阶段 3)**：在 `annual_award` 与 `annual_loss` 的 `process_domain_op_v2` 日志中，寻找 `"Plan code enrichment complete"`，验证它"根据产品线和集合/单一类型推断并补齐了多少条空缺的年金计划号"。

### 验证 SQL：事实表明细落地确认 (阶段 5-6)

```sql
-- 验证各业务事实表已通过 Idempotent Upsert (Delete + Insert) 正常入库
SELECT '中标' AS 领域, COUNT(*) AS 记录数 FROM customer."中标客户明细" WHERE EXTRACT(YEAR FROM "上报月份") = 2025
UNION ALL
SELECT '流失', COUNT(*) FROM customer."流失客户明细" WHERE EXTRACT(YEAR FROM "上报月份") = 2025
UNION ALL
SELECT '规模', COUNT(*) FROM business."规模明细" WHERE "月度" >= '2025-10-01' AND "月度" < '2025-11-01';
```

---

## 步骤四：验证 MDM 企业标识解析 (核心机制 1)

流水线中的 `CompanyIdResolutionStep` 会尽全力去匹配脏的企业名称到标准的 `company_id`。

> **注意**：项目不存在 `mdm.customer_resolution_log` 表。解析统计信息通过结构化日志输出（`Company ID resolution complete` 事件），包含缓存命中数、EQC 匹配数、临时 ID 数等指标。

**验证方式 A：查看 ETL 运行日志**

在 Dagster UI 或 CLI 输出中搜索 `Company ID resolution complete`，查看各领域的解析统计：
- `db_cache_hits`：数据库缓存命中数 (期望最高)
- `eqc_hits`：天眼查 API 匹配数
- `yaml_hits`：YAML 字典强制覆盖数
- `temp_ids`：生成的临时 `IN*` ID 数 (期望最低)

**验证方式 B：直接查询业务表中的临时 ID**

```sql
-- 1. 检查各领域中生成了多少临时 IN* ID (解析失败的兜底)
SELECT '规模' AS 领域, COUNT(*) AS 临时ID数 FROM business."规模明细" WHERE company_id LIKE 'IN%'
UNION ALL
SELECT '中标', COUNT(*) FROM customer."中标客户明细" WHERE company_id LIKE 'IN%'
UNION ALL
SELECT '流失', COUNT(*) FROM customer."流失客户明细" WHERE company_id LIKE 'IN%';

-- 2. 抽查临时 ID 对应的原始客户名称，判断是否需要加入 YAML 字典干预
SELECT company_id, "客户名称"
FROM business."规模明细"
WHERE company_id LIKE 'IN%'
LIMIT 20;
```

---

## 步骤五：验证高级聚合维表回填 (核心机制 2 · FK Backfill)

根据 `config/foreign_keys.yml`，在进行表间回填时会触发多种运算算子（`max_by`、`concat_distinct`、`jsonb_append`、`lambda`、`count_distinct`、`template`）。

**验证方式：针对 `customer."客户明细"` 表进行逐算子抽查。**

### 5.1 `max_by` — 基于规模挑选主拓机构

```sql
-- 验证主拓机构是否按最大规模推举 (annuity_performance 以期末资产规模排序, annual_award/annual_loss 以计划规模排序)
SELECT company_id, 客户名称, 主拓机构, 主拓机构代码, 关键年金计划
FROM customer."客户明细"
WHERE 主拓机构 IS NOT NULL
LIMIT 20;
```

### 5.2 `concat_distinct` — 排重拼接管理资格与计划类型

```sql
-- 验证管理资格拼接（如 "企年投资+企年受托"）和计划类型拼接（如 "单一/集合"）
SELECT company_id, 客户名称, 管理资格, 年金计划类型
FROM customer."客户明细"
WHERE 管理资格 LIKE '%+%' OR 年金计划类型 LIKE '%/%'
LIMIT 20;
```

### 5.3 `count_distinct` — 关联计划数 / 关联机构数

```sql
-- 验证自动统计的关联计划数和关联机构数
SELECT company_id, 客户名称, 关联计划数, 关联机构数, 其他年金计划, 其他开拓机构
FROM customer."客户明细"
WHERE 关联计划数 > 1
LIMIT 10;
```

### 5.4 `jsonb_append` — 业务操作轨迹标签 (tags)

> **重点验证**：`annual_award` 回填追加 `"2510中标"` 标签，`annual_loss` 回填追加 `"2510流失"` 标签。

```sql
-- 验证 tags 列中的 jsonb 数组是否正确追加了带日期前缀的操作标签
SELECT company_id, 客户名称, tags, 年金客户类型, 年金客户标签
FROM customer."客户明细"
WHERE tags::text LIKE '%中标%' OR tags::text LIKE '%流失%';
```

### 5.5 `lambda` — 日期格式化客户标签

```sql
-- 验证 lambda 算子生成的 年金客户标签 格式正确 (如 "2510新建")
SELECT company_id, 年金客户标签
FROM customer."客户明细"
WHERE 年金客户标签 IS NOT NULL AND 年金客户标签 != ''
LIMIT 10;
```

### 5.6 `template` — 固定值客户类型

```sql
-- 验证 template 算子赋值：annuity_performance 域写 "新客", annual_award 域写 "中标客户", annual_loss 域写 "流失客户"
SELECT 年金客户类型, COUNT(*)
FROM customer."客户明细"
WHERE 年金客户类型 IS NOT NULL
GROUP BY 年金客户类型;
```

### 5.7 跨领域回填优先级验证

> 由于 `annuity_performance`、`annual_award`、`annual_loss`、`annuity_income` 四个领域都对 `fk_customer` 进行回填，各自使用不同的 `max_by` 权重列（分别为 `期末资产规模`、`计划规模`、`计划规模`、`固费`），建议抽检 **同时出现在多个领域的客户**，验证最终写入主表的值是否合理：

```sql
-- 找到同时出现在中标和规模明细中的客户，验证主拓机构的最终推举一致性
SELECT c.company_id, c.客户名称, c.主拓机构,
       a."机构名称" AS 中标机构, p."机构名称" AS 规模主拓
FROM customer."客户明细" c
LEFT JOIN LATERAL (
    SELECT DISTINCT ON (company_id) "机构名称"
    FROM customer."中标客户明细"
    WHERE company_id = c.company_id
    ORDER BY company_id, "计划规模" DESC NULLS LAST
    LIMIT 1
) a ON true
LEFT JOIN LATERAL (
    SELECT DISTINCT ON (company_id) "机构名称"
    FROM business."规模明细"
    WHERE company_id = c.company_id
    ORDER BY company_id, "期末资产规模" DESC NULLS LAST
    LIMIT 1
) p ON true
WHERE a."机构名称" IS NOT NULL AND p."机构名称" IS NOT NULL
LIMIT 10;
```

---

## 步骤六：验证 Post-ETL Hook 链 — 合约状态同步

`annuity_performance` ETL 完成后，第一个被触发的 Hook 是 `contract_status_sync`。

**它做了什么**：从 `business."规模明细"` 中提取客户+计划+产品线的组合，计算 `is_strategic`（重要客户）、`is_existing`（存量客户）、`contract_status`（正常/停缴）状态，并以 SCD Type 2 方式写入 `customer."客户年金计划"` 维表。

### 6.1 验证合约维表已同步

```sql
-- 验证客户年金计划维表中有当期有效记录 (valid_to = '9999-12-31')
SELECT COUNT(*) AS 有效合约数,
       COUNT(DISTINCT company_id) AS 客户数,
       COUNT(DISTINCT plan_code) AS 计划数
FROM customer."客户年金计划"
WHERE valid_to = '9999-12-31';
```

### 6.2 验证 `is_strategic` 和 `is_existing` 赋值

```sql
-- is_strategic 基于规模阈值或白名单 Top-N 判定
SELECT is_strategic, COUNT(*) FROM customer."客户年金计划"
WHERE valid_to = '9999-12-31'
GROUP BY is_strategic;

-- is_existing 标识是否有存量业务（规模明细中出现过）
SELECT is_existing, COUNT(*) FROM customer."客户年金计划"
WHERE valid_to = '9999-12-31'
GROUP BY is_existing;
```

### 6.3 验证 `contract_status` (正常/停缴)

```sql
-- contract_status v2 逻辑:
--   正常 = AUM > 0 且 12个月内有缴费记录
--   停缴 = AUM > 0 但 12个月内无缴费记录
SELECT contract_status, COUNT(*)
FROM customer."客户年金计划"
WHERE valid_to = '9999-12-31'
GROUP BY contract_status;
```

### 6.4 验证 SCD Type 2 版本管理

```sql
-- 检查是否存在历史版本记录（valid_to != '9999-12-31'），说明 SCD 状态变更正常运作
SELECT
    COUNT(*) FILTER (WHERE valid_to = '9999-12-31') AS 当前版本数,
    COUNT(*) FILTER (WHERE valid_to != '9999-12-31') AS 历史版本数
FROM customer."客户年金计划";
```

---

## 步骤七：验证月度快照与客户状态评定 (Post-ETL Hook 3)

项目的极致闭环在于 `snapshot_refresh` Hook 会调用 `snapshot_refresh.py`。它会读取 `config/customer_status_rules.yml` 驱动 `StatusEvaluator` 引擎自动生成评定规则SQL，基于 ETL 写入的最新事实数据计算各客户的状态切面。

> **快照数据来源**：以 `customer."客户年金计划"` 中 `valid_to = '9999-12-31'` 的当前有效记录为基础，`GROUP BY (company_id, product_line_code)` 聚合得到 ProductLine 粒度，直接取记录得到 Plan 粒度。

### 7.1 ProductLine 粒度快照 — `customer."客户业务月度快照"`

此表字段与生成逻辑如下：

| 字段 | 生成方式 | 数据来源/逻辑说明 |
|---|---|---|
| `is_strategic` | `BOOL_OR` 聚合 | 来自合约维表 `客户年金计划.is_strategic`，多合约取"或" |
| `is_existing` | `BOOL_OR` 聚合 | 来自合约维表 `客户年金计划.is_existing`，多合约取"或" |
| `is_winning_this_year` | `StatusEvaluator` | EXISTS 子查询检查 `customer."中标客户明细"` 当年是否有记录 |
| `is_churned_this_year` | `StatusEvaluator` | EXISTS 子查询检查 `customer."流失客户明细"` 当年是否有记录 |
| `is_new` | `StatusEvaluator` 组合 | `is_winning_this_year = True AND NOT BOOL_OR(is_existing)` |
| `aum_balance` | SUM 子查询 | `SELECT SUM(期末资产规模) FROM business."规模明细"` 按 company_id + 产品线代码 + 当月聚合 |
| `plan_count` | COUNT DISTINCT | 按 company_id + product_line_code 下的不同 plan_code 计数 |

#### 验证 SQL

```sql
-- ① 验证快照表已有当期数据
SELECT COUNT(*) AS 记录数,
       COUNT(DISTINCT company_id) AS 客户数,
       COUNT(DISTINCT product_line_code) AS 产品线数
FROM customer."客户业务月度快照"
WHERE snapshot_month = '2025-10-31';

-- ② 验证 is_winning_this_year — 对照中标明细
SELECT f.company_id, f.product_line_code, f.customer_name,
       f.is_winning_this_year, f.is_new, f.is_existing
FROM customer."客户业务月度快照" f
WHERE f.snapshot_month = '2025-10-31'
  AND f.is_winning_this_year = true;

-- ③ 交叉核验：上面查出来的 company_id 在中标明细中是否确实存在记录
SELECT DISTINCT company_id, "产品线代码"
FROM customer."中标客户明细"
WHERE EXTRACT(YEAR FROM "上报月份") = 2025;

-- ④ 验证 is_new = is_winning_this_year AND NOT is_existing 的组合逻辑
-- is_new = true 的记录必须满足 is_winning_this_year = true 且 is_existing = false
SELECT company_id, product_line_code, is_new, is_winning_this_year, is_existing
FROM customer."客户业务月度快照"
WHERE snapshot_month = '2025-10-31'
  AND is_new = true
  AND (is_winning_this_year = false OR is_existing = true);
-- ↑ 期望结果：0行 (如有行则说明 is_new 逻辑异常)

-- ⑤ 验证 is_churned_this_year — 对照流失明细
SELECT f.company_id, f.product_line_code, f.customer_name,
       f.is_churned_this_year
FROM customer."客户业务月度快照" f
WHERE f.snapshot_month = '2025-10-31'
  AND f.is_churned_this_year = true;

-- ⑥ 验证 aum_balance 与规模明细的一致性
-- 从快照表取到的 aum 应与规模明细表 SUM 吻合
SELECT f.company_id, f.product_line_code, f.aum_balance AS 快照规模,
       COALESCE(SUM(s."期末资产规模"), 0) AS 明细规模
FROM customer."客户业务月度快照" f
LEFT JOIN business."规模明细" s
  ON f.company_id = s.company_id
  AND f.product_line_code = s."产品线代码"
  AND s."月度" = DATE_TRUNC('month', f.snapshot_month)
WHERE f.snapshot_month = '2025-10-31'
  AND f.aum_balance > 0
GROUP BY f.company_id, f.product_line_code, f.aum_balance
HAVING f.aum_balance != COALESCE(SUM(s."期末资产规模"), 0);
-- ↑ 期望结果：0行 (如有行则说明 aum_balance 汇总不一致)

-- ⑦ 验证 is_strategic 和 is_existing 聚合
SELECT is_strategic, is_existing, COUNT(*)
FROM customer."客户业务月度快照"
WHERE snapshot_month = '2025-10-31'
GROUP BY is_strategic, is_existing
ORDER BY is_strategic DESC, is_existing DESC;

-- ⑧ 验证 plan_count
SELECT f.company_id, f.product_line_code, f.plan_count AS 快照计划数,
       COUNT(DISTINCT c.plan_code) AS 维表计划数
FROM customer."客户业务月度快照" f
JOIN customer."客户年金计划" c
  ON f.company_id = c.company_id
  AND f.product_line_code = c.product_line_code
  AND c.valid_to = '9999-12-31'
WHERE f.snapshot_month = '2025-10-31'
  AND f.plan_count > 1
GROUP BY f.company_id, f.product_line_code, f.plan_count
HAVING f.plan_count != COUNT(DISTINCT c.plan_code)
LIMIT 10;
-- ↑ 期望结果：0行
```

### 7.2 Plan 粒度快照 — `customer."客户计划月度快照"`

此表字段与生成逻辑如下：

| 字段 | 生成方式 | 数据来源/逻辑说明 |
|---|---|---|
| `is_churned_this_year` | `StatusEvaluator` | EXISTS 子查询按 `company_id + 年金计划号` 匹配 `流失客户明细` |
| `contract_status` | 直取 | 来自合约维表 `客户年金计划.contract_status` |
| `aum_balance` | SUM 子查询 | `SELECT SUM(期末资产规模) FROM business."规模明细"` 按 company_id + 计划代码 + 产品线代码 + 当月聚合 |

#### 验证 SQL

```sql
-- ① 验证计划级快照数据正常生成
SELECT COUNT(*) AS 记录数,
       COUNT(DISTINCT plan_code) AS 计划数
FROM customer."客户计划月度快照"
WHERE snapshot_month = '2025-10-31';

-- ② 验证 is_churned_this_year_plan — 按 plan_code 级别判定流失
SELECT snapshot_month, company_id, plan_code, product_line_code,
       is_churned_this_year, contract_status, aum_balance
FROM customer."客户计划月度快照"
WHERE is_churned_this_year = true
  AND snapshot_month = '2025-10-31'
LIMIT 10;

-- ③ 交叉核验：上面查出来的 plan_code 在流失明细中是否确实存在
SELECT "年金计划号", company_id, "客户名称"
FROM customer."流失客户明细"
WHERE EXTRACT(YEAR FROM "上报月份") = 2025;

-- ④ 验证 contract_status 与维表一致
SELECT f.company_id, f.plan_code, f.contract_status AS 快照合约状态,
       c.contract_status AS 维表合约状态
FROM customer."客户计划月度快照" f
JOIN customer."客户年金计划" c
  ON f.company_id = c.company_id
  AND f.plan_code = c.plan_code
  AND f.product_line_code = c.product_line_code
  AND c.valid_to = '9999-12-31'
WHERE f.snapshot_month = '2025-10-31'
  AND f.contract_status != c.contract_status
LIMIT 10;
-- ↑ 期望结果：0行
```

---

## 步骤八：端到端一致性校验 (跨步骤综合验证)

以下查询用于验证从 ETL 入库→合约同步→快照刷新的全链路数据一致性。

### 8.1 中标客户全链路追踪

```sql
-- 一个当年中标的客户, 应同时满足:
-- ① 中标明细中有记录
-- ② 客户明细 tags 列包含 "中标" 标签
-- ③ 快照表 is_winning_this_year = true
SELECT a."客户名称", a.company_id, a."产品线代码",
       c.tags, c.年金客户类型, c.年金客户标签,
       f.is_winning_this_year, f.is_new
FROM customer."中标客户明细" a
JOIN customer."客户明细" c ON a.company_id = c.company_id
LEFT JOIN customer."客户业务月度快照" f
  ON a.company_id = f.company_id
  AND a."产品线代码" = f.product_line_code
  AND f.snapshot_month = '2025-10-31'
WHERE EXTRACT(YEAR FROM a."上报月份") = 2025
LIMIT 10;
```

### 8.2 流失客户全链路追踪

```sql
-- 一个当年流失的客户, 应同时满足:
-- ① 流失明细中有记录
-- ② 客户明细 tags 列包含 "流失" 标签
-- ③ 快照表 is_churned_this_year = true
SELECT l."客户名称", l.company_id, l."产品线代码",
       c.tags, c.年金客户类型,
       f.is_churned_this_year
FROM customer."流失客户明细" l
JOIN customer."客户明细" c ON l.company_id = c.company_id
LEFT JOIN customer."客户业务月度快照" f
  ON l.company_id = f.company_id
  AND l."产品线代码" = f.product_line_code
  AND f.snapshot_month = '2025-10-31'
WHERE EXTRACT(YEAR FROM l."上报月份") = 2025
LIMIT 10;
```

### 8.3 数据总量对比

```sql
-- 快照客户总数应不超过合约维表中的不同客户数
SELECT
    (SELECT COUNT(DISTINCT company_id) FROM customer."客户年金计划" WHERE valid_to = '9999-12-31') AS 维表客户数,
    (SELECT COUNT(DISTINCT company_id) FROM customer."客户业务月度快照" WHERE snapshot_month = '2025-10-31') AS 快照客户数,
    (SELECT COUNT(*) FROM customer."客户业务月度快照" WHERE snapshot_month = '2025-10-31') AS 快照记录数,
    (SELECT COUNT(*) FROM customer."客户计划月度快照" WHERE snapshot_month = '2025-10-31') AS 计划快照记录数;
```

---

## 排障与开发调试建议

若在执行上述查询时，发现有任何状态字段、合并字段为 NULL 或没有聚合上，可以尝试结合项目机制设计这样排错：

1. **查源头没进来**：如果是跑 ETL 时 `Candidates found: 0`，那说明配路径 glob 规则被重命名结构卡主了，去放宽 `config/data_sources.yml` 即可。
2. **查解析未发生 (`CompanyId` 发错了 `IN*`)**：遇到大量的虚拟 ID 挂靠没对齐，可通过修改 `config/...` 中的干预字典或 `mapping` 层来"教"系统解析这一家企业（比如企业曾用名）。
3. **查推论失败（业务字段计算错误）**：去查对应领域下的 `src/work_data_hub/domain/*/pipeline_builder.py` 里那些 Dataframe `TransformStep` 的 Mapping (例如 `"业务类型": _apply_business_type_normalization`)。
4. **查聚合错误（主拓、标签、新老客没算对）**：核心去调整两个位置——若是业务入维度主表的问题，看 `config/foreign_keys.yml` (查里头的 type 是不是填错了，像 `concat_distinct` 或者 `max_by` 字段敲错了)；若是跑完业务进驾驶舱的数据快照错，则必改 `config/customer_status_rules.yml`。
5. **查合约状态异常**：如果 `contract_status` 全是 `NULL`，检查 `contract_status_sync` Hook 是否正常执行（看 CLI 日志中是否有 `Contract status sync completed`）。如果 Hook 被跳过，检查是否使用了 `--no-post-hooks` 参数。
6. **查快照状态与事实不匹配**：如果快照的 `is_winning_this_year` 为 `false` 但中标明细有记录，检查 `customer_status_rules.yml` 中 `is_winning_this_year` 规则配置的 `match_fields` 是否与明细表的实际列名对齐（特别是 `产品线代码` 字段名)）。
7. **查快照 `aum_balance = 0` 但规模明细有数据**：确认 `snapshot_month` 格式为月末日期（如 `2025-10-31`），SQL 中使用 `DATE_TRUNC('month', snapshot_month)` 与 `规模明细.月度` 匹配，两者日期格式必须对齐。

---

## 附录：配置驱动状态字段完整参考

### `customer_status_rules.yml` 评定规则映射

| 状态字段 | 配置算子类型 | 匹配源表 | 匹配粒度 | 匹配字段 |
|---|---|---|---|---|
| `is_winning_this_year` | `exists_in_year` | `customer."中标客户明细"` | ProductLine | `company_id` + `产品线代码` |
| `is_loss_reported` | `exists_in_year` | `customer."流失客户明细"` | ProductLine | `company_id` + `产品线代码` |
| `is_churned_this_year` | `exists_in_year` | `customer."流失客户明细"` | ProductLine | `company_id` + `产品线代码` |
| `is_churned_this_year_plan` | `exists_in_year` | `customer."流失客户明细"` | Plan | `company_id` + `年金计划号` |
| `is_new` | `status_reference` + `negation` | 派生 | ProductLine | `is_winning_this_year AND NOT BOOL_OR(is_existing)` |

> **注意**: `is_loss_reported` 已在规则配置中定义但当前快照表 `客户业务月度快照` 尚未包含此列，其 SQL 生成逻辑已就绪于 `StatusEvaluator`，待后续需求可直接启用。

### `foreign_keys.yml` 聚合算子对照表

| 算子类型 | 适用领域 | 目标字段 | 逻辑说明 |
|---|---|---|---|
| `max_by` | performance/award/loss/income | `主拓机构`、`主拓机构代码`、`关键年金计划` | 按规模最大值取对应记录 |
| `concat_distinct` | performance/award/loss/income | `管理资格`、`年金计划类型`、`其他年金计划`、`其他开拓机构` | 排重拼接 (separator: +/,/) |
| `count_distinct` | performance/award/loss/income | `关联计划数`、`关联机构数` | 统计唯一非空值 |
| `lambda` | performance/income | `年金客户标签` | 日期格式化 (如 `"2510新建"`) |
| `jsonb_append` | award/loss | `tags` | JSON数组追加 (如 `["2510中标"]`) |
| `template` | performance/award/loss/income | `年金客户类型` | 固定值赋值 (`新客`/`中标客户`/`流失客户`/`新客*`) |
