# Tech-Spec: Epic 6 - Company Enrichment Service

**Created:** 2025-12-06
**Status:** Ready for Development
**Author:** Claude Code (Tech Spec Engineer)

## Overview

### Problem Statement

WorkDataHub 需要为每条业务记录确定稳定、唯一、可追溯的客户主体标识 `company_id`。当前面临的挑战：

1. **数据质量问题**：内部客户名称存在别名、错别字、不同历史阶段的写法
2. **映射分散**：Legacy 系统使用 5 层优先级映射（计划→账户→硬编码→客户名→账户名），分布在 MySQL/MongoDB
3. **外部依赖**：EQC 平台 API 是权威数据源，但存在 Token 过期（30分钟）、rate limit 等限制
4. **无闭环机制**：未命中的公司名称无法自动回填，需要人工干预

### Solution

实现渐进式 Company Enrichment Service，采用多层解析策略：

```
内部映射缓存 → EQC 同步查询(budget限制) → 异步队列回填 → 临时ID兜底
```

核心设计原则：
- **Pipeline 不阻塞**：enrichment 失败不影响主流程，使用临时 ID 兜底
- **渐进式命中率提升**：通过异步回填逐步提高缓存命中率
- **与现有架构有机融合**：复用 `CompanyIdResolver`、`Pipeline` 框架

### Scope

**In Scope:**
- Legacy 5层映射迁移到 `enterprise` schema
- 增强 `CompanyIdResolver` 支持数据库缓存查询
- EQC 同步查询集成（budget 限制）
- 异步回填队列和 Dagster Job
- 可观测性：命中率统计、unknown CSV 导出

**Out of Scope:**
- EQC Token 自动化获取（已有实现，用户手动触发）
- 复杂的置信度评分和人工审核流程（Phase 2）
- 多 Provider 抽象层（YAGNI，当前只有 EQC）

## Context for Development

### Codebase Patterns

**现有架构组件：**

| 组件 | 路径 | 状态 | 说明 |
|------|------|------|------|
| `CompanyIdResolver` | `infrastructure/enrichment/company_id_resolver.py` | ✅ 生产就绪 | 批量解析、向量化、HMAC 临时ID |
| `CompanyEnrichmentService` | `domain/company_enrichment/service.py` | ✅ 框架完成 | 内部映射→EQC→队列→临时ID |
| `EQCClient` | `io/connectors/eqc_client.py` | ✅ 完整实现 | retry、rate limit、error handling |
| `CompanyIdResolutionStep` | `domain/annuity_performance/pipeline_builder.py` | ✅ 已集成 | Pipeline Step 模式 |
| EQC Token 获取 | `io/auth/eqc_auth_handler.py` | ✅ 已实现 | Playwright + 用户手动验证 (迁移自 auth/) |
| `EqcProvider` | `infrastructure/enrichment/eqc_provider.py` | 🔲 Story 6.6 | EQC 适配器，budget 限制，Token 预检测 |

**Pipeline 集成模式：**
```python
# 当前模式 - 保持不变
CompanyIdResolutionStep(
    enrichment_service=enrichment_service,  # 可选
    plan_override_mapping=plan_overrides,
    sync_lookup_budget=sync_lookup_budget,
)
```

**临时 ID 格式：**
- 格式：`IN_<16位Base32>` (HMAC-SHA1)
- 实现：`infrastructure/enrichment/normalizer.py::generate_temp_company_id()`
- 盐值：`WDH_ALIAS_SALT` 环境变量

### Files to Reference

**核心文件：**
- `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` - 批量解析器
- `src/work_data_hub/domain/company_enrichment/service.py` - 服务层
- `src/work_data_hub/domain/company_enrichment/models.py` - 数据模型
- `src/work_data_hub/io/connectors/eqc_client.py` - EQC HTTP 客户端

**映射文件（多文件 YAML 配置）：**
```
data/mappings/
├── company_id_overrides_plan.yml         # 优先级 1: 计划代码 → company_id
├── company_id_overrides_account.yml      # 优先级 2: 账户号 → company_id
├── company_id_overrides_hardcode.yml     # 优先级 3: 硬编码特殊映射
├── company_id_overrides_name.yml         # 优先级 4: 客户名称 → company_id
└── company_id_overrides_account_name.yml # 优先级 5: 年金账户名 → company_id
```

**Legacy 映射源码参考：**
- `legacy/annuity_hub/data_handler/mappings.py` - Legacy 5层映射实现

**参考文档：**
- `docs/supplement/01_company_id_analysis.md` - 完整方案分析
- `docs/epics/epic-6-company-enrichment-service.md` - Epic 定义

### Technical Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 临时 ID 格式 | `IN_<16位Base32>` (HMAC-SHA1) | 与现有实现一致，稳定可追溯 |
| 数据库 Schema | `enterprise` schema | 与业务表隔离，便于管理 |
| Legacy 映射迁移 | 全部迁移 | 保持 Legacy Parity |
| EQC Token 管理 | 用户手动获取 + `.env` 配置 + 预检测 | Token 暂无有效期，统一配置管理 |
| Token 配置方式 | 统一使用 `.env` 文件 | 与 pydantic-settings 一致，便于环境切换 |
| Token 预检测 | Pipeline 启动前验证 | 避免运行后才发现 Token 无效 |
| 集成模式 | 增强 Pipeline Step | 最小改动，保持架构一致 |
| 映射配置架构 | 多文件 YAML + 数据库双层 | YAML 补充数据库缺失，灵活且可版本控制 |
| auth/ 目录迁移 | `auth/` → `io/auth/` | 符合 Clean Architecture 层级规范 |

## Implementation Plan

### Phase 1: 数据库 Schema 和映射迁移

#### Story 6.1: Enterprise Schema 创建

**目标：** 创建 `enterprise` schema 和核心表结构

**Tasks:**
- [ ] 创建 Alembic migration: `create_enterprise_schema`
- [ ] 创建 `enterprise.company_master` 表（主数据）
- [ ] 创建 `enterprise.company_mapping` 表（统一映射）
- [ ] 创建 `enterprise.enrichment_requests` 表（异步队列）
- [ ] 添加必要的索引

**DDL 设计：**
```sql
-- Schema
CREATE SCHEMA IF NOT EXISTS enterprise;

-- 公司主数据表
CREATE TABLE enterprise.company_master (
    company_id VARCHAR(100) PRIMARY KEY,  -- Increased from 50 to 100 for safety
    official_name VARCHAR(255) NOT NULL,
    unified_credit_code VARCHAR(50) UNIQUE,
    aliases TEXT[],
    source VARCHAR(50) NOT NULL DEFAULT 'internal',  -- internal/eqc
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 统一映射表（合并 Legacy 5层）
CREATE TABLE enterprise.company_mapping (
    id SERIAL PRIMARY KEY,
    alias_name VARCHAR(255) NOT NULL,
    canonical_id VARCHAR(100) NOT NULL,   -- Increased from 50 to 100
    match_type VARCHAR(20) NOT NULL,  -- plan/account/hardcode/name/account_name
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    source VARCHAR(50) NOT NULL DEFAULT 'internal',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (alias_name, match_type)
);

CREATE INDEX idx_company_mapping_lookup
ON enterprise.company_mapping (alias_name, priority);

-- 异步回填队列
CREATE TABLE enterprise.enrichment_requests (
    id SERIAL PRIMARY KEY,
    raw_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    temp_id VARCHAR(50),  -- 分配的临时 ID
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending/processing/done/failed
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    resolved_company_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_enrichment_requests_status
ON enterprise.enrichment_requests (status, created_at);

CREATE UNIQUE INDEX idx_enrichment_requests_normalized
ON enterprise.enrichment_requests (normalized_name)
WHERE status IN ('pending', 'processing');
```

**Acceptance Criteria:**
- [ ] Migration 可正向/反向执行
- [ ] 所有表和索引正确创建
- [ ] CI 测试通过

---

#### Story 6.2: Legacy 映射数据迁移

**目标：** 将 Legacy 5层映射迁移到 `enterprise.company_mapping`

**Tasks:**
- [ ] 创建映射导出脚本：从 Legacy MySQL 导出 CSV
- [ ] 创建映射导入 CLI：`--job import_company_mappings`
- [ ] 实现幂等导入逻辑（UPSERT）
- [ ] 验证迁移完整性（条数对比）

**Legacy 映射层级：**
| 优先级 | match_type | Legacy 源 | 说明 |
|--------|------------|-----------|------|
| 1 | plan | `mapping.年金计划` | 年金计划号 → company_id |
| 2 | account | `enterprise.annuity_account_mapping` | 年金账户号 → company_id |
| 3 | hardcode | `COMPANY_ID3_MAPPING` (代码硬编码) | 特殊计划代码 |
| 4 | name | `enterprise.company_id_mapping` | 客户名称 → company_id |
| 5 | account_name | `business.规模明细` | 年金账户名 → company_id |

**导入脚本设计：**
```python
# src/work_data_hub/scripts/import_company_mappings.py
def import_mappings(csv_path: Path, connection) -> ImportResult:
    """
    幂等导入映射数据到 enterprise.company_mapping

    CSV 格式: alias_name,canonical_id,match_type,priority,source
    """
    ...
```

**Acceptance Criteria:**
- [ ] 所有 5 层映射成功导入
- [ ] 导入前后条数一致
- [ ] 重复执行幂等（不产生重复记录）
- [ ] 与 Legacy 解析结果一致（Parity 测试）

---

### Phase 2: CompanyIdResolver 增强

#### Story 6.3: 数据库缓存查询集成

**目标：** 增强 `CompanyIdResolver` 支持从 `enterprise.company_mapping` 查询

**Tasks:**
- [ ] 创建多文件 YAML 加载函数 `load_company_id_overrides()`
- [ ] 创建新的 YAML 映射文件（account, hardcode, name, account_name）
- [ ] 创建 `CompanyMappingRepository` 数据访问层
- [ ] 增强 `CompanyIdResolver.__init__` 接受 `yaml_overrides` 和 `mapping_repository` 参数
- [ ] 实现批量查询优化（单次 SQL 查询多个 alias_name）
- [ ] 保持向后兼容（所有新参数可选）

**代码设计：**

**1. 统一 YAML 加载函数：**
```python
# src/work_data_hub/config/mapping_loader.py

def load_company_id_overrides() -> Dict[str, Dict[str, str]]:
    """
    加载所有 company_id 映射配置（5层优先级）

    Returns:
        {
            "plan": {"FP0001": "614810477", ...},         # 优先级 1
            "account": {"12345678": "601234567", ...},    # 优先级 2
            "hardcode": {"FP0001": "614810477", ...},     # 优先级 3
            "name": {"中国平安": "600866980", ...},        # 优先级 4
            "account_name": {"平安年金账户": "600866980", ...},  # 优先级 5
        }
    """
    mappings_dir = Path(os.getenv("WDH_MAPPINGS_DIR", "data/mappings"))
    result = {}

    mapping_files = {
        "plan": "company_id_overrides_plan.yml",
        "account": "company_id_overrides_account.yml",
        "hardcode": "company_id_overrides_hardcode.yml",
        "name": "company_id_overrides_name.yml",
        "account_name": "company_id_overrides_account_name.yml",
    }

    for match_type, filename in mapping_files.items():
        filepath = mappings_dir / filename
        if filepath.exists():
            result[match_type] = load_yaml(filepath) or {}
        else:
            result[match_type] = {}
            logger.debug(f"YAML mapping file not found: {filename}")

    return result
```

**2. 数据库映射仓库：**
```python
# src/work_data_hub/infrastructure/enrichment/mapping_repository.py
@dataclass
class MatchResult:
    company_id: str
    match_type: str
    priority: int
    source: str

class CompanyMappingRepository:
    """数据库映射查询仓库"""

    def __init__(self, connection):
        self.connection = connection

    def lookup_batch(
        self,
        alias_names: List[str],
        match_types: Optional[List[str]] = None
    ) -> Dict[str, MatchResult]:
        """
        批量查询映射，返回 {alias_name: MatchResult}
        按 priority 排序，返回最高优先级匹配
        """
        ...
```

**3. 增强 CompanyIdResolver：**
```python
# src/work_data_hub/infrastructure/enrichment/company_id_resolver.py
class CompanyIdResolver:
    def __init__(
        self,
        yaml_overrides: Optional[Dict[str, Dict[str, str]]] = None,  # 多文件 YAML
        mapping_repository: Optional[CompanyMappingRepository] = None,  # 数据库
        enrichment_service: Optional["CompanyEnrichmentService"] = None,
    ) -> None:
        # 加载 YAML 配置（如未提供则自动加载）
        self.yaml_overrides = yaml_overrides or load_company_id_overrides()
        self.mapping_repository = mapping_repository
        self.enrichment_service = enrichment_service
        ...

    def resolve_batch(self, df: pd.DataFrame, strategy: ResolutionStrategy) -> ResolutionResult:
        """
        批量解析 company_id，按优先级依次尝试：
        1. YAML 配置（5层优先级）
        2. 数据库缓存
        3. 现有列 passthrough
        4. EQC 同步查询
        5. 临时 ID 生成
        """
        ...
```

**Acceptance Criteria:**
- [ ] 批量查询性能 <100ms/1000条
- [ ] 现有测试全部通过（向后兼容）
- [ ] 新增单元测试覆盖数据库查询路径

---

#### Story 6.3.1: 映射回流机制

**目标：** Pipeline 处理过程中，将新发现的映射关系实时回流到数据库缓存

**背景分析（Legacy 回流机制）：**

Legacy 系统通过实时查询业务表实现映射更新：
| 优先级 | Legacy 源表 | 查询字段 | 说明 |
|--------|-------------|----------|------|
| 2 | `enterprise.annuity_account_mapping` | `年金账户号` → `company_id` | 账户映射 |
| 4 | `enterprise.company_id_mapping` | `company_name` → `company_id` | 客户名称映射 |
| 5 | `business.规模明细` | `年金账户名` → `company_id` | 账户名映射 |

新架构通过**回流机制**替代实时查询，在 Pipeline 处理时将新映射写入缓存。

**回流字段：**
| 回流字段 | match_type | priority | 来源 |
|----------|------------|----------|------|
| `年金账户号` → `company_id` | `account` | 2 | 源数据已有 company_id |
| `客户名称` → `company_id` | `name` | 4 | 源数据已有 company_id |
| `年金账户名` → `company_id` | `account_name` | 5 | 源数据已有 company_id |

**回流条件：**
1. 源数据记录中已有有效的 `company_id`（非空、非临时ID `IN_*`）
2. 该映射关系不在 `enterprise.company_mapping` 中
3. `alias_name` 非空且有效

**Tasks:**
- [ ] 在 `CompanyIdResolver` 中增加 `_backflow_new_mappings()` 方法
- [ ] 在 `CompanyMappingRepository` 中增加 `insert_batch()` 方法（ON CONFLICT DO NOTHING）
- [ ] 增加回流统计到 `ResolutionStatistics`
- [ ] 增加冲突风险日志（当映射已存在但 company_id 不同时警告）

**代码设计：**
```python
# src/work_data_hub/infrastructure/enrichment/company_id_resolver.py

def _backflow_new_mappings(
    self,
    df: pd.DataFrame,
    resolved_mask: pd.Series,
    strategy: ResolutionStrategy,
) -> int:
    """
    将新发现的映射关系回流到数据库缓存

    回流时机：当使用"现有 company_id 列"解析成功时
    回流策略：ON CONFLICT DO NOTHING（保留已有映射）

    Returns:
        回流的映射数量
    """
    if not self.mapping_repository:
        return 0

    new_mappings = []

    for idx in df[resolved_mask].index:
        row = df.loc[idx]
        company_id = str(row[strategy.output_column])

        # 跳过临时ID
        if company_id.startswith("IN_"):
            continue

        # 收集可回流的字段
        backflow_fields = [
            (strategy.account_number_column, "account", 2),
            (strategy.customer_name_column, "name", 4),
            (strategy.account_name_column, "account_name", 5),
        ]

        for column, match_type, priority in backflow_fields:
            if column not in row:
                continue
            alias_value = row[column]
            if pd.isna(alias_value) or not str(alias_value).strip():
                continue

            new_mappings.append({
                "alias_name": str(alias_value).strip(),
                "canonical_id": company_id,
                "match_type": match_type,
                "priority": priority,
                "source": "pipeline_backflow",
            })

    # 批量插入（忽略冲突，记录冲突警告）
    if new_mappings:
        result = self.mapping_repository.insert_batch_with_conflict_check(
            new_mappings
        )

        if result.conflicts:
            logger.warning(
                "Mapping backflow conflicts detected",
                conflicts=result.conflicts[:10],  # 只记录前10个
                total_conflicts=len(result.conflicts),
            )

        logger.info(
            "Mapping backflow completed",
            inserted=result.inserted_count,
            skipped=result.skipped_count,
            conflicts=len(result.conflicts),
        )

        return result.inserted_count

    return 0
```

```python
# src/work_data_hub/infrastructure/enrichment/mapping_repository.py

@dataclass
class InsertBatchResult:
    inserted_count: int
    skipped_count: int
    conflicts: List[Dict[str, Any]]  # 已存在但 company_id 不同的记录

class CompanyMappingRepository:
    def insert_batch_with_conflict_check(
        self,
        mappings: List[Dict[str, Any]],
    ) -> InsertBatchResult:
        """
        批量插入映射，检测并报告冲突

        冲突定义：alias_name + match_type 已存在，但 canonical_id 不同
        处理策略：ON CONFLICT DO NOTHING（保留已有映射）
        """
        # 1. 查询已存在的映射
        existing = self._query_existing(mappings)

        # 2. 检测冲突（已存在但 company_id 不同）
        conflicts = []
        to_insert = []
        for m in mappings:
            key = (m["alias_name"], m["match_type"])
            if key in existing:
                if existing[key] != m["canonical_id"]:
                    conflicts.append({
                        "alias_name": m["alias_name"],
                        "match_type": m["match_type"],
                        "existing_id": existing[key],
                        "new_id": m["canonical_id"],
                    })
            else:
                to_insert.append(m)

        # 3. 批量插入新映射
        inserted_count = self._bulk_insert(to_insert)

        return InsertBatchResult(
            inserted_count=inserted_count,
            skipped_count=len(mappings) - len(to_insert),
            conflicts=conflicts,
        )
```

**Acceptance Criteria:**
- [ ] Pipeline 处理时自动回流新映射
- [ ] 回流使用 ON CONFLICT DO NOTHING 策略
- [ ] 冲突时记录警告日志（alias_name 已存在但 company_id 不同）
- [ ] 回流统计包含在 `ResolutionStatistics` 中
- [ ] 单元测试覆盖回流逻辑

---

#### Story 6.4: EQC 同步查询集成

**目标：** 在 `CompanyIdResolver` 中集成 EQC 同步查询（受 budget 限制）

**Tasks:**
- [ ] 增强 `_resolve_via_enrichment_batch` 使用 `EQCClient`
- [ ] 实现查询结果自动缓存到 `enterprise.company_mapping`
- [ ] 添加 budget 消耗日志和 metrics

**解析优先级（更新后 - 双层架构）：**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Company ID 解析优先级                         │
├─────────────────────────────────────────────────────────────────┤
│  第一层: YAML 配置 (项目固定配置，版本控制，补充数据库缺失)       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ P1: company_id_overrides_plan.yml      (计划代码)          │ │
│  │ P2: company_id_overrides_account.yml   (账户号)            │ │
│  │ P3: company_id_overrides_hardcode.yml  (硬编码特殊)        │ │
│  │ P4: company_id_overrides_name.yml      (客户名称)          │ │
│  │ P5: company_id_overrides_account_name.yml (年金账户名)     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              ↓ 未命中                           │
│  第二层: 数据库缓存 (enterprise.company_mapping)                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ - Legacy 迁移数据 (大量历史映射)                            │ │
│  │ - EQC 查询结果缓存 (动态增长)                               │ │
│  │ - 按 priority 排序查询                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              ↓ 未命中                           │
│  第三层: 现有 company_id 列 (passthrough)                       │
│                              ↓ 未命中                           │
│  第四层: EQC 同步查询 (budget 限制，结果缓存到数据库)            │
│                              ↓ 未命中                           │
│  第五层: 临时 ID 生成 (IN_<16位Base32>) + 入队异步回填           │
└─────────────────────────────────────────────────────────────────┘
```

**YAML vs 数据库职责划分：**
| 数据源 | 职责 | 更新方式 | 适用场景 |
|--------|------|----------|----------|
| YAML 配置 | 核心/稳定映射，补充数据库缺失 | 代码提交，版本控制 | 硬编码特殊情况、紧急修复 |
| 数据库 | 大量历史映射 + 动态缓存 | 运行时更新 | Legacy 迁移、EQC 缓存 |

**Acceptance Criteria:**
- [ ] EQC 查询成功后自动缓存
- [ ] Budget 耗尽后不再调用 EQC
- [ ] EQC 失败不阻塞主流程
- [ ] 日志记录 EQC 调用次数和结果

---

### Phase 3: 异步回填机制

#### Story 6.5: 异步队列入队逻辑

**目标：** 未命中的公司名称自动入队等待异步回填

**Tasks:**
- [ ] 增强 `CompanyIdResolver` 在生成临时 ID 时同时入队
- [ ] 实现去重逻辑（normalized_name 唯一）
- [ ] 记录临时 ID 与队列请求的关联

**代码设计：**
```python
# 在 CompanyIdResolver.resolve_batch 中
if strategy.generate_temp_ids and mask_still_missing.any():
    # 生成临时 ID
    temp_ids = result_df.loc[mask_still_missing, strategy.customer_name_column].apply(
        lambda x: self._generate_temp_id(x)
    )
    result_df.loc[mask_still_missing, strategy.output_column] = temp_ids

    # 入队异步回填（如果 repository 可用）
    if self.mapping_repository:
        self._enqueue_for_enrichment(
            result_df.loc[mask_still_missing, strategy.customer_name_column],
            temp_ids
        )
```

**Acceptance Criteria:**
- [ ] 临时 ID 生成时自动入队
- [ ] 相同 normalized_name 不重复入队
- [ ] 队列状态正确记录

---

#### Story 6.6: EQC API Provider (Sync Lookup with Budget)

**目标：** 验证、重构、集成现有 EQC 代码，创建 `EqcProvider` 适配器

**背景：** 现有 EQC 代码分散在多个位置，需要整合并符合 Clean Architecture：
- `io/connectors/eqc_client.py` - HTTP 客户端 ✅ 保留
- `auth/` - Token 获取 → 迁移到 `io/auth/`
- `domain/company_enrichment/service.py` - 违反 Clean Architecture，需重构

**Tasks:**

**Phase 1: 审核验证**
- [ ] 验证现有 `EQCClient` 功能完整性
- [ ] 审核 `auth/` 目录结构

**Phase 2: Token 管理增强**
- [ ] Token 自动保存功能：`run_get_token(save_to_env=True)`
- [ ] Token 预检测机制：`validate_eqc_token()` + `EqcTokenInvalidError`

**Phase 3: 架构重构**
- [ ] 迁移 `auth/` → `io/auth/`
- [ ] 合并 `EQCAuthSettings` 到 `config/settings.py`

**Phase 4: 创建 EqcProvider 适配器**
- [ ] 创建 `infrastructure/enrichment/eqc_provider.py`
- [ ] 实现 `EnterpriseInfoProvider` 协议
- [ ] 包装 `EQCClient`，添加 budget 限制
- [ ] 集成到 `CompanyIdResolver`

**Token 管理策略：**
```python
# Token 从 .env 文件统一获取
# .env
WDH_EQC_TOKEN=your_token_here

# Token 预检测（Pipeline 启动前）
class EqcProvider:
    def __init__(self, validate_on_init: bool = True):
        if validate_on_init:
            if not validate_eqc_token(self.token):
                raise EqcTokenInvalidError("Token 无效，请运行: uv run python -m work_data_hub.io.auth --capture --save")
```

**Acceptance Criteria:**
- [ ] `auth/` 成功迁移到 `io/auth/`
- [ ] Token 可自动保存到 `.env`
- [ ] Pipeline 启动前 Token 预检测
- [ ] `EqcProvider` 集成到 `CompanyIdResolver`
- [ ] 所有测试通过

---

#### Story 6.7: 异步回填 Dagster Job

**目标：** 创建 Dagster Job 消费队列并调用 EQC 回填

**Tasks:**
- [ ] 创建 `enrich_company_master` Dagster Job
- [ ] 实现批量处理逻辑（每批 50 条）
- [ ] 实现重试和错误处理（最多 3 次）
- [ ] 成功后更新 `company_mapping` 和队列状态

**Job 设计：**
```python
# src/work_data_hub/orchestration/jobs.py
@job
def enrich_company_master():
    """异步回填公司主数据"""
    ...

# CLI 调用
# uv run python -m src.work_data_hub.orchestration.jobs \
#     --execute --job enrich_company_master --debug
```

**处理流程：**
```
1. 查询 pending 状态的请求（LIMIT 50）
2. 更新状态为 processing
3. 调用 EQC 搜索 + 获取详情
4. 成功：
   - 插入/更新 company_master
   - 插入 company_mapping (match_type='eqc')
   - 更新队列状态为 done
5. 失败：
   - 增加 attempts 计数
   - 记录 last_error
   - attempts >= 3 时标记为 failed
```

**Acceptance Criteria:**
- [ ] Job 可通过 CLI 执行
- [ ] 批量处理正确
- [ ] 重试逻辑正确
- [ ] 成功后缓存正确更新

---

### Phase 4: 可观测性

#### Story 6.8: 统计和导出

**目标：** 实现命中率统计和 unknown CSV 导出

**Tasks:**
- [ ] 增强 `ResolutionStatistics` 添加来源分布统计
- [ ] 实现 unknown names CSV 导出（已有基础）
- [ ] 添加队列深度监控
- [ ] 集成到现有 metrics 框架

**统计输出示例：**
```json
{
  "enrichment_stats": {
    "total_rows": 1000,
    "yaml_hits": {
      "plan": 30,
      "account": 10,
      "hardcode": 5,
      "name": 3,
      "account_name": 2,
      "total": 50
    },
    "db_cache_hits": 800,
    "existing_column_hits": 50,
    "eqc_sync_hits": 5,
    "temp_ids_generated": 95,
    "resolution_rate": 0.905,
    "backflow": {
      "inserted": 45,
      "skipped": 5,
      "conflicts": 2
    },
    "queue_depth": 95
  }
}
```

**Acceptance Criteria:**
- [ ] 统计数据准确
- [ ] CSV 导出包含 occurrence_count
- [ ] 日志格式与现有一致

---

## Acceptance Criteria (Epic Level)

### Functional Requirements

- [ ] **FR-1**: Legacy 5层映射 100% 迁移到 `enterprise.company_mapping`
- [ ] **FR-2**: 解析结果与 Legacy 系统一致（Parity 测试通过）
- [ ] **FR-3**: EQC 查询结果自动缓存，下次直接命中
- [ ] **FR-4**: 未命中公司自动入队，异步回填后命中率提升
- [ ] **FR-5**: Pipeline 不因 enrichment 失败而中断

### Non-Functional Requirements

- [ ] **NFR-1**: 批量解析性能 <100ms/1000条（无 EQC 调用）
- [ ] **NFR-2**: EQC 同步调用受 budget 限制（默认 5 次/run）
- [ ] **NFR-3**: 异步回填 Job 可独立执行，支持重试
- [ ] **NFR-4**: 所有敏感信息（Token）不出现在日志中

## Additional Context

### Dependencies

**内部依赖：**
- Epic 1: Database migration framework (Alembic)
- Epic 1: Structured logging
- Story 1.12: Standard domain generic steps

**外部依赖：**
- EQC Platform API（需要有效 Token）
- PostgreSQL（enterprise schema）

### Testing Strategy

**单元测试：**
- `CompanyMappingRepository` 查询逻辑
- `CompanyIdResolver` 各解析路径
- 临时 ID 生成稳定性

**集成测试：**
- 数据库 migration 正向/反向
- EQC 客户端 mock 测试
- 异步 Job 端到端测试

**Parity 测试：**
- 与 Legacy 系统解析结果对比
- 覆盖所有 5 层映射类型

### Risk Mitigation

| 风险 | 缓解措施 |
|------|----------|
| EQC Token 无效 | Pipeline 启动前预检测 + 明确错误提示 + 一键更新命令 |
| Token 配置遗漏 | 统一 `.env` 配置 + 启动时检查 |
| EQC API 不稳定 | retry + rate limit + graceful degradation |
| 映射数据不一致 | Parity 测试 + 导入前备份 |
| 队列积压 | 监控队列深度，告警阈值 10000 |

### Notes

**环境变量（统一配置在 `.env` 文件）：**
```bash
# .env 文件示例

# 必需
WDH_ALIAS_SALT=<production_salt>  # 临时 ID 生成盐值

# EQC 平台配置
WDH_EQC_TOKEN=<token>             # EQC API Token（通过交互式获取）
WDH_EQC_BASE_URL=https://eqc.pingan.com  # EQC API 基础 URL
WDH_EQC_TIMEOUT=5                 # 请求超时（秒）
WDH_EQC_RETRY_MAX=2               # 最大重试次数
WDH_EQC_RATE_LIMIT=60             # 每分钟请求限制

# 可选
WDH_ENRICH_SYNC_BUDGET=5          # 同步 EQC 调用预算
```

**Token 获取命令：**
```bash
# 交互式获取 Token（手动登录）
uv run python -m work_data_hub.io.auth --capture

# 交互式获取并自动保存到 .env
uv run python -m work_data_hub.io.auth --capture --save
```

**CLI 命令：**
```bash
# 映射导入
uv run python -m src.work_data_hub.orchestration.jobs \
    --job import_company_mappings --execute

# 异步回填
uv run python -m src.work_data_hub.orchestration.jobs \
    --job enrich_company_master --execute --debug

# 主流程（带 enrichment）
uv run python -m src.work_data_hub.orchestration.jobs \
    --domain annuity_performance --execute \
    --month 202412 --sync-lookup-budget 5
```

---

**Tech-Spec Complete!**

Saved to: `docs/sprint-artifacts/tech-spec/tech-spec-epic-6-company-enrichment.md`
