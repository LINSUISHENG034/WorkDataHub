"""EnrichmentServiceFactory Tests.

TDD Phase: RED
验证 Factory 模式的 enrichment 服务创建。
"""

import pytest


class TestFactoryExists:
    """验证 Factory 模块存在."""

    def test_factory_module_exists(self):
        """factory.py 模块应该存在."""
        from work_data_hub.infrastructure.enrichment.factory import (
            EnrichmentServiceFactory,
        )

        assert EnrichmentServiceFactory is not None

    def test_context_class_exists(self):
        """EnrichmentContext 应该存在."""
        from work_data_hub.infrastructure.enrichment.factory import (
            EnrichmentContext,
        )

        assert EnrichmentContext is not None


class TestFactoryBehavior:
    """验证 Factory 行为."""

    def test_plan_only_returns_empty_context(self):
        """plan_only=True 应返回空 context."""
        from work_data_hub.infrastructure.enrichment.factory import (
            EnrichmentServiceFactory,
        )

        ctx = EnrichmentServiceFactory.create(plan_only=True)
        assert ctx.service is None
        assert ctx.connection is None

    def test_context_has_cleanup_method(self):
        """EnrichmentContext 应该有 cleanup 方法."""
        from work_data_hub.infrastructure.enrichment.factory import (
            EnrichmentContext,
        )

        assert hasattr(EnrichmentContext, "cleanup")
