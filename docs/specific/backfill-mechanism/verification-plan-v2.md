# 方案 B & D 快速验证计划 (Project Integrated)

**创建日期:** 2025-12-12
**目标:** 在不修改现有生产代码和配置的前提下，通过集成脚本验证 "通用回填框架 (Option B)" 和 "预加载方案 (Option D)" 在现有项目环境中的可行性。

## 1. 验证策略

为了解决“信心不足”的问题，我们将采用 **In-Memory Integration Verification (内存集成验证)** 策略。

*   **配置验证:** 读取项目真实的 `config/data_sources.yml`，在内存中注入拟议的新配置结构，验证其与现有架构的兼容性。
*   **逻辑验证:** 使用项目现有的依赖库 (`SQLAlchemy`, `Pandas`, `Pydantic`) 在内存数据库 (SQLite) 中运行拟议的核心逻辑。
*   **零副作用:** 验证过程不会修改任何文件，不会连接真实的开发数据库，确保安全。

## 2. 关键验证点 (Risk Verification)

| 风险点 | 验证方法 | 预期结果 |
|-------|---------|---------|
| **配置兼容性** | 读取现有 `data_sources.yml` 并动态注入 `foreign_keys` 节点 | 能够无缝合并，且被 Pydantic 模型正确解析 |
| **SQL生成正确性** | 使用 SQLAlchemy Core 动态生成 `INSERT ... ON CONFLICT` | 生成的 SQL 语法正确，能被数据库执行 |
| **依赖排序逻辑** | 模拟多层级外键依赖 (Child -> Parent -> Grandparent) | 拓扑排序算法能正确输出执行顺序 |
| **异构源同步** | 模拟从 `DataFrame` 和 `YAML` 同步数据到 SQLite | 数据能正确写入，且支持全量/增量逻辑 |

## 3. 执行步骤

### 步骤 1: 准备验证脚本

我们将创建一个名为 `scripts/validation/verify_backfill_integrated.py` 的脚本。该脚本将：
1.  导入项目的 `get_settings` (如果可用) 或直接读取配置文件。
2.  定义拟议的 `ForeignKeyConfig` Pydantic 模型。
3.  实现 `GenericBackfillService` 的核心原型。
4.  运行端到端的模拟流程。

### 步骤 2: 运行验证

在终端执行：
```bash
python scripts/validation/verify_backfill_integrated.py
```

### 步骤 3: 结果评估

*   如果脚本运行成功并输出 "Verification PASSED"，说明核心设计在技术上是可行的。
*   检查输出日志中的 SQL 语句，确认其符合 PostgreSQL 的最佳实践 (尽管在 SQLite 上运行，但逻辑通用)。

---

## 4. 验证脚本内容预览

(详见 `scripts/validation/verify_backfill_integrated.py`)

## 5. 后续行动建议

如果验证通过：
1.  **正式实施:** 将 `ForeignKeyConfig` 和 `GenericBackfillService` 移植到 `src/work_data_hub/domain/reference_backfill/`。
2.  **配置更新:** 修改 `config/data_sources.yml`，正式添加外键配置。
3.  **管道集成:** 在 Dagster job 中调用新的 service。
