"""Job-Config Contract Tests.

TDD Phase: RED→GREEN
验证 CLI run_config 与 JOB_REGISTRY 中 job 所需的 ops 匹配。

这个测试类确保 build_run_config() 生成的配置包含 generic_domain_job 所需的所有 op 配置，
防止 Phase 3/4 重构过程中出现配置不匹配问题。
"""

import argparse
from typing import Set
from unittest.mock import MagicMock, patch

import pytest


class TestJobConfigContract:
    """验证 Job 和 Run Config 之间的契约."""

    EXPECTED_DOMAINS = [
        "annuity_performance",
        "annuity_income",
        "sandbox_trustee_performance",
        "annual_award",
    ]

    # Ops that are always present in run_config regardless of job
    COMMON_OPS = {"discover_files_op", "load_op"}

    # Ops required by generic_domain_job (single-file path)
    GENERIC_JOB_REQUIRED_OPS = {"read_data_op", "process_domain_op_v2"}

    # Ops that may be conditionally present based on domain config
    CONDITIONAL_OPS = {"generic_backfill_refs_op", "gate_after_backfill"}

    def _create_mock_args(
        self,
        domain: str,
        execute: bool = False,
        mode: str = "delete_insert",
    ) -> argparse.Namespace:
        """Create mock CLI args for testing."""
        args = argparse.Namespace()
        args.domain = domain
        args.execute = execute
        args.mode = mode
        args.period = None
        args.file_selection = None
        args.file = None
        args.sample = None
        args.max_files = 1
        args.sheet = None
        args.pk = None
        args.skip_facts = False
        args.session_id = "test-session"
        # EQC-related args
        args.enrich = False
        args.sync_budget = 0
        args.export_unknown = True
        args.use_pipeline = None
        return args

    @pytest.mark.parametrize("domain_name", EXPECTED_DOMAINS)
    def test_run_config_contains_generic_job_ops(self, domain_name: str):
        """验证 run_config 包含 generic_domain_job 所需的 ops."""
        from work_data_hub.cli.etl.config import build_run_config

        args = self._create_mock_args(domain=domain_name)

        with patch("work_data_hub.cli.etl.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                data_sources_config="config/data_sources.yml"
            )
            with patch(
                "work_data_hub.cli.etl.config.get_domain_config_v2"
            ) as mock_domain_cfg:
                # Setup mock domain config
                mock_cfg = MagicMock()
                mock_cfg.output = MagicMock(
                    table=domain_name, schema_name="business", pk=[]
                )
                mock_cfg.requires_backfill = False
                mock_cfg.sheet_names = None
                mock_cfg.sheet_name = "0"
                mock_domain_cfg.return_value = mock_cfg

                config = build_run_config(args, domain_name)

        configured_ops = set(config["ops"].keys())

        # Check required ops are present
        for required_op in self.GENERIC_JOB_REQUIRED_OPS:
            assert required_op in configured_ops, (
                f"Missing required op config '{required_op}' for domain '{domain_name}'. "
                f"Found ops: {configured_ops}"
            )

    @pytest.mark.parametrize("domain_name", EXPECTED_DOMAINS)
    def test_run_config_no_legacy_ops(self, domain_name: str):
        """验证 run_config 不包含旧的 per-domain ops."""
        from work_data_hub.cli.etl.config import build_run_config

        # Legacy ops that should NOT be present
        legacy_ops = {
            "read_excel_op",
            "process_annuity_performance_op",
            "process_annuity_income_op",
            "process_annual_award_op",
            "process_sandbox_trustee_performance_op",
        }

        args = self._create_mock_args(domain=domain_name)

        with patch("work_data_hub.cli.etl.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                data_sources_config="config/data_sources.yml"
            )
            with patch(
                "work_data_hub.cli.etl.config.get_domain_config_v2"
            ) as mock_domain_cfg:
                mock_cfg = MagicMock()
                mock_cfg.output = MagicMock(
                    table=domain_name, schema_name="business", pk=[]
                )
                mock_cfg.requires_backfill = False
                mock_cfg.sheet_names = None
                mock_cfg.sheet_name = "0"
                mock_domain_cfg.return_value = mock_cfg

                config = build_run_config(args, domain_name)

        configured_ops = set(config["ops"].keys())
        found_legacy = configured_ops & legacy_ops

        assert not found_legacy, (
            f"Found legacy op configs {found_legacy} for domain '{domain_name}'. "
            f"These should be replaced with generic ops."
        )

    def test_job_registry_uses_generic_domain_job(self):
        """验证 JOB_REGISTRY 中所有 domain 使用 generic_domain_job."""
        from work_data_hub.orchestration.jobs import (
            JOB_REGISTRY,
            generic_domain_job,
        )

        for domain, entry in JOB_REGISTRY.items():
            assert entry.job == generic_domain_job, (
                f"Domain '{domain}' should use generic_domain_job, "
                f"but uses {entry.job.__name__}"
            )
