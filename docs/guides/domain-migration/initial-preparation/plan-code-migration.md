# 计划代码映射迁移指南

本文档记录了年金计划映射从Legacy数据库迁移到`enterprise.enrichment_index`的完整过程，以及如何解除New Pipeline对Legacy数据库的依赖。

## 背景与问题

### 原始问题
- Legacy系统在`mapping.年金计划`表中存储计划代码到company_id的映射
- New Pipeline通过`src/work_data_hub/io/loader/company_mapping_loader.py`中的`_extract_company_id1_mapping`函数查询Legacy数据库
- 这造成了New Pipeline对Legacy数据库的依赖，违反了系统解耦原则

### 迁移目标
1. 将计划代码映射数据完全迁移到`enterprise.enrichment_index`
2. 删除对Legacy数据库的查询代码
3. 确保New Pipeline能正常解析计划代码

## 迁移过程

### 1. 数据准备
```bash
# 检查原始数据
source .env
PGPASSWORD=$WDH_DATABASE_PASSWORD psql -h $WDH_DATABASE_HOST -U $WDH_DATABASE_USER -d legacy -c "
    SELECT COUNT(*) FROM mapping.\"年金计划\" WHERE \"计划类型\" = '单一计划'
"
```

结果：1137条单一计划记录

### 2. 执行迁移
```bash
# 使用迁移脚本
source .env && DATABASE_URL="postgresql://$WDH_DATABASE_USER:$WDH_DATABASE_PASSWORD@$WDH_DATABASE_HOST:$WDH_DATABASE_PORT/$WDH_DATABASE_DB" \
PYTHONPATH=src uv run python scripts/migrations/migrate_plan_mapping_simple.py
```

迁移结果：
- 成功迁移：1,125条记录
- 查询类型：`plan_code`
- 置信度：1.00
- source：`legacy_migration`

### 3. 验证迁移
```bash
# 验证迁移结果
PYTHONPATH=src uv run python scripts/migrations/migrate_plan_mapping_simple.py --verify
```

验证结果：
- 计划代码映射总数：1,125
- 唯一计划代码数：1,125
- 空company_id记录数：0

### 4. 代码清理

#### 4.1 删除Legacy查询函数
文件：`src/work_data_hub/io/loader/company_mapping_loader.py`

删除：
```python
def _extract_company_id1_mapping() -> Dict[str, str]:
    # 已删除 - 整个函数移除
```

#### 4.2 移除相关调用代码
```python
# NOTE: COMPANY_ID1_MAPPING (Plan codes) extraction has been removed
# The plan code mapping data has been migrated to enterprise.enrichment_index
# This reduces dependency on Legacy database and improves system decoupling
```

### 5. 更新Pipeline代码

文件：`src/work_data_hub/domain/annuity_performance/pipeline_builder.py`

更新CompanyIdResolutionStep类，增加mapping_repository参数：
```python
class CompanyIdResolutionStep(TransformStep):
    def __init__(
        self,
        # ... 其他参数
        mapping_repository=None,  # 新增参数
    ) -> None:
        self._resolver = CompanyIdResolver(
            # ... 其他参数
            mapping_repository=mapping_repository,  # 传入参数
        )
```

## 测试验证

### 1. 单元测试
测试CompanyIdResolver能正确从enrichment_index查询计划代码：
```python
# 测试结果
✅ 1S1036 → 602785212
✅ AN003 → 600866980
✅ NP001 → 640589279
```

### 2. 集成测试
测试annuity_performance pipeline能正确解析company_id：
```python
# 测试数据：3条记录（2个已知计划代码，1个未知）
# 结果：
- 数据库缓存命中：2条
- 临时ID生成：1条
- 解析正确率：100%
```

## 架构改进

### 迁移前
```
New Pipeline
├── YAML overrides (P1)
├── Legacy MySQL mapping.年金计划 (P1)  <-- 依赖问题
├── enrichment_index (DB-P2..P5)
└── ...
```

### 迁移后
```
New Pipeline
├── YAML overrides (P1)
├── enrichment_index (DB-P1..P5)     <-- 统一数据源
├── Legacy-free
└── ...
```

## 收益

1. **解耦**：完全解除对Legacy数据库的依赖
2. **统一**：所有company_id映射统一在enrichment_index管理
3. **性能**：批量查询优化，提高解析速度
4. **可靠性**：避免因Legacy数据库不可用导致的故障

## 注意事项

1. **mapping_repository传递**：确保在创建CompanyIdResolutionStep时传入mapping_repository
2. **数据同步**：如果计划代码有更新，需要同步更新enrichment_index
3. **监控**：关注plan_code解析的成功率和性能

## 相关文件

- 迁移脚本：`scripts/migrations/migrate_plan_mapping_simple.py`
- 验证脚本：`test_plan_code_resolution.py`
- 集成测试：`test_annuity_performance_integration.py`
- 技术规范：`docs/sprint-artifacts/tech-spec/remove-legacy-dependency-plan-mapping.md`