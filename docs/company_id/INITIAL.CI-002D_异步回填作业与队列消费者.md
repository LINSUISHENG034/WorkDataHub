# INITIAL.CI-002D — 异步回填作业与队列消费者（CLI）

目的：实现独立 CLI 消费 `enterprise.enrichment_requests` 队列，调用 Provider/Gateway 批量查询并更新缓存，形成闭环。

## FEATURE
- 新增 CLI 入口（作业或独立模块）：消费 pending→processing→done/failed；失败累计 attempts，记录 last_error。
- 与 Gateway 对接：命中后 upsert `company_master` 与 `company_name_index`。
- 输出回填报告：处理数、成功/失败、命中新增量、错误摘要。

## SCOPE
- In-scope：消费者循环、批量拉取与限速、幂等 upsert；最小日志与退出码。
- Non-goals：不实现复杂调度；不涉及 UI/守护进程部署。

## VALIDATION
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k enrich_async

export WDH_DATABASE__URI=postgresql://user:pwd@host:5432/db
export WDH_ENTERPRISE_PROVIDER=stub
uv run python -m src.work_data_hub.orchestration.jobs \
  --execute \
  --job enrich_company_master \
  --debug
```

## ACCEPTANCE CRITERIA
- 可消费并更新缓存；失败可重试；报告指标完整；对后续主作业命中率有提升（验证见 CI-002E）。

## RISKS
- 锁与并发：单实例消费者；多实例场景后续再议，先保持 KISS。

