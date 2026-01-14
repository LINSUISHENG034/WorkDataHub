"""Protocol Compliance Tests - 验证 DomainServiceProtocol 实现.

TDD Phase: RED
这些测试在 protocols.py 创建前会失败，这是预期行为。

Test Coverage:
- Protocol 模块存在性检查
- 接口属性存在性检查
- 方法签名验证
- 运行时类型检查
"""

import inspect
from typing import get_type_hints

import pytest


class TestProtocolExists:
    """验证 Protocol 定义存在."""

    def test_protocol_module_exists(self):
        """protocols.py 模块应该存在且可导入."""
        from work_data_hub.domain.protocols import DomainServiceProtocol

        assert DomainServiceProtocol is not None

    def test_processing_context_exists(self):
        """ProcessingContext 应该存在."""
        from work_data_hub.domain.protocols import ProcessingContext

        assert ProcessingContext is not None

    def test_processing_result_exists(self):
        """DomainProcessingResult 应该存在."""
        from work_data_hub.domain.protocols import DomainProcessingResult

        assert DomainProcessingResult is not None


class TestProtocolAttributes:
    """验证 Protocol 必需属性."""

    def test_protocol_has_domain_name(self):
        """Protocol 应该有 domain_name 属性."""
        from work_data_hub.domain.protocols import DomainServiceProtocol

        assert "domain_name" in dir(DomainServiceProtocol)

    def test_protocol_has_process_method(self):
        """Protocol 应该有 process 方法."""
        from work_data_hub.domain.protocols import DomainServiceProtocol

        assert hasattr(DomainServiceProtocol, "process")


class TestDomainCompliance:
    """验证所有注册 Domain 实现 Protocol."""

    EXPECTED_DOMAINS = [
        "annuity_performance",
        "annuity_income",
        "sandbox_trustee_performance",
        "annual_award",
    ]

    def test_registry_contains_expected_domains(self):
        """Registry 应包含所有预期的 domain."""
        from work_data_hub.domain.registry import DOMAIN_SERVICE_REGISTRY

        for domain in self.EXPECTED_DOMAINS:
            assert domain in DOMAIN_SERVICE_REGISTRY, f"Missing: {domain}"

    @pytest.mark.parametrize("domain_name", EXPECTED_DOMAINS)
    def test_domain_implements_protocol(self, domain_name: str):
        """验证 domain 服务实现 DomainServiceProtocol."""
        from work_data_hub.domain.protocols import DomainServiceProtocol
        from work_data_hub.domain.registry import DOMAIN_SERVICE_REGISTRY

        service = DOMAIN_SERVICE_REGISTRY[domain_name]
        assert isinstance(service, DomainServiceProtocol)
