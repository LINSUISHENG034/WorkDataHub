# INITIAL.CI-002E — 可观测性与运营指标（命中率提升验证）

目的：提供跨运行对比与运营指标，验证“同步小预算 + 异步回填”带来的实际命中率提升与未解析收敛。

## FEATURE
- 增加统计输出：
  - 命中来源分布（overrides/plan_ref/account/name/sync/unknown）
  - 同步预算消耗/溢出入队数
  - 队列规模变化、回填成功率、缓存命中新增量
- 导出审计文件：`unresolved_company_ids.csv`（附最近月度与出现次数）。

## SCOPE
- In-scope：统一日志键/格式；运行结束打印“CompanyId Enrichment Summary”；审计 CSV 字段规范。
- Non-goals：不接入外部 APM/Tracing；不做长期留存仓（仅本地或目标库统计表可选）。

## VALIDATION
```bash
uv run pytest -v -k enrichment_summary

# 流程示例：
# 1) 首次执行主作业（开启富化，使用 stub），记录 unknown 与命中分布
# 2) 执行回填作业（消费队列，更新缓存）
# 3) 二次执行主作业，对比 unknown 下降与命中上升
```

## ACCEPTANCE CRITERIA
- Summary 结构稳定（字段/顺序固定），便于测试断言；二次运行 unknown 显著下降；CSV 内容字段正确且可复核样本。

## RISKS
- 样本波动：在测试中固定输入数据集；指标以相对变化为主。

