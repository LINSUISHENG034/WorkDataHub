## 建议方案 (Recommendations)

基于 `sprint-change-proposal-infrastructure-refactoring-2025-12-01.md` 的分析与建议：

### 1. 批处理优化 (Batch Processing)
- **策略**: 优先使用 **Pandas 向量化操作 (Vectorized Operations)** 进行数据转换（如 `transforms/standard_steps.py` 中所述），这是性能提升的关键（消除 Python 循环开销）。
- **分块处理 (Chunking)**: 对于无法向量化的操作（如 Pydantic 模型验证），建议采用 **分块迭代 (Chunked Iteration)**。
- **批量大小**: 建议默认设为 **1000** 行（如提案 Story 5.5 中所示 `np.array_split(df, max(1, len(df) // 1000))`）。此数值应定义为基础设施层的常量（`BATCH_SIZE`），以便根据内存分析结果进行全局调整。

### 2. 向后兼容性 (Backward Compatibility)
- **策略**: **同步重构调用方 (Synchronous Update of Callers)** —— **不采用适配器模式**。
- **理由**: 鉴于当前架构尚未大规模投产，且存在 `legacy` 代码作为数据基线，我们应优先保证新架构的**纯粹性 (Purity)** 和 **整洁性 (Cleanliness)**。为了兼容本就需要重构的代码而引入适配器层会增加不必要的复杂度（Bloat）。
- **执行方式**:
    - **破坏性变更**: 允许 `AnnuityPerformanceService` 的接口发生重大变化（Breaking Changes）。
    - **同步修改**: 在同一个变更请求（PR）中，直接修改上游调用方（如 `orchestration/jobs.py`）以适配新的 Service 接口。
    - **数据兼容性**: 关注点应从 "API 签名兼容" 转移到 "**输出数据兼容**"。确保重构后的 Pipeline 输出的数据结构（Schema）和内容与 Legacy 系统保持一致，以保证下游报表等系统不受影响。

### 3. 错误处理策略 (Error Handling)
- **配置化**: 验证错误阈值（10%）**应当是可配置的**。建议在 `domain/annuity_performance/constants.py` 中定义默认值，并通过 `AnnuityPerformanceService` 的构造函数或 `process` 方法参数传入，以便未来针对不同数据源调整容忍度。
- **导出路径**: 错误 CSV 的导出路径 **应当是可配置的**。建议在 `infrastructure/settings/` 中通过环境变量（`ValidationSettings`）控制基础日志目录（默认为 `logs/`），以适应容器化或不同部署环境的需求。

### 4. 依赖注入 (Dependency Injection)
- **模式**: 明确推荐 **构造函数注入 (Constructor Injection)**。如提案 Story 5.7 所示：`def __init__(self, cleansing_registry, enrichment_resolver):`。这种方式清晰地声明了依赖关系，利于单元测试（易于 Mock）。
- **框架**: **不建议引入复杂的 DI 框架**。鉴于当前项目规模和 Python 的动态特性，手动注入（Manual DI / Composition Root）足够简单且维护成本低。保持代码的纯净性（Pure DI）。

### 5. 测试策略 (Testing Strategy)
- **性能测试**: **强烈建议创建专门的性能测试套件**（如 `tests/performance/`）。不仅依靠单元测试，还需要编写脚本（参考提案附录 C）运行基准测试（Benchmark），对比重构前后的时间和内存消耗。
- **数据集**: 确认使用 `reference/archive/monthly/202412/` 作为 "Gold Standard" 数据集进行 **回归测试 (Regression Testing)**。重构后的输出必须与该数据集在业务逻辑上完全一致（Bitwise identical or strictly equivalent）。