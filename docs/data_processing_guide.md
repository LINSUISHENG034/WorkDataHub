# WorkDataHub 数据处理指南

> 目标：让新用户在 15 分钟内看懂项目当前的数据处理链路、核心机制与关键字段规则。  
> 核验基线：`config/data_sources.yml`、`config/foreign_keys.yml`、`config/customer_status_rules.yml`、`src/work_data_hub/orchestration/*`、`src/work_data_hub/domain/*/pipeline_builder.py`、`src/work_data_hub/customer_mdm/*`。

文档结构遵循"由浅入深、由面到点"的原则，依次介绍整体调度架构、核心系统机制、各业务领域的特定处理细节，以及快照与状态评定全貌。

---

## 1. 整体架构概述（面：宏观视角）

项目采用了基于 [Dagster](https://dagster.io/) 的声明式数据编排引擎。为了提高代码复用率和系统扩展性，所有业务领域均接入了统一的泛化执行作业 `generic_domain_job`。

一次完整的数据流转生命周期包含以下 6 个关键阶段：

1. **发现文件 (`discover_files_op`)**
   根据 `config/data_sources.yml` 中的配置项（匹配规则、排除规则），扫描指定路径下的 Excel 报告。在存在多版本文件时，默认采用版本号最大（最高）的内容。
2. **数据读取 (`read_data_op`)**
   统一抽取 Excel 数据。对于需要跨多 Sheet 工作（比如中标/流失分为了"受托"和"投资"两个 Sheet 页）的领域，支持自动多 Sheet 合并解析。
3. **领域流水线处理 (`process_domain_op_v2`)**
   进入各领域专属的 Bronze → Silver（原始到清洗后）数据转换流水线。这一步负责字段重命名、业务规则转换、以及极重要的 **MDM 企业标识解析 (Company ID Resolution)**。
4. **外键维度回填 (`generic_backfill_refs_op`)**
   以配置文件 `config/foreign_keys.yml` 驱动，自动将流水线处理中产出的新维度关联据（如新的客户、计划、组织等）向各个中心维表执行回填操作，保证系统的雪花/星型模型维度完整。
5. **关卡校验 (`gate_after_backfill`)**
   控制流程，确保维表彻底回填完成后，才进行最终的业务事实数据入库。
6. **最终入库 (`load_op`)**
   基于联合主键（在 `data_sources.yml` 中的 `pk` 属性定义），对主业务表进行幂等性的 UPSERT（更新或插入）操作。默认模式是 `delete_insert`（先按 PK 删除，再批量插入），并非 ON CONFLICT upsert；可选 `append`。

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
- 文件发现层同时受 `version_strategy`（版本目录选择）与 `selection_strategy`（同目录多文件时怎么选）影响。`selection_strategy` 默认 `error`，不是自动"最新"。

---

## 3. 核心系统机制（中：机制视角）

在 Bronze → Silver 的转换与维表回填过程中，项目构建了两个极其重要的高级复杂机制：

### 3.1 MDM 企业标识解析机制 (Company ID Resolution)

各领域的数据通常只有源系统录入的机构名称（可能含有错别字、简称或曾用名）。流水线中的 `CompanyIdResolutionStep` 组件负责将这些脏名称解析为唯一的 `company_id`。

**解析优先级路由：**
1. **YAML 强制覆盖**：最高优先级，查阅人工配置的映射字典（`config/mappings/company_id/`）处理特殊挂靠或曾用名。
2. **本地 DB 缓存匹配**：基于以往的准确命中历史记录直接解析。
3. **EQC（天眼查/企查查 API）搜索**：调用外部服务进行模糊匹配、全称补齐获取法定企业 ID（需显式启用，内网环境使用 `--no-enrichment` 跳过）。
4. **生成临时 ID**：所有手段耗尽后，生成形如 `IN*` 的临时内部 ID 保障流程不断连。对空客户名/占位值（如 `0`、`空白`）不生成临时 ID，保持空值。

### 3.2 高级聚合维表回填机制 (FK Backfill System)

参考 `config/foreign_keys.yml` 的配置，当检测到明细宽表中出现了新的主数据维（如出现了新计划、组合、尤其是客户时），系统会根据 `insert_missing` 的原则自动回填更新各张 Master 表（如 `组织架构`表、`客户明细`表）。

**回填目标概览：**
- `annuity_performance`：`fk_plan -> fk_portfolio -> fk_product_line -> fk_organization -> fk_customer`
- `annuity_income`：同上，但客户聚合权重改为 `固费`
- `annual_award`：仅 `fk_customer`
- `annual_loss`：仅 `fk_customer`

**该机制支持极复杂的聚合运算以浓缩宽表信息到主数据中：**

| 聚合器 | 说明 | 示例 |
|--------|------|------|
| `first` | 首个非空值 | |
| `max_by(order_column)` | 按权重列取最大值对应条目 | "主拓机构"按 `期末资产规模` 推举管理规模最大的分公司 |
| `concat_distinct` | 排重拼接 | 一个客户的多种标签（`受托+投资+投管`） |
| `count_distinct` | 去重计数 | 某客户名下的关联计划总数 |
| `template` | 模板赋值（可做常量） | |
| `lambda` | 自定义表达式 | 将月份加工为 `2510中标` 等标签 |
| `jsonb_append` | 向 JSONB 数组追加 | `tags` 字段追加时间戳标签 |

**客户标签字段配置：**
- `annuity_performance`：`tags` 追加 `YYMM新建`；`年金客户类型` 写 `新客`
- `annuity_income`：`tags` 同上；`年金客户类型` 当前配置值为 `新客*`
- `annual_award`：`tags` 追加 `YYMM中标`；`年金客户类型=中标客户`
- `annual_loss`：`tags` 追加 `YYMM流失`；`年金客户类型=流失客户`

注意（实现细节）：
- `skip_blank_values` 已在配置模型中定义，但当前通用回填实现主要过滤 NULL/空字符串，不会自动按 `IN*` 前缀剔除临时 ID。

---

## 4. 通用关键字段规则（跨域）

### 4.1 文件与日期
- `base_path` 支持 `{YYYYMM}`/`{YYYY}`/`{MM}`；含模板时必须传 `--period`。
- 日期解析统一走 `parse_chinese_date`/`parse_yyyymm_or_chinese`，常见格式如 `202601`、`2026-01`、`2026年1月`。

### 4.2 机构与产品线
- `机构名称 -> 机构代码` 使用 `COMPANY_BRANCH_MAPPING`，未命中默认 `G00`。
- `业务类型 -> 产品线代码` 使用 `BUSINESS_TYPE_CODE_MAPPING`（如 `企年受托->PL202`，`企年投资->PL201`）。

### 4.3 计划与组合
- `计划代码`先做 typo 修正（如 `1P0290->P0290`），空值按 `计划类型`填默认：集合 `AN001`、单一 `AN002`。
- `组合代码`会去掉前缀 `F/f`；空值按业务/计划类型填默认（如 `QTAN001/QTAN002/QTAN003`）。

### 4.4 客户与 company_id
- 客户名先做清洗标准化，再进行 `company_id` 解析（详见 [3.1 节](#31-mdm-企业标识解析机制-company-id-resolution)）。

---

## 5. 各域特有规则（点：微观视角）

虽然享有相同的引擎骨架，但由于业务属性不同，各域在 `pipeline_builder.py`（转换逻辑）及回填配置上有各自特有行为：

### 5.1 `annuity_performance`（规模明细）

代表了持续在管的月度全量业务基底，数据体量大且最为核心。

核心流水线共 13 步（映射、派生、清洗、ID 解析、删遗留列），关键规则：
- 清洗前先保留原客户名：`年金账户名 = 客户名称`。
- `集团企业客户号`会去掉前缀 `C`，并派生 `年金账户号`。
- `期末资产规模`是后续 `fk_customer` 中 `max_by` 选择"主拓机构/关键计划"的**核心权重字段**——这是 MDM 系统判定全公司"主渠道、大本营"的算力依据。

### 5.2 `annuity_income`（收入明细）

关键规则：
- 当 `计划类型=单一计划` 且 `客户名称`为空时，尝试从 `计划名称`提取：`{企业名}企业年金计划 -> {企业名}`。
- `固费/浮费/回补/税` 空值统一补 `0`。
- `fk_customer` 相关 `max_by` 权重使用 `固费`（本域无 `期末资产规模`）。

### 5.3 `annual_award`（当年中标）

记录公司新辟疆土、获取的新账户。与存量不同，这个领域经常缺少完整年金计划号，只有宽泛的计划类型（单一/集合）和金额。

关键规则：
- `业务类型`标准化：`受托->企年受托`，`投资/投管->企年投资`。
- `计划类型`标准化：`集合->集合计划`，`单一->单一计划`。
- 从 `上报客户名称`生成清洗后的 `客户名称`。
- **独有清洗逻辑 (`PlanCodeEnrichmentStep`)**：当宽表中缺少"年金计划号"时，会拿着解好的 `company_id` 去反查主数据系统（`客户年金计划`表）。带有智能推断逻辑：集合计划优先抓取前缀为 **"P"** (Pooled) 的计划号，单一计划优先抓取 **"S"** (Single)；仍为空则默认填 `AN001/AN002`。
- 回填时采用 `计划规模` 作为 `max_by` 权重，并通过 `lambda` 向客户 MDM 追加 **"中标客户"** 及时间戳标签（如 `2510中标`）。

### 5.4 `annual_loss`（当年流失）

主要处理退费、销局的客户记录。与 `annual_award` 在构型上高度镜像，差异主要是：
- 日期字段是 `流失日期`。
- 同样使用 `PlanCodeEnrichmentStep` 反查并补齐缺失的年金计划号。
- 回填时自动为退出实体打上 **"流失客户"** 及时间戳标签（如 `2510流失`），丰富后续防流失挽回分析的洞察力。

### 5.5 `sandbox_trustee_performance`（沙箱受托业绩）

轻量沙箱域，主要用于调度/样例链路验证：
- 关键字段：`report_date`、`plan_code`、`company_code`。
- 通过 Pydantic 做强校验与规范化，通常不走主数据回填链路。

---

## 6. Post-ETL：合同状态与月度快照

仅 `annuity_performance` 成功后触发，顺序固定：

### 6.1 `contract_status_sync`（SCD2）
- 来源：`business."规模明细"`
- 目标：`customer."客户年金计划"`
- 状态规则：
  - `正常`：`期末资产规模>0` 且 `12个月滚动供款>0`
  - `停缴`：其余情况
- `is_strategic`：阈值或分支 TopN，且有"只升不降"（Ratchet）。
- `is_existing`：按"前一年 12 月是否有资产记录"。

### 6.2 `year_init`（仅 1 月）
- 年初初始化 `is_strategic/is_existing`。

### 6.3 `snapshot_refresh`（月度快照刷新）

在各领域数据完成 ETL 并回填到核心维度后，基于 `customer."客户年金计划"` 表自动生成月度快照：

1. **客户业务月度快照** (`ProductLine` 粒度)：判定客户在具体产品线（如"企年受托"、"企年投资"）上的最终业务状态标签与总规模。
2. **客户计划月度快照** (`Plan` 粒度)：更细化地观察单个年金计划的具体盈亏与合同状态。

### 6.4 关键客户状态判定逻辑 (Config-driven Status Evaluation)

系统避免了硬编码判断客户"是新客还是流失客"，而是通过纯配置驱动 (`config/customer_status_rules.yml`) 结合 `StatusEvaluator` 引擎自动生成评定规则：

| 状态字段 | 评定逻辑 |
|----------|----------|
| **is_winning_this_year** (新中标) | `exists_in_year` 算子检测该客户在当年 `中标客户明细` 中是否存在记录 |
| **is_loss_reported** (申报流失) | 检测当年 `流失客户明细` 中是否存在报备 |
| **is_churned_this_year** (已流失) | 灵活支持业务级（产品线全退）或计划级判定 |
| **is_new** (新客到账) | 组合算子：`is_winning_this_year = True` 且 `is_existing = False` |
| **aum_balance** (月度确权 AUM) | 跨 schema 下沉查询 `business."规模明细"` 按 `company_id + 产品线代码` 执行 `SUM(期末资产规模)` |

> **点金**：三大业务流负责制造与清洗（入湖），MDM 系统负责拉通孤岛（关联），而**月度快照与状态评估机制**最终把异构系统的数据拍在一个时间切片上，生产出能直接服务于管理驾驶舱分析的终端成果。

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

> 💡 完整的 CLI 参数说明请参阅 [部署与运行指南](deployment_run_guide.md)。

---

## 8. 排障顺序（建议按此顺序）

1. **看文件漏读或错读**：查 `config/data_sources.yml` 的 glob path 规则、多 Sheet 配置与文件选择策略。
2. **看业务字段计算不对（如日期没解出、业务类型张冠李戴）**：查对应领域下的 `src/work_data_hub/domain/[domain名]/pipeline_builder.py` 里定义的 Bronze → Silver DataFrame Transform Steps。
3. **看中心维表没更新、主数据抓错了大头（比方说某客户归属分公司不对）**：查 `config/foreign_keys.yml` 里的 Aggregation 聚合引擎规则与 `max_by` 参照系（多数为规模大小）。
4. **看 `load_op` 配置**：目标表名、mode、PK 是否匹配。
5. **看 Post-ETL**：只在 `annuity_performance` 触发，且 Hook 失败不会回滚事实加载。

---

## 9. 真相源文件索引

| 职责 | 文件路径 |
|------|----------|
| 域发现与输出 | `config/data_sources.yml` |
| FK 回填 | `config/foreign_keys.yml` |
| 客户状态规则 | `config/customer_status_rules.yml` |
| 作业编排 | `src/work_data_hub/orchestration/jobs.py` |
| 通用 op | `src/work_data_hub/orchestration/ops/` |
| 各域流水线 | `src/work_data_hub/domain/*/pipeline_builder.py` |
| company_id 解析 | `src/work_data_hub/infrastructure/enrichment/resolver/` |
| 合同同步与快照 | `src/work_data_hub/customer_mdm/` |
| EQC 匹配置信度 | `config/eqc_confidence.yml` |
| 客户 MDM 配置 | `config/customer_mdm.yaml` |

> 若代码与本文不一致，以上述源文件为准，并优先更新本文。
