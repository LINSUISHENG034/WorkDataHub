# Tech-Spec: Epic 5.5 - Pipeline Architecture Validation (AnnuityIncome Domain)

**Created:** 2025-12-04
**Status:** Ready for Development
**Epic:** 5.5 - Pipeline Architecture Validation
**Blocking:** Epic 6 (Company Enrichment Service)

---

## Overview

### Problem Statement

Epic 5 successfully established the Infrastructure Layer with a single domain (AnnuityPerformance). However, validating architecture generality with only one domain is insufficient. Before committing to Epic 6 and batch domain migrations, we need to:

1. **Validate architecture reusability** - Prove the 6-file domain standard works for multiple domains
2. **Identify code reuse opportunities** - AnnuityIncome shares ~70% cleansing logic with AnnuityPerformance
3. **Establish documentation standards** - Create cleansing rules documentation template for future migrations

### Solution

Implement the AnnuityIncome domain using the established Infrastructure Layer, following the exact same 6-file standard and patterns from Epic 5. This validates architecture generality while establishing documentation standards for future domain migrations.

### Scope

**In Scope:**
- Story 5.5.1: Document legacy `AnnuityIncomeCleaner` cleansing rules
- Story 5.5.2: Implement `annuity_income` domain (6-file standard), marking duplicate code with TODO comments
- Story 5.5.3: Validate 100% parity with legacy output
- Story 5.5.4: **Extract shared code to Infrastructure** + Multi-domain integration testing + optimization recommendations

**Out of Scope:**
- Implementing additional domains beyond `annuity_income`
- Breaking changes to validated core components (CompanyIdResolver core logic, CleansingRegistry core logic)
- Performance optimizations beyond code reuse (defer to Epic 6)

### Development Strategy: Phased Optimization (方案 C)

Epic 5.5 采用**分阶段优化**策略，平衡风险控制和代码复用目标：

```
Phase 1 (5.5.1-5.5.3): 实现并验证 - 允许代码复制，标记重复
Phase 2 (5.5.4):       集中重构 - 提取共享代码到 Infrastructure
```

**优势:**
- Story 5.5.2 保持简单，专注于"让它工作"
- Story 5.5.3 有稳定基线进行 Parity 验证
- Story 5.5.4 集中处理所有提取，统一测试
- Git 历史清晰：功能实现和重构分开提交

**约束:**
- Story 5.5.2 中的重复代码必须使用规范化 TODO 标记
- Story 5.5.4 只提取在 5.5.2 中标记的代码，不引入新范围
- 回归测试是 5.5.4 的 Gate：两个域的所有测试必须通过

---

## Context for Development

### Epic 5 Architecture Reference (6-File Domain Standard)

The `annuity_income` domain MUST follow the exact same structure as `annuity_performance`:

```
src/work_data_hub/domain/annuity_income/
├── __init__.py              # Module exports
├── constants.py             # Mappings, defaults, magic strings
├── helpers.py               # Utility functions, protocols
├── models.py                # Pydantic models (In/Out)
├── schemas.py               # Pandera validation schemas (Bronze/Gold)
├── pipeline_builder.py      # Pipeline composition
└── service.py               # Lightweight service orchestrator
```

### Codebase Patterns to Follow

#### Pattern 1: Input/Output Model Separation
```python
# models.py - Input model is permissive
class AnnuityIncomeIn(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)
    # Accept Chinese field names with aliases

# Output model is strict
class AnnuityIncomeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Only allowed fields, all validated
```

#### Pattern 2: Bronze/Gold Schema Separation
```python
# schemas.py
class BronzeAnnuityIncomeSchema(pa.DataFrameModel):
    # Minimal validation, nullable fields, coercion enabled

class GoldAnnuityIncomeSchema(pa.DataFrameModel):
    # Strict validation, non-nullable required fields
    # Composite primary key constraint
```

#### Pattern 3: Pipeline Composition
```python
# pipeline_builder.py
def build_bronze_to_silver_pipeline(...) -> Pipeline:
    steps = [
        MappingStep({...}),           # Column renames
        CalculationStep({...}),       # Derived fields
        CleansingStep(domain="annuity_income"),
        CompanyIdResolutionStep(...),
        DropStep([...]),              # Remove legacy columns
    ]
    return Pipeline(steps)
```

#### Pattern 4: Lightweight Service Orchestrator
```python
# service.py
def process_annuity_income(
    month: str,
    *,
    file_discovery: FileDiscoveryProtocol,
    warehouse_loader: Any,
    enrichment_service: Optional[CompanyEnrichmentService] = None,
) -> DomainPipelineResult:
    # Validate → Discover → Process → Load → Return metrics
```

### Files to Reference

| File | Purpose |
|------|---------|
| `src/work_data_hub/domain/annuity_performance/` | Reference implementation (copy structure) |
| `legacy/annuity_hub/data_handler/data_cleaner.py:237-274` | Legacy `AnnuityIncomeCleaner` source |
| `legacy/annuity_hub/data_handler/mappings.py` | Mapping tables (COMPANY_BRANCH_MAPPING, etc.) |
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | CompanyIdResolver (reuse) |
| `src/work_data_hub/infrastructure/cleansing/registry.py` | CleansingRegistry (reuse) |
| `src/work_data_hub/infrastructure/transforms/standard_steps.py` | Standard pipeline steps (reuse) |
| `config/data_sources.yml` | Domain configuration (add annuity_income) |
| `src/work_data_hub/infrastructure/cleansing/settings/cleansing_rules.yml` | Cleansing rules (add annuity_income) |

### Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Domain structure | 6-file standard | Proven in Epic 5, ensures consistency |
| Infrastructure reuse | Use existing components | CompanyIdResolver, CleansingRegistry already validated |
| Configuration approach | YAML-driven | Consistent with Epic 5 patterns |
| Testing strategy | Parity validation + unit tests | Ensures legacy compatibility |
| Company ID fallback | **CalculationStep after CompanyIdResolutionStep** | 保持 CompanyIdResolutionStep 单一职责，使用 Pipeline 组合模式添加 COMPANY_ID5_MAPPING fallback |
| Duplicate code handling | **TODO 标记 → 5.5.4 集中提取** | 分阶段优化，降低风险 |

### Code Reuse Strategy

#### TODO 标记规范

Story 5.5.2 中发现的重复代码必须使用以下格式标记：

```python
# TODO(5.5.4): Extract to infrastructure/mappings/shared_mappings.py
# Duplicated from: annuity_performance/constants.py
# Reuse potential: HIGH (used by 2+ domains)
COMPANY_BRANCH_MAPPING = {
    "总部": "G00",
    "北京": "G01",
    # ...
}
```

#### Extraction Candidates (已识别)

| 候选代码 | 当前位置 | 复用潜力 | 目标位置 | Story |
|----------|----------|----------|----------|-------|
| `COMPANY_BRANCH_MAPPING` | annuity_performance/constants.py | 高 | infrastructure/mappings/shared.py | 5.5.4 |
| `BUSINESS_TYPE_CODE_MAPPING` | annuity_performance/constants.py | 高 | infrastructure/mappings/shared.py | 5.5.4 |
| `DEFAULT_PORTFOLIO_CODE_MAPPING` | annuity_performance/constants.py | 高 | infrastructure/mappings/shared.py | 5.5.4 |
| `normalize_month()` | annuity_performance/helpers.py | 高 | infrastructure/utils/date_utils.py | 5.5.4 |
| `convert_dataframe_to_models()` | annuity_performance/helpers.py | 中 | 评估是否值得抽象 | 5.5.4 |

#### Extraction Flow (Story 5.5.4)

```
1. 收集所有 TODO(5.5.4) 标记
2. 按目标位置分组
3. 创建 infrastructure 模块 (如 infrastructure/mappings/shared.py)
4. 提取代码到新模块
5. 更新 annuity_performance 引用
6. 更新 annuity_income 引用
7. 运行两个域的完整测试套件
8. 验证 Parity 仍然 100%
```

---

## Implementation Plan

### Story 5.5.1: Legacy Cleansing Rules Documentation

**Goal:** Document all cleansing rules from `AnnuityIncomeCleaner`

**Output:** `docs/cleansing-rules/annuity-income.md`

#### Tasks

- [ ] **Task 1.1:** Analyze legacy code (lines 237-274)
  - Extract column rename operations
  - Document cleansing operations in execution order
  - Identify all mapping tables used

- [ ] **Task 1.2:** Document Company ID resolution strategy
  - Primary: `_update_company_id()` with plan_code_col='计划号'
  - Fallback: `年金账户名` → `COMPANY_ID5_MAPPING`

- [ ] **Task 1.3:** Create `docs/cleansing-rules/annuity-income.md`
  - Use template from `docs/templates/cleansing-rules-template.md`
  - Complete all sections

#### Legacy Code Analysis (AnnuityIncomeCleaner)

```python
# Source: legacy/annuity_hub/data_handler/data_cleaner.py:237-274
# Excel Sheet: 收入明细

# Operations in execution order:
1. df.rename(columns={'机构': '机构代码'})
2. df['机构代码'] = df['机构名称'].map(COMPANY_BRANCH_MAPPING)
3. df['月度'] = df['月度'].apply(parse_to_standard_date)
4. df['机构代码'] = df['机构代码'].replace('null', 'G00').fillna('G00')
5. df['组合代码'] = df['组合代码'].str.replace('^F', '', regex=True)
6. df['组合代码'] = conditional_default(业务类型 in ['职年受托','职年投资'] → 'QTAN003', else DEFAULT_PORTFOLIO_CODE_MAPPING)
7. df['产品线代码'] = df['业务类型'].map(BUSINESS_TYPE_CODE_MAPPING)
8. df['年金账户名'] = df['客户名称']  # Preserve original
9. df['客户名称'] = df['客户名称'].apply(clean_company_name)
10. df = _update_company_id(df, plan_code_col='计划号', customer_name_col='客户名称')
11. df.loc[mask, 'company_id'] = df['年金账户名'].map(COMPANY_ID5_MAPPING)  # Fallback
```

#### Acceptance Criteria

- [ ] AC1: All column mappings documented
- [ ] AC2: All cleansing rules catalogued with rule type and logic
- [ ] AC3: Company ID resolution strategy documented (including COMPANY_ID5_MAPPING fallback)
- [ ] AC4: Document follows template format

---

### Story 5.5.2: AnnuityIncome Domain Implementation

**Goal:** Implement AnnuityIncome domain using Infrastructure Layer

**Output:** `src/work_data_hub/domain/annuity_income/` (6-file standard)

#### Tasks

- [ ] **Task 2.1:** Create domain directory structure
  ```
  src/work_data_hub/domain/annuity_income/
  ├── __init__.py
  ├── constants.py
  ├── helpers.py
  ├── models.py
  ├── schemas.py
  ├── pipeline_builder.py
  └── service.py
  ```

- [ ] **Task 2.2:** Implement `constants.py`
  - Copy relevant mappings from `annuity_performance/constants.py` **with TODO(5.5.4) markers**
  - Add AnnuityIncome-specific constants:
    - `COLUMN_ALIAS_MAPPING` for 收入明细 sheet
    - `LEGACY_COLUMNS_TO_DELETE` specific to this domain
    - `COMPANY_ID5_MAPPING` (AnnuityIncome-specific, no extraction needed)
  - Mark shared mappings for extraction: `COMPANY_BRANCH_MAPPING`, `BUSINESS_TYPE_CODE_MAPPING`, `DEFAULT_PORTFOLIO_CODE_MAPPING`

- [ ] **Task 2.3:** Implement `models.py`
  - `AnnuityIncomeIn`: Permissive input model
    - Fields: 月度, 机构, 机构名称, 计划号, 客户名称, 业务类型, 计划类型, 组合代码, 收入金额, etc.
  - `AnnuityIncomeOut`: Strict output model
    - Required: 月度, 计划号, company_id, 客户名称, 产品线代码
  - `EnrichmentStats`: Reuse from annuity_performance or create similar

- [ ] **Task 2.4:** Implement `schemas.py`
  - `BronzeAnnuityIncomeSchema`: Minimal validation
  - `GoldAnnuityIncomeSchema`: Strict validation with composite key
  - `validate_bronze_dataframe()`, `validate_gold_dataframe()`

- [ ] **Task 2.5:** Implement `helpers.py`
  - Copy `normalize_month()` from annuity_performance **with TODO(5.5.4) marker**
  - Implement domain-specific helpers if needed
  - `convert_dataframe_to_models()` for AnnuityIncome **with TODO(5.5.4) marker if similar to annuity_performance**

- [ ] **Task 2.6:** Implement `pipeline_builder.py`
  - `build_bronze_to_silver_pipeline()` with steps:
    1. MappingStep: `{'机构': '机构代码'}`
    2. CalculationStep: 机构代码 from 机构名称 via COMPANY_BRANCH_MAPPING
    3. CalculationStep: Date parsing for 月度
    4. CalculationStep: 机构代码 default to 'G00'
    5. CalculationStep: 组合代码 regex replace '^F' → ''
    6. CalculationStep: 组合代码 conditional default
    7. CalculationStep: 产品线代码 from 业务类型
    8. CalculationStep: Preserve 年金账户名 = 客户名称
    9. CleansingStep: domain="annuity_income"
    10. CompanyIdResolutionStep: standard resolution
    11. **CalculationStep: COMPANY_ID5_MAPPING fallback** (使用 年金账户名 填充空 company_id)
    12. DropStep: Remove legacy columns

  **Technical Decision**: COMPANY_ID5_MAPPING fallback 使用独立的 CalculationStep 实现，保持 CompanyIdResolutionStep 单一职责：
  ```python
  # Step 11: COMPANY_ID5_MAPPING fallback for empty company_id
  CalculationStep({
      'company_id': lambda df: df['company_id'].where(
          df['company_id'].notna() & (df['company_id'] != ''),
          df['年金账户名'].map(COMPANY_ID5_MAPPING)
      )
  })
  ```

- [ ] **Task 2.7:** Implement `service.py`
  - `process_annuity_income()` following same pattern as `process_annuity_performance()`
  - `process_with_enrichment()` with COMPANY_ID5_MAPPING fallback logic

- [ ] **Task 2.8:** Update configuration files
  - Add to `config/data_sources.yml`:
    ```yaml
    annuity_income:
      base_path: "tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集"
      file_patterns:
        - "*年金终稿*.xlsx"
      exclude_patterns:
        - "~$*"
        - "*回复*"
        - "*.eml"
      sheet_name: "收入明细"
      version_strategy: "highest_number"
      fallback: "error"
    ```
  - Add to `cleansing_rules.yml`:
    ```yaml
    annuity_income:
      客户名称:
        - trim_whitespace
        - normalize_company_name
      计划号:
        - trim_whitespace
      # ... other fields
    ```

- [ ] **Task 2.9:** Write unit tests
  - `tests/unit/domain/test_annuity_income_models.py`
  - `tests/unit/domain/test_annuity_income_pipeline.py`
  - `tests/unit/domain/test_annuity_income_service.py`
  - Target: >85% coverage

#### Acceptance Criteria

- [ ] AC1: Domain follows 6-file standard
- [ ] AC2: Uses infrastructure components (CompanyIdResolver, CleansingRegistry)
- [ ] AC3: Configuration added to `data_sources.yml`
- [ ] AC4: Cleansing rules added to `cleansing_rules.yml`
- [ ] AC5: Unit tests with >85% coverage
- [ ] AC6: All imports and exports properly configured in `__init__.py`

---

### Story 5.5.3: Legacy Parity Validation

**Goal:** Validate 100% parity with legacy `AnnuityIncomeCleaner` output

**Output:** Parity validation report

#### Tasks

- [ ] **Task 3.1:** Prepare test data
  - Identify real data file for validation
  - Create golden baseline from legacy cleaner output

- [ ] **Task 3.2:** Run parity validation
  - Follow `docs/runbooks/legacy-parity-validation.md` process
  - Compare row counts, column names, data values

- [ ] **Task 3.3:** Document results
  - Create validation report
  - Document any intentional differences
  - Save artifacts to `tests/fixtures/validation_results/`

#### Acceptance Criteria

- [ ] AC1: Follow legacy parity validation process
- [ ] AC2: 100% match rate achieved (or intentional differences documented)
- [ ] AC3: Validation artifacts saved

---

### Story 5.5.4: Code Extraction & Multi-Domain Integration Test

**Goal:** Extract shared code to Infrastructure + Validate multi-domain processing + Document optimization opportunities

**Output:**
- Extracted shared modules in `infrastructure/`
- Integration tests
- `docs/sprint-artifacts/epic-5.5-optimization-recommendations.md`

**Estimated Effort:** 2-3 days (expanded from original 1 day)

#### Tasks - Phase A: Code Extraction (集中重构)

- [ ] **Task 4.1:** Collect and review all TODO(5.5.4) markers
  - Scan `annuity_income/` for all TODO(5.5.4) comments
  - Group by target extraction location
  - Verify extraction candidates are still valid

- [ ] **Task 4.2:** Extract shared mappings to Infrastructure
  - Create `src/work_data_hub/infrastructure/mappings/shared.py`
  - Extract: `COMPANY_BRANCH_MAPPING`, `BUSINESS_TYPE_CODE_MAPPING`, `DEFAULT_PORTFOLIO_CODE_MAPPING`
  - Update `annuity_performance/constants.py` to import from shared
  - Update `annuity_income/constants.py` to import from shared
  - Add unit tests for shared mappings

- [ ] **Task 4.3:** Extract shared helpers to Infrastructure
  - Create `src/work_data_hub/infrastructure/utils/date_utils.py` (if not exists)
  - Extract: `normalize_month()`
  - Update both domains to import from infrastructure
  - Add unit tests for extracted helpers

- [ ] **Task 4.4:** Regression testing after extraction
  - Run full test suite for `annuity_performance` domain
  - Run full test suite for `annuity_income` domain
  - **Gate:** All tests must pass before proceeding

- [ ] **Task 4.5:** Re-validate Parity after extraction
  - Re-run parity validation for `annuity_income`
  - **Gate:** 100% parity must be maintained

#### Tasks - Phase B: Multi-Domain Integration Test

- [ ] **Task 4.6:** Create multi-domain integration test
  - Test file: `tests/integration/test_multi_domain_pipeline.py`
  - Test both `annuity_performance` and `annuity_income` in single run
  - Verify domain isolation (no data cross-contamination)

- [ ] **Task 4.7:** Record performance baseline
  - Processing time for each domain
  - Memory usage
  - Database query count

#### Tasks - Phase C: Documentation

- [ ] **Task 4.8:** Create optimization recommendations document
  - `docs/sprint-artifacts/epic-5.5-optimization-recommendations.md`
  - Document completed extractions and their impact
  - Identify remaining optimization opportunities for Epic 6
  - Recommendations for batch domain migrations

#### Acceptance Criteria

- [ ] AC1: All TODO(5.5.4) markers resolved (extracted or documented as deferred)
- [ ] AC2: Shared mappings extracted to `infrastructure/mappings/shared.py`
- [ ] AC3: Both domains use shared infrastructure modules
- [ ] AC4: All tests pass for both domains after extraction
- [ ] AC5: Parity validation still 100% after extraction
- [ ] AC6: Integration test scans and processes both domains
- [ ] AC7: Domain isolation verified
- [ ] AC8: Performance baseline recorded
- [ ] AC9: Optimization recommendations for Epic 6 documented

---

## Additional Context

### Parity Exception Criteria

在 Story 5.5.3 Parity 验证中，以下差异类型的处理方式：

| 差异类型 | 是否允许 | 处理方式 |
|----------|----------|----------|
| **数据类型改进** (如 string → proper date) | ✅ 允许 | 文档记录为 intentional improvement |
| **Null 处理改进** (如更一致的 NaN 处理) | ✅ 允许 | 文档记录为 intentional improvement |
| **精度改进** (如更多小数位) | ✅ 允许 | 文档记录为 intentional improvement |
| **业务逻辑差异** (如不同的 mapping 结果) | ❌ 不允许 | 必须修复，确保 100% 一致 |
| **行数差异** | ❌ 不允许 | 必须调查并修复 |
| **列缺失/多余** | ❌ 不允许 | 必须修复 |

### Test Data Acquisition Plan

| 数据需求 | 来源 | 状态 | 备注 |
|----------|------|------|------|
| 收入明细 Excel 文件 | `tests/fixtures/real_data/{YYYYMM}/收集数据/数据采集/` | 待确认 | 需要确认文件路径和 sheet 名称 |
| Legacy 输出基线 | 运行 `AnnuityIncomeCleaner` 生成 | 待生成 | Story 5.5.3 Task 3.1 |
| COMPANY_ID5_MAPPING | `legacy/annuity_hub/data_handler/mappings.py` | 可用 | 需要提取到 constants.py |

**Fallback Plan:** 如果无法获取真实生产数据：
1. 使用 `tests/fixtures/` 中的合成测试数据
2. 进行有限验证（结构验证 + 抽样值验证）
3. 在 Story 5.5.3 文档中标注 "Limited validation due to data availability"
4. 在 Epic 6 开始前使用真实数据进行完整验证

### Pre-work Completed (Story 5.5.1)

以下分析工作已在 Story 文件中完成，可直接用于文档化：

| 已完成项 | 位置 | 备注 |
|----------|------|------|
| Legacy 代码分析 (11 个操作步骤) | `docs/sprint-artifacts/stories/5.5-1-*.md` Dev Notes | 可直接转换为文档 |
| Mapping 表识别 | Story 文件 | 4 个 mapping 表已识别 |
| AnnuityPerformance 对比 | Story 文件 | ~70% 共享逻辑已识别 |

### Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Epic 5 Infrastructure Layer | Complete | CompanyIdResolver, CleansingRegistry ready |
| Legacy AnnuityIncomeCleaner | Available | Lines 237-274 in data_cleaner.py |
| Mapping tables | Available | COMPANY_BRANCH_MAPPING, BUSINESS_TYPE_CODE_MAPPING, etc. |
| Test data | **Required** | Need real 收入明细 data for parity validation (see Test Data Acquisition Plan) |
| COMPANY_ID5_MAPPING | **Required** | For 年金账户名 → company_id fallback (extract from legacy mappings.py) |

### Testing Strategy

| Test Type | Location | Coverage Target |
|-----------|----------|-----------------|
| Unit tests | `tests/unit/domain/test_annuity_income_*.py` | >85% |
| Integration tests | `tests/integration/test_multi_domain_pipeline.py` | Multi-domain processing |
| Parity validation | `tests/fixtures/validation_results/` | 100% match with legacy |
| E2E tests | `tests/e2e/test_annuity_income_pipeline_e2e.py` | Full pipeline execution |

### Mapping Tables Reference

| Mapping Table | Purpose | Shared with AnnuityPerformance |
|---------------|---------|-------------------------------|
| `COMPANY_BRANCH_MAPPING` | 机构名称 → 机构代码 | Yes |
| `BUSINESS_TYPE_CODE_MAPPING` | 业务类型 → 产品线代码 | Yes |
| `DEFAULT_PORTFOLIO_CODE_MAPPING` | 计划类型 → 默认组合代码 | Yes |
| `COMPANY_ID5_MAPPING` | 年金账户名 → company_id | **No** (AnnuityIncome-specific) |

### AnnuityIncome vs AnnuityPerformance Comparison

| Aspect | AnnuityPerformance | AnnuityIncome |
|--------|-------------------|---------------|
| Excel Sheet | 规模明细 | 收入明细 |
| Primary Key | (月度, 计划代码, company_id) | (月度, 计划号, company_id) |
| Plan Code Column | 计划代码 | 计划号 |
| Company ID Fallback | None | COMPANY_ID5_MAPPING via 年金账户名 |
| 组合代码 Processing | Default only | Regex replace '^F' + conditional default |
| 产品线代码 | Derived from 业务类型 | Derived from 业务类型 |

### Notes

1. **COMPANY_ID5_MAPPING Fallback**: AnnuityIncome has an additional company ID resolution step using `年金账户名` that AnnuityPerformance does not have. This must be implemented in the `CompanyIdResolutionStep` or as a post-processing step.

2. **组合代码 Regex**: AnnuityIncome removes '^F' prefix from 组合代码 before applying defaults. This is not present in AnnuityPerformance.

3. **年金账户名 Preservation**: The original `客户名称` is preserved as `年金账户名` before normalization. This is used for the COMPANY_ID5_MAPPING fallback.

4. **Shared Infrastructure**: All infrastructure components (CompanyIdResolver, CleansingRegistry, standard steps) should be used as-is without modification.

---

## Effort Estimate

| Story | 原估算 | 新估算 | 变化原因 |
|-------|--------|--------|----------|
| 5.5.1 | 0.5 天 | 0.5 天 | 不变 (Pre-work 已完成大部分分析) |
| 5.5.2 | 1-2 天 | 1-2 天 | 不变 (只标记重复代码，不重构) |
| 5.5.3 | 0.5 天 | 0.5 天 | 不变 |
| 5.5.4 | 1 天 | **2-3 天** | 扩展为代码提取 + 回归测试 + 集成测试 |
| **总计** | 3-5 天 | **4.5-6 天** | +1-1.5 天 (代码提取工作) |

---

## Success Criteria Summary

| Story | Success Criteria |
|-------|------------------|
| 5.5.1 | Cleansing rules document complete and follows template |
| 5.5.2 | Domain implemented with 6-file standard, >85% test coverage, **all duplicate code marked with TODO(5.5.4)** |
| 5.5.3 | 100% parity with legacy output achieved (or intentional improvements documented) |
| 5.5.4 | **Shared code extracted to infrastructure**, both domains use shared modules, all tests pass, integration test passing |

**Epic 5.5 Complete When:**
1. AnnuityIncome domain passes 100% parity validation
2. **Shared mappings and helpers extracted to Infrastructure layer**
3. **Both domains use shared infrastructure modules**
4. Integration test correctly processes both domains in single run
5. Cleansing rules documentation standard established
6. Architecture optimization recommendations documented
7. Ready to proceed to Epic 6 with validated and optimized architecture

---

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-04 | Claude | Initial Tech-Spec created |
| 2025-12-04 | Claude | Applied Cross-Functional War Room enhancements: Phased Optimization (方案 C), Code Reuse Strategy, Parity Exception Criteria, Test Data Acquisition Plan, expanded Story 5.5.4 |

---

*Generated by create-tech-spec workflow on 2025-12-04*
*Enhanced via Advanced Elicitation: Cross-Functional War Room*
