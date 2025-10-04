# 数据清洗框架优化实施指导（INITIAL.md）

## FEATURE

优化现有的数据清洗框架架构设计，消除过度工程化组件，保留核心功能以支持21个legacy domain的清洗需求迁移，确保框架符合KISS和YAGNI原则。

## SCOPE

### In-scope:
- 简化`src/work_data_hub/cleansing/registry.py`的复杂索引系统
- 保留并优化`numeric_rules.py`中的核心清洗功能
- 简化`pydantic_adapter.py`的集成逻辑
- 确保两个现有domain模型能够使用优化后的框架
- 创建简洁的清洗规则注册和查找机制

### Non-goals:
- 完全重写清洗框架（保留合理的架构设计）
- 立即迁移所有21个legacy domains（分阶段实施）
- 删除所有高级功能（保留确实需要的功能）

## CONTEXT SNAPSHOT

```bash
src/work_data_hub/
  cleansing/                    # 当前框架 (893行总计)
    __init__.py                 # 137行 - 框架入口
    registry.py                 # 254行 - 注册表和索引系统 [需要简化]
    rules/
      numeric_rules.py          # 286行 - 核心清洗规则 [保留优化]
    integrations/
      pydantic_adapter.py       # 216行 - Pydantic集成 [简化]
  domain/
    annuity_performance/models.py    # 存在重复的clean_decimal_fields
    trustee_performance/models.py    # 存在重复的clean_decimal_fields
```

## EXAMPLES

**保留模式 - 核心清洗功能**：
- Path: `src/work_data_hub/cleansing/rules/numeric_rules.py` — 这是实际解决重复问题的核心代码，架构合理

**简化模式 - 注册表系统**：
- Path: `src/work_data_hub/cleansing/registry.py` — 移除复杂索引，保留基础注册功能

**集成模式 - Domain使用**：
- Path: `src/work_data_hub/domain/trustee_performance/models.py:167-237` — 参考现有clean_decimal_fields模式

```python
# 优化后的简化注册表设计
class CleansingRegistry:
    _rules: Dict[str, CleansingRule] = {}
    
    def register(self, rule: CleansingRule) -> None:
        self._rules[rule.name] = rule
    
    def get_rule(self, name: str) -> Optional[CleansingRule]:
        return self._rules.get(name)
    
    def find_numeric_rules(self) -> List[CleansingRule]:
        return [r for r in self._rules.values() if r.category == RuleCategory.NUMERIC]
```

## DOCUMENTATION

- File: `CLAUDE.md` — 项目编码规范和架构原则
- File: `docs/overview/R-015_LEGACY_INVENTORY.md` — 21个domain的清洗需求详情
- File: `docs/overview/MIGRATION_REFERENCE.md` — 迁移方法和架构要求
- File: `ROADMAP.md` — M2阶段domain迁移计划

## INTEGRATION POINTS

**数据模型**：
- 保留现有`CleansingRule`数据类，简化元数据字段
- 保留`RuleCategory`枚举，但重点关注NUMERIC类别
- 更新domain模型使用简化的清洗接口

**配置**：
- 移除复杂的配置文件驱动（`domain_rules.yml`等）
- 保留代码级别的清洗规则定义

**集成接口**：
- 简化`decimal_fields_cleaner`装饰器
- 保留与Pydantic v2的集成

## DATA CONTRACTS

```python
# 简化的清洗规则定义
@dataclass
class CleansingRule:
    name: str
    category: RuleCategory
    func: Callable
    description: str
    # 移除：applicable_types, field_patterns, version, author

# 保留的核心清洗函数接口
def comprehensive_decimal_cleaning(
    value: Any, 
    field_name: str = "", 
    precision: int = 4
) -> Optional[Decimal]:
    """统一的数值清洗函数，解决重复实现问题"""
```

## GOTCHAS & LIBRARY QUIRKS

- 保持与Pydantic v2的兼容性，不要使用v1的`orm_mode`
- 注意中文字段名的处理（期初资产规模、期末资产规模等）
- Decimal精度量化需要使用`ROUND_HALF_UP`保持一致性
- 百分比转换逻辑需要区分字符串"50%"和数值50的不同含义

## IMPLEMENTATION NOTES

**重构策略**：
1. **保留有效组件**：`numeric_rules.py`中的清洗函数是解决实际问题的核心
2. **简化注册机制**：移除多层索引，保留基础注册和查找
3. **渐进式采用**：先让现有2个domain使用，验证效果后扩展
4. **避免破坏性变更**：保持公共API的稳定性

**架构原则**：
- 遵循CLAUDE.md中的KISS原则：选择简单方案而非复杂方案
- 函数保持在50行以内，类保持在100行以内
- 优先使用组合而非继承

## VALIDATION GATES

```bash
# 基础验证
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# 确保现有功能正常
uv run pytest tests/test_cleansing_framework.py -v

# 确保domain模型集成正常
uv run pytest tests/domain/ -k "decimal" -v
```

## ACCEPTANCE CRITERIA

- [ ] 两个现有domain模型成功使用优化后的清洗框架
- [ ] `clean_decimal_fields`重复代码被消除
- [ ] 注册表系统复杂度降低，但保持基础功能
- [ ] 核心清洗规则功能完整保留
- [ ] 框架总代码行数降低20-30%
- [ ] 所有现有测试继续通过
- [ ] 新的简化API文档清晰易懂

## ROLLOUT & RISK

**实施阶段**：
1. **Phase 1**: 简化注册表，移除不必要的索引系统
2. **Phase 2**: 更新现有domain模型使用优化框架
3. **Phase 3**: 为下一个domain迁移提供简洁的清洗接口

**风险控制**：
- 保持向后兼容性，确保现有代码不受影响
- 分步骤重构，每步都有测试验证
- 保留回退选项：可以快速恢复到当前实现

## IMPLEMENTATION PRIORITY

**高优先级（立即执行）**：
1. 简化`CleansingRegistry`类，移除复杂索引
2. 更新两个domain模型使用框架，消除重复代码

**中优先级（后续优化）**：
1. 简化`pydantic_adapter.py`的装饰器逻辑
2. 优化测试覆盖率和文档

**低优先级（可选）**：
1. 为未来domain迁移准备更多清洗规则类型

通过这个优化，我们将获得一个既符合KISS/YAGNI原则，又能支持enterprise-scale domain迁移需求的清洗框架。