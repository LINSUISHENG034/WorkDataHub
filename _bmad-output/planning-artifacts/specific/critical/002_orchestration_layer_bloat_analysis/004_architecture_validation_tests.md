# Architecture Validation Tests Specification

> **Status:** Test Specification
> **Created:** 2026-01-12
> **Author:** Murat (Test Architect) via BMAD Party Mode
> **Related:** [003_orchestration_layer_refactoring_design.md](./003_orchestration_layer_refactoring_design.md)

---

## Purpose

本文档定义编排层重构的**架构可行性验证测试**。测试目标是证明：
1. 所有 Domain 服务正确实现 `DomainServiceProtocol`
2. Generic Op 可统一处理所有 Domain
3. Multi-table 加载输出格式与 single-file 一致
4. 新增 Domain 只需注册，无需修改 ops/jobs

---

## Test Categories

### 1. Protocol Compliance Tests

**目标：** 验证所有注册的 domain 服务正确实现接口契约

```python
# tests/architecture/test_protocol_compliance.py

"""
Protocol Compliance Tests - 验证 DomainServiceProtocol 实现

Test Coverage:
- 接口属性存在性检查
- 方法签名验证
- 运行时类型检查
"""

import inspect
from typing import get_type_hints

import pytest

from work_data_hub.domain.protocols import (
    DomainProcessingResult,
    DomainServiceProtocol,
    ProcessingContext,
)
from work_data_hub.domain.registry import DOMAIN_SERVICE_REGISTRY


class TestProtocolCompliance:
    """所有注册 Domain 的 Protocol 合规性测试。"""

    @pytest.fixture
    def all_registered_domains(self) -> list[str]:
        """获取所有已注册的 domain 名称。"""
        return list(DOMAIN_SERVICE_REGISTRY.keys())

    @pytest.mark.parametrize(
        "domain_name",
        list(DOMAIN_SERVICE_REGISTRY.keys()),
        ids=lambda x: f"domain_{x}",
    )
    def test_domain_implements_protocol(self, domain_name: str):
        """验证 domain 服务实现 DomainServiceProtocol。"""
        service = DOMAIN_SERVICE_REGISTRY[domain_name]

        # Runtime protocol check
        assert isinstance(service, DomainServiceProtocol), (
            f"Domain '{domain_name}' does not implement DomainServiceProtocol"
        )

    @pytest.mark.parametrize(
        "domain_name",
        list(DOMAIN_SERVICE_REGISTRY.keys()),
        ids=lambda x: f"domain_{x}_attrs",
    )
    def test_required_attributes_exist(self, domain_name: str):
        """验证必需属性存在。"""
        service = DOMAIN_SERVICE_REGISTRY[domain_name]

        # Required properties
        assert hasattr(service, "domain_name"), "Missing: domain_name"
        assert hasattr(service, "output_table"), "Missing: output_table"
        assert hasattr(service, "process"), "Missing: process method"

        # Optional with defaults
        assert hasattr(service, "requires_enrichment")
        assert hasattr(service, "requires_backfill")

    @pytest.mark.parametrize(
        "domain_name",
        list(DOMAIN_SERVICE_REGISTRY.keys()),
        ids=lambda x: f"domain_{x}_signature",
    )
    def test_process_method_signature(self, domain_name: str):
        """验证 process() 方法签名正确。"""
        service = DOMAIN_SERVICE_REGISTRY[domain_name]

        sig = inspect.signature(service.process)
        params = list(sig.parameters.keys())

        # 必需参数检查
        assert "rows" in params, "process() must accept 'rows' parameter"
        assert "context" in params, "process() must accept 'context' parameter"

    @pytest.mark.parametrize(
        "domain_name",
        list(DOMAIN_SERVICE_REGISTRY.keys()),
        ids=lambda x: f"domain_{x}_return",
    )
    def test_process_returns_correct_type(self, domain_name: str):
        """验证 process() 返回类型正确。"""
        service = DOMAIN_SERVICE_REGISTRY[domain_name]

        # 验证返回类型注解
        hints = get_type_hints(service.process)
        assert "return" in hints, "process() must have return type annotation"
        assert hints["return"] == DomainProcessingResult, (
            f"process() must return DomainProcessingResult, got {hints['return']}"
        )

    def test_domain_name_matches_registry_key(self):
        """验证 domain_name 属性与 registry key 一致。"""
        for key, service in DOMAIN_SERVICE_REGISTRY.items():
            assert service.domain_name == key, (
                f"Registry key '{key}' does not match "
                f"service.domain_name '{service.domain_name}'"
            )

    def test_boolean_properties_return_bool(self):
        """验证布尔属性返回正确类型。"""
        for domain_name, service in DOMAIN_SERVICE_REGISTRY.items():
            assert isinstance(service.requires_enrichment, bool), (
                f"{domain_name}.requires_enrichment must be bool"
            )
            assert isinstance(service.requires_backfill, bool), (
                f"{domain_name}.requires_backfill must be bool"
            )
```

---

### 2. Generic Op Uniformity Tests

**目标：** 验证 `process_domain_op` 能统一处理所有 domain，无需 per-domain 分支

```python
# tests/architecture/test_generic_op_uniformity.py

"""
Generic Op Uniformity Tests - 验证通用 Op 统一处理能力

Test Coverage:
- 所有 domain 通过同一代码路径处理
- 输出格式一致性
- 可选依赖按需注入
"""

import uuid
from typing import Any, Dict, List

import pytest

from work_data_hub.domain.protocols import ProcessingContext
from work_data_hub.domain.registry import DOMAIN_SERVICE_REGISTRY
from work_data_hub.orchestration.ops.pipeline_ops import process_domain_op


class TestGenericOpUniformity:
    """Generic Op 统一处理能力测试。"""

    @pytest.fixture
    def mock_context(self):
        """创建模拟 OpExecutionContext。"""
        # 使用 pytest-dagster 或 mock
        from unittest.mock import MagicMock
        ctx = MagicMock()
        ctx.log = MagicMock()
        return ctx

    @pytest.fixture
    def sample_fixtures(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载各 domain 的样本数据。"""
        return {
            "annuity_performance": [
                {"客户号": "C001", "姓名": "测试客户", "业绩": 10000},
            ],
            "annuity_income": [
                {"客户号": "C001", "收入类型": "年金", "金额": 5000},
            ],
            "sandbox_trustee_performance": [
                {"信托计划": "T001", "受益人": "测试", "份额": 100},
            ],
            "annual_award": [
                {"年度": 2025, "客户号": "C001", "奖项": "金奖"},
            ],
        }

    @pytest.mark.parametrize(
        "domain_name",
        list(DOMAIN_SERVICE_REGISTRY.keys()),
        ids=lambda x: f"generic_op_{x}",
    )
    def test_generic_op_processes_domain(
        self,
        mock_context,
        sample_fixtures,
        domain_name: str,
    ):
        """验证 generic op 可处理指定 domain。"""
        from work_data_hub.orchestration.ops.pipeline_ops import ProcessDomainOpConfig

        config = ProcessDomainOpConfig(
            domain=domain_name,
            plan_only=True,  # 不写数据库
            session_id=str(uuid.uuid4()),
        )
        sample_rows = sample_fixtures.get(domain_name, [{"test": "data"}])

        # 核心验证：单一代码路径，无 if/elif 分支
        result = process_domain_op(
            context=mock_context,
            config=config,
            rows=sample_rows,
            file_paths=["test_file.xlsx"],
        )

        # 输出格式验证
        assert isinstance(result, list), "Result must be a list"
        assert all(isinstance(r, dict) for r in result), "All items must be dicts"

    def test_all_domains_share_single_code_path(self):
        """
        验证所有 domain 使用同一代码路径。

        方法：分析 process_domain_op 源码，确保无 domain-specific 分支
        """
        import ast
        import inspect

        source = inspect.getsource(process_domain_op)
        tree = ast.parse(source)

        # 查找所有 if 语句
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # 检查条件是否包含 domain 比较
                condition_source = ast.unparse(node.test)
                forbidden_patterns = [
                    "domain ==",
                    "domain_name ==",
                    "config.domain ==",
                    "'annuity_performance'",
                    "'annuity_income'",
                ]
                for pattern in forbidden_patterns:
                    assert pattern not in condition_source, (
                        f"Found domain-specific branch: {condition_source}"
                    )

    def test_enrichment_service_injected_only_when_required(
        self,
        mock_context,
        sample_fixtures,
    ):
        """验证 Enrichment 服务仅在 requires_enrichment=True 时注入。"""
        from unittest.mock import patch

        for domain_name, service in DOMAIN_SERVICE_REGISTRY.items():
            with patch.object(
                service, "process", wraps=service.process
            ) as mock_process:
                # ... 执行 process_domain_op ...

                # 检查传入的 context
                if mock_process.called:
                    call_args = mock_process.call_args
                    context: ProcessingContext = call_args[0][1]

                    if service.requires_enrichment:
                        # 应该有 enrichment_service（或在 plan_only 时为 None）
                        pass  # 验证逻辑
                    else:
                        assert context.enrichment_service is None, (
                            f"{domain_name} should not receive enrichment_service"
                        )
```

---

### 3. Multi-Table Loading Consistency Tests

**目标：** 验证多表加载输出格式与单文件加载一致

```python
# tests/architecture/test_multi_table_loading.py

"""
Multi-Table Loading Tests - 验证多数据源加载一致性

Test Coverage:
- 输出类型一致 (List[Dict])
- 必需字段存在
- 值类型正确
"""

import pytest

from work_data_hub.config.domain_sources import DOMAIN_SOURCE_REGISTRY
from work_data_hub.io.reader.multi_table_loader import MultiTableLoader
from work_data_hub.io.reader.excel import ExcelReader


class TestMultiTableLoadingConsistency:
    """多表加载与单文件加载一致性测试。"""

    @pytest.fixture
    def single_file_sample(self) -> list[dict]:
        """单文件加载的样本输出。"""
        return ExcelReader.read_files(
            ["tests/fixtures/annuity_performance_sample.xlsx"]
        )

    @pytest.fixture
    def multi_table_sample(self) -> list[dict]:
        """多表加载的样本输出。"""
        config = DOMAIN_SOURCE_REGISTRY["annual_award"]
        return MultiTableLoader.load(config)

    def test_output_type_consistency(
        self,
        single_file_sample,
        multi_table_sample,
    ):
        """验证输出类型一致。"""
        # 同为 List[Dict]
        assert isinstance(single_file_sample, list)
        assert isinstance(multi_table_sample, list)

        if single_file_sample:
            assert isinstance(single_file_sample[0], dict)
        if multi_table_sample:
            assert isinstance(multi_table_sample[0], dict)

    def test_value_types_are_serializable(self, multi_table_sample):
        """验证值可 JSON 序列化。"""
        import json

        for row in multi_table_sample[:10]:  # 抽样检查
            try:
                json.dumps(row, ensure_ascii=False, default=str)
            except (TypeError, ValueError) as e:
                pytest.fail(f"Row not JSON serializable: {e}")

    def test_multi_table_join_produces_flat_structure(self, multi_table_sample):
        """验证多表 join 后输出扁平结构（无嵌套 dict）。"""
        for row in multi_table_sample[:10]:
            for key, value in row.items():
                assert not isinstance(value, dict), (
                    f"Nested dict found in key '{key}'"
                )
                assert not isinstance(value, list), (
                    f"List found in key '{key}' - should be flattened"
                )

    @pytest.mark.parametrize(
        "source_type",
        ["single_file", "multi_table"],
    )
    def test_source_type_config_valid(self, source_type: str):
        """验证所有配置的 source_type 有对应的加载器。"""
        for domain, config in DOMAIN_SOURCE_REGISTRY.items():
            if config.source_type == source_type:
                if source_type == "single_file":
                    assert hasattr(config, "discovery"), (
                        f"{domain}: single_file requires discovery config"
                    )
                elif source_type == "multi_table":
                    assert hasattr(config, "tables"), (
                        f"{domain}: multi_table requires tables config"
                    )
                    assert len(config.tables) >= 1, (
                        f"{domain}: multi_table needs at least 1 table"
                    )
```

---

### 4. Registry Auto-Discovery Tests

**目标：** 验证新增 domain 只需创建包 + 注册，无需修改 ops/jobs

```python
# tests/architecture/test_registry_auto_discovery.py

"""
Registry Auto-Discovery Tests - 验证扩展机制

Test Coverage:
- 新 domain 注册后立即可用
- generic_domain_job 可执行新 domain
- 无需修改 ops/jobs 代码
"""

import pytest
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List
from unittest.mock import MagicMock

from work_data_hub.domain.protocols import (
    DomainProcessingResult,
    DomainServiceProtocol,
    ProcessingContext,
)
from work_data_hub.domain.registry import (
    DOMAIN_SERVICE_REGISTRY,
    register_domain,
    unregister_domain,
)


@dataclass
class MockDomainService:
    """测试用 Mock Domain 服务。"""

    domain_name: str = "test_new_domain"
    output_table: str = "test_output"
    requires_enrichment: bool = False
    requires_backfill: bool = False

    def process(
        self,
        rows: List[Dict[str, Any]],
        context: ProcessingContext,
    ) -> DomainProcessingResult:
        """Mock 处理逻辑。"""
        return DomainProcessingResult(
            records=[MagicMock() for _ in rows],
            total_input=len(rows),
            total_output=len(rows),
            failed_count=0,
            processing_time_ms=10.0,
        )


@contextmanager
def mock_domain_registration(domain_name: str):
    """临时注册 mock domain 的上下文管理器。"""
    service = MockDomainService(domain_name=domain_name)
    register_domain(domain_name, service)
    try:
        yield service
    finally:
        unregister_domain(domain_name)


class TestRegistryAutoDiscovery:
    """Registry 自动发现与扩展测试。"""

    def test_new_domain_immediately_available(self):
        """验证新 domain 注册后立即可从 registry 获取。"""
        test_domain = "test_instant_domain"

        # 注册前不存在
        assert test_domain not in DOMAIN_SERVICE_REGISTRY

        with mock_domain_registration(test_domain) as service:
            # 注册后立即可用
            assert test_domain in DOMAIN_SERVICE_REGISTRY
            assert DOMAIN_SERVICE_REGISTRY[test_domain] is service

        # 注销后不存在
        assert test_domain not in DOMAIN_SERVICE_REGISTRY

    def test_generic_op_can_process_new_domain(self, mock_context):
        """验证 generic op 可处理新注册的 domain。"""
        from work_data_hub.orchestration.ops.pipeline_ops import (
            ProcessDomainOpConfig,
            process_domain_op,
        )

        test_domain = "test_dynamic_domain"

        with mock_domain_registration(test_domain):
            config = ProcessDomainOpConfig(
                domain=test_domain,
                plan_only=True,
            )

            result = process_domain_op(
                context=mock_context,
                config=config,
                rows=[{"test": "data"}],
                file_paths=["test.xlsx"],
            )

            assert isinstance(result, list)

    def test_no_ops_jobs_modification_needed(self):
        """
        验证添加新 domain 不需要修改 ops/jobs 文件。

        方法：检查 ops/jobs 文件中无 domain-specific imports
        """
        import ast
        from pathlib import Path

        files_to_check = [
            Path("src/work_data_hub/orchestration/ops/pipeline_ops.py"),
            Path("src/work_data_hub/orchestration/jobs.py"),
        ]

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            # 检查是否有 domain-specific imports
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    # 不应直接 import 具体 domain 包
                    forbidden = [
                        "domain.annuity_performance",
                        "domain.annuity_income",
                        "domain.sandbox_trustee",
                        "domain.annual_award",
                    ]
                    for pattern in forbidden:
                        assert pattern not in module, (
                            f"{file_path.name} imports domain-specific module: {module}"
                        )

    def test_registry_type_check_enforced(self):
        """验证 registry 拒绝非 Protocol 实现。"""

        class InvalidService:
            """不实现 Protocol 的类。"""
            pass

        with pytest.raises((TypeError, ValueError)):
            register_domain("invalid", InvalidService())

    @pytest.fixture
    def mock_context(self):
        """Mock OpExecutionContext。"""
        from unittest.mock import MagicMock
        ctx = MagicMock()
        ctx.log = MagicMock()
        return ctx
```

---

## Test Execution Plan

### Phase-wise Test Gates

| Phase | 必须通过的测试 | 阻塞条件 |
|-------|---------------|----------|
| Phase 0 | `TestMultiTableLoadingConsistency` | 任何失败 |
| Phase 1 | 现有测试 + Factory 单元测试 | 任何失败 |
| Phase 2 | `TestProtocolCompliance` | 任何失败 |
| Phase 3 | `TestGenericOpUniformity` + `TestRegistryAutoDiscovery` | 任何失败 |
| Phase 4 | 全量回归测试 | 任何失败 |

### CI Integration

```yaml
# .github/workflows/architecture-tests.yml

name: Architecture Validation

on:
  pull_request:
    paths:
      - 'src/work_data_hub/domain/**'
      - 'src/work_data_hub/orchestration/**'
      - 'config/domain_sources.yaml'

jobs:
  architecture-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Architecture Tests
        run: |
          pytest tests/architecture/ -v --tb=short
```

---

## Success Metrics

| 指标 | 目标 |
|------|------|
| Protocol Compliance | 100% domains pass |
| Generic Op Coverage | 100% domains processable |
| No Domain-Specific Branches | 0 if/elif on domain name in ops/jobs |
| New Domain Test | Mock domain works without code changes |

---

## References

- [003_orchestration_layer_refactoring_design.md](./003_orchestration_layer_refactoring_design.md) — 架构设计
- [002_orchestration_layer_bloat_analysis.md](./002_orchestration_layer_bloat_analysis.md) — 问题分析

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2026-01-12 | Murat (Test Architect) | Initial specification |
