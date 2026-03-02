# WorkDataHub 数据处理指南（已核验）

> 目标：让新用户在 10~15 分钟内看懂项目当前的数据处理链路与关键字段规则。  
> 核验基线：`config/data_sources.yml`、`config/foreign_keys.yml`、`config/customer_status_rules.yml`、`src/work_data_hub/orchestration/*`、`src/work_data_hub/domain/*/pipeline_builder.py`、`src/work_data_hub/customer_mdm/*`。

---

## 1. 先看全局：一条 ETL 任务实际发生了什么

默认单域任务（`python -m work_data_hub.cli etl --domains <domain> ...`）走这条链路：

1. `discover_files_op`：按 `config/data_sources.yml` 发现输入文件。
2. `read_data_op`：读取 Excel/CSV（支持单 Sheet、多 Sheet 合并、采样）。
3. `process_domain_op_v2`：按 domain 注册服务做 Bronze → Silver 清洗。
4. `generic_backfill_refs_op`：按 `config/foreign_keys.yml` 做维表回填（若配置存在）。
5. `gate_after_backfill`：等待回填完成后再放行事实表加载。
6. `load_op`：写入目标表（默认 `delete_insert`，可改 `append`）。
7. Post-ETL Hooks：仅 `annuity_performance` 会触发（合同同步、年初初始化、快照刷新）。

关键分支：
- `--execute` 不传时默认是 plan-only（不落库）。
- `sandbox_trustee_performance` 在 `max-files > 1` 时走多文件专用 op。
- `generic_backfill_refs_op` 总会被调用，但无配置时会直接返回 0 操作。

---

## 2. 当前支持的数据域（Domain）

| Domain | 输入文件/Sheet | 输出表 | 刷新键（PK） | FK 回填 |
|---|---|---|---|---|
| `annuity_performance` | `*规模收入数据*.xlsx` / `规模明细` | `business."规模明细"` | `月度 + 业务类型 + 计划类型` | 是 |
| `annuity_income` | `*规模收入数据*.xlsx` / `收入明细` | `business."收入明细"` | `月度 + 业务类型 + 计划类型` | 是 |
| `annual_award` | `*台账登记*.xlsx`/`*当年中标*.xlsx`，多 Sheet 合并 | `customer."中标客户明细"` | `上报月份 + 业务类型` | 是 |
| `annual_loss` | `*台账登记*.xlsx`/`*当年流失*.xlsx`，多 Sheet 合并 | `customer."流失客户明细"` | `上报月份 + 业务类型` | 是 |
| `sandbox_trustee_performance` | `**/*受托业绩*.xlsx` | `sandbox."sandbox_trustee_performance"` | 调度场景默认 `report_date + plan_code + company_code` | 通常无有效配置 |

补充：
- 文件发现层同时受 `version_strategy`（版本目录选择）与 `selection_strategy`（同目录多文件时怎么选）影响。`selection_strategy` 默认 `error`，不是自动“最新”。

---

## 3. 通用关键字段规则（跨域）

### 3.1 文件与日期
- `base_path` 支持 `{YYYYMM}`/`{YYYY}`/`{MM}`；含模板时必须传 `--period`。
- 日期解析统一走 `parse_chinese_date`/`parse_yyyymm_or_chinese`，常见格式如 `202601`、`2026-01`、`2026年1月`。

### 3.2 机构与产品线
- `机构名称 -> 机构代码` 使用 `COMPANY_BRANCH_MAPPING`，未命中默认 `G00`。
- `业务类型 -> 产品线代码` 使用 `BUSINESS_TYPE_CODE_MAPPING`（如 `企年受托->PL202`，`企年投资->PL201`）。

### 3.3 计划与组合
- `计划代码`先做 typo 修正（如 `1P0290->P0290`），空值按 `计划类型`填默认：集合 `AN001`、单一 `AN002`。
- `组合代码`会去掉前缀 `F/f`；空值按业务/计划类型填默认（如 `QTAN001/QTAN002/QTAN003`）。

### 3.4 客户与 company_id
- 客户名先做清洗标准化，再进行 `company_id` 解析。
- 解析优先级：YAML 覆盖 → DB 缓存 → 源字段已有 ID → EQC 同步查找（需显式启用）→ 临时 ID（`IN...`）。
- 对空客户名/占位值（如 `0`、`空白`）不生成临时 ID，保持空值。

### 3.5 事实加载（load_op）
- 默认模式是 `delete_insert`（先按 PK 删除，再批量插入），并非 ON CONFLICT upsert。
- 可选 `append`；`delete_insert` 必须有 PK。

---

## 4. 各 Domain 的“特有规则”

### 4.1 `annuity_performance`

核心流水线共 13 步（映射、派生、清洗、ID 解析、删遗留列），关键规则：
- 清洗前先保留原客户名：`年金账户名 = 客户名称`。
- `集团企业客户号`会去掉前缀 `C`，并派生 `年金账户号`。
- `期末资产规模`是后续 `fk_customer` 中 `max_by` 选择“主拓机构/关键计划”的主权重字段。

### 4.2 `annuity_income`

关键规则：
- 当 `计划类型=单一计划` 且 `客户名称`为空时，尝试从 `计划名称`提取：`{企业名}企业年金计划 -> {企业名}`。
- `固费/浮费/回补/税` 空值统一补 `0`。
- `fk_customer` 相关 `max_by` 权重使用 `固费`（本域无 `期末资产规模`）。

### 4.3 `annual_award`

关键规则：
- `业务类型`标准化：`受托->企年受托`，`投资/投管->企年投资`。
- `计划类型`标准化：`集合->集合计划`，`单一->单一计划`。
- 从 `上报客户名称`生成清洗后的 `客户名称`。
- `年金计划号`补齐分两段：
  1) 若有 DB 连接，按 `company_id + 产品线代码`查 `customer."客户年金计划"`，集合优先 `P*`，单一优先 `S*`；
  2) 仍为空则默认填 `AN001/AN002`。

### 4.4 `annual_loss`

与 `annual_award` 基本镜像，差异主要是日期字段与标签语义：
- 日期字段是 `流失日期`。
- 客户标签语义是“流失”而非“中标”。

### 4.5 `sandbox_trustee_performance`

这是轻量沙箱域，主要用于调度/样例链路验证：
- 关键字段：`report_date`、`plan_code`、`company_code`。
- 通过 Pydantic 做强校验与规范化，通常不走主数据回填链路。

---

## 5. FK 回填规则（`config/foreign_keys.yml`）

### 5.1 回填目标概览
- `annuity_performance`：`fk_plan -> fk_portfolio -> fk_product_line -> fk_organization -> fk_customer`
- `annuity_income`：同上，但客户聚合权重改为 `固费`
- `annual_award`：仅 `fk_customer`
- `annual_loss`：仅 `fk_customer`

### 5.2 常用聚合器
- `first`：首个非空值
- `max_by(order_column)`：按权重列选值
- `concat_distinct`：去重拼接
- `count_distinct`：去重计数
- `template`：模板赋值（可做常量）
- `lambda`：自定义表达式
- `jsonb_append`：向 JSONB 数组追加（如 `tags`）

### 5.3 客户标签字段
- `annuity_performance`：`tags` 追加 `YYMM新建`；`年金客户类型` 写 `新客`
- `annuity_income`：`tags` 同上；`年金客户类型` 当前配置值为 `新客*`
- `annual_award`：`tags` 追加 `YYMM中标`；`年金客户类型=中标客户`
- `annual_loss`：`tags` 追加 `YYMM流失`；`年金客户类型=流失客户`

注意（实现细节）：
- `skip_blank_values` 已在配置模型中定义，但当前通用回填实现主要过滤 NULL/空字符串，不会自动按 `IN*` 前缀剔除临时 ID。

---

## 6. Post-ETL：合同状态与月度快照

仅 `annuity_performance` 成功后触发，顺序固定：

1. `contract_status_sync`（SCD2）
   - 来源：`business."规模明细"`
   - 目标：`customer."客户年金计划"`
   - 状态规则：
     - `正常`：`期末资产规模>0` 且 `12个月滚动供款>0`
     - `停缴`：其余情况
   - `is_strategic`：阈值或分支 TopN，且有“只升不降”（Ratchet）。
   - `is_existing`：按“前一年 12 月是否有资产记录”。

2. `year_init`（仅 1 月）
   - 年初初始化 `is_strategic/is_existing`。

3. `snapshot_refresh`
   - 刷新两张快照：
     - `customer."客户业务月度快照"`（company + product_line）
     - `customer."客户计划月度快照"`（company + plan + product_line）
   - 状态逻辑由 `config/customer_status_rules.yml` 生成 SQL（`StatusEvaluator`）。

---

## 7. 新用户最常用命令

```bash
# 1) 先做计划预览（不落库）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance --period 202601

# 2) 单域执行（落库）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance --period 202601 --execute

# 3) 多域执行
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annuity_performance,annuity_income,annual_award,annual_loss \
  --period 202601 --execute

# 4) 指定文件直跑（跳过自动发现）
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
  --domains annual_award --file data/real_data/202601/收集数据/业务收集/台账登记.xlsx --execute

# 5) 手工重跑客户主数据后处理
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm sync --period 202601
uv run --env-file .wdh_env python -m work_data_hub.cli customer-mdm snapshot --period 202601
```

---

## 8. 排障顺序（建议按此顺序）

1. 看 `config/data_sources.yml`：路径模板、文件 pattern、sheet 配置是否对。
2. 看对应 `pipeline_builder.py`：字段映射、默认值、清洗步骤顺序。
3. 看 `config/foreign_keys.yml`：是否有该域回填配置、聚合权重列是否存在。
4. 看 `load_op` 配置：目标表名、mode、PK 是否匹配。
5. 看 Post-ETL：只在 `annuity_performance` 触发，且 Hook 失败不会回滚事实加载。

---

## 9. 这份文档的“真相源文件”

- 域发现与输出：`config/data_sources.yml`
- FK 回填：`config/foreign_keys.yml`
- 客户状态规则：`config/customer_status_rules.yml`
- 作业编排：`src/work_data_hub/orchestration/jobs.py`
- 通用 op：`src/work_data_hub/orchestration/ops/`
- 各域流水线：`src/work_data_hub/domain/*/pipeline_builder.py`
- company_id 解析：`src/work_data_hub/infrastructure/enrichment/resolver/`
- 合同同步与快照：`src/work_data_hub/customer_mdm/`

> 若代码与本文不一致，以以上文件为准，并优先更新本文。
