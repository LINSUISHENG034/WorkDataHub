# Epic 5 迁移差距分析报告

**日期:** 2025-12-03
**分析目的:** 核实 `domain/annuity_performance/` 模块与提案规划的差距原因

---

## 1. 总体对比（最新快照）

### 提案目标 (sprint-change-proposal Section 4.4)
提案文档: `docs/sprint-artifacts/auxiliary/sprint-change-proposal-2025-12-01-infrastructure-refactoring.md`
```
domain/annuity_performance/
├── service.py              # <150 lines (orchestration only)
├── models.py               # <200 lines
├── schemas.py              # <100 lines
└── constants.py            # Business constants

Total: <500 lines
```

### 实际结构（2025-12-03 22:45）
```
domain/annuity_performance/
├── __init__.py              40 lines
├── constants.py            192 lines
├── discovery_helpers.py     97 lines
├── models.py               648 lines
├── pipeline_builder.py     284 lines
├── pipeline_steps.py       468 lines
├── processing_helpers.py   172 lines
├── schemas.py              611 lines
└── service.py              168 lines

Total: 2,680 lines (目标的 536%) —— 结构拆分已做，但行数缩减停滞
```

---

## 2. 逐文件核实结果（结合 Epic5 实施）

### 2.1 `pipeline_steps.py` (468行) - **应删除/迁移但未删除**

**提案要求:**
> `DELETE (migrated to infrastructure) ├── pipeline_steps.py → infrastructure/transforms/`

**实际状态:** 文件仍存在，包含以下类：

| 类名 | 行数 | 迁移状态 | 说明 |
|------|------|----------|------|
| `CompanyIdResolutionStep` | 126行 | **重复实现** | `pipeline_builder.py` 中有新版本使用 `infrastructure/enrichment/CompanyIdResolver`，旧版未清理 |
| `BronzeSchemaValidationStep` | 27行 | **未迁移** | 仍被 `schemas.py` 引用使用 |
| `GoldProjectionStep` | 99行 | **未迁移** | 仍被 `schemas.py` 引用使用 |
| `GoldSchemaValidationStep` | ~30行 | **未迁移** | 仍被使用 |
| `build_annuity_pipeline` | ~50行 | **已废弃** | 不再被调用，但未删除 |
| `load_mappings_from_json_fixture` | ~20行 | **已废弃** | 不再被调用，但未删除 |

**结论:**
- ❌ 迁移后未清理旧实现 (`CompanyIdResolutionStep`)
- ❌ 验证/投影步骤未迁移到 infra (`BronzeSchemaValidationStep`, `GoldProjectionStep`, `GoldSchemaValidationStep`)
- ❌ 废弃代码未删除 (`build_annuity_pipeline`, `load_mappings_from_json_fixture`)

---

### 2.2 `pipeline_builder.py` (284行) - **提案未规划的新文件**

**提案要求:** 无此文件规划

**实际状态:** 新创建的文件，包含：

| 符号 | 说明 |
|------|------|
| `CompanyIdResolutionStep` | **新版本**，使用 `infrastructure/enrichment/CompanyIdResolver` |
| `build_bronze_to_silver_pipeline` | 构建管道的函数 |
| `load_plan_override_mapping` | 加载映射的辅助函数 |

**分析:**
- 这是 Story 5.7 重构时创建的新文件
- `CompanyIdResolutionStep` 是对 `infrastructure/CompanyIdResolver` 的包装
- 符合提案的"轻量级编排"理念，但提案未明确规划此文件

**结论:** ⚠️ **合理的新增**，但导致与 `pipeline_steps.py` 中的旧版本重复

---

### 2.3 `models.py` (648行) - **未按提案简化**

**提案要求:** `<200 lines (simplified)`

**实际状态:** 648行，包含：

| 符号 | 类型 | 说明 |
|------|------|------|
| `AnnuityPerformanceIn` | Pydantic Model | Bronze层输入模型，包含大量验证器 |
| `AnnuityPerformanceOut` | Pydantic Model | Gold层输出模型 |
| `EnrichmentStats` | Pydantic Model | 统计信息模型 |
| `ProcessingResultWithEnrichment` | Pydantic Model | 处理结果模型 |
| `apply_domain_rules` | Function | 清洗规则应用函数 |
| 多个常量和辅助函数 | - | 清洗相关配置 |

**分析:**
- 大量 `@field_validator` 内联业务/清洗逻辑（可外移至 infra/cleansing + pandera）
- 输出模型/统计模型合并在单文件，缺少拆分或继承复用
- 提案要求“移除复杂转换逻辑”未执行

**结论:** ❌ **代码未按提案简化**

---

### 2.4 `schemas.py` (611行) - **未按提案简化**

**提案要求:** `<100 lines`

**实际状态:** 611行，包含：

| 符号 | 类型 | 说明 |
|------|------|------|
| `BronzeAnnuitySchema` | Pandera Schema | Bronze层验证 |
| `GoldAnnuitySchema` | Pandera Schema | Gold层验证 |
| `BronzeValidationSummary` | Dataclass | 验证摘要 |
| `GoldValidationSummary` | Dataclass | 验证摘要 |
| `validate_bronze_dataframe` | Function | Bronze验证函数 |
| `validate_gold_dataframe` | Function | Gold验证函数 |
| 多个辅助函数 | - | 数值清洗、日期解析等 |

**分析:**
- 包含大量辅助函数 (`_clean_numeric_for_schema`, `_coerce_numeric_columns`, `_parse_bronze_dates` 等)
- 这些辅助函数应该在 infrastructure 层
- 直接引用 `pipeline_steps.py` 中的类

**结论:** ❌ **代码未按提案简化，辅助函数未迁移到 infrastructure**

---

### 2.5 `service.py` (168行) - **基本符合目标**

**提案要求:** `<150 lines (orchestration only)`

**实际状态:** 168行，包含：

| 符号 | 类型 | 说明 |
|------|------|------|
| `process_annuity_performance` | Function | 主入口函数 (74行) |
| `process_with_enrichment` | Function | 处理函数 (57行) |
| `_records_to_dataframe` | Function | 辅助函数 |

**分析:**
- 基本符合“轻量级编排”目标；近期已补充 PipelineContext 契约字段（domain/run_id/extra）
- 仍缺少对 db 查询计数、性能等指标的真实埋点（测试内靠 metadata 计数占位）

**结论:** ✅ **基本符合目标** (略超18行)

---

### 2.6 `constants.py` (192行) - **符合目标**

**提案要求:** 业务常量文件

**实际状态:** 192行，包含业务常量和映射

**结论:** ✅ **符合目标**

---

### 2.7 `processing_helpers.py` (172行) - **提案未规划的新文件**

**提案要求:** 无此文件规划

**实际状态:** 包含：

| 符号 | 说明 |
|------|------|
| `convert_dataframe_to_models` | DataFrame转Pydantic模型 |
| `export_unknown_names_csv` | 导出未知名称CSV |
| `summarize_enrichment` | 统计摘要 |
| `parse_report_period` | 日期解析 |
| `parse_report_date` | 日期解析 |

**分析:**
- 从原 `service.py` 拆分，但目录定位偏 domain；日期解析/汇总逻辑可下沉至 utils/infra

**结论:** ⚠️ **合理的拆分，但部分函数位置不当**

---

### 2.8 `discovery_helpers.py` (97行) - **提案未规划的新文件**

**提案要求:** 无此文件规划

**实际状态:** 包含文件发现相关的辅助函数

**分析:**
- 从 `service.py` 拆分出来的发现逻辑
- 使用 Protocol 避免直接导入 io 层

**结论:** ⚠️ **合理的拆分**

---

## 3. Infrastructure 层迁移状态（Epic5 实施情况）

### 已正确迁移到 Infrastructure

| 组件 | 位置 | 状态 |
|------|------|------|
| `CompanyIdResolver` | `infrastructure/enrichment/company_id_resolver.py` | ✅ 已迁移 |
| `handle_validation_errors` | `infrastructure/validation/error_handler.py` | ✅ 已迁移 |
| `CleansingRegistry` | `infrastructure/cleansing/registry.py` | ✅ 已迁移 |
| `MappingStep`, `RenameStep`, etc. | `infrastructure/transforms/standard_steps.py` | ✅ 已迁移 |
| `Pipeline`, `TransformStep` | `infrastructure/transforms/base.py` | ✅ 已迁移 |

### 应迁移但未迁移

| 组件 | 当前位置 | 应迁移到 |
|------|----------|----------|
| `BronzeSchemaValidationStep` | `domain/.../pipeline_steps.py` | `infrastructure/validation/` |
| `GoldProjectionStep` | `domain/.../pipeline_steps.py` | `infrastructure/transforms/` |
| `GoldSchemaValidationStep` | `domain/.../pipeline_steps.py` | `infrastructure/validation/` |
| `_clean_numeric_for_schema` | `domain/.../schemas.py` | `infrastructure/cleansing/` |
| `_coerce_numeric_columns` | `domain/.../schemas.py` | `infrastructure/transforms/` |
| `_parse_bronze_dates` | `domain/.../schemas.py` | `infrastructure/transforms/` 或 `utils/` |
| 日期/报表周期解析 | `processing_helpers.py` | `utils/date_parser.py`（统一入口） |

---

## 4. 问题根因分析

### 4.1 代码重复问题

**问题:** `CompanyIdResolutionStep` 存在两个版本
- 旧版本: `pipeline_steps.py:90-216` (126行) - 基于 Row-level 处理
- 新版本: `pipeline_builder.py:62-141` (79行) - 使用 `infrastructure/CompanyIdResolver`

**原因:** Story 5.7 创建了新版本，但未删除旧版本

### 4.2 未完成的迁移

**问题:** `BronzeSchemaValidationStep`, `GoldProjectionStep` 等未迁移

**原因:**
1. 验证类与 Pandera schema 紧耦合，迁移需要同步重构 `schemas.py`
2. Story 5.6 标准化步骤未覆盖验证类，导致留在 domain
3. 缺少清理步骤/owner 关闭旧实现

### 4.3 模型/Schema 未简化

**问题:** `models.py` (648行) 和 `schemas.py` (611行) 远超目标

**原因:**
1. 验证/清洗逻辑嵌入 Pydantic validators，未复用 pandera + infra cleansing
2. 辅助函数未提取到 infra/utils，重复实现多处
3. 行数目标偏激进，未结合现有业务字段数量重新评估

---

## 5. 收尾计划（一次性彻底清理，执行即闭环）

以下项均已核实存在，按顺序全部完成后才算收尾：

1) **删除重复/废弃实现（已确认无必要引用）**
   - 移除 `pipeline_steps.py` 中旧版 `CompanyIdResolutionStep`、`build_annuity_pipeline`、`load_mappings_from_json_fixture`。
   - 清理对 `pipeline_steps.py` 旧类/函数的所有引用，若有遗留引用统一改到新路径（pipeline_builder + infra）。

2) **验证/投影步骤下沉 infra（需实际移动代码并替换引用）**
   - 将 `BronzeSchemaValidationStep`、`GoldSchemaValidationStep` 迁至 `infrastructure/validation/`（新文件如 `schema_steps.py`），`GoldProjectionStep` 迁至 `infrastructure/transforms/`（如 `projection_step.py`）。
   - 在原位置保留最薄兼容层（可选），但所有调用点改为新路径；`schemas.py` 不再声明 TransformStep。

3) **清洗/日期/数值辅助函数下沉**
   - `_clean_numeric_for_schema` → `infrastructure/cleansing/`；`_coerce_numeric_columns`、`_parse_bronze_dates` → `infrastructure/transforms/` 或复用 `utils/date_parser.py`。
   - `processing_helpers.py` 中的日期/报表周期解析统一迁入 `utils/date_parser.py`；导出 CSV/汇总等通用函数视需要迁入 infra/utils，domain 仅保留 orchestrator glue。

4) **强制复用标准步骤**
   - `pipeline_builder` 仅使用 infra `standard_steps` + 第 2 步迁出的 schema steps；删除/禁用 domain 内重复的 mapping/replacement/cleansing 实现。
   - 在 lint/ruff 或简单守卫中阻止 domain 重新定义通用步骤类。

5) **瘦身 models/schemas 并重估目标（实际落地）**
   - 将字段级校验尽量迁入 pandera + infra 清洗；Pydantic 主要保留类型和出站序列化。
   - 达成并记录新行数目标：`models.py < 400`，`schemas.py < 250`；提交前重新统计并更新文档/性能报告。

6) **验证与文档闭环**
   - 补充/更新单元、集成、E2E 测试以覆盖迁移后的路径；确保 parity/性能基线测试仍可运行。
   - 更新 README / docs/architecture/architectural-decisions.md / docs/domains/annuity_performance.md / performance report，反映最终结构与行数。

---

## 6. 总结（更新版）

| 指标 | 提案目标 | 实际结果 | 差距原因 |
|------|----------|----------|----------|
| **Domain总行数** | <500 (提案) | 2,680 | 迁移未完成，目标需重估 |
| **service.py** | <150 | 168 | ✅ 基本达标 |
| **models.py** | <200 (提案) | 648 | 验证/清洗未外移，目标需重估 |
| **schemas.py** | <100 (提案) | 611 | 辅助函数未迁移，目标需重估 |
| **pipeline_steps.py** | 删除/迁移 | 468 | 重复/遗留未清理 |
| **新增文件** | 0 | 3个 | 合理拆分，但需后续瘦身 |

**主要问题:**
1. ❌ 迁移后未清理旧实现（重复步骤、废弃函数）
2. ❌ 验证/清洗逻辑未下沉 infra，导致 schema/models 过重
3. ❌ 辅助函数留在 domain，未复用 infra/utils
4. ⚠️ 初始行数目标偏激进，需结合业务字段重新设定

**建议下一步:**
1. 用单独清理 Story/任务关闭 5.1 立即项（删除重复/废弃，实现路径切换到 infra）
2. 并行规划 5.2 迁移任务，将验证/清洗函数迁出 domain；pipeline_builder 全部使用 infra steps
3. 重估行数目标并设定新的质量门槛（models <400, schemas <250），完成后更新性能/文档报告
