# 企业客户身份识别服务 (Company Enrichment Service)

> **文档状态**: 已验证 - 与代码同步
> **Epic**: 6 - Company Enrichment Service
> **最后更新**: 2026-01-07
> **Layer 2 增强**: 已实现 - 参见 Story 6.1.1 ~ 6.1.3

---

## 1. 概述

### 1.1 业务背景

在年金业务数据处理中，Excel 源文件中的公司名称存在多种变体形式：
- "公司A"、"A公司"、"公司A有限公司" 可能指向同一家企业
- 不同数据源使用不同的命名约定
- 部分记录可能缺少公司标识信息

**Company Enrichment Service** 的核心目标是将这些变体统一解析为规范的企业 ID (`company_id`)，从而实现：
- 跨域数据关联（年金业绩、年金收入等）
- 客户归属准确统计
- 数据质量提升

### 1.2 设计原则

1. **永不阻塞** - 解析失败不会中断 Pipeline，使用临时 ID 作为兜底
2. **多层解析** - 5 层优先级查找，逐层降级
3. **自学习** - Backflow 机制将成功解析结果回写缓存
4. **可观测** - 完整的统计指标和日志

---

## 2. 核心架构

### 2.1 解析流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Company ID Resolution Flow                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  输入: DataFrame (含 计划代码, 客户名称, 年金账户名, 年金账户号, 公司代码)    │
│                              ↓                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 1: YAML Configuration (3 Priority Levels)                        │ │
│  │   P1: plan_code → company_id (计划代码直接映射)                         │ │
│  │   P2: hardcode → company_id (计划代码+客户名组合映射)                   │ │
│  │   P3: customer_name → company_id (客户名称映射)                         │ │
│  │   Note: account_name/account_number 已移除 (Story 6.1.1)               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              ↓ Not found                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 2: Database Cache (enterprise.enrichment_index)                  │ │
│  │   DB-P1: plan_code → company_id                                        │ │
│  │   DB-P2: customer_name (normalized) → company_id                       │ │
│  │   DB-P3: plan_customer (plan_code + customer_name) → company_id        │ │
│  │   DB-P4: former_name (公司曾用名) → company_id                         │ │
│  │   - 包含历史 EQC API 查询结果、手动映射、Domain 自学习数据              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              ↓ Not found                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 3: Existing company_id Column (Passthrough + Backflow)           │ │
│  │   - 如果源数据已有有效 company_id，直接使用                             │ │
│  │   - Backflow: 将有效映射回写到 DB Cache 供未来使用                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              ↓ Not found                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 4: EQC Sync Lookup (Budget-Limited)                              │ │
│  │   - 调用 EQC 平台 API 查询公司信息                                      │ │
│  │   - 预算限制: 默认 5 次/运行 (防止成本失控)                             │ │
│  │   - 成功结果自动缓存到 DB Cache                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              ↓ Not found / Budget exhausted                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Layer 5: Temporary ID Generation + Async Queue                         │ │
│  │   - 生成临时 ID: IN<16-char-Base32> (HMAC-SHA1 确定性生成)              │ │
│  │   - 同一公司名始终生成相同临时 ID (支持跨运行关联)                       │ │
│  │   - 加入异步队列: enterprise.enrichment_requests                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                              ↓                                               │
│  输出: company_id (真实 ID 或临时 ID IN_*)                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 异步解析循环

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Async Enrichment Loop (Background)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Dagster Schedule (每小时)                                                   │
│       ↓                                                                      │
│  从 enrichment_requests 取 pending 请求 (respects next_retry_at)            │
│       ↓                                                                      │
│  调用 EQC API 解析 (无预算限制)                                              │
│       ↓                                                                      │
│  成功 → 更新 company_name_index → 下次运行命中缓存                           │
│  失败 → 指数退避重试 [1, 5, 15] 分钟 → 3次后标记 failed                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Domain 自学习循环 (已实现)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Domain Learning Loop (Post-Processing)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Domain Pipeline 处理完成 (如 annuity_performance)                           │
│       ↓                                                                      │
│  从 Domain 表中提取有效映射                                                  │
│  (company_id 非空且非临时 ID IN_*)                                           │
│       ↓                                                                      │
│  按 lookup_type 分类整理 (4 种类型):                                          │
│    - plan_code → company_id                                                  │
│    - customer_name (normalized) → company_id                                 │
│    - plan_customer (plan_code + customer_name) → company_id                  │
│    - former_name → company_id                                                │
│       ↓                                                                      │
│  批量写入 enrichment_index                                                   │
│  (ON CONFLICT 更新 confidence 和 hit_count)                                  │
│       ↓                                                                      │
│  下次运行时 Layer 2 命中率提升                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **实现代码**: `src/work_data_hub/infrastructure/enrichment/domain_learning_service.py`

---

## 3. 核心组件

### 3.1 CompanyIdResolver

**位置**: `src/work_data_hub/infrastructure/enrichment/resolver/` (已拆分为子模块)

**核心文件**:

| 文件 | 说明 |
|------|------|
| `core.py` | 主入口，CompanyIdResolver 类定义 |
| `yaml_strategy.py` | Layer 1: YAML 配置查找 |
| `db_strategy.py` | Layer 2: 数据库缓存查找 |
| `eqc_strategy.py` | Layer 4: EQC API 同步查找 |
| `backflow.py` | Layer 3: Backflow 回写机制 |
| `progress.py` | 进度跟踪和日志 |

**职责**: 批量解析 DataFrame 中的公司 ID

### 3.2 ResolutionStrategy

**位置**: `src/work_data_hub/infrastructure/enrichment/types.py`

**职责**: 配置解析行为

```python
@dataclass
class ResolutionStrategy:
    plan_code_column: str = "计划代码"
    customer_name_column: str = "客户名称"
    account_name_column: str = "年金账户名"
    account_number_column: str = "年金账户号"
    company_id_column: str = "公司代码"
    output_column: str = "company_id"
    use_enrichment_service: bool = False
    sync_lookup_budget: int = 0          # EQC API 调用预算
    generate_temp_ids: bool = True       # 是否生成临时 ID
    enable_backflow: bool = True         # 是否启用 Backflow
    enable_async_queue: bool = True      # 是否启用异步队列
```

### 3.3 ResolutionStatistics

**位置**: `src/work_data_hub/infrastructure/enrichment/types.py`

**职责**: 解析统计信息

```python
@dataclass
class ResolutionStatistics:
    total_rows: int = 0
    yaml_hits: Dict[str, int] = field(default_factory=dict)  # 按优先级统计 {plan, account_name, ...}
    db_cache_hits: Dict[str, int] = field(default_factory=dict)  # 按优先级统计 {plan_code, account_name, ...}
    db_cache_hits_total: int = 0
    existing_column_hits: int = 0
    eqc_sync_hits: int = 0
    temp_ids_generated: int = 0
    budget_consumed: int = 0
    budget_remaining: int = 0
    backflow_stats: Dict[str, int] = field(default_factory=dict)
    domain_learning_stats: Dict[str, int] = field(default_factory=dict)  # 自学习统计
    async_queued: int = 0
```

---

## 4. YAML 配置文件

### 4.1 文件位置

```
config/mappings/company_id/
├── company_id_overrides_plan.yml      # P1: 计划代码 → company_id
├── company_id_overrides_hardcode.yml  # P2: 计划代码+客户名组合 → company_id
└── company_id_overrides_name.yml      # P3: 客户名称 → company_id
```

> **Note**: `company_id_overrides_account.yml` 和 `company_id_overrides_account_name.yml` 已在 Story 6.1.1 中移除。

### 4.2 配置格式

**P1 - 计划代码映射** (`company_id_overrides_plan.yml`):
```yaml
FP0001: 614810477
FP0002: 614810477
P0809: 608349737
```

**P4 - 客户名称映射** (`company_id_overrides_name.yml`):
```yaml
公司A有限公司: 614810477
公司B股份有限公司: 608349737
```

**P5 - 计划代码→客户名称→公司** (`company_id_overrides_hardcode.yml`):
```yaml
XNP001:
  客户名称A: 614810477
  客户名称B: 608349737
```

### 4.3 优先级说明

| 优先级 | 字段 | 说明 | 适用场景 |
|--------|------|------|----------|
| P1 | plan_code | 计划代码直接映射 | 一个计划只属于一家公司 |
| P2 | hardcode | 计划代码+客户名组合映射 | 同一计划下多个客户 |
| P3 | customer_name | 客户名称映射 | 通用客户名称匹配 |

> **Note**: `account_name` 和 `account_number` 已在 Story 6.1.1 中移除。

---

## 5. 数据库 Schema

### 5.1 enterprise.enrichment_index (已实现)

**用途**: 多优先级公司映射缓存，支持 4 种 lookup_type

```sql
CREATE TABLE enterprise.enrichment_index (
    id SERIAL PRIMARY KEY,

    -- 查找键
    lookup_key VARCHAR(255) NOT NULL,
    lookup_type VARCHAR(20) NOT NULL,  -- plan_code, customer_name, plan_customer, former_name

    -- 映射结果
    company_id VARCHAR(50) NOT NULL,

    -- 元数据
    confidence DECIMAL(3,2) DEFAULT 1.00,
    source VARCHAR(50) NOT NULL,       -- yaml, eqc_api, manual, backflow, domain_learning
    source_domain VARCHAR(50),         -- 学习来源 domain: annuity_performance, annuity_income, etc.
    source_table VARCHAR(100),         -- 学习来源表

    -- 统计信息
    hit_count INT DEFAULT 0,
    last_hit_at TIMESTAMP,

    -- 审计字段
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE (lookup_key, lookup_type)
);

-- 索引优化
CREATE INDEX ix_enrichment_index_type_key ON enterprise.enrichment_index(lookup_type, lookup_key);
CREATE INDEX ix_enrichment_index_source ON enterprise.enrichment_index(source);
CREATE INDEX ix_enrichment_index_source_domain ON enterprise.enrichment_index(source_domain);
```

**lookup_type 枚举值**:

| lookup_type | 说明 | lookup_key 格式 |
|-------------|------|-----------------|
| `plan_code` | 计划代码 (DB-P1) | 原始值 |
| `customer_name` | 客户名称 (DB-P2) | normalized 值 |
| `plan_customer` | 计划+客户组合 (DB-P3) | `{plan_code}\|{normalized_name}` |
| `former_name` | 公司曾用名 (DB-P4) | normalized 值 |

> **Note**: `account_name` 和 `account_number` 已在 Story 6.1.1 中移除。

**source 枚举值**:

| source | 说明 | confidence |
|--------|------|------------|
| `yaml` | 从 YAML 配置同步 | 1.00 |
| `eqc_api` | EQC API 查询结果 | 1.00 |
| `manual` | 手动添加 | 1.00 |
| `backflow` | Layer 3 Backflow 回写 | 1.00 |
| `domain_learning` | Domain 数据自学习 | 0.85-0.95 |
| `legacy_migration` | Legacy 数据迁移 | 0.90-1.00 |

### 5.2 enterprise.enrichment_requests

**用途**: 异步解析队列

```sql
CREATE TABLE enterprise.enrichment_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    temp_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, done, failed
    attempts INT DEFAULT 0,
    next_retry_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

-- 部分唯一索引：防止重复入队
CREATE UNIQUE INDEX ix_enrichment_requests_pending_name
ON enterprise.enrichment_requests(normalized_name)
WHERE status IN ('pending', 'processing');

-- 高效出队查询
CREATE INDEX ix_enrichment_requests_status_retry
ON enterprise.enrichment_requests(status, next_retry_at);
```

---

## 6. 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `WDH_ALIAS_SALT` | (必填) | 临时 ID 生成的 HMAC 密钥 |
| `WDH_MAPPINGS_DIR` | `data/mappings` | YAML 配置文件目录 |
| `WDH_EQC_TOKEN` | (可选) | EQC 平台 API Token |
| `WDH_EQC_API_BASE_URL` | `https://eqc.pingan.com/` | EQC API 地址 |
| `WDH_ENRICH_ENABLED` | `true` | 是否启用富化服务 |
| `WDH_ASYNC_ENRICHMENT_ENABLED` | `true` | 是否启用异步队列调度 |
| `DATABASE_URL` | (必填) | PostgreSQL 连接字符串 |

---

## 7. 使用示例

### 7.1 基本使用

```python
from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    ResolutionStrategy,
)
import pandas as pd

# 准备数据
df = pd.DataFrame({
    "计划代码": ["FP0001", "XNP001", "UNKNOWN"],
    "客户名称": ["公司A", "公司B", "新公司"],
    "年金账户名": ["账户A", "账户B", "账户C"],
    "年金账户号": ["ACC001", "ACC002", "ACC003"],
    "公司代码": [None, None, None],
})

# 创建解析器
resolver = CompanyIdResolver()

# 配置解析策略
strategy = ResolutionStrategy(
    sync_lookup_budget=5,      # 允许 5 次 EQC API 调用
    enable_backflow=True,      # 启用 Backflow
    enable_async_queue=True,   # 启用异步队列
)

# 执行解析
result_df, stats = resolver.resolve_batch(df, strategy)

# 查看结果
print(result_df["company_id"])
print(stats.to_dict())
```

### 7.2 统计信息解读

```python
{
    "total_rows": 1000,
    "yaml_hits": {"plan": 500, "account_name": 100, "customer_name": 200},
    "yaml_hits_total": 800,
    "db_cache_hits": {
        "plan_code": 30,
        "account_name": 20,
        "account_number": 10,
        "customer_name": 35,
        "plan_customer": 5
    },
    "db_cache_hits_total": 100,
    "existing_column_hits": 50,
    "eqc_sync_hits": 5,
    "temp_ids_generated": 45,
    "budget_consumed": 5,
    "budget_remaining": 0,
    "backflow": {"candidates": 50, "inserted": 45, "skipped": 5},
    "domain_learning": {"extracted": 800, "inserted": 750, "updated": 50},
    "async_queued": 40
}
```

---

## 8. 运维手册

### 8.1 常见操作

**查看队列状态**:
```sql
SELECT status, COUNT(*)
FROM enterprise.enrichment_requests
GROUP BY status;
```

**手动添加映射**:
```sql
INSERT INTO enterprise.company_name_index
(normalized_name, company_id, match_type, confidence, source)
VALUES ('新公司名称', 'COMP123', 'manual', 1.00, 'manual');
```

**重置失败的队列项**:
```sql
UPDATE enterprise.enrichment_requests
SET status = 'pending', attempts = 0, next_retry_at = NOW()
WHERE status = 'failed';
```

**清理已完成的队列项**:
```sql
DELETE FROM enterprise.enrichment_requests
WHERE status = 'done' AND processed_at < NOW() - INTERVAL '30 days';
```

### 8.2 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 大量临时 ID | YAML 配置缺失 | 补充 YAML 映射 |
| EQC API 401 | Token 过期 | 运行 `uv run python -m work_data_hub.io.auth --capture --save` |
| 队列积压 | 异步调度未运行 | 检查 Dagster 调度状态 |
| Backflow 失败 | 数据库连接问题 | 检查 DATABASE_URL |

### 8.3 监控指标

- **cache_hit_rate**: 缓存命中率 (目标 >90%)
- **temp_id_rate**: 临时 ID 生成率 (目标 <10%)
- **queue_depth**: 异步队列深度 (告警阈值 10,000)
- **api_budget_usage**: API 预算使用情况

---

## 9. 测试验证

### 9.1 自动化测试

**执行单元测试**:

```bash
# 运行 enrichment 相关单元测试
uv run pytest tests/unit/infrastructure/enrichment/ -v --tb=short

# 运行 mapping repository 测试
uv run pytest tests/unit/infrastructure/enrichment/test_mapping_repository_enrichment_index.py -v

# 运行 enrichment service 测试
uv run pytest tests/domain/company_enrichment/test_enrichment_service.py -v
```

**测试覆盖范围**:

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_mapping_repository_enrichment_index.py` | LookupType, SourceType, EnrichmentIndexRecord, lookup/insert 方法 |
| `test_enrichment_service.py` | CompanyEnrichmentService, EQC 集成, 缓存机制 |
| `test_enrichment_index_migration.py` | 数据库迁移 |

### 9.2 手动验证

**ETL 验证**:

```bash
# 干运行测试
uv run python -m work_data_hub etl annuity_performance --dry-run

# 查看解析统计
uv run python -m work_data_hub etl annuity_performance --verbose
```

---

## 10. 变更历史

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|----------|------|
| 2026-01-07 | 1.0 | 与代码同步: 简化 YAML/DB 优先级, 更新代码结构, 添加测试命令 | Link |
| 2025-12-08 | 0.1 | 初始框架创建 | Epic 6 Retrospective |

---

## 附录

### A. 相关文档

- Epic 定义: `docs/epics/epic-6-company-enrichment-service.md`
- Story 文件: `docs/sprint-artifacts/stories/6-*.md`
- 架构决策: `docs/architecture/architectural-decisions.md` (AD-002, AD-010)

### B. 代码位置

| 组件 | 路径 |
|------|------|
| CompanyIdResolver (core) | `src/work_data_hub/infrastructure/enrichment/resolver/core.py` |
| YAML Strategy | `src/work_data_hub/infrastructure/enrichment/resolver/yaml_strategy.py` |
| DB Strategy | `src/work_data_hub/infrastructure/enrichment/resolver/db_strategy.py` |
| EQC Strategy | `src/work_data_hub/infrastructure/enrichment/resolver/eqc_strategy.py` |
| Backflow | `src/work_data_hub/infrastructure/enrichment/resolver/backflow.py` |
| Types | `src/work_data_hub/infrastructure/enrichment/types.py` |
| MappingRepository | `src/work_data_hub/infrastructure/enrichment/mapping_repository.py` |
| EnrichmentIndexOps | `src/work_data_hub/infrastructure/enrichment/repository/enrichment_index_ops.py` |
| DomainLearningService | `src/work_data_hub/infrastructure/enrichment/domain_learning_service.py` |
| EqcProvider | `src/work_data_hub/infrastructure/enrichment/eqc_provider.py` |
| LookupQueue | `src/work_data_hub/domain/company_enrichment/lookup_queue.py` |
| Observability | `src/work_data_hub/domain/company_enrichment/observability.py` |
