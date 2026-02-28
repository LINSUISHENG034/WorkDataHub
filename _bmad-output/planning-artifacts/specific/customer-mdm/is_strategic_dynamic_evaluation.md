# is_strategic 动态评估改进方案

> **发现日期**: 2026-02-28
> **发现来源**: 验证指南(`docs\verification_guide_real_data.md`)步骤六 (6.2) 验证过程
> **状态**: 待修复

---

## 问题描述

当前 `is_strategic` 的判定逻辑仅基于**上年12月**的 `business.规模明细` 数据（AUM Top N 或 ≥ 阈值 5亿），
导致2025年新增的大客户（即使当前 AUM 已远超阈值）不会被标记为战略客户。

### 影响范围

- **受影响合约数**: 30 条（当前 AUM ≥ 5亿但 `is_strategic = false`）
- **典型案例**: 交通银行（25.4亿）、深圳能源集团（19.9亿）、广东省社会保险基金管理局（14.5亿）

### 根因

`common_ctes.sql` 中的 `strategic_whitelist` CTE 仅查询上年12月数据：

```sql
-- CTE 2: strategic_whitelist
WHERE EXTRACT(MONTH FROM 月度) = 12
  AND EXTRACT(YEAR FROM 月度) = %s  -- prior_year (2024)
```

---

## 决策

| 字段 | 评估方式 | 说明 |
|---|---|---|
| `is_existing` | ✅ 保持不变：基于上年12月数据 | 用于识别存量/新增客户，语义正确 |
| `is_strategic` | ❌→✅ 改为**动态评估** | 应基于当期数据判断，而非仅看上年12月 |

### 核心规则

1. **动态评估**: `is_strategic` 应在每次 `contract_status_sync` 时基于**当期 AUM** 重新计算
2. **不回退策略 (Ratchet Rule)**: 一旦标记为 `true`，不能因后续 AUM 下降而回退为 `false`
   - 注: 此 Ratchet Rule 已在 `close_old_records.sql` 第 70 行实现 (`old.is_strategic = FALSE AND new.is_strategic = TRUE`)

---

## 修复方案

### 修改 `common_ctes.sql` 中的 `strategic_whitelist` CTE

将数据源从"上年12月"改为"当期数据（所有可用月份）"：

```sql
-- 修改前: 仅看上年12月
WHERE EXTRACT(MONTH FROM 月度) = 12
  AND EXTRACT(YEAR FROM 月度) = %s  -- prior_year

-- 修改后: 看所有可用数据（动态评估）
WHERE company_id IS NOT NULL
-- 移除月份和年份限制，使用全量数据进行排名
```

或者更精确地，只看**当期月份**的数据：

```sql
-- 修改后: 基于当期月份数据
WHERE 月度 = (SELECT MAX(月度) FROM business.规模明细)
  AND company_id IS NOT NULL
```

### 涉及文件

| 文件 | 修改内容 |
|---|---|
| `src/work_data_hub/customer_mdm/sql/common_ctes.sql` | `strategic_whitelist` CTE 数据源改为当期 |
| `src/work_data_hub/customer_mdm/contract_sync.py` | 可能需要调整 SQL 参数 |
| `src/work_data_hub/customer_mdm/year_init.py` | `_update_strategic` 函数同步检查 |

### 不需修改

- `close_old_records.sql` 第 70 行的 Ratchet Rule 已正确实现
- `is_existing` 的 `prior_year_dec` CTE 保持不变
