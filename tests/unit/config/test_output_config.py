"""
Unit tests for domain output configuration helper.

This module tests the get_domain_output_config() function which retrieves
output table configuration from data_sources.yml with fallback logic.
"""

import pytest
import yaml
from unittest.mock import patch
from datetime import datetime

from src.work_data_hub.config.output_config import get_domain_output_config
from src.work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourcesValidationError,
)


@pytest.fixture
def config_with_output(tmp_path):
    """Create a temporary config file with output configuration."""
    config_data = {
        "schema_version": "1.0",
        "domains": {
            "annuity_performance": {
                "base_path": "reference/monthly/{YYYYMM}/数据采集",
                "file_patterns": ["*.xlsx"],
                "sheet_name": "Sheet1",
                "output": {
                    "table": "annuity_performance",
                    "schema_name": "public"
                }
            },
            "annuity_income": {
                "base_path": "reference/monthly/{YYYYMM}/数据采集",
                "file_patterns": ["*.xlsx"],
                "sheet_name": "Sheet1",
                "output": {
                    "table": "annuity_income",
                    "schema_name": "analytics"
                }
            }
        }
    }

    config_path = tmp_path / "data_sources.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True)

    return str(config_path)


@pytest.fixture
def config_without_output(tmp_path):
    """Create a temporary config file without output configuration."""
    config_data = {
        "schema_version": "1.0",
        "domains": {
            "test_domain": {
                "base_path": "reference/monthly/{YYYYMM}/数据采集",
                "file_patterns": ["*.xlsx"],
                "sheet_name": "Sheet1",
                # No output configuration
            }
        }
    }

    config_path = tmp_path / "data_sources.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True)

    return str(config_path)


class TestGetDomainOutputConfig:
    """Test cases for get_domain_output_config() function."""

    def test_successful_config_read_with_validation_mode(self, config_with_output):
        """Test successful configuration reading with Strangler Fig suffix."""
        table_name, schema_name = get_domain_output_config(
            "annuity_performance",
            is_validation_mode=True,
            config_path=config_with_output,
        )

        assert table_name == "annuity_performance_NEW"
        assert schema_name == "public"

    def test_successful_config_read_without_validation_mode(self, config_with_output):
        """Test configuration reading without Strangler Fig suffix."""
        table_name, schema_name = get_domain_output_config(
            "annuity_performance",
            is_validation_mode=False,
            config_path=config_with_output,
        )

        assert table_name == "annuity_performance"
        assert schema_name == "public"

    def test_config_read_with_custom_schema(self, config_with_output):
        """Test configuration reading with non-default schema."""
        table_name, schema_name = get_domain_output_config(
            "annuity_income",
            is_validation_mode=True,
            config_path=config_with_output,
        )

        assert table_name == "annuity_income_NEW"
        assert schema_name == "analytics"

    def test_fallback_when_output_missing(self, config_without_output):
        """Test fallback to temporary table when output config is missing."""
        # Mock datetime to get predictable timestamp
        mock_datetime = datetime(2025, 12, 12, 14, 30, 22)

        with patch('src.work_data_hub.config.output_config.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime

            table_name, schema_name = get_domain_output_config(
                "test_domain",
                is_validation_mode=True,
                config_path=config_without_output,
            )

        assert table_name == "temp_test_domain_20251212"
        assert schema_name == "public"

    def test_fallback_respects_validation_mode(self, config_without_output):
        """Test that fallback tables don't get _NEW suffix (already temp)."""
        mock_datetime = datetime(2025, 12, 12, 14, 30, 22)

        with patch('src.work_data_hub.config.output_config.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime

            # With validation mode
            table_name_val, _ = get_domain_output_config(
                "test_domain",
                is_validation_mode=True,
                config_path=config_without_output,
            )

            # Without validation mode
            table_name_no_val, _ = get_domain_output_config(
                "test_domain",
                is_validation_mode=False,
                config_path=config_without_output,
            )

        # Both should be the same (temp tables don't get _NEW suffix)
        assert table_name_val == "temp_test_domain_20251212"
        assert table_name_no_val == "temp_test_domain_20251212"

    def test_invalid_domain_name_raises_error(self, config_with_output):
        """Test that invalid domain name raises ValueError."""
        with pytest.raises(ValueError, match="Failed to load configuration"):
            get_domain_output_config(
                "nonexistent_domain",
                is_validation_mode=True,
                config_path=config_with_output,
            )

    def test_empty_domain_name_raises_error(self, config_with_output):
        """Test that empty domain name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid domain_name"):
            get_domain_output_config(
                "",
                is_validation_mode=True,
                config_path=config_with_output,
            )

    def test_none_domain_name_raises_error(self, config_with_output):
        """Test that None domain name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid domain_name"):
            get_domain_output_config(
                None,  # type: ignore
                is_validation_mode=True,
                config_path=config_with_output,
            )

    def test_default_validation_mode_is_true(self, config_with_output):
        """Test that default is_validation_mode is True."""
        table_name, _ = get_domain_output_config(
            "annuity_performance",
            config_path=config_with_output,
        )

        # Should have _NEW suffix by default
        assert table_name == "annuity_performance_NEW"
