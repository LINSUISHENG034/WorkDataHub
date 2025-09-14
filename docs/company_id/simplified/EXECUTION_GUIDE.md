# Company ID 简化方案执行指南

基于KISS/YAGNI原则重新设计的company_id解决方案，通过4个阶段递进实施。

## 📅 执行时序

**严格按顺序执行，每个阶段完成并验证通过后再进入下一阶段。**

```mermaid
graph LR
    S001[S-001 Legacy映射迁移] --> S002[S-002 EQC客户端集成]
    S002 --> S003[S-003 基础缓存机制]
    S003 --> S004[S-004 MVP端到端验证]
    S004 --> Decision{效果评估}
    Decision -->|满足需求| Complete[完成MVP]
    Decision -->|需要优化| S005[S-005 异步队列扩展]
```

## 🎯 各阶段目标与产出

### S-001: Legacy映射迁移
**目标**: 将现有5层映射转换为简化的2表结构
**产出**:
- `enterprise.company_mapping`表和数据
- `CompanyMappingService`类
- 映射导入CLI工具
- 100%映射覆盖率验证

**验收标准**:
```bash
# 映射导入成功
uv run python -m src.work_data_hub.orchestration.jobs --job import_company_mappings --execute

# 查询功能验证
SELECT count(*) FROM enterprise.company_mapping;  -- 应该>1000条记录
```

### S-002: EQC客户端集成
**目标**: 直接实现EQC查询客户端，无抽象层
**产出**:
- `EQCClient`类
- 错误处理和重试机制
- 模拟测试和真实集成测试

**验收标准**:
```bash
# 单元测试通过
uv run pytest -v tests/io/connectors/test_eqc_client.py

# 集成测试（需要真实token）
export WDH_EQC_TOKEN=your_token
uv run pytest -v -m integration
```

### S-003: 基础缓存机制
**目标**: 集成映射服务和EQC客户端，实现统一解析服务
**产出**:
- `CompanyEnrichmentService`核心服务
- `enterprise.lookup_requests`异步队列表
- 临时ID生成机制（TEMP_序号）
- 优先级解析逻辑

**验收标准**:
```bash
# 服务集成测试
uv run pytest -v tests/domain/company_enrichment/

# 临时ID生成测试
uv run python -c "
from src.work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
service = CompanyEnrichmentService(...)
print(service.generate_temp_id())  # 应输出TEMP_000001格式
"
```

### S-004: MVP端到端验证
**目标**: 在annuity_performance域中完整验证新方案
**产出**:
- 集成到现有处理流程
- 与legacy对比验证报告
- 性能基准测试结果
- 异步队列处理CLI

**验收标准**:
```bash
# 端到端流程验证
export WDH_COMPANY_ENRICHMENT_ENABLED=1
uv run python -m src.work_data_hub.orchestration.jobs \
  --domain annuity_performance \
  --execute --max-files 1 \
  --enrichment-enabled \
  --enrichment-sync-budget 5

# 对比一致性>95%，性能开销<50%
```

## 🔧 环境准备

### 数据库环境
```sql
-- 创建enterprise schema
CREATE SCHEMA IF NOT EXISTS enterprise;

-- 确保有足够权限
GRANT ALL ON SCHEMA enterprise TO current_user;
GRANT ALL ON ALL TABLES IN SCHEMA enterprise TO current_user;
```

### 开发环境
```bash
# 依赖安装
uv sync

# 环境变量配置
cp .env.example .env
# 编辑.env，设置数据库连接和其他配置

# 代码质量检查
uv run ruff check src/ --fix
uv run mypy src/
```

### 测试数据准备
```bash
# 确保测试数据存在
ls tests/fixtures/sample_data/annuity_subsets/
# 应该包含至少一个Excel文件

# 验证数据库连接
export WDH_DATABASE__URI=postgresql://user:pass@host:5432/db
psql "$WDH_DATABASE__URI" -c "SELECT version();"
```

## 📊 关键指标跟踪

### S-001完成后
- [ ] 映射记录总数: _____ 条
- [ ] 5层映射覆盖情况:
  - 计划映射: _____ 条
  - 账户映射: _____ 条
  - 硬编码映射: 8 条（固定）
  - 客户名映射: _____ 条
  - 账户名映射: _____ 条

### S-002完成后
- [ ] EQC连通性测试: ✅/❌
- [ ] 搜索响应时间: _____ ms
- [ ] 错误处理覆盖: ✅/❌

### S-003完成后
- [ ] 优先级逻辑测试: ✅/❌
- [ ] 临时ID生成测试: ✅/❌
- [ ] 并发安全性测试: ✅/❌

### S-004完成后（关键验收指标）
- [ ] 与legacy一致性: _____%（目标>95%）
- [ ] 性能开销: _____%（目标<50%）
- [ ] 新增解析能力: _____ 条
- [ ] 异步队列处理: ✅/❌

## 🚨 常见问题排查

### S-001阶段问题
**问题**: 映射导入失败
**排查**:
```bash
# 检查legacy数据库连接
python -c "from legacy.annuity_hub.database_operations.mysql_ops import MySqlDBManager; print('MySQL连接OK')"

# 检查PostgreSQL连接
psql "$WDH_DATABASE__URI" -c "SELECT 1;"
```

### S-002阶段问题
**问题**: EQC认证失败
**排查**:
```bash
# 检查token配置
echo $WDH_EQC_TOKEN | wc -c  # 应该>10个字符

# 手动测试EQC接口
curl -H "Authorization: Bearer $WDH_EQC_TOKEN" \
  "https://eqc.pingan.com/kg-api-hfd/api/search/searchAll?keyword=测试"
```

### S-003阶段问题
**问题**: 临时ID重复
**排查**:
```sql
-- 检查序号表状态
SELECT * FROM enterprise.temp_id_sequence;

-- 检查是否有重复的临时ID
SELECT company_id, COUNT(*)
FROM enterprise.company_mapping
WHERE company_id LIKE 'TEMP_%'
GROUP BY company_id
HAVING COUNT(*) > 1;
```

### S-004阶段问题
**问题**: 端到端测试失败
**排查**:
```bash
# 分步验证
# 1. 不启用enrichment的baseline
export WDH_COMPANY_ENRICHMENT_ENABLED=0
uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only

# 2. 启用enrichment但不使用EQC
export WDH_COMPANY_ENRICHMENT_ENABLED=1
export WDH_ENRICHMENT_SYNC_BUDGET=0
uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only

# 3. 启用小额度EQC查询
export WDH_ENRICHMENT_SYNC_BUDGET=2
uv run python -m src.work_data_hub.orchestration.jobs --domain annuity_performance --plan-only
```

## 🎉 成功标准

### MVP验收通过标准
- ✅ 所有4个阶段的验收标准全部通过
- ✅ 与legacy对比一致性>95%
- ✅ 性能开销<50%
- ✅ 错误场景下系统稳定，优雅降级
- ✅ 异步队列功能正常，可以提升命中率

### 可选扩展触发条件
如果MVP验收后发现以下情况，可考虑进入S-005扩展阶段：
- 并发查询需求>10次/分钟，需要优化
- 需要支持多个外部Provider（非EQC）
- 需要复杂的置信度评分和人工审核
- 需要更复杂的临时ID管理

### 项目完成标志
- 📋 MVP功能完全可用，满足当前业务需求
- 📈 数据质量显著提升，unknown samples减少
- ⚡ 性能符合预期，不影响现有流程
- 🛡️ 稳定性良好，错误处理完备
- 📖 文档完整，便于维护和扩展

---

**执行建议**: 建议分配1-2周时间完成所有4个阶段，每个阶段1-3天。严格按顺序执行，确保每个阶段都充分验证后再进入下一阶段。