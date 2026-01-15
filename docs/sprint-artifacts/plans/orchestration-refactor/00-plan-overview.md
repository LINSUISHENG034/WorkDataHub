# Orchestration Layer Refactor - TDD Implementation Plan

> **Branch:** `feature/orchestration-layer-refactor`
> **Worktree:** `E:/Projects/WorkDataHub-orchestration-refactor`
> **Created:** 2026-01-12
> **Status:** Planning

---

## Executive Summary

本计划基于 `002_orchestration_layer_bloat_analysis` 方案及第一性原理分析的优化建议，采用 TDD 方法实施编排层重构。

### 核心目标

| 目标 | 度量 |
|------|------|
| 消除 per-domain 冗余 | ops/jobs 文件行数减少 60%+ |
| 统一 Domain 服务接口 | 4 个 domain 实现 Protocol |
| 建立 Factory 模式 | Enrichment 初始化代码集中 |
| 配置驱动数据源 | 支持 multi-sheet/multi-table |

### 修正后的优先级（基于第一性原理分析）

```
Phase 0: DomainServiceProtocol 定义 + Adapter 实现
         ↓ (前置条件)
Phase 1: 配置驱动数据源 (可并行)
         ↓
Phase 2: EnrichmentServiceFactory
         ↓
Phase 3: Generic Op + Job
         ↓
Phase 4: 清理旧代码
```

---

## Plan Files Structure

```
docs/plans/orchestration-refactor/
├── 00-plan-overview.md          # 本文件
├── 01-phase0-protocol.md        # Phase 0: Protocol + Adapters
├── 02-phase1-data-source.md     # Phase 1: 配置驱动数据源
├── 03-phase2-factory.md         # Phase 2: EnrichmentServiceFactory
├── 04-phase3-generic-ops.md     # Phase 3: Generic Op + Job
├── 05-phase4-cleanup.md         # Phase 4: 清理旧代码
└── 06-test-strategy.md          # 测试策略总览
```

---

## TDD Workflow

每个 Phase 遵循 Red-Green-Refactor 循环：

```
1. RED:    编写失败的测试（定义期望行为）
2. GREEN:  编写最小代码使测试通过
3. REFACTOR: 重构代码，保持测试通过
```

---

## Success Criteria

| Phase | 验收标准 |
|-------|----------|
| Phase 0 | 所有 domain 通过 Protocol Compliance 测试 |
| Phase 1 | multi-sheet 配置可加载 annual_award 数据 |
| Phase 2 | pipeline_ops.py 减少 ~120 行 |
| Phase 3 | Generic Op 可处理所有 registered domains |
| Phase 4 | 删除所有 per-domain ops/jobs，全量测试通过 |

---

## References

- [002_orchestration_layer_bloat_analysis.md](../../specific/critical/002_orchestration_layer_bloat_analysis/)
- [005_architecture_review_notes.md](../../specific/critical/002_orchestration_layer_bloat_analysis/005_architecture_review_notes.md)
