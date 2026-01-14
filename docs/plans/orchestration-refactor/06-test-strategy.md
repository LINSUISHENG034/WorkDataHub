# Test Strategy - Orchestration Layer Refactor

> **Created:** 2026-01-12
> **Scope:** 架构验证测试 + 回归测试

---

## 测试分类

| 类别 | 目的 | 运行时机 |
|------|------|----------|
| Protocol Compliance | 验证接口实现 | Phase 0 完成后 |
| Generic Op Uniformity | 验证统一处理 | Phase 3 完成后 |
| Multi-Table Loading | 验证数据加载 | Phase 1 完成后 |
| Registry Auto-Discovery | 验证扩展机制 | Phase 3 完成后 |
| Regression | 验证无功能回归 | 每个 Phase |

---

## Phase-wise Test Gates

| Phase | 必须通过的测试 | 阻塞条件 |
|-------|---------------|----------|
| Phase 0 | Protocol Compliance | 任何失败 |
| Phase 1 | Multi-Table Loading | 任何失败 |
| Phase 2 | Factory 单元测试 | 任何失败 |
| Phase 3 | Generic Op Uniformity | 任何失败 |
| Phase 4 | 全量回归 | 任何失败 |

---

## 测试文件结构

```
tests/
├── architecture/
│   ├── test_protocol_compliance.py
│   ├── test_generic_op_uniformity.py
│   ├── test_multi_table_loading.py
│   └── test_registry_auto_discovery.py
├── infrastructure/
│   └── test_enrichment_factory.py
└── orchestration/
    └── test_generic_ops.py
```

---

## 成功指标

| 指标 | 目标 |
|------|------|
| Protocol Compliance | 100% domains pass |
| Generic Op Coverage | 100% domains processable |
| No Domain-Specific Branches | 0 if/elif in ops/jobs |
| Code Reduction | ops/jobs 减少 60%+ |
