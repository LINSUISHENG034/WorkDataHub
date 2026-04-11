# Customer MDM Backfill Analysis

> Source of truth: `config/foreign_keys.yml`, `config/data_sources.yml`, `config/customer_status_rules.yml`, `src/work_data_hub/customer_mdm/`, `src/work_data_hub/cli/etl/hooks.py`
> Last verified: `2026-04-11`
> Scope: Current business interpretation of customer backfill and MDM status sources

## 1. 当前结论

客户主数据和客户状态并不是同一个层面的问题。

当前代码中的职责拆分是：

- 活动 ETL 域负责把事实数据写入各自主表
- `foreign_keys.yml` 驱动主数据回填到参考/主数据表
- Customer MDM 相关 hook 和服务再基于这些事实表与主数据表生成合同状态和月度快照

## 2. 当前活动域与客户回填

按当前配置，以下活动域都启用了回填：

- `annuity_performance`
- `annuity_income`
- `annual_award`
- `annual_loss`

这些域在 `config/data_sources.yml` 中都启用了 `requires_backfill`，并在 `config/foreign_keys.yml` 中定义了客户相关回填规则。

## 3. 当前客户相关数据层

从业务上可以把当前结构理解成三层：

### 事实层

- `business."规模明细"`
- `business."收入明细"`
- `customer."中标客户明细"`
- `customer."流失客户明细"`

### 主数据 / 参考层

- `customer."客户明细"`
- `mapping."年金计划"`
- `mapping."产品线"`

### 状态 / 快照层

- `customer."客户年金计划"`
- `customer."客户业务月度快照"`
- `customer."客户计划月度快照"`

## 4. 业务状态来源

当前 `customer_status_rules.yml` 明确了状态来源：

- `annuity_performance` 来源于 `business."规模明细"`
- `annual_award` 来源于 `customer."中标客户明细"`
- `annual_loss` 来源于 `customer."流失客户明细"`

因此，当前业务语义已经不是旧文档里那种“中标/流失尚未接入”或“只影响草案层”的状态。

## 5. 应如何理解这些状态

- `is_winning_this_year` 反映年度中标事实
- `is_loss_reported` 反映年度流失申报事实
- `is_churned_this_year` 反映基于当前规则判定的流失状态
- `is_new` 是基于已有状态推导出的组合状态

这些状态属于“分析与经营判断”层，不应该和客户主数据实体本身混成一张语义不清的表。

## 6. 当前文档应避免的旧说法

以下说法已经不适合继续作为现状描述：

- “annual_award / annual_loss 尚未配置回填”
- “需要未来再创建 customer_status_rules.yml”
- “customer_plan_contract 是当前核心落点”
- “中标/流失只停留在规划阶段”

这些内容在当前代码和配置里都已经不是事实。

## 7. 相关文档

- [数据处理指南](../reference/data_processing_guide.md)
- [数据库 Schema 概览](../reference/database-schema-panorama.md)
- [annuity_performance 域文档](../domains/annuity_performance.md)
- [annual_award 域文档](../domains/annual_award.md)
- [annual_loss 域文档](../domains/annual_loss.md)
