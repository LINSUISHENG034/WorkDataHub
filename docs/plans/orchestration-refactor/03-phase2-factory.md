# Phase 2: EnrichmentServiceFactory

> **Priority:** P2 (依赖 Phase 0)
> **Estimated Scope:** Factory 类 + ops 层重构

---

## 目标

将 Enrichment 初始化逻辑从 ops 层提取到 Factory，减少 ~120 行代码。

## TDD 测试清单

### Test 1: Factory 创建 EnrichmentContext

```python
# tests/infrastructure/test_enrichment_factory.py
def test_factory_creates_context():
    from work_data_hub.infrastructure.enrichment.factory import (
        EnrichmentServiceFactory,
        EnrichmentContext,
    )
    ctx = EnrichmentServiceFactory.create(
        eqc_config=EqcLookupConfig.disabled(),
        plan_only=True,
    )
    assert isinstance(ctx, EnrichmentContext)

def test_plan_only_returns_empty_context():
    ctx = EnrichmentServiceFactory.create(
        eqc_config=EqcLookupConfig.enabled(),
        plan_only=True,
    )
    assert ctx.service is None
    assert ctx.connection is None
```

### Test 2: Context cleanup

```python
def test_context_cleanup_closes_connection():
    ctx = EnrichmentServiceFactory.create(...)
    ctx.cleanup()
    # 验证连接已关闭
```

---

## 实现步骤

### Step 1: 创建 Factory

**文件:** `src/work_data_hub/infrastructure/enrichment/factory.py`

### Step 2: 重构 pipeline_ops.py

移除 enrichment 初始化代码，改用 Factory。

---

## 验收标准

- [ ] Factory 可创建 EnrichmentContext
- [ ] `pipeline_ops.py` 减少 ~120 行
- [ ] 现有功能无回归
