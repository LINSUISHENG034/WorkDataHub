# Layer 2 Enrichment Index 增强需求

> **文档状态**: ✅ 已完成/归档
> **创建日期**: 2025-12-08
> **归档日期**: 2026-01-07
> **来源**: Epic 6 回顾讨论
> **实现状态**: Story 6.1.1 ~ 6.1.3, Story 7.1-4

> [!IMPORTANT]
> **此文档已归档**。所有功能已在以下 Story 中实现：
> - Story 6.1.1: Enrichment Index Schema Enhancement
> - Story 6.1.3: Domain Learning Mechanism
> - Story 7.1-4: Legacy Migration to enrichment_index
> 
> **实现差异**: 最终实现简化为 4 种 lookup_type (`plan_code`, `customer_name`, `plan_customer`, `former_name`)，移除了 `account_name` 和 `account_number`。
> 
> 最新文档请参见: `docs/guides/infrastructure/company-enrichment-service.md`

---

## 1. 背景与问题

### 1.1 当前实现

**Layer 1 (YAML Configuration)** 实现了 5 个优先级的决策流程：

| 优先级 | 查找方式 | 说明 |
|--------|----------|------|
| P1 | plan_code → company_id | 计划代码直接映射 |
| P2 | account_name → company_id | 年金账户名映射 |
| P3 | account_number → company_id | 年金账户号映射 |
| P4 | customer_name (normalized) → company_id | 客户名称映射 |
| P5 | plan_code + customer_name → company_id | 组合映射 |

**Layer 2 (Database Cache)** 当前只有单一匹配：

```
normalized_name → company_id  (仅此一种)
```

### 1.2 问题陈述

1. **优先级缺失**：Layer 2 缺少与 Layer 1 对应的多优先级决策机制
2. **自学习不足**：当前 Backflow 仅在 Layer 3 (Existing Column) 命中时触发，未能充分利用已处理数据
3. **数据孤岛**：各 Domain 处理后的有效映射关系未能回馈到全局缓存

---

## 2. 需求目标

### 2.1 核心目标

1. **多优先级决策**：Layer 2 实现与 Layer 1 相同的 P1-P5 优先级查找
2. **自学习机制**：从已处理的 Domain 数据中学习，自动积累有效映射
3. **跨 Domain 共享**：一个 Domain 学习到的映射可被其他 Domain 复用

### 2.2 预期效果

- 随着数据处理量增加，缓存命中率持续提升
- 减少对 EQC API 的依赖
- 减少临时 ID 生成数量

---

## 3. 技术设计

### 3.1 数据库 Schema

#### 新表：`enterprise.enrichment_index`

```sql
CREATE TABLE enterprise.enrichment_index (
    id SERIAL PRIMARY KEY,

    -- 查找键
    lookup_key VARCHAR(255) NOT NULL,
    lookup_type VARCHAR(20) NOT NULL,  -- plan_code, account_name, account_number, customer_name, plan_customer

    -- 映射结果
    company_id VARCHAR(50) NOT NULL,

    -- 元数据
    confidence DECIMAL(3,2) DEFAULT 1.00,
    source VARCHAR(50) NOT NULL,       -- yaml, eqc_api, manual, backflow, domain_learning
    source_domain VARCHAR(50),         -- 学习来源 domain: annuity_performance, annuity_income, etc.
    source_table VARCHAR(100),         -- 学习来源表: annuity_performance_new, etc.

    -- 统计信息
    hit_count INT DEFAULT 0,           -- 命中次数（用于优化）
    last_hit_at TIMESTAMP,             -- 最后命中时间

    -- 审计字段
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- 约束
    UNIQUE (lookup_key, lookup_type)
);

-- 索引优化
CREATE INDEX ix_enrichment_index_type_key
ON enterprise.enrichment_index(lookup_type, lookup_key);

CREATE INDEX ix_enrichment_index_source
ON enterprise.enrichment_index(source);

CREATE INDEX ix_enrichment_index_source_domain
ON enterprise.enrichment_index(source_domain);
```

#### lookup_type 枚举值

| lookup_type | 说明 | lookup_key 格式 |
|-------------|------|-----------------|
| `plan_code` | 计划代码 | 原始值 |
| `account_name` | 年金账户名 | 原始值 |
| `account_number` | 年金账户号 | 原始值 |
| `customer_name` | 客户名称 | normalized 值 |
| `plan_customer` | 计划+客户组合 | `{plan_code}|{normalized_name}` |

#### source 枚举值

| source | 说明 |
|--------|------|
| `yaml` | 从 YAML 配置同步 |
| `eqc_api` | EQC API 查询结果 |
| `manual` | 手动添加 |
| `backflow` | Layer 3 Backflow 回写 |
| `domain_learning` | Domain 数据自学习 |
| `legacy_migration` | Legacy 数据迁移 |

### 3.2 Layer 2 决策流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Layer 2: Database Cache (Enhanced)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DB-P1: plan_code → company_id                                               │
│         SELECT company_id, confidence FROM enrichment_index                  │
│         WHERE lookup_type = 'plan_code' AND lookup_key = :plan_code          │
│         ORDER BY confidence DESC LIMIT 1                                     │
│                              ↓ Not found                                     │
│  DB-P2: account_name → company_id                                            │
│         SELECT company_id, confidence FROM enrichment_index                  │
│         WHERE lookup_type = 'account_name' AND lookup_key = :account_name    │
│         ORDER BY confidence DESC LIMIT 1                                     │
│                              ↓ Not found                                     │
│  DB-P3: account_number → company_id                                          │
│         SELECT company_id, confidence FROM enrichment_index                  │
│         WHERE lookup_type = 'account_number' AND lookup_key = :account_number│
│         ORDER BY confidence DESC LIMIT 1                                     │
│                              ↓ Not found                                     │
│  DB-P4: customer_name (normalized) → company_id                              │
│         SELECT company_id, confidence FROM enrichment_index                  │
│         WHERE lookup_type = 'customer_name' AND lookup_key = :normalized_name│
│         ORDER BY confidence DESC LIMIT 1                                     │
│                              ↓ Not found                                     │
│  DB-P5: plan_code + customer_name → company_id                               │
│         SELECT company_id, confidence FROM enrichment_index                  │
│         WHERE lookup_type = 'plan_customer'                                  │
│         AND lookup_key = :plan_code || '|' || :normalized_name               │
│         ORDER BY confidence DESC LIMIT 1                                     │
│                              ↓ Not found                                     │
│  继续到 Layer 3                                                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 自学习机制

#### 3.3.1 学习触发时机

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Domain 数据自学习流程                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Pipeline 处理完成                                                           │
│       ↓                                                                      │
│  从 Domain 表中提取有效映射                                                  │
│  (company_id 非空且非临时 ID)                                                │
│       ↓                                                                      │
│  按 lookup_type 分类整理                                                     │
│       ↓                                                                      │
│  批量写入 enrichment_index                                                   │
│  (ON CONFLICT 更新 confidence 和 hit_count)                                  │
│       ↓                                                                      │
│  记录学习统计                                                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 学习数据提取 SQL

```sql
-- 从 annuity_performance_new 表学习
-- 提取有效的 plan_code → company_id 映射

INSERT INTO enterprise.enrichment_index
    (lookup_key, lookup_type, company_id, confidence, source, source_domain, source_table)
SELECT DISTINCT
    ap.计划代码 as lookup_key,
    'plan_code' as lookup_type,
    ap.company_id,
    0.95 as confidence,  -- Domain 学习的 confidence 略低于手动配置
    'domain_learning' as source,
    'annuity_performance' as source_domain,
    'annuity_performance_new' as source_table
FROM annuity_performance_new ap
WHERE ap.company_id IS NOT NULL
  AND ap.company_id NOT LIKE 'IN_%'  -- 排除临时 ID
  AND ap.计划代码 IS NOT NULL
ON CONFLICT (lookup_key, lookup_type)
DO UPDATE SET
    confidence = GREATEST(enrichment_index.confidence, EXCLUDED.confidence),
    hit_count = enrichment_index.hit_count + 1,
    updated_at = NOW();

-- 类似地提取其他 lookup_type 的映射...
```

#### 3.3.3 学习配置

```python
# config/settings.py

class DomainLearningConfig:
    """Domain 数据自学习配置"""

    # 启用自学习的 Domain 列表
    enabled_domains: List[str] = [
        "annuity_performance",
        "annuity_income",
    ]

    # 各 lookup_type 的学习配置
    learning_rules: Dict[str, LearningRule] = {
        "plan_code": LearningRule(
            source_column="计划代码",
            confidence=0.95,
            enabled=True,
        ),
        "account_name": LearningRule(
            source_column="年金账户名",
            confidence=0.90,
            enabled=True,
        ),
        "account_number": LearningRule(
            source_column="年金账户号",
            confidence=0.95,
            enabled=True,
        ),
        "customer_name": LearningRule(
            source_column="客户名称",
            normalize=True,  # 需要规范化
            confidence=0.85,
            enabled=True,
        ),
        "plan_customer": LearningRule(
            source_columns=["计划代码", "客户名称"],
            normalize_customer=True,
            confidence=0.90,
            enabled=True,
        ),
    }

    # 学习触发条件
    min_records_for_learning: int = 10  # 至少处理 10 条记录才触发学习

    # Confidence 阈值
    min_confidence_for_cache: float = 0.80  # 低于此值不写入缓存
```

### 3.4 与现有 Backflow 的关系

| 机制 | 触发时机 | 数据来源 | Confidence |
|------|----------|----------|------------|
| **Backflow (现有)** | Layer 3 命中时 | 源数据中的 existing company_id | 1.00 |
| **Domain Learning (新增)** | Pipeline 处理完成后 | Domain 表中的有效记录 | 0.85-0.95 |
| **EQC API Cache** | EQC 查询成功时 | EQC API 响应 | 1.00 |

**优先级**：Backflow > EQC API Cache > Domain Learning

---

## 4. 实现计划

### 4.1 Story 拆分建议

#### Story 6.9: Enrichment Index Schema Enhancement

**目标**：创建新的 `enrichment_index` 表，支持多优先级查找

**任务**：
- [ ] 创建 Alembic 迁移脚本
- [ ] 迁移现有 `company_name_index` 数据
- [ ] 更新 `CompanyMappingRepository`

#### Story 6.10: Layer 2 Multi-Priority Lookup

**目标**：实现 Layer 2 的 P1-P5 优先级决策流程

**任务**：
- [ ] 修改 `CompanyIdResolver._resolve_via_db_cache()`
- [ ] 实现批量查询优化
- [ ] 更新 `ResolutionStatistics` 记录各优先级命中

#### Story 6.11: Domain Learning Mechanism

**目标**：实现 Domain 数据自学习机制

**任务**：
- [ ] 创建 `DomainLearningService`
- [ ] 实现学习数据提取逻辑
- [ ] 集成到 Pipeline 后处理流程
- [ ] 添加学习统计和日志

#### Story 6.12: Legacy Data Migration to Enrichment Index

**目标**：将 Legacy 数据迁移到新的 `enrichment_index` 表

**任务**：
- [ ] 分析 Legacy 数据结构
- [ ] 创建迁移脚本
- [ ] 执行迁移并验证

### 4.2 依赖关系

```
Story 6.9 (Schema)
    ↓
Story 6.10 (Multi-Priority Lookup) ←── Story 6.12 (Legacy Migration)
    ↓
Story 6.11 (Domain Learning)
```

---

## 5. 数据迁移计划

### 5.1 现有数据迁移

```sql
-- 从 company_name_index 迁移到 enrichment_index
INSERT INTO enterprise.enrichment_index
    (lookup_key, lookup_type, company_id, confidence, source, created_at)
SELECT
    normalized_name as lookup_key,
    'customer_name' as lookup_type,
    company_id,
    confidence,
    source,
    created_at
FROM enterprise.company_name_index
ON CONFLICT (lookup_key, lookup_type) DO NOTHING;
```

### 5.2 Legacy 数据迁移

参考 `golden-dataset-testing-plan.md` 中的 Legacy 数据迁移计划，需要扩展为支持多 lookup_type。

---

## 6. 监控与可观测性

### 6.1 新增指标

| 指标 | 说明 |
|------|------|
| `enrichment_index_total` | 索引总记录数 |
| `enrichment_index_by_type` | 按 lookup_type 分类的记录数 |
| `enrichment_index_by_source` | 按 source 分类的记录数 |
| `domain_learning_records` | Domain 学习新增记录数 |
| `db_cache_hit_by_priority` | 按优先级分类的 DB Cache 命中数 |

### 6.2 决策路径增强

```
# 增强后的决策路径格式
P1:MISS→P2:MISS→P3:MISS→P4:MISS→P5:MISS→DB-P1:MISS→DB-P2:MISS→DB-P3:HIT

# 或简化格式
YAML:MISS→DB:P3:HIT
```

---

## 7. 风险与注意事项

### 7.1 性能考虑

- **批量查询优化**：避免逐行查询，使用批量 IN 查询
- **索引设计**：确保 `(lookup_type, lookup_key)` 索引高效
- **缓存预热**：考虑在 Pipeline 启动时预加载高频映射

### 7.2 数据一致性

- **Confidence 冲突**：同一 lookup_key 可能有多个来源，需要合理处理
- **临时 ID 过滤**：学习时必须排除 `IN_*` 临时 ID
- **数据清洗**：学习前需要验证 company_id 的有效性

### 7.3 向后兼容

- **保留 company_name_index**：迁移期间保留旧表，确保平滑过渡
- **API 兼容**：`CompanyIdResolver` 的外部 API 保持不变

---

## 8. 相关文档

- 技术指南: `docs/guides/company-enrichment-service.md`
- 测试规划: `docs/specific/company-enrichment-service/golden-dataset-testing-plan.md`
- Epic 6 回顾: `docs/sprint-artifacts/retrospective/epic-6-retro-2025-12-08.md`
- Legacy 数据: `reference/archive/db_migration/sqls/enterprise/`

---

## 变更历史

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|----------|------|
| 2025-12-08 | 0.1 | 初始需求规划 | Epic 6 Retrospective |
