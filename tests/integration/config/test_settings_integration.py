"""
Integration tests for Epic 3 configuration loading with Settings class (Story 3.0).

This module tests the integration between Pydantic configuration validation
and the Settings class from Epic 1 Story 1.4 configuration framework.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch

from src.work_data_hub.config.settings import Settings, get_settings
from src.work_data_hub.config.schema import DataSourcesValidationError


@pytest.fixture
def valid_epic3_config():
    """Sample valid Epic 3 data sources configuration for integration testing."""
    return {
        "schema_version": "1.0",
        "domains": {
            "annuity_performance": {
                "base_path": "reference/monthly/{YYYYMM}/收集数据/数据采集",
                "file_patterns": ["*年金终稿*.xlsx"],
                "exclude_patterns": ["~$*", "*回复*", "*.eml"],
                "sheet_name": "规模明细",
                "version_strategy": "highest_number",
                "fallback": "error"
            }
        }
    }


@pytest.fixture
def invalid_epic3_config_missing_field():
    """Invalid Epic 3 config missing required field."""
    return {
        "schema_version": "1.0",
        "domains": {
            "annuity_performance": {
                "base_path": "reference/monthly/{YYYYMM}/收集数据/数据采集",
                "file_patterns": ["*年金终稿*.xlsx"],
                # Missing sheet_name
                "version_strategy": "highest_number",
                "fallback": "error"
            }
        }
    }


@pytest.fixture
def invalid_epic3_config_invalid_enum():
    """Invalid Epic 3 config with invalid enum value."""
    return {
        "schema_version": "1.0",
        "domains": {
            "annuity_performance": {
                "base_path": "reference/monthly/{YYYYMM}/收集数据/数据采集",
                "file_patterns": ["*年金终稿*.xlsx"],
                "exclude_patterns": ["~$*"],
                "sheet_name": "规模明细",
                "version_strategy": "newest",  # Invalid enum
                "fallback": "error"
            }
        }
    }


class TestSettingsInitialization:
    """Integration tests for Settings class with Epic 3 configuration."""

    def test_settings_loads_valid_config_file(self, tmp_path, valid_epic3_config):
        """AC-5.1: Settings loads and validates data_sources.yml."""
        config_path = tmp_path / "data_sources.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(valid_epic3_config, f, allow_unicode=True)

        # Patch the config file path to our temporary file
        with patch('src.work_data_hub.config.settings.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__str__ = lambda: str(config_path)

            # Mock open function to return our test config
            with patch('builtins.open', side_effect=lambda path, *args, **kwargs: open(config_path, *args, **kwargs)):
                settings = Settings()

        assert settings.data_sources is not None
        assert len(settings.data_sources.domains) == 1
        assert "annuity_performance" in settings.data_sources.domains

        domain_config = settings.data_sources.domains["annuity_performance"]
        assert domain_config.base_path == "reference/monthly/{YYYYMM}/收集数据/数据采集"
        assert domain_config.file_patterns == ["*年金终稿*.xlsx"]
        assert domain_config.sheet_name == "规模明细"
        assert domain_config.version_strategy == "highest_number"

    def test_settings_fails_with_invalid_config_missing_field(self, tmp_path, invalid_epic3_config_missing_field):
        """AC-5.2: Settings initialization fails with invalid config."""
        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_epic3_config_missing_field, f, allow_unicode=True)

        with patch('src.work_data_hub.config.settings.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__str__ = lambda: str(config_path)

            with pytest.raises(Exception) as exc_info:
                Settings()

        assert "sheet_name" in str(exc_info.value) or "validation failed" in str(exc_info.value).lower()

    def test_settings_fails_with_invalid_config_enum(self, tmp_path, invalid_epic3_config_invalid_enum):
        """AC-5.2: Settings initialization fails with invalid enum value."""
        config_path = tmp_path / "invalid_enum.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_epic3_config_invalid_enum, f, allow_unicode=True)

        with patch('src.work_data_hub.config.settings.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__str__ = lambda: str(config_path)

            with pytest.raises(Exception) as exc_info:
                Settings()

        assert "version_strategy" in str(exc_info.value) or "validation failed" in str(exc_info.value).lower()

    def test_settings_fails_with_missing_config_file(self):
        """AC-5.2: Settings initialization fails when config file doesn't exist."""
        with patch('src.work_data_hub.config.settings.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_path.return_value.__str__ = lambda: "/nonexistent/config/data_sources.yml"

            with pytest.raises(FileNotFoundError, match="Configuration file not found"):
                Settings()

    def test_get_settings_singleton_returns_same_instance(self):
        """AC-5.4: get_settings() returns cached instance."""
        # Clear any existing singleton
        import src.work_data_hub.config.settings
        src.work_data_hub.config.settings._settings_instance = None

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_settings_with_multiple_domains(self, tmp_path):
        """AC-5.4: Settings handles configuration with multiple domains."""
        multi_domain_config = {
            "schema_version": "1.0",
            "domains": {
                "annuity_performance": {
                    "base_path": "reference/monthly/{YYYYMM}/收集数据/数据采集",
                    "file_patterns": ["*年金终稿*.xlsx"],
                    "sheet_name": "规模明细"
                },
                "universal_insurance": {
                    "base_path": "reference/monthly/{YYYYMM}/收集数据/业务收集",
                    "file_patterns": ["*万能险*.xlsx"],
                    "sheet_name": "明细数据"
                }
            }
        }

        config_path = tmp_path / "multi_domain.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(multi_domain_config, f, allow_unicode=True)

        with patch('src.work_data_hub.config.settings.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__str__ = lambda: str(config_path)

            with patch('builtins.open', side_effect=lambda path, *args, **kwargs: open(config_path, *args, **kwargs)):
                settings = Settings()

        assert len(settings.data_sources.domains) == 2
        assert "annuity_performance" in settings.data_sources.domains
        assert "universal_insurance" in settings.data_sources.domains

        # Verify each domain has correct configuration
        annuity = settings.data_sources.domains["annuity_performance"]
        universal = settings.data_sources.domains["universal_insurance"]

        assert annuity.sheet_name == "规模明细"
        assert universal.sheet_name == "明细数据"
        assert "*年金终稿*.xlsx" in annuity.file_patterns
        assert "*万能险*.xlsx" in universal.file_patterns

    def test_data_sources_accessible_via_settings(self, tmp_path, valid_epic3_config):
        """AC-5.4: Configuration accessible via settings singleton."""
        config_path = tmp_path / "data_sources.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(valid_epic3_config, f, allow_unicode=True)

        with patch('src.work_data_hub.config.settings.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.__str__ = lambda: str(config_path)

            with patch('builtins.open', side_effect=lambda path, *args, **kwargs: open(config_path, *args, **kwargs)):
                settings = Settings()

        # Test accessing configuration through settings
        assert hasattr(settings, 'data_sources')
        assert settings.data_sources is not None

        # Test domain access
        domain_config = settings.data_sources.domains["annuity_performance"]
        assert domain_config.sheet_name == "规模明细"
        assert "*年金终稿*.xlsx" in domain_config.file_patterns


class TestEndToEndIntegration:
    """End-to-end integration tests for Epic 3 configuration."""

    def test_end_to_end_config_loading_workflow(self, tmp_path):
        """AC-5.5: End-to-end config validation workflow."""
        # This test verifies that configuration system works end-to-end
        # and would prevent runtime errors mentioned in Epic 3 tech spec

        config_data = {
            "schema_version": "1.0",
            "domains": {
                "annuity_performance": {
                    "base_path": "reference/monthly/202411/收集数据/数据采集",
                    "file_patterns": ["*年金终稿*.xlsx"],
                    "exclude_patterns": ["~$*", "*回复*"],
                    "sheet_name": "规模明细",
                    "version_strategy": "highest_number",
                    "fallback": "error"
                }
            }
        }

        config_path = tmp_path / "end_to_end.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True)

        # Test that configuration system can load and validate this without errors
        from src.work_data_hub.config.schema import validate_data_sources_config_v2

        try:
            # This should not raise any errors if system works correctly
            result = validate_data_sources_config_v2(str(config_path))
            assert result is True

            # Test that we can get domain configuration
            from src.work_data_hub.config.schema import get_domain_config_v2
            domain_config = get_domain_config_v2("annuity_performance", str(config_path))

            # Verify configuration matches what we expect
            assert domain_config.base_path == "reference/monthly/202411/收集数据/数据采集"
            assert domain_config.file_patterns == ["*年金终稿*.xlsx"]
            assert domain_config.sheet_name == "规模明细"
            assert domain_config.version_strategy == "highest_number"

        except DataSourcesValidationError as e:
            pytest.fail(f"End-to-end configuration loading failed: {e}")

    def test_real_config_file_validation(self):
        """AC-5.5: Test actual config/data_sources.yml file if it exists."""
        config_path = "config/data_sources.yml"

        if Path(config_path).exists():
            # Test loading real configuration file
            from src.work_data_hub.config.schema import validate_data_sources_config_v2

            try:
                result = validate_data_sources_config_v2(config_path)
                assert result is True

                # Test getting annuity_performance domain
                from src.work_data_hub.config.schema import get_domain_config_v2
                annuity_config = get_domain_config_v2("annuity_performance", config_path)

                assert annuity_config.sheet_name == "规模明细"
                assert annuity_config.version_strategy == "highest_number"
                assert "*年金终稿*.xlsx" in annuity_config.file_patterns

            except DataSourcesValidationError as e:
                pytest.fail(f"Real config file validation failed: {e}")
        else:
            # Config file doesn't exist yet, which is expected before Story 3.0 completion
            pytest.skip("Real config/data_sources.yml not found - expected before Story 3.0 completion")