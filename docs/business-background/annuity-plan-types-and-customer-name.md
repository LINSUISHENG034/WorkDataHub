# 年金计划类型与客户名称业务背景

> Source of truth: `config/data_sources.yml`, `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`, `src/work_data_hub/domain/annuity_income/pipeline_builder.py`
> Last verified: `2026-04-11`
> Scope: Business semantics behind plan types and customer-name handling

## 1. 背景

`annuity_performance` 与 `annuity_income` 都处理年金业务明细，但客户识别并不总是直接来自 `客户名称` 字段。业务上，`计划类型` 会影响计划名称、客户名称以及后续 `company_id` 解析的可用线索。

## 2. 单一计划

单一计划的业务含义是一个计划主要对应单一企业客户。

常见特点：

- 计划名称通常更接近企业主体名称
- 即使 `客户名称` 为空，计划代码和计划名称仍可能提供有效识别线索
- 在技术实现中，计划代码、客户名称、计划名称提取结果、账户类字段都可能参与 `company_id` 解析

业务含义：

- `客户名称` 为空不一定代表数据错误
- 不能把“客户名称为空”直接等同于“无法识别客户”

## 3. 集合计划

集合计划的业务含义是一个计划可能承载多个企业参与方，计划名称更像产品或品牌标识，而不一定直接对应单一企业主体。

常见特点：

- 计划名称不应被简单视为企业全称
- 组合代码、计划代码、后续回填关系会比单纯的 `客户名称` 更重要
- 对集合计划来说，某些记录的 `company_id` 解析路径会天然更复杂

业务含义：

- 集合计划场景下，缺少直接客户名称并不罕见
- 需要接受“并非每条记录都能通过单一字段完成识别”的事实

## 4. 对 ETL 的影响

当前活动代码的处理重点不是“强行补齐客户名称”，而是尽量利用多种业务线索完成稳定解析：

- 计划代码
- 客户名称
- 计划名称可提取信息
- 年金账户类字段
- 共享 enrichment / cache 机制

这也是为什么 `annuity_performance` 与 `annuity_income` 都保留了围绕计划代码、客户名称和账户字段的派生与解析步骤。

## 5. 当前应坚持的业务认知

- `客户名称` 为空本身不是缺陷判定条件。
- 单一计划与集合计划不能使用完全相同的识别假设。
- 技术文档应把“识别策略”写成多线索解析，而不是单字段兜底。
- 具体解析优先级以当前代码实现为准，不应在业务背景文档里固化旧版本细节。

## 6. 相关文档

- [数据处理指南](../reference/data_processing_guide.md)
- [annuity_performance 域文档](../domains/annuity_performance.md)
- [annuity_income 域文档](../domains/annuity_income.md)
- [数据库 Schema 概览](../reference/database-schema-panorama.md)
