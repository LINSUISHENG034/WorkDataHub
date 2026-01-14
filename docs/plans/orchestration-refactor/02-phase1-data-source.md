# Phase 1: 配置驱动数据源

> **Priority:** P1 (可与 Phase 0 并行)
> **Estimated Scope:** 配置文件 + MultiTableLoader

---

## 目标

实现配置驱动的数据源加载，支持 single-file 和 multi-table 两种模式。

## TDD 测试清单

### Test 1: 配置文件加载

```python
# tests/config/test_domain_sources.py
def test_domain_source_config_loads():
    from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY
    assert "annuity_performance" in DOMAIN_SOURCE_REGISTRY
    assert "annual_award" in DOMAIN_SOURCE_REGISTRY

def test_source_type_valid():
    for domain, config in DOMAIN_SOURCE_REGISTRY.items():
        assert config.source_type in ["single_file", "multi_table"]
```

### Test 2: Multi-table 输出格式一致性

```python
def test_multi_table_output_is_list_of_dicts():
    config = DOMAIN_SOURCE_REGISTRY["annual_award"]
    result = MultiTableLoader.load(config)
    assert isinstance(result, list)
    assert all(isinstance(r, dict) for r in result)
```

---

## 实现步骤

### Step 1: 创建配置文件

**文件:** `config/domain_sources.yaml`

```yaml
annuity_performance:
  source_type: single_file
  discovery:
    path_pattern: "{data_root}/年金业绩/*.xlsx"

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
```

### Step 2: 实现配置加载器

**文件:** `src/work_data_hub/config/domain_sources.py`

### Step 3: 实现 MultiTableLoader

**文件:** `src/work_data_hub/io/reader/multi_table_loader.py`

---

## 验收标准

- [ ] 配置文件可正确解析
- [ ] `annual_award` 通过 multi_table 加载
- [ ] 输出格式与 single_file 一致 (List[Dict])
