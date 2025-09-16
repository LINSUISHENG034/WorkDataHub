INITIAL — S-004 MVP 端到端验证（Definition of Ready）

本 INITIAL 将 S‑001 → S‑003 的成果在 annuity_performance 域内做一次端到端（E2E）集成验证，确保新方案与 legacy 等价，具备可观测性、可回退与可扩展性。此文档作为生成 PRP 的唯一输入，请严格按本文的路径、指令和边界执行。

---

## FEATURE

在 annuity_performance 处理流程中可选集成 CompanyEnrichmentService（company_id 统一解析：内部映射 → EQC（预算内）→ 队列 → 临时 ID），输出统计与对比报告，完成 MVP 级别的端到端验证。

## SCOPE
- In‑scope:
  - 在 `annuity_performance.service.py` 增加 enrichment 集成（可配置启用，默认关闭）
  - 在 `orchestration/ops.py` 的 `process_annuity_performance_op` 注入 enrichment 开关与预算参数
  - 在 `orchestration/jobs.py` 增加一个用于消费队列的 job/CLI 入口（利用现有 jobs 结构）
  - 统计与导出：输出 `EnrichmentStats`（各来源命中计数、耗时、预算使用），导出未解析样本 CSV（可选）
  - 与 legacy 结果对比的测试与报告（≥95% 一致性）
  - 覆盖错误场景：EQC 不可用、预算耗尽、DB 失败时的优雅降级

- Non‑goals:
  - 不改动其他域逻辑，不做历史全量回填
  - 不实现 Web/UI 或复杂报表，仅 CLI + CSV
  - 不做生产环境部署与运维，保持 CLI‑first

## CONTEXT SNAPSHOT

```bash
src/work_data_hub/
  domain/
    annuity_performance/
      service.py                   # 集成点（新增 enrichment 可选注入）
    company_enrichment/
      service.py                   # S‑003：统一解析服务
      models.py                    # 结果/状态/请求模型
      lookup_queue.py              # S‑003：队列 DAO
  io/
    loader/
      company_enrichment_loader.py # 缓存 UPSERT
  orchestration/
    ops.py                         # 修改 process_annuity_performance_op（新增配置）
    jobs.py                        # 增加/暴露 队列处理 job 入口
  config/
    settings.py                    # 已有 WDH_* 配置，沿用/扩展
scripts/
  create_table/
    ddl/
      lookup_requests.sql          # S‑003 DDL（已实现，需应用在本地 DB）
```

## EXAMPLES（要镜像的实现/测试风格）
- Path: `src/work_data_hub/domain/annuity_performance/service.py`
  - 集成模式：在现有按行处理逻辑中调用 `CompanyEnrichmentService.resolve_company_id(...)`，再写回 `row["company_id"]`
- Path: `src/work_data_hub/orchestration/ops.py`
  - 参考现有 `*_op` 配置模式，新增 enrichment 相关配置项与输出（stats/report）
- Path: `tests/domain/company_enrichment/test_enrichment_service.py`
  - Mock/断言风格与状态枚举沿用
- Path: `legacy/annuity_hub/data_handler/data_cleaner.py`
  - 对照 legacy 命中逻辑进行一致性对比

示例（集成片段原型）：
```python
# in src/work_data_hub/domain/annuity_performance/service.py

def process_annuity_performance_rows(
    rows: list[dict],
    enrichment_service: CompanyEnrichmentService | None = None,
    *,
    sync_lookup_budget: int = 0,
    export_unknown_names: bool = True,
) -> ProcessingResultWithEnrichment:
    stats = EnrichmentStats()
    unknowns: list[str] = []

    for row in rows:
        if enrichment_service:
            res = enrichment_service.resolve_company_id(
                plan_code=row.get("计划代码"),
                customer_name=row.get("客户名称"),
                account_name=row.get("年金账户名"),
                sync_lookup_budget=sync_lookup_budget,
            )
            row["company_id"] = res.company_id
            stats.record(res.status, res.source)
            if not res.company_id and row.get("客户名称"):
                unknowns.append(str(row.get("客户名称")))
        # 保持原有处理逻辑...

    csv_path = None
    if export_unknown_names and unknowns:
        csv_path = write_unknowns_csv(unknowns)  # 放在标准输出目录

    return ProcessingResultWithEnrichment(
        # 继承原有字段...
        enrichment_stats=stats,
        unknown_names_csv=csv_path,
    )
```

## DOCUMENTATION
- File: `docs/company_id/simplified/S-001_Legacy映射迁移.md`
- File: `docs/company_id/simplified/S-002_EQC客户端集成.md`
- File: `docs/company_id/simplified/S-003_基础缓存机制.md`
- File: `docs/company_id/simplified/S-004_MVP端到端验证.md`（本任务主文档）
- File: `src/work_data_hub/config/settings.py`（WDH_* 配置）
- File: `scripts/create_table/ddl/lookup_requests.sql`（DDL）

## INTEGRATION POINTS
- Data models（新增/扩展）
  - `EnrichmentStats`：计数/耗时/预算使用
  - `ProcessingResultWithEnrichment(ProcessingResult)`：增加 `enrichment_stats` 和 `unknown_names_csv`
- Database
  - 复用 `enterprise.company_mapping`（缓存）与 `enterprise.lookup_requests`、`enterprise.temp_id_sequence`
  - 确保在本地测试库执行 `scripts/create_table/ddl/lookup_requests.sql`
- Config/ENV（沿用并扩展）
  - `WDH_COMPANY_ENRICHMENT_ENABLED`（默认 false）
  - `WDH_ENRICHMENT_SYNC_BUDGET`（默认 0）
  - `WDH_ENRICHMENT_EXPORT_UNKNOWNS`（默认 true）
- Ops/Jobs（CLI）
  - 在 `process_annuity_performance_op` 中新增 config schema：`enrichment_enabled`、`enrichment_sync_budget`、`export_unknown_names`
  - 在 `jobs.py` 增加 `process_company_lookup_queue` job（批量消费队列，使用已有 service+queue+loader 结构）

## DATA CONTRACTS
```python
from pydantic import BaseModel, Field
from typing import Optional

class EnrichmentStats(BaseModel):
    total_records: int = 0
    success_internal: int = 0
    success_external: int = 0
    pending_lookup: int = 0
    temp_assigned: int = 0
    failed: int = 0
    sync_budget_used: int = 0
    processing_time_ms: int = 0

class ProcessingResultWithEnrichment(ProcessingResult):
    enrichment_stats: EnrichmentStats
    unknown_names_csv: Optional[str] = None
```

```bash
# ENV（建议默认值）
WDH_COMPANY_ENRICHMENT_ENABLED=0
WDH_ENRICHMENT_SYNC_BUDGET=5
WDH_ENRICHMENT_EXPORT_UNKNOWNS=1
```

## GOTCHAS & LIBRARY QUIRKS
- enrichment 代码必须是“可插拔”的：默认关闭时对现有流程零影响
- 同步 EQC 查询严格受预算控制；错误降级到入队或临时 ID，不中断主流程
- 导出 CSV 路径与现有输出目录保持一致；注意文件名去重与编码
- 与 legacy 对比时需统一空值口径（None/空串）
- 队列消费要支持幂等与可中断重试
- 日志字段避免使用保留键（如 LogRecord 的 `name`），统一使用 `company_name`

## IMPLEMENTATION NOTES
- 保持现有函数签名与返回结构兼容（在原有结构上“加字段”而非“改结构”）
- 依赖注入 CompanyEnrichmentService；在 ops 层按配置开关与预算初始化
- 复用 `settings.py` 的 WDH_* 模式；不新增破坏性配置
- 阶段性打印/记录统计（stats）便于 E2E 验证与回归定位
- 不引入新的外部依赖

## VALIDATION GATES（必须通过）
```bash
# 语法/类型/测试（最小集合）
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# S‑003/S‑004 聚焦测试
uv run pytest -v -k "company_enrichment or enrichment_service or lookup_queue"

# 端到端需要 DB 与样本数据（可选）
export WDH_DATABASE__URI=postgresql://user:pass@host:5432/db
psql "$WDH_DATABASE__URI" -f scripts/create_table/ddl/lookup_requests.sql

export WDH_COMPANY_ENRICHMENT_ENABLED=1
export WDH_ENRICHMENT_SYNC_BUDGET=5
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute --max-files 1 \
  --mode append --debug \
  --enrichment-enabled \
  --enrichment-sync-budget 5

# 队列消费（验证异步处理路径）
uv run python -m src.work_data_hub.orchestration.jobs \
  --job process_company_lookup_queue \
  --execute --debug
```

## ACCEPTANCE CRITERIA
- 功能
  - [ ] enrichment 可选启用，默认关闭且不影响既有流程
  - [ ] 内部映射命中率与 legacy 基本一致（>95%）
  - [ ] 同步 EQC 在预算内工作，超预算入队
  - [ ] 队列消费成功处理 pending 请求；错误不阻塞
  - [ ] 生成统计报告并（可选）导出未解析名称 CSV
- 性能
  - [ ] enrichment 开启后处理时间增长 < 50%
  - [ ] 同步查询单次响应 < 5 秒（在测试环境）
- 质量
  - [ ] 与 legacy 对比一致性 > 95%
  - [ ] 错误路径不影响主流程（降级到队列或临时 ID）
- 运维
  - [ ] 支持 plan‑only 预览与 CLI 参数帮助
  - [ ] 通过 WDH_* 环境变量即可开关与调参

## ROLLOUT & RISK
- Rollout（按阶段）：
  1) 测试环境验证（关闭 EQC）→ 2) 小额度启用（预算=5）→ 3) 队列消费验证 → 4) 是否推广到其他域
- 风险与缓解：
  - 数据一致性：用对比测试与灰度开关控制；保留回退
  - 性能：严格预算与异步降级；统计开销用于优化
  - 外部依赖：EQC 不可用时降级（入队/临时 ID）
  - 操作复杂：CLI‑first，避免额外运行时组件

## APPENDICES（可选片段）
```python
# 测试骨架参考
import pytest

def test_enrichment_off_keeps_baseline():
    # Arrange: enrichment_enabled=False
    # Act: run pipeline
    # Assert: baseline behavior unchanged
    assert True

@pytest.mark.e2e
def test_annuity_performance_with_enrichment_e2e():
    # Arrange: enable enrichment + sync budget
    # Act: run job with one sample file
    # Assert: stats present and budget respected
    assert True
```

```bash
# 搜索帮助（ripgrep）
rg "def process_annuity_performance_rows" src/
rg "CompanyEnrichmentService" src/
rg "process_company_lookup_queue" src/
```
