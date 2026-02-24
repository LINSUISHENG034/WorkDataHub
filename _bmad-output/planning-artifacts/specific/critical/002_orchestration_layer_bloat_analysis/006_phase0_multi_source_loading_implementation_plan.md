# Phase 0: Multi-Source Data Loading 实施计划

> **Status:** Ready for Implementation
> **Created:** 2026-01-13
> **Branch:** `feature/orchestration-layer-refactor`
> **Related:** [003_orchestration_layer_refactoring_design.md](./003_orchestration_layer_refactoring_design.md)

---

## 1. 问题背景

在编排层重构实施审核中发现，Phase 0 (Multi-Source Data Loading) **仅完成了配置层**，实际的多表加载逻辑未实现：

| 组件 | 设计状态 | 实现状态 |
|------|----------|----------|
| `domain_sources.yaml` | ✅ 设计完成 | ✅ 已实现 |
| `domain_sources.py` 配置加载 | ✅ 设计完成 | ✅ 已实现 |
| `MultiTableLoader` | ✅ 设计完成 | ❌ **未实现** |
| `read_data_op` 增强 | ✅ 设计完成 | ❌ **未实现** |
| `annual_award` multi_table 配置 | ✅ 设计完成 | ❌ 仍为 single_file |

---

## 2. 目标

1. 实现 `MultiTableLoader` 类，支持从数据库多表加载并合并数据
2. 增强 `read_data_op` 以支持 `multi_table` 源类型
3. 更新 `annual_award` 配置为 `multi_table` 模式
4. 确保与现有 `single_file` 域的向后兼容

---

## 3. Proposed Changes

### 3.1 Configuration Layer Enhancement

#### [MODIFY] [domain_sources.yaml](file:///E:/Projects/WorkDataHub-orchestration-refactor/config/domain_sources.yaml)

更新 `annual_award` 配置为 `multi_table` 模式：

```yaml
annual_award:
  source_type: multi_table
  tables:
    - schema: business
      table: 年度表彰_主表
      role: primary
    - schema: business
      table: 年度表彰_明细
      role: detail
  join_strategy:
    type: merge_on_key
    key_columns: ["客户号", "年度"]
  output_format: flattened
```

#### [MODIFY] [domain_sources.py](file:///E:/Projects/WorkDataHub-orchestration-refactor/src/work_data_hub/config/domain_sources.py)

扩展配置模型支持 `multi_table` 类型：

```python
@dataclass
class TableConfig:
    """单表配置."""
    schema: str
    table: str
    role: str  # "primary" | "detail"

@dataclass
class JoinStrategy:
    """表合并策略."""
    type: str  # "merge_on_key" | "left_join" | "union"
    key_columns: List[str]

@dataclass
class DomainSourceConfig:
    """Domain 数据源配置."""
    source_type: str  # "single_file" | "multi_table"
    discovery: Optional[DiscoveryConfig] = None
    tables: Optional[List[TableConfig]] = None
    join_strategy: Optional[JoinStrategy] = None
    output_format: str = "flattened"
```

---

### 3.2 Multi-Table Loader Implementation

#### [NEW] [multi_table_loader.py](file:///E:/Projects/WorkDataHub-orchestration-refactor/src/work_data_hub/io/reader/multi_table_loader.py)

```python
"""Multi-Table Data Loader.

从数据库多表加载数据并按配置策略合并。
"""

from typing import Any, Dict, List
import pandas as pd
from sqlalchemy import create_engine, text

from work_data_hub.config.settings import get_settings
from work_data_hub.config.domain_sources import DomainSourceConfig, TableConfig


class MultiTableLoader:
    """多表数据加载器."""

    @classmethod
    def load(cls, config: DomainSourceConfig) -> List[Dict[str, Any]]:
        """
        从多张数据库表加载数据并按配置策略合并.

        Args:
            config: Domain 源配置

        Returns:
            统一格式的 List[Dict]，与单文件加载输出格式一致
        """
        if not config.tables:
            raise ValueError("multi_table config requires 'tables' definition")

        settings = get_settings()
        engine = create_engine(settings.get_database_connection_string())

        tables_data: Dict[str, pd.DataFrame] = {}
        for table_cfg in config.tables:
            df = cls._load_table(engine, table_cfg)
            tables_data[table_cfg.role] = df

        merged = cls._apply_join_strategy(tables_data, config.join_strategy)
        
        return merged.to_dict(orient="records")

    @classmethod
    def _load_table(cls, engine, table_config: TableConfig) -> pd.DataFrame:
        """Load single table from database."""
        query = f'SELECT * FROM "{table_config.schema}"."{table_config.table}"'
        return pd.read_sql(text(query), engine)

    @classmethod
    def _apply_join_strategy(
        cls,
        tables_data: Dict[str, pd.DataFrame],
        strategy: "JoinStrategy",
    ) -> pd.DataFrame:
        """Apply configured join strategy."""
        if strategy is None or strategy.type == "merge_on_key":
            primary = tables_data.get("primary")
            detail = tables_data.get("detail")
            
            if primary is None:
                raise ValueError("merge_on_key requires 'primary' role table")
            if detail is None:
                return primary
            
            return primary.merge(
                detail,
                on=strategy.key_columns if strategy else [],
                how="left",
            )
        elif strategy.type == "union":
            return pd.concat(list(tables_data.values()), ignore_index=True)
        else:
            raise ValueError(f"Unknown join strategy: {strategy.type}")
```

---

### 3.3 Data Ops Enhancement

#### [MODIFY] [file_processing.py](file:///E:/Projects/WorkDataHub-orchestration-refactor/src/work_data_hub/orchestration/ops/file_processing.py)

增强 `read_excel_op` 或创建统一的 `read_data_op`：

```python
from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY
from work_data_hub.io.reader.multi_table_loader import MultiTableLoader


@op
def read_data_op(
    context: OpExecutionContext,
    config: ReadDataOpConfig,
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    统一数据加载入口 - 根据 domain 配置选择加载策略.

    Supports:
    - single_file: 从 Excel 文件加载
    - multi_table: 从数据库多表加载并合并
    """
    domain = config.domain
    source_config = DOMAIN_SOURCE_REGISTRY.get(domain)

    if source_config is None:
        # Fallback: 未配置的 domain 使用默认 Excel 加载
        context.log.warning(f"Domain '{domain}' not in source registry, using Excel loader")
        return _read_excel_files(file_paths, config)

    if source_config.source_type == "multi_table":
        context.log.info(f"Loading {domain} via multi_table strategy")
        return MultiTableLoader.load(source_config)
    else:
        return _read_excel_files(file_paths, config)
```

---

### 3.4 Generic Job Integration

#### [MODIFY] [jobs.py](file:///E:/Projects/WorkDataHub-orchestration-refactor/src/work_data_hub/orchestration/jobs.py)

更新 `generic_domain_job` 使用 `read_data_op`：

```python
@job
def generic_domain_job() -> Any:
    """Generic ETL job with multi-source support."""
    discovered_paths = discover_files_op()
    
    # 使用统一的 read_data_op 替代 read_excel_op
    rows = read_data_op(discovered_paths)
    
    processed_data = process_domain_op_v2(rows, discovered_paths)
    backfill_result = generic_backfill_refs_op(processed_data)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)
```

---

## 4. Implementation Phases

| Phase | 任务 | 预估工时 | 风险 |
|-------|------|----------|------|
| 4.1 | 扩展 `domain_sources.py` 配置模型 | 1h | 低 |
| 4.2 | 实现 `MultiTableLoader` | 2h | 中 |
| 4.3 | 创建/增强 `read_data_op` | 1h | 低 |
| 4.4 | 更新 `annual_award` 配置 | 0.5h | 低 |
| 4.5 | 集成测试 | 2h | 中 |

**总预估工时**: 6.5 小时

---

## 5. Verification Plan

### 5.1 Unit Tests

#### [NEW] test_multi_table_loader.py

```bash
# 运行单元测试
uv run pytest tests/io/reader/test_multi_table_loader.py -v
```

测试用例：
- `test_load_single_table` - 单表加载
- `test_merge_on_key_strategy` - 主从表合并
- `test_union_strategy` - 表联合
- `test_missing_primary_table_error` - 缺失主表错误处理

### 5.2 Integration Tests

```bash
# 运行 annual_award 域端到端测试
uv run pytest tests/domain/annual_award/test_integration.py -v

# 验证 multi_table 加载
uv run python -m work_data_hub.cli etl --domains annual_award --plan-only
```

### 5.3 Regression Tests

```bash
# 确保现有 single_file 域不受影响
uv run pytest tests/orchestration/ -v -k "annuity"
```

### 5.4 Manual Verification

1. **验证配置加载**:
   ```python
   from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY
   cfg = DOMAIN_SOURCE_REGISTRY.get("annual_award")
   assert cfg.source_type == "multi_table"
   assert len(cfg.tables) == 2
   ```

2. **验证数据加载**:
   ```python
   from work_data_hub.io.reader.multi_table_loader import MultiTableLoader
   from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY
   
   cfg = DOMAIN_SOURCE_REGISTRY.get("annual_award")
   rows = MultiTableLoader.load(cfg)
   print(f"Loaded {len(rows)} rows from multi-table source")
   ```

---

## 6. Acceptance Criteria

| # | 验收标准 | 验证方法 |
|---|----------|----------|
| AC1 | `MultiTableLoader.load()` 返回 `List[Dict]` | Unit test |
| AC2 | `annual_award` 配置为 `multi_table` | Config check |
| AC3 | `read_data_op` 根据配置分发到正确加载器 | Integration test |
| AC4 | 现有 `single_file` 域行为无变化 | Regression test |
| AC5 | 主从表合并使用配置的 key_columns | Unit test |

---

## 7. Rollback Plan

如果实施失败：

1. 将 `annual_award` 配置恢复为 `single_file`
2. `read_data_op` 保持使用 Excel 加载逻辑
3. `MultiTableLoader` 可安全删除（未被调用）

---

## 8. Dependencies

| 依赖 | 版本 | 用途 |
|------|------|------|
| `pandas` | >=2.0 | DataFrame 操作 |
| `sqlalchemy` | >=2.0 | 数据库连接 |
| `psycopg2` | >=2.9 | PostgreSQL driver |

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2026-01-13 | Implementation Review | Initial plan |
