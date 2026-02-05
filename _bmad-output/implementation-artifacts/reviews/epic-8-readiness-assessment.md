# Epic 8 Readiness Assessment

**Created:** 2025-12-23
**Last Updated:** 2025-12-25
**Status:** Active - Pre-Flight Phase

---

## Executive Summary

Epic 7 (Code Quality - File Length Refactoring) 已成功完成全部6个Story。在进入Epic 8 (Testing & Validation Infrastructure) 之前，本文档整合了所有准备工作、已知问题和行动指引。

### 🆕 Epic 7.1 已创建

**所有P0/P1/P2问题已整合到 Epic 7.1：**
- **Reference:** [Sprint Change Proposal - Epic 7.1](../sprint-change-proposal/sprint-change-proposal-2025-12-23-epic-7.1-pre-epic8-fixes.md)
- **Status:** In Progress (sprint-status.yaml updated)
- **Scope:** 11 stories (4 P0 + 4 P1 + 3 P2)

### 关键决策

**Epic 8策略已修订:** 从"Golden Dataset"方案改为"Classification-Based Validation"方案。

| 原方案 | 新方案 |
|--------|--------|
| Legacy = 正确答案 | 业务规则 = 正确答案 |
| 8-1: Golden Dataset提取 | 8-1: Validation Rule Engine |
| 8-2: 自动对账引擎 | 8-2: Field Classification Framework |
| 8-3: CI集成对比测试 | 8-3: Regression Detection in CI |
| 8-4: 差异报告工具 | 8-4: Divergence Classification & Reporting |

**详细方案:** [Sprint Change Proposal](../../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-23-epic8-validation-strategy.md)

---

## 1. Current Project Health

### 1.1 Test Suite Status

| Metric | Value | Status |
|--------|-------|--------|
| Unit Tests Passed | 1990 | ✅ Healthy |
| Tests Failed | 33 | ⚠️ Mostly DB integration |
| Collection Errors | 2 | ⚠️ Module import issues |
| Skipped Tests | 169 | Expected (postgres/monthly markers) |
| Tech Debt (Ruff) | 1074 warnings | ⚠️ Documented in Story 7.6 |

### 1.2 Validation Results

| Test | Result | Notes |
|------|--------|-------|
| ETL Pipeline (plan-only) | ✅ PASS | 37,127 rows processed |
| GenericBackfillService | ✅ PASS | 4 FK tables validated |
| FileDiscoveryService | ✅ PASS | selection_strategy working |
| cleaner_compare.py | ✅ PASS | Bug fixed during retrospective |
| Numeric Fields Match | ✅ PASS | 100行样本零差异 |
| company_id Enrichment | ⚠️ 17差异 | 数据源差异，非代码BUG |

---

## 2. Pre-Flight Checklist

### 2.1 P0 - BLOCKING (必须完成)

| # | Action Item | Status | Details |
|---|-------------|--------|---------|
| P0-1 | 修复enrichment_index被意外清空 | ⏳ TODO | 见2.4节 |
| P0-2 | ETL `--execute`模式验证 | ⏳ TODO | 确认实际写入正常 |
| P0-3 | 修复测试收集错误(2个文件) | ⏳ TODO | 见2.5节 |

### 2.2 P1 - HIGH (强烈建议)

| # | Action Item | Status | Details |
|---|-------------|--------|---------|
| P1-1 | cleaner_compare.py添加`--file-selection` | ✅ DONE | Story 7.1-5 |
| P1-2 | 修复分类逻辑 | ✅ DONE | Story 7.1-6 |
| P1-3 | 确认Legacy数据库连接 | ✅ VERIFIED | Story 7.1-7 (with notes) |

### 2.3 P2 - MEDIUM (推荐)

| # | Action Item | Status |
|---|-------------|--------|
| P2-1 | 清理33个失败测试 | ⏳ TODO |
| P2-2 | 分类1074个Ruff警告 | ⏳ TODO |
| P2-3 | 更新project-context.md | ⏳ TODO |

### 2.4 P0-1 详情: enrichment_index被清空

**症状:** `enterprise.enrichment_index`表数据被意外清空

**相关文件(含DELETE语句):**
```
scripts/migrations/enrichment_index/cleanup_enrichment_index.py:90,99,108
scripts/migrations/enrichment_index/migrate_customer_name_mapping.py:727
src/migrations/migrate_legacy_to_enrichment_index.py:242
tests/integration/infrastructure/enrichment/test_domain_learning_integration.py:80
tests/integration/migrations/test_enrichment_index_migration.py:342,398,470
```

**排查步骤:**
1. 检查上述文件的DELETE条件是否过于宽泛
2. 确认测试是否使用独立数据库/事务回滚
3. 添加保护机制防止生产数据被意外清空

### 2.5 P0-3 详情: 测试收集错误

**受影响文件:**
- `tests/integration/scripts/test_legacy_migration_integration.py`
- `tests/unit/scripts/test_migrate_legacy_to_enrichment_index.py`

**错误:** `ModuleNotFoundError: No module named 'work_data_hub.scripts'`

**解决方案选项:**
1. 移动脚本到 `src/work_data_hub/scripts/`
2. 删除测试(如脚本已废弃)
3. 修复导入路径

### 2.6 P1-3 详情: Legacy数据库连接验证

**Story:** 7.1-7-verify-legacy-db-connection.md

**验证结果:**
- ✅ AC-1: `WDH_LEGACY_*` 环境变量已配置 (5/5 variables)
- ✅ AC-2: `PostgresSourceAdapter` 可正常实例化
- ✅ AC-3: Legacy数据库连接成功 (PostgreSQL 17.6)
- ⚠️ AC-4: 参考表不存在于Legacy数据库

**发现的问题:**
`config/reference_sync.yml` 配置的以下表不存在于Legacy数据库:
- `enterprise.annuity_plan`
- `enterprise.portfolio_plan`
- `enterprise.organization`

**根因分析:**
Story 6.2-P1 (MySQL → PostgreSQL migration) 时，只迁移了部分表结构。Legacy数据库 `enterprise` schema 实际包含的表:
- `annuity_account_mapping`, `base_info`, `biz_label`, `blank_company_id`
- `business_info`, `company_id_mapping`, `company_types_classification`
- `eqc_search_result`, `industrial_classification`

**影响评估:**
- **连接基础设施**: ✅ 完全正常
- **参考数据同步**: ⚠️ 需要创建缺失的参考表或更新reference_sync.yml配置

**建议行动:**
1. Epic 8不依赖这些参考表进行Golden Dataset对比
2. reference_sync.yml配置修正可延后至Epic 8之后
3. 当前Story目标(验证连接)已达成

### 2.7 P1-2 详情: 分类逻辑问题

**当前逻辑 (cleaner_compare.py:531-533):**
```python
# Case 3: Both numeric but different - REGRESSION (错误!)
if legacy_is_numeric and new_is_numeric and legacy_val != new_val:
    return CLASSIFICATION_REGRESSION_MISMATCH
```

**问题:** 将数据源差异错误标记为"回归"

**修复方案:**
```python
# Case 3: Both numeric but different - DATA SOURCE DIFFERENCE
if legacy_is_numeric and new_is_numeric and legacy_val != new_val:
    return CLASSIFICATION_DATA_SOURCE_DIFFERENCE  # 新分类
```

---

## 3. Known Issues (Not Blocking)

### 3.1 联想集团company_id匹配问题

| 来源 | company_id | 公司名称 |
|------|------------|----------|
| New Pipeline | 633167472 | 联想集团公司驻深圳办事处 (EQC第一结果) |
| Legacy | 712180666 | 手动校准值 |
| **正确值** | 602270789 | 联想（北京）有限公司 |

**根因:** EQC搜索结果排序问题，返回第一个匹配结果而非最佳匹配

**结论:** 非代码BUG，所有数值字段完全匹配

**临时方案:** 使用`confidence`字段标记低置信度匹配

**长期方案:** 升级匹配算法(Epic 8+)

---

## 4. Validation Commands

### ETL --execute 验证 (P0-2)
```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl \
    --domains annuity_performance --period 202510 \
    --file-selection newest --execute --no-enrichment
```

### 测试套件
```bash
PYTHONPATH=src uv run pytest tests/ -v --tb=short 2>&1 | head -100
```

### Cleaner Compare (全量)
```bash
PYTHONPATH=src uv run python scripts/validation/CLI/cleaner_compare.py \
    --domain annuity_performance --month 202510 --export
```

### enrichment_index查询
```bash
PYTHONPATH=src uv run --env-file .wdh_env python -c "
from sqlalchemy import create_engine, text
from work_data_hub.config.settings import get_settings
engine = create_engine(get_settings().get_database_connection_string())
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM enterprise.enrichment_index'))
    print(f'enrichment_index count: {result.scalar()}')
"
```

---

## 5. Definition of Done

### Epic 8开发可以开始，当且仅当：

- [ ] **P0-1:** enrichment_index清空问题已定位并修复
- [ ] **P0-2:** ETL --execute验证通过
- [ ] **P0-3:** 测试收集错误已修复或文档化为out-of-scope

### 强烈建议(可并行):

- [ ] **P1-2:** 分类逻辑已修复 (将`regression_company_id_mismatch`改为`data_source_difference`)

---

## 6. Field Classification Strategy (Epic 8 Foundation)

### 字段分类标准

| 分类 | 验证策略 | 字段示例 | 差异处理 |
|------|---------|---------|---------|
| **NUMERIC** | 零容差匹配 | 供款、流失、投资收益 | ❌ FAIL |
| **DERIVED** | 公式验证 | 流失_含待遇支付 | ❌ FAIL |
| **DIMENSION** | 精确匹配 | 月度、计划代码 | ❌ FAIL |
| **ENRICHMENT** | 有效解析 | company_id | ⚠️ WARN |
| **UPGRADE** | 允许差异 | 年金账户名、客户名称 | ✅ DOCUMENT |

### 核心原则

```
验证标准 = 业务规则 (不是 Legacy匹配)

company_id 验证规则:
├── must_not_be_null        ✓
├── must_exist_in_公司信息   ✓
└── legacy_match_required   ✗ (不要求)
```

---

## Appendix

### A. Related Documents

| Document | Location |
|----------|----------|
| Epic 8 Strategy Change Proposal | `docs/sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-23-epic8-validation-strategy.md` |
| Epic 7 Retrospective | `docs/sprint-artifacts/retrospective/epic-7-retro-2025-12-23.md` |
| Sprint Status | `docs/sprint-artifacts/sprint-status.yaml` |

### B. Archived Documents

以下文档内容已整合到本文档，可删除：
- `docs/specific/critical/epic-8-implementation-success-plan.md`
- `docs/specific/critical/epic-8-pre-flight-checklist.md`

---

**Document Version:** 2.0 (Consolidated)
**Next Review:** Epic 8 Kickoff
