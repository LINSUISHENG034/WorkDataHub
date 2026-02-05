# Sprint Change Proposal: 规模明细 ETL Pipeline 字段派生修复

**Date**: 2025-12-16
**Author**: Correct-Course Workflow
**Status**: Pending Approval
**Priority**: P0/P1

---

## 1. Issue Summary

### Problem Statement

在 Story 6.2-P6 CLI Architecture Unification 验证阶段，使用 202510 月度数据执行 `--dry-run` 时发现以下问题：

1. **`年金账户号` 列始终为空** - 应从 `集团企业客户号` 派生
2. **所有 `company_id` 均为临时 ID (`IN_xxx`)** - P2 层级查询失效

### Root Cause Analysis

Pipeline 在 Step 9 清洗 `集团企业客户号`（去除 "C" 前缀）后，直接在 Step 12 删除该列，**未将其赋值给 `年金账户号`**。

```python
# 当前实现 (有缺陷)
Step 9:  集团企业客户号 lstrip "C"  # 清洗
Step 12: 删除 集团企业客户号         # 数据丢失！

# 缺失的步骤
Step 9b: 年金账户号 = 集团企业客户号  # ← 应该添加
```

### Discovery Context

- **触发故事**: Story 6.2-P6 CLI Architecture Unification
- **发现时间**: 2025-12-16
- **发现方式**: CLI 验证 (`--dry-run --debug`)
- **分析报告**: `docs/specific/etl/20251216-guimo-mingxi-issue-analysis.md`

### Evidence

1. **代码审查**: `pipeline_builder.py:201-272` 确认缺失赋值步骤
2. **Legacy 对照**: `legacy/data_cleaner.py:251-279` 使用 `集团企业客户号` 查询 P2 映射
3. **数据验证**: `enrichment_index` 表为空或不存在

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact Type | Details |
|------|-------------|---------|
| Epic 6.2 | Direct | 需添加补丁故事 Story 6.2-P11 |
| Epic 7 | Indirect | Golden Dataset 测试将验证此修复 |

### Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 6.2-P10 | Done | 无影响 (SQL Module) |
| 6.2-P11 | **New** | 本提案创建的新故事 |
| 7-1 | Backlog | 将验证修复正确性 |

### Artifact Conflicts

| Artifact | Change Type | Details |
|----------|-------------|---------|
| `pipeline_builder.py` | Code Modify | 添加 Step 9b: `年金账户号` 赋值 |
| `enrichment_index` 表 | Data Restore | alembic 迁移 + 数据导入 |
| Test Cases | Add | 字段派生验证测试 |
| Cleansing Docs | Update | 添加字段派生说明 |
| CLI `etl.py` | Code Modify | Token 预检测 (P2) |

### Technical Impact

- **代码变更**: 约 10 行新增代码
- **数据库**: 表结构无变更，需恢复数据
- **部署**: 无部署变更
- **性能**: 无性能影响

---

## 3. Recommended Approach

### Selected Path: Direct Adjustment

在 Epic 6.2 中添加补丁故事 **Story 6.2-P11** 直接修复问题。

### Rationale

| Factor | Assessment |
|--------|------------|
| Implementation Effort | 🟢 Low - 1-2 小时 |
| Technical Risk | 🟢 Low - 变更范围小 |
| Timeline Impact | 🟢 None - 不延迟 Epic 7 |
| Team Morale | 🟢 Positive - 快速解决 |
| Long-term Sustainability | 🟢 Good - 符合现有架构 |

### Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Rollback recent stories | 问题是原始设计遗漏，回滚无益 |
| Adjust MVP scope | 修复成本低，无需范围调整 |
| Defer to Epic 7 | 会导致 Golden Dataset 测试失败 |

### Effort & Risk Estimates

| Task | Effort | Risk |
|------|--------|------|
| enrichment_index 恢复 | 30 min | Low |
| Pipeline 步骤修复 | 1 hour | Low |
| 单元测试 | 30 min | Low |
| 文档更新 | 15 min | Low |
| CLI Token 预检测 | 30 min | Low |
| **Total** | **~2.5 hours** | **Low** |

---

## 4. Detailed Change Proposals

### 4.1 Pipeline Step Fix (P1)

**File**: `src/work_data_hub/domain/annuity_performance/pipeline_builder.py`

**Change**: 在 Step 9 后添加 Step 9b

```python
# Step 9: 集团企业客户号 清洗 - lstrip "C"
CalculationStep({
    "集团企业客户号": lambda df: df["集团企业客户号"].str.lstrip("C")
    if "集团企业客户号" in df.columns else pd.Series([None] * len(df)),
}),

# Step 9b: 派生 年金账户号 from cleaned 集团企业客户号 [NEW]
CalculationStep({
    "年金账户号": lambda df: df["集团企业客户号"].copy()
    if "集团企业客户号" in df.columns else pd.Series([None] * len(df)),
}),
```

### 4.2 enrichment_index Table Restoration (P0)

**Type**: Operations (not code change)

**Commands**:
```powershell
# Step 1: 检查当前迁移状态
uv run --env-file .wdh_env alembic current

# Step 2: 执行迁移创建 enrichment_index 表
uv run --env-file .wdh_env alembic upgrade 20251208_000001

# Step 3: 导入 Legacy 映射数据
PYTHONPATH=src uv run --env-file .wdh_env python scripts/migrations/enrichment_index/migrate_full_legacy_db.py

# Step 4: 验证数据完整性
PYTHONPATH=src uv run --env-file .wdh_env python scripts/migrations/enrichment_index/migrate_plan_mapping.py --verify
```

### 4.3 Unit Tests (P1)

**File**: `tests/unit/domain/annuity_performance/test_pipeline_builder.py`

**New Tests**:
- `test_annuity_account_number_derived_from_group_customer_number`
- `test_annuity_account_number_empty_when_source_missing`

### 4.4 Documentation Update (P2)

**File**: `docs/cleansing-rules/guimo-mingxi.md`

**Change**: Add field derivation documentation for `年金账户号`

### 4.5 CLI Token Pre-check + Auto Refresh (P2)

**File**: `src/work_data_hub/cli/etl.py`

**Change**: Add `validate_eqc_token()` check at CLI startup with automatic token refresh via `auto_eqc_auth.py`

**Implementation**:
```python
from work_data_hub.infrastructure.enrichment.eqc_provider import (
    validate_eqc_token,
    EqcTokenInvalidError,
)
from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr

# In etl command:
if enrichment_enabled:
    settings = get_settings()
    token_valid = False

    if settings.eqc_token:
        try:
            validate_eqc_token(settings.eqc_token, settings.eqc_base_url)
            token_valid = True
        except EqcTokenInvalidError:
            pass

    # Auto refresh if invalid
    if not token_valid and auto_refresh_token:
        new_token = run_get_token_auto_qr(
            timeout_seconds=120,
            save_to_env=True,
            env_file=".wdh_env"
        )
        if new_token:
            settings = get_settings(reload=True)
            token_valid = True
```

**User Experience**: When token is invalid, automatically opens QR code popup for scanning with "快乐平安" APP

---

## 5. Implementation Handoff

### Change Scope Classification

**Scope**: 🟡 **Minor to Moderate**
- Code changes are small
- But involves data correctness and Legacy Parity

### Handoff Recipients

| Role | Responsibility | Deliverable |
|------|----------------|-------------|
| **Dev Team** | Implement code fixes | PR with tests |
| **Dev Team** | Execute data migration | Verification report |
| **SM** | Update sprint-status.yaml | Status file |
| **SM** | Create Story 6.2-P11 file | Story document |

### No Escalation Required

- ❌ No PM involvement needed (not a strategic change)
- ❌ No Architect involvement needed (no architecture change)

### Success Criteria

1. ✅ `年金账户号` 正确从 `集团企业客户号` 派生
2. ✅ `enrichment_index` 表包含 Legacy 映射数据
3. ✅ 202510 月度数据 `company_id` 解析率 > 50% (非临时 ID)
4. ✅ 所有新增单元测试通过
5. ✅ CLI Token 预检测正常工作

### Implementation Order

```
Phase 1: Data Layer [P0] - 30 min
├── alembic upgrade 20251208_000001
├── migrate_full_legacy_db.py
└── Verify enrichment_index data

Phase 2: Code Fix [P1] - 1 hour
├── Add CalculationStep for 年金账户号
├── Write unit tests
└── Local validation with 202510 data

Phase 3: Optional Enhancements [P2] - 45 min
├── CLI Token pre-check
└── Documentation update
```

---

## Appendix

### Related Documents

- Issue Analysis: `docs/specific/etl/20251216-guimo-mingxi-issue-analysis.md`
- Epic Definition: `docs/epics/epic-6-company-enrichment-service.md`
- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md`

### Key Code References

| File | Description |
|------|-------------|
| `pipeline_builder.py:165-176` | CompanyIdResolutionStep configuration |
| `pipeline_builder.py:201-272` | Pipeline step definitions |
| `company_id_resolver.py:195-408` | resolve_batch main logic |
| `legacy/data_cleaner.py:251-279` | Legacy 5-tier matching |

---

**Document Generated**: 2025-12-16
**Workflow**: Correct-Course (BMM)
**Approval Status**: Pending User Approval
