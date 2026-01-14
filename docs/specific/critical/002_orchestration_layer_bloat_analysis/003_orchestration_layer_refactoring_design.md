# Orchestration Layer Refactoring Design

> **Status:** Approved Design
> **Created:** 2026-01-12
> **Authors:** BMAD Party Mode (Winston, Amelia, Barry, John, Murat)
> **Related:** [002_orchestration_layer_bloat_analysis.md](./002_orchestration_layer_bloat_analysis.md)

---

## Executive Summary

本文档提出编排层的统一重构方案，目标是：
1. **消除 per-domain ops/jobs 冗余** — 新增 domain 只需创建领域包 + 注册
2. **统一 Domain 服务接口** — 所有 domain 实现 `DomainServiceProtocol`
3. **增强数据加载层** — 支持多表数据源，消除 `annual_award` 的"例外"
4. **建立 Factory 模式** — 基础设施关注点从编排层剥离

---

## Design Principles

| 原则 | 体现 |
|------|------|
| **Single Responsibility** | Factory 只负责服务组装，Protocol 定义接口契约 |
| **Open/Closed** | 新增 domain 通过注册扩展，无需修改 ops/jobs |
| **Dependency Inversion** | 编排层依赖抽象接口，不依赖具体 domain 实现 |
| **KISS** | 统一接口，消除分支判断 |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Orchestration Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │ generic_domain  │──│ process_domain  │──│ EnrichmentService       │  │
│  │ _job            │  │ _op             │  │ Factory                 │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────────────┘  │
│           │                    │                                         │
│           ▼                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                  DOMAIN_SERVICE_REGISTRY                         │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │    │
│  │  │ annuity_ │ │ annuity_ │ │ sandbox_ │ │ annual_award     │    │    │
│  │  │ perfor.. │ │ income   │ │ trustee  │ │                  │    │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘    │    │
│  │       │            │            │                │               │    │
│  │       ▼            ▼            ▼                ▼               │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │              DomainServiceProtocol                         │  │    │
│  │  │  • domain_name: str                                        │  │    │
│  │  │  • requires_enrichment: bool                               │  │    │
│  │  │  • requires_backfill: bool                                 │  │    │
│  │  │  • process(rows, context) -> DomainProcessingResult        │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          Data Loading Layer                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     read_data_op                                 │    │
│  │  ┌────────────────┐    ┌─────────────────────────────────────┐  │    │
│  │  │ source_type:   │    │ DOMAIN_SOURCE_REGISTRY              │  │    │
│  │  │ single_file    │◄───│ (config/domain_sources.yaml)        │  │    │
│  │  │ multi_table    │    │                                     │  │    │
│  │  └────────────────┘    └─────────────────────────────────────┘  │    │
│  │         │                                                        │    │
│  │         ▼                                                        │    │
│  │  ┌──────────────────────────────────────────────────────────┐   │    │
│  │  │ Unified Output: List[Dict[str, Any]]                      │   │    │
│  │  └──────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. DomainServiceProtocol

**Location:** `src/work_data_hub/domain/protocols.py` (新文件)

```python
"""
Domain Service Protocol - 所有领域服务的统一接口契约。

Design Goals:
- 统一 process() 签名，消除 per-domain ops
- 通过 requires_* 属性声明依赖，编排层按需注入
- 返回标准化结果，便于通用处理
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService


@runtime_checkable
class DomainServiceProtocol(Protocol):
    """所有 Domain 服务必须实现的接口。"""

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """Registry 用于查找的唯一标识符。"""
        ...

    @property
    def requires_enrichment(self) -> bool:
        """是否需要 CompanyEnrichmentService 注入。默认 False。"""
        return False

    @property
    def requires_backfill(self) -> bool:
        """是否需要 ReferenceBackfillService 注入。默认 False。"""
        return False

    @property
    def output_table(self) -> str:
        """目标数据库表名（用于 load_op）。"""
        ...

    @abstractmethod
    def process(
        self,
        rows: List[Dict[str, Any]],
        context: "ProcessingContext",
    ) -> "DomainProcessingResult":
        """
        统一处理入口。

        Args:
            rows: 原始数据行（已由 read_data_op 加载并统一格式）
            context: 运行时上下文（含注入的服务实例）

        Returns:
            标准化处理结果
        """
        ...


@dataclass
class ProcessingContext:
    """运行时上下文 — 由编排层根据 requires_* 属性填充。"""

    data_source: str
    session_id: str
    plan_only: bool = True

    # Optional injected services (populated by EnrichmentServiceFactory)
    enrichment_service: Optional["CompanyEnrichmentService"] = None
    eqc_config: Optional[Any] = None  # EqcLookupConfig

    # Runtime flags
    export_unknown_names: bool = True


@dataclass
class DomainProcessingResult:
    """统一的处理结果结构。"""

    records: List[Any]  # Pydantic models
    total_input: int
    total_output: int
    failed_count: int
    processing_time_ms: float

    # Optional enrichment data
    enrichment_stats: Optional[Dict[str, Any]] = None
    unknown_names_csv: Optional[str] = None

    def to_dicts(self) -> List[Dict[str, Any]]:
        """Convert records to JSON-serializable dicts for loading."""
        return [
            record.model_dump(mode="json", by_alias=True, exclude_none=True)
            for record in self.records
        ]

    @property
    def success_rate(self) -> float:
        """Processing success rate."""
        if self.total_input == 0:
            return 0.0
        return self.total_output / self.total_input
```

---

### 2. Multi-Source Data Loading

**Location:** `config/domain_sources.yaml` (新文件)

```yaml
# Domain Source Configuration
# 定义每个 domain 的数据来源类型和加载策略

annuity_performance:
  source_type: single_file
  discovery:
    path_pattern: "{data_root}/年金业绩/*.xlsx"
    sheet_name: null  # 自动检测

annuity_income:
  source_type: single_file
  discovery:
    path_pattern: "{data_root}/年金收入/*.xlsx"
    sheet_name: null

sandbox_trustee_performance:
  source_type: single_file
  discovery:
    path_pattern: "{data_root}/信托/*.xlsx"
    sheet_name: null

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
  output_format: flattened  # 输出扁平化的 List[Dict]
```

**增强 read_data_op:**

```python
# orchestration/ops/data_ops.py (修改现有文件)

from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY

@op
def read_data_op(
    context: OpExecutionContext,
    config: ReadDataOpConfig,
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    统一数据加载入口 — 根据 domain 配置选择加载策略。

    Supports:
    - single_file: 从 Excel 文件加载
    - multi_table: 从数据库多表加载并合并
    """
    domain = config.domain
    source_config = DOMAIN_SOURCE_REGISTRY.get(domain)

    if source_config is None:
        raise ValueError(f"Unknown domain: {domain}")

    if source_config.source_type == "multi_table":
        return MultiTableLoader.load(source_config)
    else:
        return ExcelReader.read_files(file_paths)


class MultiTableLoader:
    """多表数据加载器。"""

    @classmethod
    def load(cls, config: DomainSourceConfig) -> List[Dict[str, Any]]:
        """
        从多张数据库表加载数据并按配置策略合并。

        Returns:
            统一格式的 List[Dict]，与单文件加载输出格式一致
        """
        tables_data = {}
        for table_config in config.tables:
            df = cls._load_table(table_config)
            tables_data[table_config.role] = df

        # 按配置策略合并
        merged = cls._apply_join_strategy(tables_data, config.join_strategy)

        # 转换为标准格式
        return merged.to_dict(orient="records")
```

---

### 3. EnrichmentServiceFactory

**Location:** `src/work_data_hub/infrastructure/enrichment/factory.py` (新文件)

> 完整代码见 [002_orchestration_layer_bloat_analysis.md](./002_orchestration_layer_bloat_analysis.md) Solution C 部分

**核心职责：**
- 数据库连接验证与创建
- psycopg2 延迟加载
- CompanyEnrichmentService 依赖注入
- 资源生命周期管理 (EnrichmentContext.cleanup())

---

### 4. Generic Domain Op

**Location:** `src/work_data_hub/orchestration/ops/pipeline_ops.py` (修改现有)

```python
@op
def process_domain_op(
    context: OpExecutionContext,
    config: ProcessDomainOpConfig,
    rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    通用领域处理 Op — 替代所有 per-domain ops。

    通过 DOMAIN_SERVICE_REGISTRY 查找服务，统一调用接口。
    """
    domain = config.domain
    file_path = file_paths[0] if file_paths else "unknown"

    # 1. 从 Registry 获取服务
    service = DOMAIN_SERVICE_REGISTRY.get(domain)
    if service is None:
        raise ValueError(f"Domain '{domain}' not registered")

    # 2. 按需创建 Enrichment 上下文
    enrichment_ctx = None
    if service.requires_enrichment:
        eqc_config = EqcLookupConfig.from_dict(config.eqc_lookup_config) \
            if config.eqc_lookup_config else EqcLookupConfig.disabled()
        enrichment_ctx = EnrichmentServiceFactory.create(
            eqc_config=eqc_config,
            plan_only=config.plan_only,
            sync_lookup_budget=config.enrichment_sync_budget,
        )

    try:
        # 3. 构建统一上下文
        processing_context = ProcessingContext(
            data_source=file_path,
            session_id=config.session_id or str(uuid.uuid4()),
            plan_only=config.plan_only,
            enrichment_service=enrichment_ctx.service if enrichment_ctx else None,
            eqc_config=eqc_config if service.requires_enrichment else None,
            export_unknown_names=config.export_unknown_names,
        )

        # 4. 调用统一接口
        result = service.process(rows, processing_context)

        # 5. 日志记录
        context.log.info(
            "domain_processing.completed",
            extra={
                "domain": domain,
                "input_rows": result.total_input,
                "output_records": result.total_output,
                "failed": result.failed_count,
                "success_rate": f"{result.success_rate:.2%}",
            },
        )

        return result.to_dicts()

    finally:
        if enrichment_ctx:
            enrichment_ctx.cleanup()
```

---

### 5. Generic Domain Job

**Location:** `src/work_data_hub/orchestration/jobs.py` (修改现有)

```python
@job(
    resource_defs={"io_manager": fs_io_manager},
    config=GENERIC_DOMAIN_JOB_CONFIG,
)
def generic_domain_job() -> Any:
    """
    通用 ETL Job — 替代所有 per-domain jobs。

    Domain 通过 run_config 指定：
    {
        "ops": {
            "process_domain_op": {
                "config": {"domain": "annuity_performance", ...}
            }
        }
    }
    """
    # Step 1: File Discovery
    discovered_paths = discover_files_op()

    # Step 2: Data Loading (支持 single_file 和 multi_table)
    rows = read_data_op(discovered_paths)

    # Step 3: Domain Processing (通用接口)
    processed_data = process_domain_op(rows, discovered_paths)

    # Step 4: Reference Backfill (按需)
    backfill_result = generic_backfill_refs_op(processed_data)

    # Step 5: Gate Check
    gated_rows = gate_after_backfill(processed_data, backfill_result)

    # Step 6: Load to Database
    load_op(gated_rows)
```

---

## Implementation Phases

### Phase 0: Multi-Source Data Loading

| 变更文件 | 类型 | 描述 |
|----------|------|------|
| `config/domain_sources.yaml` | NEW | Domain 数据源配置 |
| `src/work_data_hub/config/domain_sources.py` | NEW | 配置加载逻辑 |
| `src/work_data_hub/io/reader/multi_table_loader.py` | NEW | 多表加载器 |
| `src/work_data_hub/orchestration/ops/data_ops.py` | MODIFY | 增强 read_data_op |

**验收标准：**
- `annual_award` 通过 multi_table 配置加载，输出 `List[Dict]`
- 现有 single_file domains 行为不变

---

### Phase 1: EnrichmentServiceFactory

| 变更文件 | 类型 | 描述 |
|----------|------|------|
| `src/work_data_hub/infrastructure/enrichment/factory.py` | NEW | Factory 实现 |
| `src/work_data_hub/orchestration/ops/pipeline_ops.py` | MODIFY | 使用 Factory |

**验收标准：**
- `pipeline_ops.py` 减少 ~120 行
- Enrichment 初始化逻辑集中到 Factory
- 现有功能无回归

---

### Phase 2: DomainServiceProtocol + Wrappers

| 变更文件 | 类型 | 描述 |
|----------|------|------|
| `src/work_data_hub/domain/protocols.py` | NEW | Protocol 定义 |
| `src/work_data_hub/domain/annuity_performance/service.py` | MODIFY | 实现 Protocol |
| `src/work_data_hub/domain/annuity_income/service.py` | MODIFY | 实现 Protocol |
| `src/work_data_hub/domain/sandbox_trustee_performance/service.py` | MODIFY | 实现 Protocol |
| `src/work_data_hub/domain/annual_award/service.py` | MODIFY | 实现 Protocol |
| `src/work_data_hub/domain/registry.py` | MODIFY | 注册服务实例 |

**验收标准：**
- 所有 4 个 domain 实现 `DomainServiceProtocol`
- Protocol compliance 测试通过
- 现有功能无回归

---

### Phase 3: Generic Ops/Jobs

| 变更文件 | 类型 | 描述 |
|----------|------|------|
| `src/work_data_hub/orchestration/ops/pipeline_ops.py` | MODIFY | 实现 process_domain_op |
| `src/work_data_hub/orchestration/jobs.py` | MODIFY | 实现 generic_domain_job |
| `src/work_data_hub/cli/main.py` | MODIFY | CLI 使用 generic job |

**验收标准：**
- `process_domain_op` 可处理所有 registered domains
- `generic_domain_job` 通过 config 指定 domain 运行
- 端到端测试通过

---

### Phase 4: Cleanup

| 变更文件 | 类型 | 描述 |
|----------|------|------|
| `src/work_data_hub/orchestration/ops/pipeline_ops.py` | MODIFY | 删除 per-domain ops |
| `src/work_data_hub/orchestration/jobs.py` | MODIFY | 删除 per-domain jobs |

**验收标准：**
- 删除 `process_annuity_performance_op`, `process_annuity_income_op`, etc.
- 删除 `annuity_performance_job`, `annuity_income_job`, etc.
- 所有测试通过
- `pipeline_ops.py` < 300 行, `jobs.py` < 300 行

---

## Expected Outcomes

| 指标 | Before | After | 改善 |
|------|--------|-------|------|
| `pipeline_ops.py` 行数 | 604 | ~200 | **-67%** |
| `jobs.py` 行数 | 687 | ~200 | **-71%** |
| 新增 domain 需修改文件数 | 3 | 1 | **-67%** |
| Per-domain ops 数量 | 4 | 0 | **-100%** |
| Per-domain jobs 数量 | 4 | 0 | **-100%** |

---

## References

- [002_orchestration_layer_bloat_analysis.md](./002_orchestration_layer_bloat_analysis.md) — 问题分析
- [004_architecture_validation_tests.md](./004_architecture_validation_tests.md) — 测试规范

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2026-01-12 | BMAD Party Mode | Initial design based on discussion |
