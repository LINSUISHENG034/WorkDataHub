# Architecture Review Notes - First Principles Analysis

> **Status:** Draft - Pending First Principles Validation
> **Created:** 2026-01-12
> **Author:** Architect Agent

---

## Current Recommendations Summary

### Identified Problems

1. **Three-layer per-domain redundancy**: domain层、ops层、jobs层都需要为每个domain写代码
2. **Enrichment initialization leakage**: ~150行enrichment初始化代码泄漏到ops层
3. **Insufficient configuration-driven design**: 很多差异可以通过配置而不是代码表达
4. **Multi-sheet data source**: annual_award需要从多个sheet读取数据，这是通用需求

### Proposed Solutions (Priority Order)

| Priority | Task | Expected Benefit |
|----------|------|------------------|
| P0 | EnrichmentServiceFactory | Reduce ~150 lines from ops |
| P1 | Config-driven data source (multi-sheet) | Solve annual_award needs, enable future extension |
| P2 | Generic Op + Job | Eliminate per-domain ops/jobs |
| P3 | DomainServiceProtocol | Unified interface (optional) |

### Proposed Architecture

```yaml
# config/domain_sources.yaml
annuity_performance:
  source:
    type: excel
    sheets: ["规模明细"]
  requires_enrichment: true
  requires_backfill: true

annual_award:
  source:
    type: excel
    sheets: ["企年受托中标(空白)", "企年投资中标(空白)"]
  requires_enrichment: true
  requires_backfill: false
```

---

## First Principles Analysis

### 1. ETL 管道的本质

ETL = Extract → Transform → Load

```
数据源 (Excel) → [Extract] → List[Dict] → [Transform] → List[Model] → [Load] → Database
```

**核心洞察**：所有 domain 的 ETL 管道本质上做的是同一件事，差异仅在于：
- Transform 阶段的业务逻辑
- 是否需要外部依赖（enrichment、backfill）

### 2. 代码分析：当前 Domain Service 接口对比

| Domain | 核心函数 | 输入 | 输出 | 特殊依赖 |
|--------|---------|------|------|----------|
| annuity_performance | `process_with_enrichment()` | `List[Dict]` | `ProcessingResultWithEnrichment` | EqcLookupConfig, CompanyMappingRepository |
| annuity_income | `process_with_enrichment()` | `List[Dict]` | `ProcessingResultWithEnrichment` | CompanyMappingRepository |
| sandbox_trustee | `process()` | `List[Dict]` | `List[Model]` | 无 |
| annual_award | `pipeline.execute()` | DataFrame | DataFrame | CompanyMappingRepository |

**关键发现**：
1. 输入格式本质一致：`List[Dict]` 或可互转的 DataFrame
2. 输出格式本质一致：Pydantic 模型列表
3. 真正差异：enrichment 依赖的有无和类型

### 3. 核心问题重新定义

**原始问题描述的偏差**：

| 原描述 | 实际情况 |
|--------|----------|
| "Enrichment 初始化泄漏到 ops 层" | Enrichment 初始化在 ops 层和 domain 层**都有重复** |
| "annual_award 需要多表数据源" | annual_award 需要**多 sheet**，不是多表 |
| "Domain 接口不一致" | 接口差异很小，核心是 enrichment 依赖注入方式不同 |

**真正的根本问题**：

1. **职责边界模糊**：Domain 层的 `process_xxx()` 包含了 file_discovery（应属于 orchestration）
2. **依赖初始化重复**：CompanyMappingRepository 在 ops 和 domain 层都有初始化代码
3. **两套 API 并存**：每个 domain 有高层 API 和低层 API，但 ops 只用低层 API

### 4. 建议可行性验证

#### P0: EnrichmentServiceFactory

| 维度 | 评估 |
|------|------|
| 可行性 | ⚠️ 中等 |
| 原因 | 需要同时重构 ops 层和 domain 层的重复代码 |
| 前置条件 | 明确 enrichment 依赖的统一注入点 |
| 风险 | 如果只改 ops 层，domain 层重复仍存在 |

#### P1: 配置驱动的数据源（multi-sheet）

| 维度 | 评估 |
|------|------|
| 可行性 | ✅ 高 |
| 原因 | `read_excel_op` 已支持 `sheet_names` 参数 |
| 前置条件 | 设计配置文件格式和加载机制 |
| 风险 | 低，属于增量改进 |

#### P2: Generic Op + Job

| 维度 | 评估 |
|------|------|
| 可行性 | ❌ 低（当前状态） |
| 原因 | Domain service 接口不一致，Generic Op 会变成 if/elif 分支 |
| 前置条件 | **必须先统一 domain service 接口** |
| 风险 | 高，可能引入更多复杂性 |

#### P3: DomainServiceProtocol

| 维度 | 评估 |
|------|------|
| 可行性 | ⚠️ 中等 |
| 原因 | 接口差异小，但需要为每个 domain 添加 wrapper |
| 前置条件 | 明确 Protocol 的最小契约 |
| 风险 | 过度抽象的风险 |

### 5. 第一性原理结论

**原方案的问题**：

1. **P0 (EnrichmentServiceFactory)** - 只解决表面问题，不解决根本的重复
2. **P2 (Generic Op)** - 在接口不统一的情况下不可行
3. **优先级顺序有误** - 应该先统一接口，再做 Generic Op

**修正后的优先级**：

| 新优先级 | 任务 | 理由 |
|----------|------|------|
| P0 | 统一 Domain Service 接口 | 这是所有后续改进的前置条件 |
| P1 | 配置驱动的数据源 | 独立可行，解决 multi-sheet 需求 |
| P2 | Generic Op + Job | 在 P0 完成后才可行 |
| P3 | EnrichmentServiceFactory | 作为 P0 的一部分，统一依赖注入 |

---

## 关键洞察

### 原方案不可行的根本原因

```
当前状态:
  Domain A: process_with_enrichment(rows, eqc_config, ...)
  Domain B: process_with_enrichment(rows, ...)  # 无 eqc_config
  Domain C: process(rows, data_source)          # 完全不同
  Domain D: pipeline.execute(df, context)       # DataFrame 接口

期望的 Generic Op:
  for domain in domains:
      result = domain.process(rows, context)  # 统一接口
```

**如果不先统一接口，Generic Op 必然变成：**

```python
if domain == "annuity_performance":
    result = process_with_enrichment(rows, eqc_config=...)
elif domain == "annuity_income":
    result = process_with_enrichment(rows)
elif domain == "sandbox_trustee":
    result = process(rows, data_source)
elif domain == "annual_award":
    result = pipeline.execute(df, context)
```

**这不是消除 per-domain 代码，而是把它集中到一个大函数里。**

---

## 修正后的建议

### 正确的实施路径

```
Step 1: 定义统一的 DomainServiceProtocol
        ↓
Step 2: 为每个 domain 实现 Protocol adapter
        ↓
Step 3: 实现配置驱动的数据源（multi-sheet）
        ↓
Step 4: 实现 Generic Op（基于统一接口）
        ↓
Step 5: 实现 Generic Job
        ↓
Step 6: 清理旧的 per-domain ops/jobs
```

### 最小可行的 Protocol 定义

```python
class DomainServiceProtocol(Protocol):
    domain_name: str
    
    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> ProcessingResult:
        ...
```

**ProcessingContext 封装所有可选依赖**，domain 按需使用。

