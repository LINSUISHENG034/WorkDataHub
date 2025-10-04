# Company ID 简化实施方案

基于KISS/YAGNI原则的company_id字段问题解决方案，采用MVP优先、按需扩展的策略。

## 📋 任务拆分

### Phase 1: MVP核心功能
- **S-001**: Legacy映射迁移 - 将现有5层映射转换为简化表结构
- **S-002**: EQC客户端集成 - 直接实现EQC查询，无抽象层
- **S-003**: 基础缓存机制 - 实现2表缓存结构
- **S-004**: MVP端到端验证 - 完整流程测试

### Phase 2: 可选扩展（仅在MVP验证成功后考虑）
- **S-005**: 异步查询机制 - 如确有性能需求时实现

## 🏗️ 简化架构设计

### 核心表结构
```sql
-- 主映射表（替代原方案的4个表）
enterprise.company_mapping (
  alias_name TEXT,      -- 原始名称/计划代码等
  canonical_id TEXT,    -- 标准company_id
  source TEXT,          -- internal|external
  match_type TEXT,      -- exact|fuzzy|plan|account
  updated_at TIMESTAMP
);

-- 查询请求表（简化的队列）
enterprise.lookup_requests (
  name TEXT,
  status TEXT,          -- pending|done|failed
  created_at TIMESTAMP
);
```

### 处理优先级
1. 计划代码映射
2. 账户号映射
3. 客户名称精确匹配
4. EQC外部查询
5. 临时ID生成（TEMP_序号，简单递增）

## 🎯 与原方案差异

### 简化点
- ❌ 移除Provider抽象层 → ✅ 直接EQCClient
- ❌ 移除Gateway聚合层 → ✅ 简单优先级逻辑
- ❌ 移除复杂HMAC临时ID → ✅ 简单TEMP_序号
- ❌ 移除4个细分表 → ✅ 2个核心表
- ❌ 移除置信度评分 → ✅ 简单匹配状态

### 保留核心价值
- ✅ 覆盖所有legacy映射需求
- ✅ 支持外部EQC查询
- ✅ 缓存机制提高性能
- ✅ 审计追踪能力
- ✅ CLI-first集成

## 📈 成功标准

MVP验证通过标准：
- [ ] Legacy映射100%迁移成功
- [ ] EQC查询功能正常
- [ ] 缓存命中率提升可量化
- [ ] 端到端流程无阻塞
- [ ] 性能满足现有需求

扩展触发条件：
- 并发查询需求 > 10次/分钟
- 需要多Provider支持
- 需要复杂评分/审核机制

## 🚀 执行顺序

严格按S-001 → S-002 → S-003 → S-004顺序执行，每个阶段完成并验证后再进入下一阶段。