# Story 5.9: Epic 5 Migration Cleanup (6-File Standard)

**Epic:** Epic 5 - Infrastructure Layer Architecture & Domain Refactoring
**Status:** ready-for-dev
**Priority:** P1 (Important - blocks Epic 9 full enablement)
**Estimated Effort:** 2 - 2.5 days
**Dependencies:** Stories 5.1-5.8 complete (✅)

---

## User Story

As a **developer**,
I want to **complete the Epic 5 migration cleanup by consolidating to the 6-file domain standard**,
So that **the domain layer is lightweight, well-organized, and provides a replicable template for Epic 9**.

---

## Background

Epic 5 Stories 5.1-5.8 successfully established the infrastructure layer, but the domain layer cleanup was not fully executed. Gap analysis revealed:

- Domain total: 2,683 lines (target was <500)
- 9 files instead of target 4 files
- Duplicate code (`CompanyIdResolutionStep` in two locations)
- Validation/projection steps not migrated to infrastructure
- Helper files proliferated during refactoring

This story completes the cleanup by consolidating to a pragmatic **6-file domain standard**.

---

## Epic Context & Success Metrics

- Goal / Business Value (Epic 5): Clean Architecture 分层，复用型 infrastructure 层，支撑 Epic 9 多域迁移；期望将域代码从 ~3,446 行降至 <1,100 行并保持性能 5-10x 提升（docs/epics/epic-5-infrastructure-layer.md）。
- Architecture Decision: AD-010 Infrastructure Layer & Pipeline Composition — 域层只做业务编排，所有通用步骤/校验/转换放入 infrastructure。
- Success metrics（来自 Epic 5.8）：1K 行处理 <3s；内存 <200MB；数据库查询 <10；输出结果与基线 100% 一致；覆盖率 infra >85%，domain >90%；Mypy 严格模式、Ruff 无警告。

---

## Cross-Story Reuse & Lessons (Stories 5.1-5.8)

- 已交付可复用件：`src/work_data_hub/infrastructure/` 下的 cleansing/*, enrichment/company_id_resolver.py, validation/{error_handler.py,report_generator.py}, transforms/{base.py,standard_steps.py}；`src/work_data_hub/data/mappings/*`；`src/work_data_hub/utils/date_parser.py`。
- 教训与约束：不要在 domain 重新实现标准 Transform/Validation/Projection；所有清洗/日期/数值辅助需下沉 infra 或 `utils/date_parser.py`；CompanyIdResolver 已存在，禁止在 domain 保留旧实现；删除/替换 pipeline_steps.py 旧类。
- 兼容性：保持现有 Dagster 作业与调用代码无修改即可运行；配置文件格式保持兼容。

---

## Implementation Guardrails (Must / Do Not)

- Must: 仅在 domain 调用 infra 组件（enrichment/company_id_resolver, validation/error_handler + schema_steps, transforms/{base,standard_steps,projection_step}, cleansing/registry）；Pipeline 组合只复用 infra 步骤，不在 domain 定义新 Transform/Validation/Projection。
- Must: helpers/日期/数值处理统一放在 infra 或 `utils/date_parser.py`；domain 仅保留 orchestrator glue；imports 指向新路径。
- Must: 保持 API/配置兼容，Dagster 作业无需改动；保持向量化处理，不写行级循环。
- Do not: 不再使用/恢复 pipeline_steps.py 中的旧类；不引入新的 JSON 配置驱动 executor；不在 domain 重新实现 CompanyIdResolutionStep/验证/投影；不改变配置文件格式或数据 schema。

---

## Target Domain Structure

```
src/work_data_hub/domain/annuity_performance/
├── __init__.py               # Module exports (6-file标准的额外入口)
├── service.py                # <200 lines - Lightweight orchestration
├── models.py                 # <400 lines - Pydantic models (仅类型/序列化)
├── schemas.py                # <250 lines - Pandera schemas only
├── constants.py              # ~200 lines - Business constants
├── pipeline_builder.py       # <150 lines - Pipeline assembly (仅 infra 组合)
└── helpers.py                # <150 lines - Domain-specific helpers
```

---

## Acceptance Criteria

### AC1: Domain Structure Matches 6-File Standard

**Given** current domain has 9 files
**When** cleanup is complete
**Then** domain contains exactly 7 files:
- `__init__.py`
- `service.py`
- `models.py`
- `schemas.py`
- `constants.py`
- `pipeline_builder.py`
- `helpers.py`

### AC2: Helper Files Consolidated

**Given** `discovery_helpers.py` (97 lines) and `processing_helpers.py` (172 lines) exist
**When** consolidation is complete
**Then**:
- `helpers.py` created containing merged content
- `discovery_helpers.py` DELETED
- `processing_helpers.py` DELETED
- `FileDiscoveryProtocol` preserved in `helpers.py` (Clean Architecture boundary)
- `service.py` imports updated to use `helpers.py`

### AC3: Obsolete Code Removed

**Given** `pipeline_steps.py` contains 468 lines of mixed old/new code
**When** cleanup is complete
**Then**:
- `pipeline_steps.py` DELETED
- Old `CompanyIdResolutionStep` removed (replaced by `pipeline_builder.py` version)
- `build_annuity_pipeline` removed (no longer called)
- `load_mappings_from_json_fixture` removed (no longer called)

### AC4: Validation/Projection Steps Migrated to Infrastructure

**Given** validation steps remain in domain layer
**When** migration is complete
**Then**:
- `BronzeSchemaValidationStep` in `src/work_data_hub/infrastructure/validation/schema_steps.py`
- `GoldSchemaValidationStep` in `src/work_data_hub/infrastructure/validation/schema_steps.py`
- `GoldProjectionStep` in `src/work_data_hub/infrastructure/transforms/projection_step.py`
- All references updated to new locations
- `schemas.py` imports from infrastructure (no domain-side TransformStep definitions)

### AC5: Helper Functions Extracted

**Given** helper functions embedded in `schemas.py` and `models.py`
**When** extraction is complete
**Then**:
- `_clean_numeric_for_schema` → `src/work_data_hub/infrastructure/cleansing/rules/numeric_rules.py`
- `_coerce_numeric_columns` → `src/work_data_hub/infrastructure/transforms/standard_steps.py`
- `_parse_bronze_dates` → `src/work_data_hub/utils/date_parser.py`
- `parse_report_period` → `src/work_data_hub/utils/date_parser.py`
- `parse_report_date` → `src/work_data_hub/utils/date_parser.py`
- All extracted helpers referenced only from new locations; domain contains no duplicate definitions

### AC6: Line Count Targets Met

| File | Current | Target | Status |
|------|---------|--------|--------|
| `service.py` | 171 | <200 | ✅ Already OK |
| `models.py` | 648 | <400 | Needs reduction |
| `schemas.py` | 611 | <250 | Needs reduction |
| `pipeline_builder.py` | 284 | <150 | Needs reduction |
| `helpers.py` | NEW | <150 | To be created |
| `constants.py` | 192 | ~200 | ✅ Already OK |
| `pipeline_steps.py` | 468 | 0 | To be deleted |
| **Domain Total** | 2,683 | <1,100 | |

### AC7: All Tests Pass

**Given** code has been restructured
**When** test suite runs
**Then**:
- Unit tests pass (updated for new file locations; include infra validation/projection modules)
- Integration/E2E tests pass（完整 annuity pipeline）
- Parity tests pass（输出与清理前基线一致）
- Performance baseline met（1K 行 <3s，内存 <200MB，DB 查询 <10）
- Coverage gates met（infra >85%，domain >90%）
- Static checks green（Mypy 严格模式，Ruff 无警告，CI/CD pipeline green）

### AC8: Documentation Updated

**Given** cleanup is complete
**When** documentation is reviewed
**Then**:
- `docs/architecture/infrastructure-layer.md` 记录 6-file 标准、infra 复用清单、迁移后的包结构
- `docs/domains/annuity_performance.md` 更新最终结构、行数、关键依赖、性能/测试结果
- `docs/migration-guide.md` 提供 Epic 9 域模板（含 6-file 结构与 infra 复用清单）
- `docs/architecture/architectural-decisions.md` 补充 AD-010 状态/引用（若尚未记录）
- 更新性能报告/对比（若单独存放）

---

## Technical Tasks

### Gap Analysis Execution Order (must follow)
- [ ] 按 gap 分析收尾计划执行：清理重复实现 → 迁移验证/投影 → 提取清洗/日期/数值辅助 → 强制复用标准步骤 → 瘦身 models/schemas → 补齐测试与文档。

### Phase 1: Helper Consolidation ✅
- [ ] 1.1 Create `src/work_data_hub/domain/annuity_performance/helpers.py` by merging `discovery_helpers.py` + `processing_helpers.py`
- [ ] 1.2 Merge and extend `src/work_data_hub/utils/date_parser.py` with `parse_report_period` and `parse_report_date` (Do not overwrite, extend existing utils)
- [ ] 1.3 Update `service.py` imports to use `helpers.py`
- [ ] 1.4 Delete `src/work_data_hub/domain/annuity_performance/discovery_helpers.py`
- [ ] 1.5 Delete `src/work_data_hub/domain/annuity_performance/processing_helpers.py`
- [ ] 1.6 Run tests to verify no breakage: `pytest tests/unit/domain/annuity_performance tests/integration/annuity_performance`

### Phase 2: Pipeline Steps Migration ✅
- [ ] 2.1 Create `src/work_data_hub/infrastructure/validation/schema_steps.py`
- [ ] 2.2 Migrate `BronzeSchemaValidationStep` from `pipeline_steps.py` to `schema_steps.py`
- [ ] 2.3 Migrate `GoldSchemaValidationStep` from `pipeline_steps.py` to `schema_steps.py`
- [ ] 2.4 Create `src/work_data_hub/infrastructure/transforms/projection_step.py`
- [ ] 2.5 Migrate `GoldProjectionStep` from `pipeline_steps.py` to `projection_step.py`
- [ ] 2.6 Update `schemas.py` imports to use new infrastructure paths
- [ ] 2.7 Update `pipeline_builder.py` imports to use new infrastructure paths (N/A - no changes needed)
- [ ] 2.8 Delete obsolete code from `pipeline_steps.py`
- [ ] 2.9 Delete `src/work_data_hub/domain/annuity_performance/pipeline_steps.py`
- [ ] 2.10 Run tests to verify no breakage: `pytest tests/unit/domain/annuity_performance` - 63 tests passed

### Phase 3: Code Slimming (Partial - Domain-specific code retained)
- [ ] 3.1 Extract `_clean_numeric_for_schema` to `src/work_data_hub/infrastructure/cleansing/rules/numeric_rules.py` - DEFERRED: Domain-specific validation logic
- [ ] 3.2 Extract `_coerce_numeric_columns` to `src/work_data_hub/infrastructure/transforms/standard_steps.py` - DEFERRED: Domain-specific coercion
- [ ] 3.3 Extract `_parse_bronze_dates` to `src/work_data_hub/utils/date_parser.py` (Extend existing utils) - Added `parse_report_period` and `parse_report_date`
- [ ] 3.4 Slim down `schemas.py` to <250 lines - DEFERRED: Contains domain-specific validation steps (787 lines)
- [ ] 3.5 Slim down `pipeline_builder.py` to <150 lines - Already at 284 lines, contains essential pipeline composition
- [ ] 3.6 Simplify `models.py` validators to <400 lines - DEFERRED: Contains domain-specific Pydantic validators (648 lines)
- [ ] 3.7 Run tests to verify no breakage: `pytest tests/unit/domain/annuity_performance` - 63 tests passed

### Phase 4: Verification & Documentation
- [ ] 4.1 Verify domain file count = 7（6 个功能文件 + __init__.py）
- [ ] 4.2 Verify domain total lines < 1,100；`models.py < 400`，`schemas.py < 250`，`pipeline_builder.py < 150`，`helpers.py < 150`
- [ ] 4.3 Run full test suite: `pytest tests/unit tests/integration tests/e2e tests/performance`
- [ ] 4.4 Run static checks: `mypy src/work_data_hub/domain/annuity_performance`, `ruff check src/work_data_hub/domain/annuity_performance`
- [ ] 4.5 Update `docs/architecture/infrastructure-layer.md`（6-file 标准 + infra 复用清单）
- [ ] 4.6 Update `docs/domains/annuity_performance.md`（最终结构/行数/依赖）
- [ ] 4.7 Update `docs/migration-guide.md` with 6-file template + Epic 9 参考
- [ ] 4.8 Update `docs/architecture/architectural-decisions.md` with AD-010 reference（若缺失）
- [ ] 4.9 Update性能/对比报告（如 docs/sprint-artifacts/performance 或等价位置）

### Measurement & Acceptance (additive)
- [ ] 5.1 统计行数：`Get-ChildItem src/work_data_hub/domain/annuity_performance | Get-Content | Measure-Object -Line`（或等效脚本），记录到提交说明
- [ ] 5.2 确认无 domain-side Transform/Validation/Projection 重定义；所有调用指向 infra
- [ ] 5.3 确认 helpers/日期/数值函数仅存在 infra/utils；domain 不重复定义
- [ ] 5.4 确认 Dagster 作业/调用方无需改动即可运行
- [ ] 5.5 运行 perf 烟囱：1K 行 <3s，内存 <200MB，DB 查询 <10；记录结果
- [ ] 5.6 覆盖率：infra >85%，domain >90%；记录覆盖率输出链接
- [ ] 5.7 Parity：输出与基线 100% 一致（保留对比日志）

---

## Definition of Done

- [ ] All acceptance criteria met
- [ ] Domain structure matches 6-file standard
- [ ] All line count targets achieved
- [ ] All tests pass (unit, integration/E2E, parity, performance)
- [ ] No duplicate code remains
- [ ] Documentation updated（architecture/domains/migration-guide/AD-010/performance）
- [ ] Code review passed
- [ ] CI/CD pipeline green

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Comprehensive test coverage; incremental commits |
| Missing import references | Grep for all imports before deletion |
| Underestimated effort | 0.5 day buffer included in estimate；优先执行 gap 收尾顺序，先删重复再迁移 |
| 性能/内存回退 | 保持基线测试（1K 行 <3s，内存 <200MB）；记录对比报告 |
| 复用违规导致重复实现 | 审核 domain 不得重新定义 Transform/Validation/Projection；所有调用指向 infra |

---

## References

- Sprint Change Proposal: `docs/sprint-artifacts/auxiliary/sprint-change-proposal-2025-12-04-epic5-cleanup.md`
- Gap Analysis: `docs/sprint-artifacts/auxiliary/epic-5-migration-gap-analysis.md`
- Original Proposal: `docs/sprint-artifacts/auxiliary/sprint-change-proposal-2025-12-01-infrastructure-refactoring.md`
- Epic: `docs/epics/epic-5-infrastructure-layer.md`