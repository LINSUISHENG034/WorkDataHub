# S-001 — Legacy映射迁移到简化表结构

将现有legacy系统中的5层company_id映射逻辑转换为新的简化2表结构，确保100%兼容性。

## FEATURE

将legacy/annuity_hub中的COMPANY_ID1-5_MAPPING转换为enterprise.company_mapping表，保持所有映射关系和优先级逻辑不变。

## SCOPE

### In-scope
- 迁移5层映射数据到统一的company_mapping表
- 保持原有优先级顺序：计划号→账户号→硬编码→客户名称→账户名
- 创建简化的DDL和索引结构
- 提供映射数据导入CLI工具
- 单元测试覆盖所有映射场景

### Non-goals
- 不修改现有业务逻辑，只做数据结构转换
- 不对映射数据进行清洗或去重（保持原样）
- 不涉及外部EQC查询功能

## CONTEXT SNAPSHOT

```bash
src/work_data_hub/
  domain/
    company_enrichment/          # 新增域
      models.py                  # 映射数据模型
      service.py                 # 映射查询逻辑
  io/
    loader/
      company_mapping_loader.py  # 映射数据导入器
  scripts/
    create_table/
      ddl/
        company_mapping.sql      # DDL脚本

legacy/annuity_hub/data_handler/
  mappings.py                    # 源映射数据
```

## EXAMPLES

- Path: `src/work_data_hub/domain/annuity_performance/models.py` — Pydantic模型结构参考
- Path: `src/work_data_hub/io/loader/warehouse_loader.py` — 数据装载模式参考
- Path: `src/work_data_hub/orchestration/ops.py` — CLI集成参考

```python
# 参考现有域模型模式
class CompanyMappingRecord(BaseModel):
    alias_name: str = Field(..., max_length=255)
    canonical_id: str = Field(..., max_length=50)
    source: Literal["internal"] = "internal"
    match_type: Literal["plan", "account", "hardcode", "name", "account_name"]
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

## DOCUMENTATION

- File: `legacy/annuity_hub/data_handler/mappings.py` — 原始映射逻辑
- File: `legacy/annuity_hub/data_handler/data_cleaner.py` — _update_company_id方法
- File: `src/work_data_hub/config/data_sources.yml` — 配置模式参考
- File: `CLAUDE.md` — 项目架构约定

## INTEGRATION POINTS

### Data models
```python
class CompanyMappingRecord(BaseModel):
    alias_name: str        # 源字段：计划号/账户号/客户名称等
    canonical_id: str      # 目标company_id
    source: str            # "internal"
    match_type: str        # "plan"|"account"|"hardcode"|"name"|"account_name"
    priority: int          # 1-5，对应原有5层优先级
    updated_at: datetime

class CompanyMappingService:
    def resolve_company_id(self, plan_code: str, customer_name: str, account_name: str) -> Optional[str]
```

### Database
```sql
CREATE TABLE enterprise.company_mapping (
    alias_name VARCHAR(255) NOT NULL,
    canonical_id VARCHAR(50) NOT NULL,
    source VARCHAR(20) DEFAULT 'internal',
    match_type VARCHAR(20) NOT NULL,
    priority INTEGER NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (alias_name, match_type)
);

CREATE INDEX idx_company_mapping_priority ON enterprise.company_mapping (priority, alias_name);
```

### Config/ENV
- `WDH_COMPANY_MAPPING_ENABLED=1` — 启用新映射逻辑开关
- 复用现有数据库连接配置

### Jobs/Events
- 新增CLI命令：`--job import_company_mappings`

## DATA CONTRACTS

### Legacy映射层级转换
```python
# 转换规则：
MAPPING_CONVERSION = {
    "COMPANY_ID1_MAPPING": ("plan", 1),      # 年金计划号 -> company_id
    "COMPANY_ID2_MAPPING": ("account", 2),   # 年金账户号 -> company_id
    "COMPANY_ID3_MAPPING": ("hardcode", 3),  # 硬编码映射
    "COMPANY_ID4_MAPPING": ("name", 4),      # 客户名称 -> company_id
    "COMPANY_ID5_MAPPING": ("account_name", 5) # 年金账户名 -> company_id
}
```

### 示例数据结构
```json
[
    {"alias_name": "AN001", "canonical_id": "614810477", "source": "internal", "match_type": "plan", "priority": 1},
    {"alias_name": "GM123456", "canonical_id": "608349737", "source": "internal", "match_type": "account", "priority": 2},
    {"alias_name": "FP0001", "canonical_id": "614810477", "source": "internal", "match_type": "hardcode", "priority": 3}
]
```

## GOTCHAS & LIBRARY QUIRKS

- Legacy MySQL连接可能不稳定，需要重试机制
- `COMPANY_ID3_MAPPING`是硬编码字典，需要手动转换
- 客户名称中可能包含特殊字符，需要适当转义
- PostgreSQL的VARCHAR长度限制与MySQL不同，注意字段长度
- 保持原有空值处理逻辑，None/空字符串的优先级判断

## IMPLEMENTATION NOTES

- 遵循现有错误处理模式：`src/work_data_hub/io/loader/warehouse_loader.py`
- 使用事务保证数据一致性
- 日志记录每层映射的转换统计
- 单个函数<50行，拆分为多个小函数
- 优先级查询使用ORDER BY priority ASC，LIMIT 1模式

## VALIDATION GATES

```bash
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v -k "test_company_mapping"

# 数据验证
uv run python -m src.work_data_hub.orchestration.jobs --job import_company_mappings --plan-only
uv run python -m src.work_data_hub.orchestration.jobs --job import_company_mappings --execute
```

## ACCEPTANCE CRITERIA

- [ ] 所有5层legacy映射100%导入到company_mapping表
- [ ] 优先级查询逻辑与legacy完全一致
- [ ] 支持增量更新和全量重建两种模式
- [ ] 导入过程支持plan-only预览模式
- [ ] 单元测试覆盖所有映射场景和边界条件
- [ ] 导入统计报告（每层映射条数、冲突处理等）
- [ ] 性能测试：查询响应时间<100ms

## ROLLOUT & RISK

### Feature flags
- `WDH_COMPANY_MAPPING_ENABLED=0` 默认关闭，不影响现有逻辑
- 渐进式启用：先在测试环境验证，再生产切换

### Migration strategy
- 支持回滚：保留原legacy映射逻辑作为fallback
- 数据备份：导入前自动备份现有company_mapping表
- 增量同步：定期从legacy同步映射变更

### Risk mitigation
- 映射缺失风险：导入前后进行条数对比验证
- 性能风险：分批导入，避免长事务锁表
- 数据质量风险：导入过程验证canonical_id格式

## APPENDICES

### 测试数据示例
```python
@pytest.fixture
def sample_legacy_mappings():
    return {
        "COMPANY_ID1_MAPPING": {"AN001": "614810477", "AN002": "608349737"},
        "COMPANY_ID2_MAPPING": {"GM123456": "614810477"},
        "COMPANY_ID3_MAPPING": {"FP0001": "614810477", "P0809": "608349737"},
        "COMPANY_ID4_MAPPING": {"测试企业A": "614810477"},
        "COMPANY_ID5_MAPPING": {"测试年金账户": "614810477"}
    }

def test_mapping_conversion_priority():
    # 验证优先级：计划号 > 账户号 > 硬编码 > 客户名 > 账户名
    assert service.resolve_company_id("AN001", "测试企业A", "测试年金账户") == "614810477"  # AN001优先
```

### 有用的搜索命令
```bash
rg "COMPANY_ID.*_MAPPING" legacy/annuity_hub/
rg "_update_company_id" legacy/annuity_hub/
rg "company_id.*map" src/work_data_hub/
```