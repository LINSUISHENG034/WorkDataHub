# 领域数据输出配置重构方案 (2025-12-11)

## 1. 背景与目标

### 问题现状
目前，各个业务域（如 `annuity_performance`, `annuity_income`）的数据写入目标表名（如 `annuity_performance_NEW`）硬编码在 Pipeline 逻辑或 Orchestration 代码中。

### 改进目标
为了提高系统的可配置性和可维护性，需将数据写入位置的配置统一迁移至 `config/data_sources.yml` 中管理，实现代码与配置的解耦。

## 2. 已实施的修改 (Infrastructure Layer)

以下修改已在 `2025-12-11` 完成并提交：

### 2.1 配置 Schema 更新
文件：`src/work_data_hub/infrastructure/settings/data_source_schema.py`
- 新增 `OutputConfig` 类，包含 `table` (必填) 和 `schema_name` (默认 "public")。
- 更新 `DomainConfigV2`，新增可选字段 `output`。

### 2.2 配置文件更新
文件：`config/data_sources.yml`
- 为 `annuity_performance` 域增加了输出配置。
- 为 `annuity_income` 域增加了输出配置。

```yaml
# 示例配置
domains:
  annuity_performance:
    # ... 其他配置 ...
    output:
      table: "annuity_performance"
      schema_name: "public"
```

### 2.3 测试验证
文件：`tests/unit/config/test_schema_v2.py`
- 增加了针对 `output` 字段解析和验证的单元测试，均已通过。

## 3. 开发实施指南 (Next Steps)

请开发团队根据以下指南修改 Pipeline 代码，以引用新的配置。

### 3.1 引用方式示例

在 Pipeline 代码中（如 `src/work_data_hub/domain/<domain>/pipeline.py` 或 Orchestration 任务中），请使用 `get_settings()` 获取配置。

```python
from work_data_hub.config import get_settings

def get_target_table(domain_name: str, is_validation_mode: bool = True) -> str:
    """
    根据配置获取目标表名。
    如果是验证模式，根据 Strangler Fig 模式追加 _NEW 后缀。
    """
    settings = get_settings()
    domain_config = settings.data_sources.domains.get(domain_name)
    
    if not domain_config or not domain_config.output:
        # Fallback 或 抛出异常，视具体策略而定
        raise ValueError(f"Output configuration missing for domain: {domain_name}")
    
    table_name = domain_config.output.table
    
    # 维持现有的 Strangler Fig 验证逻辑
    if is_validation_mode:
        return f"{table_name}_NEW"
        
    return table_name

# 在 Loader 调用中使用
# ...
loader.load_with_refresh(
    df=data,
    table=get_target_table("annuity_performance"),
    schema=domain_config.output.schema_name,
    # ...
)
```

### 3.2 待修改点建议
建议全文搜索 `load_with_refresh` 或 `load_dataframe` 方法的调用点，重点关注以下模块：
1. `src/work_data_hub/domain/annuity_performance/` 下的 Pipeline 入口。
2. `src/work_data_hub/orchestration/` 下的 Job 定义。

### 3.3 验证要求
- 修改后，请运行 `tests/e2e/` 相关测试，确保数据依然能正确写入到数据库。
- 验证 `_NEW` 后缀逻辑在开发/测试环境是否正常工作。
