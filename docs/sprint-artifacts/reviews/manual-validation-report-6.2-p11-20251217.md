# Manual Validation Report: Story 6.2-P11

**Guide:** `scripts/validation/CLI/manual-validation-guide-story-6.2-p11.md`  
**Date:** 2025-12-17

---

## 结论

- ✅ 验证一（Pipeline 字段派生）：通过
- ✅ 验证二（enrichment_index 数据完整性）：通过（已补齐 plan_code/account_number/account_name/customer_name）
- ✅ 验证三（CLI Token 预检测）：通过（Token 无效时能提示；`--no-auto-refresh-token` 生效；自动刷新需人工扫码）
- ✅ 验证四（端到端数据流）：通过（年金账户号填充率、company_id 解析率均满足阈值）
- ✅ 验证五（边界条件）：通过

---

## 关键结果

### 1) 年金账户号派生

- `年金账户号` 列存在，且 `C12345678 -> 12345678`，空值保持 `None`。

### 2) enrichment_index（enterprise.enrichment_index）

- 表存在，数据来源 `legacy_migration`。
- 当前分布（总计）：42,527
  - `customer_name`: 19,840
  - `account_name`: 11,276
  - `account_number`: 10,286
  - `plan_code`: 1,125
- `company_id` 为空：0
- `(lookup_type, lookup_key)` 重复键：0

### 3) CLI Token 预检测

- `validate_eqc_token()` 返回 `False`（当前环境 Token 已失效）。
- CLI 在 `--no-auto-refresh-token` 下仍会执行预检测并输出：
  - `🔐 Validating EQC token... ❌ Token invalid/expired`
  - `⚠️  Auto-refresh disabled (--no-auto-refresh-token)`
- 二维码自动刷新流程可触发，但需要人工扫码完成（本次仅做了短超时 smoke test，未覆盖成功登录）。

### 4) 端到端 ETL（annuity_performance, 202510）

- 执行命令（dry-run/plan-only）：`python -m work_data_hub.cli etl --domains annuity_performance --period 202510 --enrichment-enabled`
- 执行命令（写入 DB）：`python -m work_data_hub.cli etl --domains annuity_performance --period 202510 --enrichment-enabled --execute --no-auto-refresh-token`
- 结果表：`business.规模明细`
- 行数（WHERE 月度 = '2025-10-01'）：37,121
- 指标（WHERE 月度 = '2025-10-01'）：
  - 年金账户号填充率：99.9%
  - company_id 解析率（非 `IN*` 临时ID）：97.6%
  - `company_id='N'`：0

### 5) 边界条件

- 空 DataFrame：正常返回空输出
- 缺失 `集团企业客户号`：`年金账户号` 正常创建且为 `None`

---

## 为了完成验证而进行的修复/调整

- `src/work_data_hub/cli/etl.py`：`--no-auto-refresh-token` 不再跳过 Token 预检测；`--enrichment-sync-budget` 默认值调整为 5（可传 0 禁用）。
- `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py`：拒绝将 `company_id='N'` 等非数字值视为有效（含源列透传 & DB cache 命中）。
- `src/work_data_hub/infrastructure/enrichment/domain_learning_service.py`：学习/回写只接受纯数字 company_id，过滤 `IN*` 临时ID及非数字值。
- `src/work_data_hub/infrastructure/enrichment/mapping_repository.py`：修复 enqueue SQL 参数绑定（避免 `:param::text[]` 导致 psycopg2 语法错误）。
