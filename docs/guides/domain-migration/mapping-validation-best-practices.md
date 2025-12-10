# Mapping Validation Best Practices

本文档记录了 domain 迁移过程中映射验证的最佳实践，基于 `annuity_performance` domain 的实际审核经验。

## 🔍 关键发现：映射完整性检查

### 问题 1：映射表不完整导致的数据差异

#### 现象
在审核 `annuity_performance` domain 时发现，New Pipeline 的 `COMPANY_BRANCH_MAPPING` 仅包含 26 条映射，而 Legacy 系统包含 44 条映射。

#### 影响
- 18 个省份/直辖市（如河北、河南、四川、天津等）在 New Pipeline 中会错误地映射到默认值 "G00"
- 与 Legacy 系统的处理结果不一致

#### 根本原因
1. Legacy 系统从数据库动态加载映射：`SELECT 机构, 机构代码 FROM 组织架构`（38条）
2. Legacy 系统有 6 个特殊调整的映射
3. New Pipeline 仅手动维护了部分映射

#### 解决方案
```python
# 在 infrastructure/mappings/shared.py 中补充所有缺失的映射
COMPANY_BRANCH_MAPPING: Dict[str, str] = {
    # 完整的数据库映射（38条）
    "总部": "G00",
    "北京": "G01",
    # ... 所有其他映射

    # 特殊调整（6条）
    "内蒙": "G31",
    "战略": "G37",
    "中国": "G37",
    "济南": "G21",
    "北京其他": "G37",
    "北分": "G37",

    # 新增映射（可选）
    "深圳分公司": "G05",
    "广州": "G04",
}
```

#### 最佳实践
1. **验证映射完整性**：确保 New Pipeline 包含所有 Legacy 系统的映射
2. **统一管理**：将所有映射集中到 `infrastructure/mappings/shared.py`
3. **清晰注释**：标明每个映射的来源（数据库/特殊调整/新增）

### 问题 2：特殊值处理不一致

#### 现象
Legacy 系统明确处理字符串 "null"：
```python
df["机构代码"] = df["机构代码"].replace("null", "G00")
```

而 New Pipeline 最初没有这个处理：
```python
df["机构名称"].map(COMPANY_BRANCH_MAPPING).fillna("G00")
```

#### 影响
如果源数据包含字面值字符串 "null"，两个系统的处理结果会不一致。

#### 解决方案
在处理管道中添加特殊值处理：
```python
df["机构名称"]
    .map(COMPANY_BRANCH_MAPPING)
    .fillna("G00")
    .replace("null", "G00")  # 处理字符串 "null"
```

## 📋 验证清单

### 迁移前检查
- [ ] 识别 Legacy 系统中所有的映射表和配置
- [ ] 记录映射的来源（数据库查询、硬编码、外部文件等）
- [ ] 列出所有特殊值的处理逻辑

### 实现时检查
- [ ] 确保映射数量与 Legacy 系统一致
- [ ] 实现所有特殊值的处理
- [ ] 使用相同的默认值逻辑

### 验证时检查
- [ ] 使用相同的测试数据集
- [ ] 逐字段对比处理结果
- [ ] 特别关注边缘情况（null、空字符串、特殊字符）

## 🛠️ 推荐的验证流程

### 1. 逐步字段验证
```python
# 创建验证脚本
def validate_field(field_name, legacy_result, new_result):
    differences = []
    for i, (legacy_val, new_val) in enumerate(zip(legacy_result, new_result)):
        if legacy_val != new_val:
            differences.append({
                'row': i,
                'legacy': legacy_val,
                'new': new_val,
                'input': test_data[i]
            })
    return differences
```

### 2. 使用实际数据测试
- 使用生产环境的真实数据样本
- 覆盖各种边缘情况
- 记录并分析所有差异

### 3. 自动化验证
```python
# 在 CI/CD 中添加验证
def test_legacy_parity():
    legacy_output = process_with_legacy(test_data)
    new_output = process_with_new(test_data)

    assert legacy_output.equals(new_output), \
        f"Parity check failed. Differences: {find_differences(legacy_output, new_output)}"
```

## 📝 文档更新

### 更新映射文档
在补充映射后，更新相关文档：

```python
# infrastructure/mappings/shared.py
"""
Company branch name to institution code mapping

CRITICAL: Complete mapping including:
1. All 38 mappings from legacy.mapping."组织架构" database table
2. 6 legacy overrides from Story 5.5-1
3. Any new mappings added in pipeline

Total: XX mappings (complete parity with Legacy system)
"""
```

### 记录验证过程
在 domain 的 cleansing-rules 文档中添加：
- 验证日期和人员
- 发现的问题和解决方案
- 验证通过的映射清单

## 🚨 注意事项

1. **不要依赖记忆**：使用代码检查和自动化脚本
2. **不要假设**：总是验证每个映射和特殊值处理
3. **不要遗漏**：逐字段、逐场景进行完整验证
4. **不要忽视边缘情况**：空值、特殊字符、边界值都要测试

## 📚 相关资源

- [Legacy Parity Validation Guide](../../runbooks/legacy-parity-validation.md)
- [Domain Development Guide](./development-guide.md)
- [Cleansing Rules Template](../../templates/cleansing-rules-template.md)