# INITIAL — S-003 基础缓存机制与核心服务（KISS/YAGNI）

本 INITIAL 定义 S-003 的最小可行范围、产出文件、实现要点、验证门与验收标准，指导 Claude 生成 PRP 并完成实现。目标：整合内部映射与 S-002 的 EQCClient，完成 company_id 的统一解析与基础缓存闭环。

## 范围（Scope）

In-scope
- 统一解析服务：`CompanyEnrichmentService`（同步解析 + 队列处理）
- 基础缓存：写回 `enterprise.company_mapping`（UPSERT）
- 队列：`enterprise.lookup_requests` + 轻量 DAO
- 临时ID：`TEMP_{number:06d}`（简化序列表）
- 配置：WDH_* 服务与队列参数
- 测试：Mock 单测，可选集成

Out-of-scope
- 多 Provider 抽象、复杂评分/标签、服务化/分布式队列

## 产出物（文件与位置）

新增
- `scripts/create_table/ddl/lookup_requests.sql`（含可选 `temp_id_sequence`）
- `src/work_data_hub/domain/company_enrichment/lookup_queue.py`（队列 DAO）
- `src/work_data_hub/io/loader/company_enrichment_loader.py`（company_mapping UPSERT）
- `tests/domain/company_enrichment/test_enrichment_service.py`（服务单测）
- `tests/domain/company_enrichment/test_lookup_queue.py`（队列单测）

修改
- `src/work_data_hub/domain/company_enrichment/models.py`：新增 `ResolutionStatus`、`CompanyIdResult`、`LookupRequest`
- `src/work_data_hub/domain/company_enrichment/service.py`：扩展并实现服务
- `src/work_data_hub/config/settings.py`：新增配置
- 可选：`src/work_data_hub/orchestration/ops.py` 增加 `process_lookup_queue_op`

## DDL（参考，实现到文件即可）

```sql
CREATE SCHEMA IF NOT EXISTS enterprise;
CREATE TABLE IF NOT EXISTS enterprise.lookup_requests (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  normalized_name VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lookup_requests_status ON enterprise.lookup_requests (status, created_at);
CREATE INDEX IF NOT EXISTS idx_lookup_requests_normalized_name ON enterprise.lookup_requests (normalized_name);
CREATE TABLE IF NOT EXISTS enterprise.temp_id_sequence (
  id BIGSERIAL PRIMARY KEY,
  last_number INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now()
);
INSERT INTO enterprise.temp_id_sequence (last_number)
SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM enterprise.temp_id_sequence);
```

## 服务接口（精确规范）

```python
class CompanyEnrichmentService:
    def __init__(self, loader, queue, eqc_client, *, sync_lookup_budget: int = 0):
        ...

    def resolve_company_id(self, *, plan_code: str | None = None, customer_name: str | None = None,
                           account_name: str | None = None, sync_lookup_budget: int | None = None) -> CompanyIdResult:
        """优先级：内部映射 →（预算内）EQC 搜索+详情→缓存 → 入队 →（customer_name 为空时）分配 TEMP_*"""

    def process_lookup_queue(self, *, batch_size: int | None = None) -> int:
        """消费 pending→processing→done/failed，返回处理条数"""
```

实现要点
- 规范化：`normalize_name(s: str) -> str`
- 缓存回写：`alias_name`+`canonical_id` UPSERT 至 `enterprise.company_mapping`
- EQC：取第一条候选（或最简单规则），再拉详情，落模 `CompanyDetail`
- TEMP：`UPDATE ... RETURNING` 从 `temp_id_sequence` 取号
- 队列：enqueue/dequeue/mark_done/mark_failed；attempts++；按 `created_at` 取批
- 日志：记录命中来源/耗时，脱敏，不输出 token

## 配置（Settings）

- `company_enrichment_enabled: bool = True`（WDH_COMPANY_ENRICHMENT_ENABLED）
- `company_sync_lookup_limit: int = 5`（WDH_COMPANY_SYNC_LOOKUP_LIMIT）
- `lookup_queue_batch_size: int = 50`（WDH_LOOKUP_QUEUE_BATCH_SIZE）
- `lookup_retry_max: int = 3`（WDH_LOOKUP_RETRY_MAX）
- `lookup_retry_delay: int = 300`（WDH_LOOKUP_RETRY_DELAY）

## 测试

- `test_enrichment_service.py`：
  - 内部命中→SUCCESS_INTERNAL
  - 内部未命中+预算>0→EQC 成功→写回→SUCCESS_EXTERNAL
  - 预算=0→入队→PENDING_LOOKUP
  - customer_name 为空→TEMP_ASSIGNED
  - EQC 429/5xx→不阻塞，最终入队
- `test_lookup_queue.py`：enqueue/dequeue/mark_* 流程与 attempts

可选集成（需 DB）：
```bash
export WDH_DATABASE__URI=postgresql://user:pass@host:5432/db
psql "$WDH_DATABASE__URI" -f scripts/create_table/ddl/lookup_requests.sql
pytest -v -m company_enrichment_integration
```

## 验证门（Validation Gates）

```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "enrichment_service or lookup_queue"
```

## 验收标准
- [ ] 统一解析服务覆盖关键路径并通过测试
- [ ] 队列处理可消费 pending 并正确回写/标记
- [ ] company_mapping UPSERT 正常
- [ ] 日志脱敏，错误不阻塞主流程
- [ ] 所有验证门通过

## 参考
- `docs/company_id/simplified/S-003_基础缓存机制.md`
- 现有 `EQCClient`：`src/work_data_hub/io/connectors/eqc_client.py`
- 现有模型：`src/work_data_hub/domain/company_enrichment/models.py`
