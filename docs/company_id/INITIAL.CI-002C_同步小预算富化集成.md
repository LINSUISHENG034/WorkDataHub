# INITIAL.CI-002C — 同步小预算富化集成（接入 annuity_performance）

目的：在不破坏现有 E2E 的前提下，为规模明细流程接入 Gateway，同步小预算在线查询；其余未命中入队队列并导出 CSV。

## FEATURE
- 新增开关：`WDH_ENRICH_COMPANY_ID=1` 开启同步富化；`WDH_ENRICH_SYNC_BUDGET=N` 限定每次运行在线查询额度。
- 在 `process_annuity_performance_op` 阶段调用 Gateway：按“内部优先”并在预算内触发在线查询；记录命中来源、预算消耗、unknown。
- 未命中：写入 `enterprise.enrichment_requests` + 导出 `./.wdh/staging/unresolved_company_ids.csv`。

## SCOPE
- In-scope：ops 集成点与统计输出；CSV 导出；预算控制逻辑；内部优先顺序（覆盖→参考/账户→名称索引→在线→入队→兜底）。
- Non-goals：不实现异步消费者；不改变 load/backfill 行为。

## VALIDATION
```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k enrich_sync

export WDH_DATA_BASE_DIR=tests/fixtures/sample_data/annuity_subsets
export WDH_ENRICH_COMPANY_ID=1
export WDH_ENTERPRISE_PROVIDER=stub
export WDH_ENRICH_SYNC_BUDGET=10
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --plan-only \
  --max-files 1 \
  --sheet "规模明细" \
  --debug
```

## ACCEPTANCE CRITERIA
- 预算严格生效；Summary 输出命中分布与 unknown；CSV 正确生成（若 unknown>0）。不开关时行为与现有 E2E 一致。

## RISKS
- 运行时抖动：在线查询失败不影响主流程，按未命中入队并记录错误。

