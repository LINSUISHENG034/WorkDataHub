# Phase 0: DomainServiceProtocol + Adapters

> **Priority:** P0 (前置条件)
> **Estimated Scope:** 4 个 domain adapter + 1 个 protocol 定义

---

## 目标

定义统一的 `DomainServiceProtocol`，为所有 domain 实现 adapter，使 Generic Op 成为可能。

## TDD 测试清单

### Test 1: Protocol 定义存在性

```python
# tests/architecture/test_protocol_exists.py
def test_protocol_module_exists():
    from work_data_hub.domain.protocols import DomainServiceProtocol
    assert DomainServiceProtocol is not None

def test_protocol_has_required_attributes():
    from work_data_hub.domain.protocols import DomainServiceProtocol
    assert hasattr(DomainServiceProtocol, 'domain_name')
    assert hasattr(DomainServiceProtocol, 'process')
```

### Test 2: Protocol Compliance（每个 domain）

```python
# tests/architecture/test_protocol_compliance.py
@pytest.mark.parametrize("domain", [
    "annuity_performance",
    "annuity_income",
    "sandbox_trustee_performance",
    "annual_award",
])
def test_domain_implements_protocol(domain):
    service = DOMAIN_SERVICE_REGISTRY[domain]
    assert isinstance(service, DomainServiceProtocol)
```

### Test 3: process() 签名一致性

```python
def test_process_signature_uniform():
    for domain, service in DOMAIN_SERVICE_REGISTRY.items():
        sig = inspect.signature(service.process)
        params = list(sig.parameters.keys())
        assert "rows" in params
        assert "context" in params
```

---

## 实现步骤

### Step 1: 创建 Protocol 定义

**文件:** `src/work_data_hub/domain/protocols.py`

```python
from typing import Protocol, List, Dict, Any
from dataclasses import dataclass

@dataclass
class ProcessingContext:
    data_source: str
    session_id: str
    plan_only: bool = True
    enrichment_service: Any = None
    eqc_config: Any = None

@dataclass
class DomainProcessingResult:
    records: List[Any]
    total_input: int
    total_output: int
    failed_count: int
    processing_time_ms: float

class DomainServiceProtocol(Protocol):
    @property
    def domain_name(self) -> str: ...

    @property
    def requires_enrichment(self) -> bool: ...

    @property
    def requires_backfill(self) -> bool: ...

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult: ...
```

### Step 2: 实现 Adapters（每个 domain 一个）

详见各 domain 的 adapter 实现文件。

---

## 验收标准

- [ ] `protocols.py` 文件存在且可导入
- [ ] 4 个 domain 全部通过 Protocol Compliance 测试
- [ ] `domain_name` 属性与 registry key 一致
- [ ] `process()` 返回 `DomainProcessingResult`
