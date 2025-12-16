# EQC 查询问题排查经验总结（2025-12-17）

适用范围：`annuity_performance` 端到端 ETL（`work_data_hub.cli etl`）启用 `--enrichment-enabled` 后的 EQC 同步查询（New Pipeline 的 “EQC→失败→临时ID” 路径）。

---

## 1) 典型现象与快速定位

### 1.1 现象：`EQC request forbidden` / 403

- 表现：日志出现 `eqc_provider.request_error` / `forbidden`，EQC 查询无命中，随后大量 `company_id` 变为 `IN*` 临时ID。
- 高概率原因：EQC Token 无效/过期/无权限（`validate_eqc_token()` 对 `401/403` 判定为无效）。

### 1.2 快速验证 Token 是否可用

```powershell
$env:PYTHONPATH='src'
uv run --env-file .wdh_env python -c "
from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token
from work_data_hub.config.settings import get_settings
s=get_settings()
print(validate_eqc_token(s.eqc_token, s.eqc_base_url))
"
```

### 1.3 CLI 端到端确认（含 Token 预检）

```powershell
$env:PYTHONPATH='src'
uv run --env-file .wdh_env python -m work_data_hub.cli etl `
  --domains annuity_performance `
  --period 202510 `
  --enrichment-enabled `
  --execute `
  --debug
```

期望日志关键点：
- `🔐 Validating EQC token... ✅ Token valid`
- `company_id_resolver.eqc_provider_completed`（包含 `eqc_hits`、`budget_remaining`）

> 注意：`--no-auto-refresh-token` 会禁用自动刷新，但仍会输出 token 预检结果。

---

## 2) 数据面证据：EQC 是否“真的执行且落库”

### 2.1 enrichment_index 是否出现 `eqc_api` 来源

```sql
SELECT source, COUNT(*) FROM enterprise.enrichment_index GROUP BY source ORDER BY 2 DESC;
SELECT * FROM enterprise.enrichment_index WHERE source='eqc_api' ORDER BY updated_at DESC LIMIT 10;
```

期望：`source='eqc_api'` 记录数 > 0，且 `lookup_type='customer_name'`。

### 2.2 base_info 是否写入原始响应（full coverage）

```sql
SELECT MAX(api_fetched_at), COUNT(*) FROM enterprise.base_info;
SELECT company_id, search_key_word, api_fetched_at,
       raw_data IS NOT NULL AS has_raw_data,
       raw_business_info IS NOT NULL AS has_raw_business_info,
       raw_biz_label IS NOT NULL AS has_raw_biz_label
FROM enterprise.base_info
ORDER BY api_fetched_at DESC
LIMIT 10;
```

期望：新一轮 ETL 后 `api_fetched_at` 更新、记录数增加，且 `raw_data/raw_business_info/raw_biz_label` 至少部分非空（成功时通常三者都非空）。

---

## 3) 常见“看起来像没查 EQC”的原因

### 3.1 同步预算为 0 导致不触发 EQC

- 触发条件：`ResolutionStrategy.sync_lookup_budget > 0` 才会走 EQC sync lookup。
- CLI 参数：`--enrichment-sync-budget`（建议默认 > 0；可显式传 0 禁用）。

### 3.2 DB cache 脏值导致 company_id 异常（例如 `company_id='N'`）

- 现象：`enterprise.enrichment_index` 中某些 `plan_code` 映射存在 `company_id='N'` 等非数字占位符。
- 处理原则：非纯数字 company_id 不应被当作有效 company_id，应该继续向下尝试（EQC/临时ID）。

---

## 4) 重要实现细节（排查时的“坑”）

### 4.1 临时ID格式差异：`IN_...` vs `IN...`

- 生成：`generate_temp_company_id()` 生成形如 `IN_<base32>`。
- 入库：领域模型会对 `company_id` 做规范化（去掉 `_`），导致 DB 中可能看到 `IN...`。
- 因此：过滤临时ID时应使用 `startswith('IN')` 而不是仅 `IN_`。

### 4.2 Settings 缓存导致“刷新 token 但本进程不生效”

`get_settings()` 使用 `lru_cache`；如果自动刷新 token 写入 `.wdh_env` 后不清缓存，同一进程可能仍沿用旧 token。

---

## 5) 本次结论（2025-12-17）

- 当 Token 更新为有效值后，端到端 ETL 日志出现 `✅ Token valid` 且出现 `company_id_resolver.eqc_provider_completed`。
- DB 侧出现 `enterprise.enrichment_index.source='eqc_api'` 新增记录，并且 `enterprise.base_info.api_fetched_at` 更新且记录数增长，证明 EQC 查询与持久化链路实际生效。

