# Domain架构重构增强实施方案

**文档版本：** 1.1
**日期：** 2025-12-01
**关联文档：** `domain-refactoring-design.md`
**状态：** 待实施

---

## 1. 方案评估与核心改进

基于对原设计文档的评估及现有代码库（特别是 `processing_helpers.py`）的分析，原方案在方向上正确（轻量化、配置驱动、向量化），但在**工程落地**、**类型安全**和**风险控制**上存在优化空间。本方案引入三个核心增强机制：

### 改进 A：引入强类型配置验证 (Configuration as Code)
*   **原风险**：依赖 Python 字典 (`Dict`) 作为配置，容易出现拼写错误（如 `"regex"` vs `"pattern"`），且在运行时才报错，难以调试。
*   **新策略**：在基础设施层引入 **Pydantic Configuration Model**。
    *   **收益**：IDE 自动补全、启动时即刻校验配置合法性、错误提示清晰。
    *   **实现**：定义 `DomainConfig`, `FieldMappingConfig`, `TransformationRule` 等 Pydantic 模型。

### 改进 B：建立 "黄金卷标" (Golden Master) 测试体系
*   **原风险**：重构不仅是代码搬运，更是逻辑重写。微小的差异（如浮点数精度、空值处理、日期格式）可能导致数据不一致，且难以被单元测试完全覆盖。
*   **新策略**：在动工前，建立**全量数据快照对比机制**。
    *   **收益**：确保重构前后的数据输出在比特级别（Bit-level）一致，或差异可解释。

### 改进 C：强制向量化约束 (Strict Vectorization)
*   **原风险**：`transformers.py` 缺乏约束，可能再次退化为包含行级循环（`for row in df`）的低效代码。
*   **新策略**：基础设施层的接口设计应**物理屏蔽**行级访问。
    *   **实现**：转换接口仅接收 `pd.DataFrame`，禁止传入 `List[Dict]`。提供标准化的 `VectorizedOps` 工具库。

---

## 2. 详细实施路线图

实施过程分为四个阶段，每个阶段都有明确的**准入条件**和**交付产物**。

### Phase 0: 安全基线与环境准备 (准备期 - 2天)
**目标**：确保重构过程中随时可以验证数据的正确性，不破坏现有业务。

1.  **构建 "黄金卷标" (Golden Master) 数据集**
    *   选取 `annuity_performance` 过去 3 个月的真实数据（脱敏后）。
    *   运行现有 Legacy 逻辑，保存中间结果（Pipeline Output）和最终结果（DB Load Ready）为 Parquet 文件。
    *   **产物**：`tests/fixtures/golden_master/annuity_v1_output.parquet`

2.  **开发快照对比工具**
    *   编写脚本 `scripts/compare_implementation.py`，用于对比新旧实现的 DataFrame 差异（利用 `pandas.testing.assert_frame_equal`）。
    *   **产物**：自动化对比脚本，集成到开发流程中。

### Phase 1: 强健基础设施构建 (核心期 - 3-4天)
**目标**：构建"防呆"且高性能的通用处理框架。

1.  **定义配置 Schema (Infrastructure Layer)**
    *   建立 `infrastructure/configuration/`。
    *   实现 `FieldMappingConfig`, `ValidationRuleConfig`, `TransformationConfig` 等 Pydantic 模型。
    *   **关键点**：配置加载器必须在应用启动时验证 `rules.py` 的合法性。

2.  **开发通用批处理器 (BatchProcessor)**
    *   实现 `BatchProcessor` 类，封装 Pandera 验证和通用 Pandas 操作。
    *   **工具库**：开发 `infrastructure/processing/vector_ops.py`，提供常用的向量化操作（如：安全日期解析、批量正则替换、分级回退逻辑）。

3.  **Epic 5 预埋 (Company ID Resolver)**
    *   实现基于 DataFrame 的 `BatchCompanyIdResolver`，支持缓存和批处理接口，替代原有的单条查询逻辑。

### Phase 2: 垂直切片迁移 (试点期 - 3天)
**目标**：以 `annuity_performance` 为试点，验证新架构。

1.  **迁移业务逻辑**
    *   使用新定义的 Pydantic Schema 重写 `domain/annuity_performance/rules.py`。
    *   将 `processing_helpers.py` 中的 850+ 行代码逻辑，转化为配置规则或 `transformers.py` 中的向量化函数。
    *   **约束**：`transformers.py` 中的函数**必须**接收 DataFrame 并返回 DataFrame。

2.  **服务编排重构**
    *   重写 `service.py`，移除所有行级处理逻辑，仅保留 `BatchProcessor` 的调用链。

### Phase 3: 并行运行与验证 (验收期 - 2天)
**目标**：在准生产环境验证稳定性与性能。

1.  **双轨运行 (Shadow Mode)**
    *   修改入口函数，可选地同时运行 Old Service 和 New Service。
    *   记录 New Service 的执行时间、内存消耗，并实时对比结果。
    *   **日志**：输出 `DIFF_CHECK: MATCH` 或 `DIFF_CHECK: MISMATCH`。

2.  **性能压测**
    *   使用大文件（10万行+）测试新架构性能。目标是比 Legacy 快 3-5 倍。

### Phase 4: 清理与技术债务偿还 (收尾期 - 1天)
**目标**：移除冗余代码，确保代码库整洁。

1.  **识别废弃模块**
    *   `src/work_data_hub/domain/annuity_performance/processing_helpers.py` (核心重构对象)
    *   `src/work_data_hub/domain/annuity_performance/schemas.py` (将被 Pydantic Config 取代)
    *   `src/work_data_hub/domain/annuity_performance/pipeline_steps.py` (旧 Pipeline 逻辑)

2.  **依赖检查与安全删除**
    *   使用 `ripgrep` 全局搜索模块引用，确保无残留依赖。
    *   执行物理删除操作。

3.  **遗留代码归档**
    *   如有必要，将删除的代码归档至 `legacy/archive/` 目录，保留 30 天以备查阅。

---

## 3. 架构设计微调建议

建议调整目录结构，显式分离配置定义与业务逻辑：

```text
work_data_hub/
├── infrastructure/
│   ├── configuration/          # [新增] 配置定义与加载器
│   │   ├── schemas.py          # Pydantic Models (定义配置的结构)
│   │   └── loader.py           # 负责加载并验证 rules.py
│   ├── processing/
│   │   ├── batch_processor.py  # 核心批处理逻辑
│   │   └── ops_library.py      # [新增] 通用向量化算子库
│   └── ...
├── domain/
│   ├── annuity_performance/
│   │   ├── config.py           # [修改] 实例化 Pydantic Model，而非纯字典
│   │   ├── rules.py            # (可选) 具体的配置数据文件
│   │   ├── transformers.py     # 仅包含无法通过配置表达的复杂向量化逻辑
│   │   └── service.py          # 服务编排
│   └── ...
```

## 4. 风险管理矩阵

| 风险点 | 影响等级 | 应对策略 |
| :--- | :--- | :--- |
| **配置过于复杂** | 中 | 对于极度复杂的逻辑（如跨多行计算），不要强行塞入 Config DSL，直接在 `transformers.py` 编写 Python 代码。Config 仅用于 80% 的通用映射与验证。 |
| **内存溢出 (OOM)** | 高 | `BatchProcessor` 需内置 `chunk_size` 支持。虽然是向量化，但对于超大文件仍需分块（Chunking）处理（例如每 50,000 行一个 Batch）。 |
| **调试困难** | 中 | 基础设施层需实现 `TraceableDataFrame` 机制，在 Pipeline 的关键节点自动记录 `df.head()` 和 `df.shape` 到 DEBUG 日志，方便追踪数据变化。 |
