"""Cleanup Verification Tests (Phase 4).

TDD Phase: RED
验证旧的 per-domain ops 已被移除，只保留 Generic Op。
"""

import ast
import pytest
from pathlib import Path


class TestOldOpsRemoved:
    """验证旧的 per-domain ops 已被移除."""

    def test_process_sandbox_trustee_performance_op_removed(self):
        """process_sandbox_trustee_performance_op 应该已被移除."""
        from work_data_hub.orchestration.ops import pipeline_ops

        assert not hasattr(pipeline_ops, "process_sandbox_trustee_performance_op"), (
            "process_sandbox_trustee_performance_op should be removed"
        )

    def test_process_annuity_performance_op_removed(self):
        """process_annuity_performance_op 应该已被移除."""
        from work_data_hub.orchestration.ops import pipeline_ops

        assert not hasattr(pipeline_ops, "process_annuity_performance_op"), (
            "process_annuity_performance_op should be removed"
        )

    def test_process_annuity_income_op_removed(self):
        """process_annuity_income_op 应该已被移除."""
        from work_data_hub.orchestration.ops import pipeline_ops

        assert not hasattr(pipeline_ops, "process_annuity_income_op"), (
            "process_annuity_income_op should be removed"
        )

    def test_process_annual_award_op_removed(self):
        """process_annual_award_op 应该已被移除."""
        from work_data_hub.orchestration.ops import pipeline_ops

        assert not hasattr(pipeline_ops, "process_annual_award_op"), (
            "process_annual_award_op should be removed"
        )


class TestOldRegistryRemoved:
    """验证旧的 Registry 已被移除."""

    def test_domain_service_entry_removed(self):
        """DomainServiceEntry 应该已被移除."""
        from work_data_hub.orchestration.ops import pipeline_ops

        assert not hasattr(pipeline_ops, "DomainServiceEntry"), (
            "DomainServiceEntry should be removed"
        )

    def test_old_domain_service_registry_removed(self):
        """旧的 DOMAIN_SERVICE_REGISTRY 应该已被移除."""
        from work_data_hub.orchestration.ops import pipeline_ops

        assert not hasattr(pipeline_ops, "DOMAIN_SERVICE_REGISTRY"), (
            "Old DOMAIN_SERVICE_REGISTRY should be removed from pipeline_ops"
        )


class TestProcessingConfigKept:
    """验证 ProcessingConfig 仍然存在."""

    def test_processing_config_exists(self):
        """ProcessingConfig 应该仍然存在."""
        from work_data_hub.orchestration.ops.pipeline_ops import ProcessingConfig

        assert ProcessingConfig is not None


class TestFileSizeReduced:
    """验证文件大小已减少."""

    def test_pipeline_ops_under_300_lines(self):
        """pipeline_ops.py 应该少于 300 行."""
        pipeline_ops_path = Path(__file__).parent.parent.parent / (
            "src/work_data_hub/orchestration/ops/pipeline_ops.py"
        )

        with open(pipeline_ops_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) < 300, (
            f"pipeline_ops.py should be under 300 lines, got {len(lines)}"
        )
