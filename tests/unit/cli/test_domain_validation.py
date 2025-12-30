"""Unit tests for domain registry validation (Story 7.4-4)."""

import warnings

import pytest

from work_data_hub.cli.etl.domain_validation import validate_domain_registry


@pytest.mark.unit
class TestValidateDomainRegistry:
    """Tests for validate_domain_registry() function."""

    def test_all_configured_domains_have_jobs_no_warning(self, monkeypatch, capsys):
        """Test case: All configured domains have jobs → no warning."""

        def mock_load_domains():
            return [
                "annuity_performance",
                "annuity_income",
                "sandbox_trustee_performance",
            ]

        monkeypatch.setattr(
            "work_data_hub.cli.etl.domain_validation._load_configured_domains",
            mock_load_domains,
        )

        # JOB_REGISTRY contains these 3 domains
        # No warning should be emitted
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            validate_domain_registry()

            # No UserWarning should have been raised
            user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(user_warnings) == 0

    def test_one_domain_missing_from_job_registry_emits_warning(self, monkeypatch):
        """Test case: One domain missing from JOB_REGISTRY → warning emitted."""

        def mock_load_domains():
            # annuity_plans is NOT in JOB_REGISTRY
            return ["annuity_performance", "annuity_income", "annuity_plans"]

        monkeypatch.setattr(
            "work_data_hub.cli.etl.domain_validation._load_configured_domains",
            mock_load_domains,
        )

        with pytest.warns(UserWarning) as warning_list:
            validate_domain_registry()

        # Should emit exactly one UserWarning
        assert len(warning_list) == 1
        assert issubclass(warning_list[0].category, UserWarning)
        message = str(warning_list[0].message)
        assert "Domains in data_sources.yml without jobs" in message
        assert "annuity_plans" in message

    def test_special_domains_excluded_from_mismatch_detection(self, monkeypatch):
        """Test case: SPECIAL_DOMAINS in config → no warning (excluded)."""

        def mock_load_domains():
            # company_lookup_queue and reference_sync are SPECIAL_DOMAINS
            # They should be excluded from mismatch detection
            return [
                "annuity_performance",
                "company_lookup_queue",
                "reference_sync",
            ]

        monkeypatch.setattr(
            "work_data_hub.cli.etl.domain_validation._load_configured_domains",
            mock_load_domains,
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            validate_domain_registry()

            # No UserWarning should have been raised
            user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(user_warnings) == 0

    def test_config_loading_fail_graceful_handling_no_crash(self, monkeypatch):
        """Test case: Config loading fails → graceful handling (no crash)."""

        def mock_load_domains():
            raise RuntimeError("Config file not found")

        monkeypatch.setattr(
            "work_data_hub.cli.etl.domain_validation._load_configured_domains",
            mock_load_domains,
        )

        # Should not raise exception
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            validate_domain_registry()

            # No warning should be emitted when config fails to load
            user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(user_warnings) == 0

    def test_warning_message_format_and_userwarning_category(self, monkeypatch):
        """Test case: Verify warning message format and UserWarning category."""

        def mock_load_domains():
            return ["missing_domain_1", "missing_domain_2"]

        monkeypatch.setattr(
            "work_data_hub.cli.etl.domain_validation._load_configured_domains",
            mock_load_domains,
        )

        with pytest.warns(UserWarning) as warning_list:
            validate_domain_registry()

        assert len(warning_list) == 1
        warning = warning_list[0]
        assert issubclass(warning.category, UserWarning)

        message = str(warning.message)
        assert "Domains in data_sources.yml without jobs:" in message
        assert "missing_domain_1" in message
        assert "missing_domain_2" in message

    def test_multiple_missing_domains_all_reported(self, monkeypatch):
        """Test case: Multiple missing domains → all reported in warning."""

        def mock_load_domains():
            return [
                "annuity_performance",  # exists in JOB_REGISTRY
                "missing_domain_1",  # missing
                "missing_domain_2",  # missing
                "annuity_income",  # exists in JOB_REGISTRY
                "missing_domain_3",  # missing
            ]

        monkeypatch.setattr(
            "work_data_hub.cli.etl.domain_validation._load_configured_domains",
            mock_load_domains,
        )

        with pytest.warns(UserWarning) as warning_list:
            validate_domain_registry()

        assert len(warning_list) == 1
        message = str(warning_list[0].message)
        # All 3 missing domains should be reported
        assert "missing_domain_1" in message
        assert "missing_domain_2" in message
        assert "missing_domain_3" in message
        # Existing domains should not be in the warning
        assert "annuity_performance" not in message
        assert "annuity_income" not in message
