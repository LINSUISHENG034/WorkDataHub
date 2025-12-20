# Sprint Change Proposal: Annuity Module Architecture Alignment

**Date:** 2025-11-30
**Author:** Claude (Correct Course Workflow)
**Status:** Pending Approval
**Scope Classification:** Minor (Direct implementation by dev team)

---

## 1. Issue Summary

### Problem Statement

> **annuity_performance 模块没有使用已有的共享 Pipeline 框架，而是自己实现了一套并行的处理逻辑。**

### Discovery Context

- **Triggering Story:** Story 4.8 (Annuity Module Deep Refactoring)
- **Discovery Date:** 2025-11-30
- **Evidence Document:** `docs/specific/annuity-module-bloat-analysis.md`

### Root Cause

Tech-Spec 技术指导不完整：
1. Tech-Spec 只说"使用 Pipeline 框架"，没有指导"复用已有共享步骤"
2. 导致开发者在 `pipeline_steps.py` 中重新实现了所有步骤
3. 已有的 `domain/pipelines/steps/` 共享步骤完全没有被使用
4. 同时保留了 legacy 路径作为 fallback，形成双轨架构

### Quantified Impact

| 问题 | 影响行数 | 严重程度 |
|------|----------|----------|
| 双轨并行处理架构 | ~320行 | P0 (Critical) |
| 第三套转换逻辑 (transformations.py) | ~362行 | P1 (High) |
| 未使用共享步骤 | ~400-500行 | P1 (High) |
| 包装函数冗余 | ~100行 | P2 (Medium) |
| 多入口函数职责混乱 | ~200行 | P2 (Medium) |
| **总计可优化** | **~1,500行 (30%)** | - |

### Module Size Comparison

| 模块 | 文件数 | 总行数 | 功能复杂度 |
|------|--------|--------|------------|
| `annuity_performance/` | 11 | **4,942** | 高（含 enrichment） |
| `sample_trustee_performance/` | 3 | **629** | 中（类似业务逻辑） |
| **比例** | - | **7.9x** | - |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact Level | Description |
|------|--------------|-------------|
| **Epic 4** | ⚠️ Moderate | 需要添加 Story 4.9 进行模块重构 |
| **Epic 5** | ⚠️ Minor | Enrichment 集成点可能需要调整 |
| **Epic 9** | ✅ Positive | 重构后的 annuity 将成为更好的参考实现 |
| **Epic 6** | ⚠️ Minor | 需要更新测试以反映重构后的结构 |

### Story Impact

**Current Stories (Completed):**
- Story 4.7 (Pipeline Framework Refactoring): ✅ Done - 创建了共享步骤
- Story 4.8 (Annuity Module Deep Refactoring): ✅ Done - 部分优化

**New Story Required:**
- **Story 4.9: Annuity Module Decomposition for Reusability**
  - 目标: 将 annuity_performance 从 4,942 行减少到 <2,000 行
  - 方法: 删除双轨架构、使用共享步骤、清理冗余代码

### Artifact Conflicts

| Artifact | Conflict | Required Update |
|----------|----------|-----------------|
| `architecture.md` | ⚠️ Decision #3 未被遵循 | 添加强制性共享步骤使用指南 |
| `tech-spec-epic-4.md` | ⚠️ 缺少共享步骤使用要求 | 补充共享步骤使用指导 |
| Tests | ⚠️ transformations.py 测试 | 删除或更新相关测试 |
| Documentation | ⚠️ 模块文档 | 更新 annuity 模块文档 |

### Technical Impact

**Code Changes Required:**

1. **删除双轨架构** (`processing_helpers.py`)
   - 删除 `process_rows_via_legacy()` (~165行)
   - 统一到 `process_rows_via_pipeline()` 路径
   - 删除 `_determine_pipeline_mode()` 分支逻辑

2. **删除孤立代码** (`transformations.py`)
   - 删除整个文件 (~362行)
   - 删除相关测试文件

3. **使用共享步骤** (`pipeline_steps.py`)
   - 导入 `domain/pipelines/steps/` 的共享步骤
   - 删除重复实现的步骤类
   - 保留领域特定步骤 (PlanCodeCleansingStep, etc.)

4. **清理包装函数** (`schemas.py`)
   - 直接使用 `domain/pipelines/validation/helpers.py` 的函数
   - 删除冗余的包装函数

---

## 3. Recommended Approach

### Selected Path: Option 1 - Direct Adjustment

**Add Story 4.9 to Epic 4 for module refactoring**

### Rationale

| Factor | Assessment |
|--------|------------|
| **Implementation Effort** | Medium - 有详细分析报告指导 |
| **Technical Risk** | Low - 问题已被充分理解 |
| **Timeline Impact** | 1-2 days |
| **Long-term Maintainability** | High - 重构后代码更清晰 |
| **Business Value** | Supports PRD goal "add a domain in <4 hours" |

### Alternatives Considered

| Option | Viability | Reason |
|--------|-----------|--------|
| **Rollback** | ❌ Not viable | 会丢失 Story 4.7/4.8 创建的有价值基础设施 |
| **MVP Review** | ❌ Not needed | MVP 功能已完成，这是技术债务清理 |
| **Defer to Epic 9** | ⚠️ Possible but not recommended | 会让 Epic 9 继承不良参考实现 |

---

## 4. Detailed Change Proposals

### Story Changes

#### NEW: Story 4.9 - Annuity Module Decomposition for Reusability

**As a** data engineer,
**I want** the annuity_performance module to use shared pipeline infrastructure,
**So that** the module is maintainable and serves as a clean reference for future domain migrations.

**Acceptance Criteria:**

1. **AC-4.9.1:** Module size reduced from 4,942 to <2,000 lines
2. **AC-4.9.2:** Dual-track architecture removed (single pipeline path)
3. **AC-4.9.3:** Shared steps from `domain/pipelines/steps/` are used
4. **AC-4.9.4:** `transformations.py` and related tests deleted
5. **AC-4.9.5:** All existing tests pass after refactoring
6. **AC-4.9.6:** Real data validation passes (202412 dataset)

**Technical Tasks:**

```
[ ] 1. 删除双轨架构
    - 删除 process_rows_via_legacy() 函数
    - 删除 _determine_pipeline_mode() 分支逻辑
    - 统一到 process_rows_via_pipeline() 路径

[ ] 2. 删除孤立代码
    - 删除 transformations.py (~362行)
    - 删除 tests/unit/.../test_transformations.py
    - 删除 tests/integration/.../test_transformations_real_data.py

[ ] 3. 使用共享步骤
    - 导入 ColumnNormalizationStep, DateParsingStep, etc.
    - 删除 pipeline_steps.py 中的重复实现
    - 保留领域特定步骤

[ ] 4. 清理包装函数
    - 直接使用 domain/pipelines/validation/helpers.py
    - 删除 schemas.py 中的冗余包装函数

[ ] 5. 更新测试
    - 更新单元测试以反映新结构
    - 验证集成测试通过

[ ] 6. 更新文档
    - 更新 annuity 模块文档
    - 更新 architecture.md 共享步骤使用指南
```

### Architecture Changes

#### architecture.md Updates

**Section: Decision #3 - Hybrid Pipeline Step Protocol**

Add mandatory guidance:

```markdown
#### Mandatory Shared Step Usage

All domain pipelines MUST use shared steps from `domain/pipelines/steps/` where applicable:

| Shared Step | When to Use |
|-------------|-------------|
| `ColumnNormalizationStep` | All domains with Excel input |
| `DateParsingStep` | All domains with date fields |
| `CustomerNameCleansingStep` | All domains with customer names |
| `FieldCleanupStep` | All domains before Gold projection |

Domain-specific steps should ONLY be created for:
- Business logic unique to that domain
- Mappings specific to that domain (e.g., PlanCodeCleansingStep)
- Enrichment logic specific to that domain
```

### PRD Changes

**No PRD changes required.** This is a technical debt cleanup that supports existing PRD goals.

---

## 5. Implementation Handoff

### Scope Classification: Minor

**Direct implementation by development team**

### Responsibilities

| Role | Responsibility |
|------|----------------|
| **Developer** | Implement Story 4.9 changes |
| **Developer** | Update tests and documentation |
| **SM (Code Review)** | Review refactoring for quality |
| **Architect** | Update architecture.md guidance |

### Success Criteria

1. ✅ Module size: 4,942 → <2,000 lines
2. ✅ All existing tests pass
3. ✅ Real data validation passes (202412 dataset)
4. ✅ No regression in pipeline functionality
5. ✅ Architecture documentation updated

### Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Story 4.9 Implementation | 1-2 days | Refactored module |
| Code Review | 0.5 day | Approved PR |
| Documentation Update | 0.5 day | Updated docs |
| **Total** | **2-3 days** | - |

---

## 6. Appendix

### Reference Documents

- `docs/specific/annuity-module-bloat-analysis.md` - Detailed problem analysis
- `docs/architecture.md` - Architecture decisions
- `docs/sprint-artifacts/tech-spec-epic-4.md` - Epic 4 technical specification
- `docs/epics.md` - Epic and story definitions

### Optimization Scenarios

| Scenario | Target Lines | Reduction |
|----------|--------------|-----------|
| Conservative (P0+P2) | ~3,500 | -29% |
| Moderate (P0+P1+P2) | ~2,500 | -49% |
| Aggressive (Full refactor) | ~1,500 | -70% |

**Recommended:** Moderate optimization targeting ~2,500 lines

---

## Approval

**Status:** ✅ APPROVED

**Approval Date:** 2025-11-30
**Approved By:** Link (via Party Mode consensus)

**Team Consensus (Party Mode Discussion):**
- 🏗️ Winston (Architect): Approved - supports shared step reuse
- 📋 John (PM): Approved - delivers measurable business value for Epic 9
- 🏃 Bob (SM): Approved - ACs are clear and actionable
- 💻 Amelia (Dev): Approved - 2-3 day estimate confirmed
- 🧪 Murat (TEA): Approved - recommends 0.5 day buffer for test archaeology
- 📚 Paige (Tech Writer): Approved - will add concrete example post-refactoring
- 📊 Mary (Analyst): Approved - identified process gap for future improvement

**Follow-up Items:**
- [ ] Tech-Spec Template Enhancement (separate backlog item)
- [ ] Documentation example after Story 4.9 complete

---

*Generated by Correct Course Workflow*
*🤖 Generated with [Claude Code](https://claude.com/claude-code)*
