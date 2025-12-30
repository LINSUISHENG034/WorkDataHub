"""
Unit tests for Domain Registry (Story 7.4-3).

Tests for DOMAIN_SERVICE_REGISTRY, ProcessDomainOpConfig, and process_domain_op.
"""

import json
from unittest.mock import ANY, Mock, patch

import pytest
from dagster import build_op_context


class TestDomainServiceRegistry:
    """Test DOMAIN_SERVICE_REGISTRY structure and entries (Story 7.4-3)."""

    def test_registry_has_all_expected_domains(self):
        """Test registry contains all 3 expected domains (AC1)."""
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
        )

        expected_domains = {
            "annuity_performance",
            "annuity_income",
            "sandbox_trustee_performance",
        }

        assert set(DOMAIN_SERVICE_REGISTRY.keys()) == expected_domains

    def test_registry_entries_have_required_attributes(self):
        """Test each registry entry has service_fn, supports_enrichment, domain_name (AC1)."""
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
        )

        for domain_key, entry in DOMAIN_SERVICE_REGISTRY.items():
            assert hasattr(entry, "service_fn"), f"{domain_key} missing service_fn"
            assert callable(entry.service_fn), f"{domain_key} service_fn not callable"

            assert hasattr(entry, "supports_enrichment"), (
                f"{domain_key} missing supports_enrichment"
            )
            assert isinstance(entry.supports_enrichment, bool), (
                f"{domain_key} supports_enrichment not bool"
            )

            assert hasattr(entry, "domain_name"), f"{domain_key} missing domain_name"
            assert isinstance(entry.domain_name, str), (
                f"{domain_key} domain_name not str"
            )

    def test_annuity_performance_enrichment_flag(self):
        """Test annuity_performance supports enrichment (AC4)."""
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
        )

        entry = DOMAIN_SERVICE_REGISTRY["annuity_performance"]
        assert entry.supports_enrichment is True
        assert "Annuity Performance" in entry.domain_name

    def test_annuity_income_no_enrichment(self):
        """Test annuity_income does NOT support enrichment (AC4)."""
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
        )

        entry = DOMAIN_SERVICE_REGISTRY["annuity_income"]
        assert entry.supports_enrichment is False
        assert "Annuity Income" in entry.domain_name

    def test_sandbox_trustee_performance_no_enrichment(self):
        """Test sandbox_trustee_performance does NOT support enrichment (AC4)."""
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
        )

        entry = DOMAIN_SERVICE_REGISTRY["sandbox_trustee_performance"]
        assert entry.supports_enrichment is False
        assert "Trustee Performance" in entry.domain_name


class TestProcessDomainOpConfig:
    """Test ProcessDomainOpConfig validation (Story 7.4-3 Task 3)."""

    def test_config_creation_with_domain(self):
        """Test config creation with required domain field (AC2)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
        )

        config = ProcessDomainOpConfig(domain="annuity_performance")
        assert config.domain == "annuity_performance"
        assert config.enrichment_enabled is False  # Default
        assert config.plan_only is True  # Default

    def test_config_with_enrichment_settings(self):
        """Test config with enrichment fields (AC2, AC4)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
        )

        config = ProcessDomainOpConfig(
            domain="annuity_performance",
            enrichment_enabled=True,
            enrichment_sync_budget=10,
            export_unknown_names=False,
        )

        assert config.domain == "annuity_performance"
        assert config.enrichment_enabled is True
        assert config.enrichment_sync_budget == 10
        assert config.export_unknown_names is False

    def test_sync_budget_validation_negative_raises_error(self):
        """Test negative sync_budget raises ValidationError."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
        )

        with pytest.raises(ValueError, match="Sync budget must be non-negative"):
            ProcessDomainOpConfig(
                domain="annuity_performance", enrichment_sync_budget=-1
            )

    def test_sync_budget_validation_zero_acceptable(self):
        """Test sync_budget=0 is valid (disabled enrichment)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
        )

        config = ProcessDomainOpConfig(
            domain="annuity_income", enrichment_sync_budget=0
        )
        assert config.enrichment_sync_budget == 0


class TestProcessDomainOp:
    """Test process_domain_op generic functionality (Story 7.4-3 AC2)."""

    def test_unknown_domain_raises_value_error(self):
        """Test unknown domain raises ValueError with supported list (AC2)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
            process_domain_op,
        )

        context = build_op_context()
        config = ProcessDomainOpConfig(domain="unknown_domain")
        excel_rows = []
        file_paths = ["test.xlsx"]

        with pytest.raises(ValueError, match="Unknown domain: unknown_domain"):
            process_domain_op(context, config, excel_rows, file_paths)

    def test_sandbox_trustee_performance_minimal_interface(self):
        """Test sandbox_trustee_performance uses minimal interface (AC2)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            DOMAIN_SERVICE_REGISTRY,
            ProcessDomainOpConfig,
            process_domain_op,
        )

        context = build_op_context()
        config = ProcessDomainOpConfig(
            domain="sandbox_trustee_performance", plan_only=True
        )
        excel_rows = [{"年": "2024", "月": "11", "计划代码": "PLAN001"}]
        file_paths = ["test.xlsx"]

        # Save original service_fn and patch registry entry directly
        # (module-level patch doesn't work because registry captures function at import)
        original_entry = DOMAIN_SERVICE_REGISTRY["sandbox_trustee_performance"]
        mock_process = Mock()
        mock_model = Mock()
        mock_model.model_dump.return_value = {"plan_code": "PLAN001"}
        mock_process.return_value = [mock_model]

        try:
            # Replace registry entry with patched service_fn
            from work_data_hub.orchestration.ops.pipeline_ops import DomainServiceEntry

            DOMAIN_SERVICE_REGISTRY["sandbox_trustee_performance"] = DomainServiceEntry(
                service_fn=mock_process,
                supports_enrichment=False,
                domain_name="Sandbox Trustee Performance",
            )

            result = process_domain_op(context, config, excel_rows, file_paths)

            # Verify service was called with minimal interface
            mock_process.assert_called_once_with(excel_rows, data_source="test.xlsx")

            # Verify result is JSON-serializable
            json.dumps(result)
            assert result == [{"plan_code": "PLAN001"}]
        finally:
            # Restore original entry
            DOMAIN_SERVICE_REGISTRY["sandbox_trustee_performance"] = original_entry

    def test_annuity_income_no_enrichment_path(self):
        """Test annuity_income uses sync_lookup_budget, no eqc_config (AC2, AC4)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
            process_domain_op,
        )
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
            DomainServiceEntry,
        )

        context = build_op_context()
        config = ProcessDomainOpConfig(
            domain="annuity_income",
            enrichment_sync_budget=5,
            export_unknown_names=True,
            plan_only=True,
        )
        excel_rows = [{"计划号": "PLAN001"}]
        file_paths = ["test.xlsx"]

        # Patch registry entry directly
        original_entry = DOMAIN_SERVICE_REGISTRY["annuity_income"]
        mock_process = Mock()
        mock_result = Mock()
        mock_result.records = []
        mock_process.return_value = mock_result

        try:
            DOMAIN_SERVICE_REGISTRY["annuity_income"] = DomainServiceEntry(
                service_fn=mock_process,
                supports_enrichment=False,
                domain_name="Annuity Income (收入明细)",
            )

            process_domain_op(context, config, excel_rows, file_paths)

            # Verify service was called with sync_lookup_budget
            mock_process.assert_called_once_with(
                excel_rows,
                data_source="test.xlsx",
                sync_lookup_budget=5,
                export_unknown_names=True,
            )
        finally:
            DOMAIN_SERVICE_REGISTRY["annuity_income"] = original_entry

    def test_annuity_performance_eqc_config_path(self):
        """Test annuity_performance passes eqc_config for enrichment (AC2, AC4)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
            process_domain_op,
        )
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
            DomainServiceEntry,
        )
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig

        context = build_op_context()
        eqc_dict = EqcLookupConfig(enabled=True, sync_budget=10).to_dict()

        config = ProcessDomainOpConfig(
            domain="annuity_performance",
            eqc_lookup_config=eqc_dict,
            enrichment_enabled=False,  # Disabled to avoid DB setup
            plan_only=True,
        )
        excel_rows = [{"计划代码": "PLAN001"}]
        file_paths = ["test.xlsx"]

        # Patch registry entry directly
        original_entry = DOMAIN_SERVICE_REGISTRY["annuity_performance"]
        mock_process = Mock()
        mock_result = Mock()
        mock_result.records = []
        mock_result.enrichment_stats.total_records = 0
        mock_process.return_value = mock_result

        try:
            DOMAIN_SERVICE_REGISTRY["annuity_performance"] = DomainServiceEntry(
                service_fn=mock_process,
                supports_enrichment=True,
                domain_name="Annuity Performance (规模明细)",
            )

            process_domain_op(context, config, excel_rows, file_paths)

            # Verify service was called with eqc_config
            mock_process.assert_called_once()
            call_kwargs = mock_process.call_args.kwargs
            assert "eqc_config" in call_kwargs
            # eqc_config is disabled because plan_only=True and enrichment_enabled=False
            # The code sets eqc_config to disabled in this case per line 708-710
            assert call_kwargs["eqc_config"].enabled is False
        finally:
            DOMAIN_SERVICE_REGISTRY["annuity_performance"] = original_entry

    def test_enrichment_flag_propagation(self):
        """Test enrichment flag propagates from registry entry (AC4)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
            process_domain_op,
        )
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
            DomainServiceEntry,
        )

        context = build_op_context()
        config = ProcessDomainOpConfig(
            domain="annuity_performance",
            enrichment_enabled=True,
            plan_only=True,  # Plan-only to avoid DB setup
        )
        excel_rows = []
        file_paths = ["test.xlsx"]

        # Patch registry entry directly
        original_entry = DOMAIN_SERVICE_REGISTRY["annuity_performance"]
        mock_process = Mock()
        mock_result = Mock()
        mock_result.records = []
        mock_result.enrichment_stats.total_records = 0
        mock_result.enrichment_stats.success_internal = 0
        mock_result.enrichment_stats.success_external = 0
        mock_result.enrichment_stats.pending_lookup = 0
        mock_result.enrichment_stats.temp_assigned = 0
        mock_result.enrichment_stats.failed = 0
        mock_result.enrichment_stats.sync_budget_used = 0
        mock_result.unknown_names_csv = None
        mock_process.return_value = mock_result

        try:
            DOMAIN_SERVICE_REGISTRY["annuity_performance"] = DomainServiceEntry(
                service_fn=mock_process,
                supports_enrichment=True,
                domain_name="Annuity Performance (规模明细)",
            )

            process_domain_op(context, config, excel_rows, file_paths)

            # Verify enrichment_service is None (plan-only mode)
            call_kwargs = mock_process.call_args.kwargs
            assert call_kwargs["enrichment_service"] is None
        finally:
            DOMAIN_SERVICE_REGISTRY["annuity_performance"] = original_entry

    def test_output_normalization_processing_result_with_enrichment(self):
        """Test output normalization for ProcessingResultWithEnrichment (AC2)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
            process_domain_op,
        )
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
            DomainServiceEntry,
        )

        context = build_op_context()
        config = ProcessDomainOpConfig(domain="annuity_performance", plan_only=True)
        excel_rows = [{"计划代码": "PLAN001"}]
        file_paths = ["test.xlsx"]

        # Patch registry entry directly
        original_entry = DOMAIN_SERVICE_REGISTRY["annuity_performance"]
        mock_process = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.model_dump.return_value = {"plan_code": "PLAN001"}
        mock_result.records = [mock_record]
        mock_result.enrichment_stats.total_records = 0
        mock_process.return_value = mock_result

        try:
            DOMAIN_SERVICE_REGISTRY["annuity_performance"] = DomainServiceEntry(
                service_fn=mock_process,
                supports_enrichment=True,
                domain_name="Annuity Performance (规模明细)",
            )

            result = process_domain_op(context, config, excel_rows, file_paths)

            # Should extract .records and serialize to dicts
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["plan_code"] == "PLAN001"

            # Verify JSON-serializable
            json.dumps(result)
        finally:
            DOMAIN_SERVICE_REGISTRY["annuity_performance"] = original_entry

    def test_output_normalization_list_direct(self):
        """Test output normalization for direct model list (AC2)."""
        from work_data_hub.orchestration.ops.domain_processing import (
            ProcessDomainOpConfig,
            process_domain_op,
        )
        from work_data_hub.orchestration.ops.pipeline_ops import (
            DOMAIN_SERVICE_REGISTRY,
            DomainServiceEntry,
        )

        context = build_op_context()
        config = ProcessDomainOpConfig(domain="sandbox_trustee_performance")
        excel_rows = [{"年": "2024"}]
        file_paths = ["test.xlsx"]

        # Patch registry entry directly
        original_entry = DOMAIN_SERVICE_REGISTRY["sandbox_trustee_performance"]
        mock_process = Mock()
        mock_model = Mock()
        mock_model.model_dump.return_value = {"year": "2024"}
        mock_process.return_value = [mock_model]

        try:
            DOMAIN_SERVICE_REGISTRY["sandbox_trustee_performance"] = DomainServiceEntry(
                service_fn=mock_process,
                supports_enrichment=False,
                domain_name="Sandbox Trustee Performance",
            )

            result = process_domain_op(context, config, excel_rows, file_paths)

            # Should serialize models to dicts directly
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["year"] == "2024"

            # Verify JSON-serializable
            json.dumps(result)
        finally:
            DOMAIN_SERVICE_REGISTRY["sandbox_trustee_performance"] = original_entry
