# CLI Schema配置继承问题描述

## 问题概述

CLI在构建数据源配置时，没有正确使用已有的配置继承机制，导致domain配置无法继承defaults中的`schema_name`设置，造成ETL执行时表名缺少schema前缀的错误。

## 问题详情

### 1. 配置文件结构

`config/data_sources.yml` 文件采用 defaults/overrides 模式：

```yaml
schema_version: "1.1"

# ============================================================================
# DEFAULTS - Applied to all domains unless overridden
# ============================================================================
defaults:
  exclude_patterns:
    - "~$*"         # Excel temp files
    - "*.eml"       # Email files
  version_strategy: "highest_number"
  fallback: "error"

  # Default output schema
  output:
    schema_name: "business"

# ============================================================================
# DOMAINS - Only specify what differs from defaults
# ============================================================================
domains:
  annuity_performance:
    # ... 其他配置
    output:
      table: "规模明细"
      # 注意：这里没有显式指定 schema_name
      pk:
        - "月度"
        - "业务类型"
        - "计划类型"
```

### 2. 预期行为

根据设计文档（Story 6.2-P14），配置继承规则为：
- **标量值**: domain配置覆盖defaults
- **列表**: domain配置替换defaults（使用"+"前缀可扩展）
- **字典**: 深度合并，domain值覆盖defaults值

因此，`annuity_performance` 应该继承 defaults 中的 `schema_name: "business"`，最终配置应该是：
```yaml
output:
  table: "规模明细"
  schema_name: "business"  # 继承自defaults
```

### 3. 实际行为

CLI代码 (`src/work_data_hub/cli/etl.py:256-264`) 直接解析YAML，没有使用已有的继承逻辑：

```python
# Epic 3 schema prefers output.table + output.schema_name
output_cfg = domain_config.get("output") if isinstance(domain_config, dict) else None
if isinstance(output_cfg, dict) and output_cfg.get("table"):
    table_name = str(output_cfg["table"])
    schema_name = output_cfg.get("schema_name")  # 只检查domain级别的配置
    if schema_name:
        table = f"{schema_name}.{table_name}"
    else:
        table = table_name
```

### 4. 现有解决方案

项目中已有正确的继承实现：
- **函数**: `get_domain_config_v2()` 在 `src/work_data_hub/infrastructure/settings/data_source_schema.py`
- **功能**: 使用 `_merge_with_defaults()` 正确处理defaults/domain合并
- **位置**: 第416-420行

```python
def get_domain_config_v2(domain_name: str, config_path: str = "config/data_sources.yml") -> DomainConfigV2:
    # ...
    domain_raw = data["domains"][domain_name] or {}
    defaults = data.get("defaults") or {}

    merged = _merge_with_defaults(domain_raw, defaults) if defaults else domain_raw
    return DomainConfigV2(**merged)
```

### 5. 问题影响

#### 症状表现：
1. ETL执行失败，错误：`关系 "规模明细" 不存在`
2. 生成的SQL缺少schema前缀：`DELETE FROM "规模明细"` 而不是 `DELETE FROM "business"."规模明细"`

#### 根本原因：
CLI没有使用 `get_domain_config_v2()` 处理配置继承，导致：
- defaults中的 `schema_name: "business"` 被忽略
- 最终table名称只是 `"规模明细"`，缺少 `"business."` 前缀

#### 影响范围：
- 所有没有显式指定 `schema_name` 的domain配置
- 依赖defaults继承的配置项
- ETL数据加载功能

## 技术细节

### 配置解析路径对比

**当前CLI路径（有问题）**:
```
CLI → 直接YAML解析 → domain_config.get("output") → schema_name missing
```

**正确路径（已存在）**:
```
CLI → get_domain_config_v2() → _merge_with_defaults() → 完整继承配置
```

### 相关文件
- `src/work_data_hub/cli/etl.py` - 问题代码位置（第245-264行）
- `src/work_data_hub/infrastructure/settings/data_source_schema.py` - 正确实现
- `config/data_sources.yml` - 配置文件
- `src/work_data_hub/io/loader/warehouse_loader.py` - 表名引用逻辑

### 测试验证方法
```python
# 当前CLI逻辑测试
from work_data_hub.config.settings import get_settings
import yaml

settings = get_settings()
with open(settings.data_sources_config, 'r', encoding='utf-8') as f:
    data_sources = yaml.safe_load(f)

domain = 'annuity_performance'
domain_config = data_sources.get('domains', {}).get(domain, {})
output_cfg = domain_config.get('output')
# 结果: schema_name = None (丢失defaults继承)

# 正确逻辑测试
from work_data_hub.infrastructure.settings.data_source_schema import get_domain_config_v2
config = get_domain_config_v2('annuity_performance')
# 结果: config.output.schema_name = 'business' (正确继承)
```

## 上下文信息

- **发现时间**: 2025-12-21 (Story 6.2-P17测试过程中)
- **影响Sprint**: Sprint Change Proposal 2025-12-20 EQC lookup config unification
- **相关Story**: Story 6.2-P14 Config File Modularization (已实现defaults/overrides机制)
- **代码审查需求**: 需要评估将CLI迁移到使用 `get_domain_config_v2()` 的影响范围