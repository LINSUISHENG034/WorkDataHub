# Phase 4: Cleanup

> **Priority:** P4 (最后阶段)
> **Estimated Scope:** 删除旧代码 + 回归测试

---

## 目标

删除所有 per-domain ops/jobs，完成重构。

## TDD 测试清单

### Test 1: 旧代码已删除

```python
def test_per_domain_ops_removed():
    source = Path("src/.../pipeline_ops.py").read_text()
    removed = [
        "process_annuity_performance_op",
        "process_annuity_income_op",
    ]
    for fn in removed:
        assert fn not in source
```

### Test 2: 全量回归

```python
def test_all_domains_still_work():
    for domain in DOMAIN_SERVICE_REGISTRY.keys():
        # 端到端测试
        pass
```

---

## 验收标准

- [ ] 删除所有 per-domain ops
- [ ] 删除所有 per-domain jobs
- [ ] `pipeline_ops.py` < 300 行
- [ ] `jobs.py` < 300 行
- [ ] 全量测试通过
