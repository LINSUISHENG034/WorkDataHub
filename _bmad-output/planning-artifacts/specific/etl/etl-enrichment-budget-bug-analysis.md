# ETL Enrichment Budget 传递缺失 Bug 分析

> 日期: 2025-03-05
> 状态: 待确认修复

## 问题现象

内网环境下运行 ETL（不带 `--no-enrichment`），所有客户名均生成临时 `company_id`（`IN` 前缀哈希），无法获取真实 EQC company_id。而 `eqc -gui` 模块能正常获取并写入真实 ID。

## 根因分析

**这不是 PACSession / 内网代理问题。** PACSession 已正确注入 `EQCTransport` 和 `validate_eqc_token`。Token 刷新成功也证实了代理链路畅通。

**真正原因：CLI enrichment 参数未传递到 Dagster Pipeline Op，导致 EQC 查询预算始终为 0。**

## 问题链路追踪

```
CLI 层                     Dagster Config 层                    Op 执行层
─────────────────────     ──────────────────────────          ─────────────────────────
main.py 解析参数:          config.py build_run_config():       generic_ops.py:
  enrichment_enabled=True    ❌ 未传递 enrichment_enabled       GenericDomainOpConfig 中
  enrichment_sync_budget=500 ❌ 未传递 enrichment_sync_budget   没有 enrichment 字段
                                                               │
                                                               ▼
                                                             factory.py:
                                                               EnrichmentServiceFactory.create(
                                                                 plan_only=False,
                                                                 sync_lookup_budget=0  ← 默认值!
                                                               )
                                                               │
                                                               ▼
                                                             CompanyEnrichmentService:
                                                               budget=0 → 不发起任何 EQC 查询
                                                               → 全部生成临时 company_id
```

## 涉及文件详情

### 1. [config.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/cli/etl/config.py) — 配置构建

`build_run_config()` 构建 `process_domain_op_v2` 的 Dagster config 时，**只传了 `domain`、`plan_only`、`session_id`**，完全丢弃了 enrichment 参数：

```python
# Line 201-207
run_config["ops"]["process_domain_op_v2"] = {
    "config": {
        "domain": domain,
        "plan_only": effective_plan_only,
        "session_id": session_id,
        # ❌ 缺少: enrichment_enabled, enrichment_sync_budget
    }
}
```

### 2. [generic_ops.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/orchestration/ops/generic_ops.py) — Dagster Op

`GenericDomainOpConfig` 中没有 enrichment 字段：

```python
class GenericDomainOpConfig(Config):
    domain: str
    plan_only: bool = True
    session_id: Optional[str] = None
    # ❌ 缺少: enrichment_enabled, enrichment_sync_budget
```

调用 Factory 时 `sync_lookup_budget` 使用默认值 0：

```python
# Line 59-61
enrichment_ctx = EnrichmentServiceFactory.create(
    plan_only=config.plan_only,
    # ❌ sync_lookup_budget 默认 0
)
```

### 3. [factory.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/infrastructure/enrichment/factory.py) — 工厂

`create()` 签名中 `sync_lookup_budget` 默认为 0：

```python
@classmethod
def create(
    cls,
    plan_only: bool = True,
    sync_lookup_budget: int = 0,  # ← 这里
) -> EnrichmentContext:
```

### 4. eqc-gui 为何能正常工作

`eqc-gui` **直接创建 `EQCClient` 发起 HTTP 请求**，绕过了 Dagster pipeline 和 `EnrichmentServiceFactory`，因此不受此 bug 影响。

## 对比：预期 vs 实际

| 步骤 | 预期行为 | 实际行为 |
|------|----------|---------|
| CLI 解析 `--enrichment-sync-budget` | 默认 500 | ✅ 500 |
| `build_run_config()` 传递 budget | 写入 run_config | ❌ 未传递 |
| `GenericDomainOpConfig` 接收 budget | config 字段存在 | ❌ 字段不存在 |
| `EnrichmentServiceFactory.create()` budget | 500 | ❌ 0 (默认值) |
| EQC API 查询 | 发起最多 500 次 | ❌ 不发起 |

## 建议修复方案

### 方案 A：最小化修改（推荐）

在现有链路上打通参数传递：

1. **`GenericDomainOpConfig`** 增加两个字段：
   ```python
   enrichment_sync_budget: int = 0
   enrich_enabled: bool = True
   ```

2. **`build_run_config()`** 补充参数传递：
   ```python
   run_config["ops"]["process_domain_op_v2"] = {
       "config": {
           "domain": domain,
           "plan_only": effective_plan_only,
           "session_id": session_id,
           "enrichment_sync_budget": getattr(args, "enrichment_sync_budget", 500),
           "enrich_enabled": bool(getattr(args, "enrichment_enabled", True)),
       }
   }
   ```

3. **`process_domain_op_v2`** 透传给 Factory：
   ```python
   enrichment_ctx = EnrichmentServiceFactory.create(
       plan_only=config.plan_only,
       sync_lookup_budget=config.enrichment_sync_budget,
   )
   ```

4. **`EnrichmentServiceFactory.create()`** 增加 `enrich_enabled` 参数覆盖，或保持从 settings 读取。

### 方案 B：利用已有 `EqcLookupConfig` 体系

`eqc_lookup_config.py` 中已有完整的 `EqcLookupConfig` dataclass 和 `from_cli_args()` 工厂方法。可以序列化后通过 Dagster config 传递（`ProcessingConfig` 中已有 `eqc_lookup_config` 可选字段）。但需要改动更多层。

## 影响范围

- 此 bug **不仅影响内网**，在外网环境（有 EQC API 访问能力时）也同样存在
- 所有通过 `process_domain_op_v2` 执行的 domain 均受影响（`annuity_performance`、`annuity_income`、`annual_award`、`annual_loss`）
- `--enrichment-sync-budget` CLI 参数在当前架构下完全无效
