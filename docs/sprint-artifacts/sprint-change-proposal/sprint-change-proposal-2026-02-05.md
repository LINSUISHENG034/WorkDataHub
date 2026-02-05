# Sprint Change Proposal: Customer MDM 战客身份规则实现差距修复

**文档版本**: 1.0
**创建日期**: 2026-02-05
**提案人**: Correct Course Workflow
**变更范围**: Moderate (需要 Backlog 重组和 PO/SM 协调)

---

## 1. Issue Summary

### 1.1 Problem Statement

`customer.customer_plan_contract` 表的实现与业务规范 `docs/memories/战客身份定义与更新逻辑.md` 存在 **4 个关键差距**，导致数据一致性问题。

### 1.2 Discovery Context

**触发来源**: 实现后质量审计 - `customer-plan-contract-implementation-gap-analysis.md`
**发现日期**: 2026-02-05
**相关 Stories**: Story 7.6-6 (Contract Status Sync), Story 7.6-12 (SCD Type 2 Fix)

### 1.3 Evidence and Impact

| GAP | 严重程度 | 描述 | 数据证据 |
|-----|----------|------|----------|
| GAP-1 | **严重** | 年度切断未实现 | 0 条记录的 `valid_from` 是1月1日 |
| GAP-2 | **严重** | 只增不减规则未实现 | 10,417 条记录状态不一致 |
| GAP-3 | **中等** | 设计理念冲突 | `year_init.py` 与 `contract_sync.py` 冲突 |
| GAP-4 | **严重** | contract_status 同步失效 | 10,417 条记录应为"停缴"但显示"正常" |

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | 影响 | 描述 |
|------|------|------|
| **Epic Customer MDM (7.6)** | **需修改** | 需要新增 2 个 Stories 来修复差距 |

**Epic 变更详情**:

1. **新增 Story 7.6-14**: 年度切断逻辑实现 (GAP-1)
2. **新增 Story 7.6-15**: 只增不减规则实现 (GAP-2)
3. **修改 Story 7.6-9**: 整合 `year_init.py` 与 `contract_sync.py` 设计 (GAP-3)
4. **修复 GAP-4**: 在 Story 7.6-15 中一并解决 contract_status 同步问题

### 2.2 Story Impact

| Story | 状态 | 影响 |
|-------|------|------|
| 7.6-6 Contract Status Sync | done | 需要补充 "只增不减" 逻辑 |
| 7.6-12 SCD Type 2 Fix | done | 需要修改状态检测条件 |
| 7.6-14 年度切断 | new | 新增 Story |
| 7.6-15 只增不减规则 | new | 新增 Story |

### 2.3 Artifact Conflicts

| 文档 | 冲突 | 所需操作 |
|------|------|----------|
| `customer-plan-contract-specification.md` | §5.3 缺少"只增不减"规则定义 | 更新规范文档 |
| `战客身份定义与更新逻辑.md` | 规范已定义，代码未遵循 | 无需修改（已有正确规范） |

### 2.4 Technical Impact

| 组件 | 影响 |
|------|------|
| `contract_sync.py` | 需要修改 `has_status_changed()` 逻辑 |
| `close_old_records.sql` | 需要修改 SCD 变更检测条件 |
| `year_init.py` | 需要重构为 SCD Type 2 模式 |

---

## 3. Recommended Approach

### 3.1 Selected Path

**选项 1: 直接调整 (Direct Adjustment)** - ✓ 推荐

### 3.2 Rationale

| 因素 | 评估 |
|------|------|
| **实施工作量** | 中 (3-5 天) |
| **技术风险** | 低 (SCD Type 2 框架已就位) |
| **时间线影响** | 中 (需要新增 2 个 Stories) |
| **长期可持续性** | 高 (修复后符合业务规范) |
| **业务价值** | 高 (解决数据一致性问题) |

### 3.3 Alternatives Considered

- **选项 2: 回滚** - 不可行：现有实现基础良好，回滚反而增加工作量
- **选项 3: MVP 审查** - 不需要：MVP 范围无需调整

---

## 4. Detailed Change Proposals

### 4.1 Story: 7.6-14 年度切断逻辑实现 (GAP-1)

**目标**: 实现1月1日强制生成新记录的逻辑

**OLD** (当前 `year_init.py` line 155-161):
```sql
UPDATE customer.customer_plan_contract c
SET is_strategic = TRUE
...
WHERE c.is_strategic = FALSE
```

**NEW** (新增 `annual_cutover()` 函数):
```python
def annual_cutover(year: int):
    """年度切断 - 1月1日执行

    原则一：年度切断
    - 无论客户状态是否变化，跨年时刻（1月1日）必须强制生成新记录
    - 目的：区分"2024年的战客"与"2025年的战客"
    """
    # Step 1: 关闭所有当前记录
    UPDATE valid_to = f'{year}-01-01'
    WHERE valid_to = '9999-12-31'

    # Step 2: 为所有活跃客户插入新记录
    INSERT INTO customer_plan_contract
    SELECT ..., status_year = year, valid_from = f'{year}-01-01'
```

**验收标准**:
- AC-1: 每年1月1日，所有 `valid_to = '9999-12-31'` 的记录被关闭
- AC-2: 新记录的 `status_year = 当前年份`, `valid_from = 'YYYY-01-01'`
- AC-3: 查询 `WHERE EXTRACT(DAY FROM valid_from) = 1 AND EXTRACT(MONTH FROM valid_from) = 1` 返回 > 0 条记录

---

### 4.2 Story: 7.6-15 只增不减规则实现 (GAP-2, GAP-4)

**目标**: 战客身份只能晋升不能降级，并修复 contract_status 同步

**OLD** (`close_old_records.sql` line 57-60):
```sql
AND (
    old.contract_status IS DISTINCT FROM new.contract_status
    OR old.is_strategic IS DISTINCT FROM new.is_strategic  -- ❌ 会触发降级
    OR old.is_existing IS DISTINCT FROM new.is_existing
)
```

**NEW**:
```sql
AND (
    old.contract_status IS DISTINCT FROM new.contract_status
    OR (old.is_strategic = FALSE AND new.is_strategic = TRUE)  -- ✓ 只允许晋升
    OR old.is_existing IS DISTINCT FROM new.is_existing
)
```

**Python 逻辑**:
```python
def apply_ratchet_rule(is_strategic_db: bool, is_strategic_calculated: bool) -> tuple[bool, bool]:
    """应用"只增不减"规则

    原则三：只增不减 (The "Ratchet" Rule)
    - 同一 status_year 内，战客身份具有棘轮效应
    - 可以晋升：普通客户 → 战客（年中 AUM 达标）
    - 不可降级：战客 → 普通客户（即使 AUM 下跌）

    Returns:
        (final_strategic_status, trigger_scd_update)
    """
    if is_strategic_db == True and is_strategic_calculated == False:
        # 战客 AUM 下跌 -> 依然保持战客身份
        return True, False  # 不更新记录

    if is_strategic_db == False and is_strategic_calculated == True:
        # 普通客户 AUM 达标 -> 晋升为战客
        return True, True  # 触发 SCD 更新

    # 状态不变
    return is_strategic_calculated, False
```

**验收标准**:
- AC-1: 战客 AUM 下跌不触发降级（不生成新 SCD 记录）
- AC-2: 普通客户 AUM 达标触发晋升（生成新 SCD 记录）
- AC-3: 10,417 条状态不一致记录被修复
- AC-4: 验证 SQL 查询不一致记录数返回 0

---

### 4.3 PRD 规范文档更新

**文件**: `docs/specific/customer-mdm/customer-plan-contract-specification.md`

**Section 5.3.1 添加**:
```markdown
#### 5.3.1 状态变化检测规则修正

**只增不减规则 (The "Ratchet" Rule)**:

在同一个 status_year 内，战客身份 (is_strategic) 具有棘轮效应：
- **可以晋升**: FALSE → TRUE (普通客户 → 战客)
- **不可降级**: TRUE → FALSE (战客 → 普通客户，即使 AUM 下跌)

**修正后的检测逻辑**:
```sql
-- 原逻辑 (会触发降级) - ❌ 错误
OR old.is_strategic IS DISTINCT FROM new.is_strategic

-- 新逻辑 (只允许晋升) - ✓ 正确
OR (old.is_strategic = FALSE AND new.is_strategic = TRUE)
```
```

---

## 5. Implementation Handoff

### 5.1 Change Scope Classification

**变更范围**: **Moderate**

- 需要新增 2 个 Stories
- 需要修改现有代码逻辑
- 需要更新规范文档
- 不影响其他 Epic 或 MVP 范围

### 5.2 Handoff Recipients

| 角色 | 职责 |
|------|------|
| **Product Owner** | 审批并优先级调整新增 Stories |
| **Scrum Master** | 将新增 Stories 加入 Sprint Backlog |
| **开发团队** | 实现修复逻辑，编写测试用例 |

### 5.3 Success Criteria

1. **数据一致性**: 10,417 条状态不一致记录修复为 0
2. **年度切断**: 查询返回 > 0 条 `valid_from` 为1月1日的记录
3. **只增不减**: 单元测试覆盖战客降级保护场景
4. **文档更新**: 规范文档 §5.3.1 添加"只增不减"规则

### 5.4 Implementation Sequence

```
Sprint N:
├── Story 7.6-15: 只增不减规则 (P0 - 数据一致性最紧急)
│   ├── 修改 has_status_changed() 逻辑
│   ├── 修改 close_old_records.sql
│   ├── 编写单元测试
│   └── 运行同步修复数据
│
└── Story 7.6-14: 年度切断逻辑
    ├── 新增 annual_cutover() 函数
    ├── 添加 ETL Hook 或定时任务
    ├── 编写单元测试
    └── 更新规范文档
```

---

## 6. References

| 文档 | 路径 |
|------|------|
| 差距分析 | `docs/specific/customer-mdm/customer-plan-contract-implementation-gap-analysis.md` |
| 业务规范 | `docs/memories/战客身份定义与更新逻辑.md` |
| 表规范 | `docs/specific/customer-mdm/customer-plan-contract-specification.md` |
| Story 7.6-6 | `docs/sprint-artifacts/stories/epic-customer-mdm/7.6-6-contract-status-sync-post-etl-hook.md` |
| Story 7.6-12 | `docs/sprint-artifacts/stories/epic-customer-mdm/7.6-12-scd2-implementation-fix.md` |

---

**审批状态**: 待审批
**预期完成**: Sprint N+1 (约 2 周)
