# Phase 3: Generic Op + Job

> **Priority:** P3 (依赖 Phase 0, 2)
> **Estimated Scope:** Generic Op + Generic Job 实现

---

## 目标

实现统一的 `process_domain_op` 和 `generic_domain_job`，替代所有 per-domain 实现。

## TDD 测试清单

### Test 1: Generic Op 处理所有 domain

```python
# tests/orchestration/test_generic_op.py
@pytest.mark.parametrize("domain", DOMAIN_SERVICE_REGISTRY.keys())
def test_generic_op_processes_domain(domain, mock_context):
    config = ProcessDomainOpConfig(domain=domain, plan_only=True)
    result = process_domain_op(mock_context, config, sample_rows, ["test.xlsx"])
    assert isinstance(result, list)
```

### Test 2: 无 domain-specific 分支

```python
def test_no_domain_specific_branches():
    source = inspect.getsource(process_domain_op)
    forbidden = ["annuity_performance", "annuity_income"]
    for pattern in forbidden:
        assert pattern not in source
```

---

## 实现步骤

### Step 1: 实现 process_domain_op

**文件:** `src/work_data_hub/orchestration/ops/pipeline_ops.py`

### Step 2: 实现 generic_domain_job

**文件:** `src/work_data_hub/orchestration/jobs.py`

---

## 验收标准

- [ ] Generic Op 可处理所有 registered domains
- [ ] 无 if/elif domain 分支
- [ ] 端到端测试通过
