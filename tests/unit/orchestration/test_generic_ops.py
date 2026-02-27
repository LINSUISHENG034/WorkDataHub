"""Generic Op Tests.

TDD Phase: RED
验证 Generic Op 使用 Protocol 统一处理所有 domain。
"""

import pytest
from unittest.mock import MagicMock


class TestGenericOpExists:
    """验证 Generic Op 模块存在."""

    def test_generic_op_v2_exists(self):
        """process_domain_op_v2 应该存在."""
        from work_data_hub.orchestration.ops.generic_ops import (
            process_domain_op_v2,
        )

        assert process_domain_op_v2 is not None

    def test_config_class_exists(self):
        """GenericDomainOpConfig 应该存在."""
        from work_data_hub.orchestration.ops.generic_ops import (
            GenericDomainOpConfig,
        )

        assert GenericDomainOpConfig is not None


class TestGenericOpBehavior:
    """验证 Generic Op 行为."""

    EXPECTED_DOMAINS = [
        "annuity_performance",
        "annuity_income",
        "sandbox_trustee_performance",
        "annual_award",
    ]

    @pytest.mark.parametrize("domain_name", EXPECTED_DOMAINS)
    def test_op_uses_protocol_registry(self, domain_name: str):
        """Op 应该从 Protocol Registry 获取服务."""
        from work_data_hub.domain.registry import DOMAIN_SERVICE_REGISTRY

        assert domain_name in DOMAIN_SERVICE_REGISTRY
