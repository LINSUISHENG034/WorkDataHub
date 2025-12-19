"""
Unit tests for Epic 3 data source configuration schema validation (Story 3.0).

This module tests the V2 schema validation functionality for data_sources.yml
configuration, including validation of domain configurations, security checks,
and error handling.
"""

import pytest
import yaml
from pathlib import Path
from pydantic import ValidationError

from src.work_data_hub.infrastructure.settings.data_source_schema import (
    DomainConfigV2,
    DataSourceConfigV2,
    OutputConfig,
    DataSourcesValidationError,
    validate_data_sources_config_v2,
    get_domain_config_v2,
)


@pytest.fixture
def valid_domain_config_v2():
    """Sample valid Epic 3 domain configuration."""
    return {
        "base_path": "reference/monthly/{YYYYMM}/收集数据/数据采集",
        "file_patterns": ["*年金终稿*.xlsx"],
        "exclude_patterns": ["~$*", "*回复*", "*.eml"],
        "sheet_name": "规模明细",
        "version_strategy": "highest_number",
        "fallback": "error",
    }


@pytest.fixture
def valid_data_source_config_v2(valid_domain_config_v2):
    """Sample valid complete Epic 3 data sources configuration."""
    return {
        "schema_version": "1.0",
        "domains": {
            "annuity_performance": valid_domain_config_v2,
            "universal_insurance": {
                "base_path": "reference/monthly/{YYYYMM}/收集数据/业务收集",
                "file_patterns": ["*万能险*.xlsx"],
                "sheet_name": "明细数据",
            },
        },
    }


@pytest.fixture
def config_file_v2(tmp_path, valid_data_source_config_v2):
    """Create a temporary Epic 3 data sources config file for testing."""
    config_path = tmp_path / "test_data_sources_v2.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(valid_data_source_config_v2, f, allow_unicode=True)
    return str(config_path)


class TestDomainConfigV2:
    """Test cases for Epic 3 DomainConfigV2 validation."""

    def test_valid_config_with_all_fields(self, valid_domain_config_v2):
        """AC-1: Valid configuration passes validation."""
        config = DomainConfigV2(**valid_domain_config_v2)

        assert config.base_path == "reference/monthly/{YYYYMM}/收集数据/数据采集"
        assert config.file_patterns == ["*年金终稿*.xlsx"]
        assert config.exclude_patterns == ["~$*", "*回复*", "*.eml"]
        assert config.sheet_name == "规模明细"
        assert config.version_strategy == "highest_number"
        assert config.fallback == "error"

    def test_valid_config_with_defaults(self):
        """AC-1: Optional fields use defaults."""
        config = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/数据采集",
            file_patterns=["*.xlsx"],
            sheet_name="Sheet1",
            # version_strategy and fallback use defaults
            # exclude_patterns uses default empty list
        )

        assert config.version_strategy == "highest_number"
        assert config.fallback == "error"
        assert config.exclude_patterns == []
        assert config.output is None

    def test_valid_config_with_output(self):
        """Test configuration with output destination."""
        config = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/数据采集",
            file_patterns=["*.xlsx"],
            sheet_name="Sheet1",
            output={
                "table": "target_table",
                "schema_name": "target_schema"
            }
        )

        assert config.output is not None
        assert config.output.table == "target_table"
        assert config.output.schema_name == "target_schema"

    def test_missing_required_field_raises_error(self):
        """AC-2: Missing required field raises ValidationError."""
        # Missing sheet_name
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                base_path="reference/monthly/{YYYYMM}/数据采集",
                file_patterns=["*.xlsx"],
            )

        assert "sheet_name" in str(exc_info.value)
        assert "Field required" in str(exc_info.value)

    def test_missing_base_path_raises_error(self):
        """AC-2: Missing base_path raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                file_patterns=["*.xlsx"],
                sheet_name="Sheet1",
            )

        assert "base_path" in str(exc_info.value)

    def test_missing_file_patterns_raises_error(self):
        """AC-2: Missing file_patterns raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                base_path="reference/monthly/{YYYYMM}/数据采集",
                sheet_name="Sheet1",
            )

        assert "file_patterns" in str(exc_info.value)

    def test_invalid_version_strategy_raises_error(self):
        """AC-3: Invalid enum value raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                base_path="reference/monthly/{YYYYMM}/数据采集",
                file_patterns=["*.xlsx"],
                sheet_name="Sheet1",
                version_strategy="newest",  # Invalid, not in enum
            )

        assert "version_strategy" in str(exc_info.value)
        # Pydantic v2 error message includes valid options
        assert "highest_number" in str(exc_info.value) or "Input should be" in str(
            exc_info.value
        )

    def test_invalid_fallback_raises_error(self):
        """AC-3: Invalid fallback enum value raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                base_path="reference/monthly/{YYYYMM}/数据采集",
                file_patterns=["*.xlsx"],
                sheet_name="Sheet1",
                fallback="ignore",  # Invalid
            )

        assert "fallback" in str(exc_info.value)

    def test_invalid_file_patterns_type_raises_error(self):
        """AC-1: Invalid field type (string instead of list) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                base_path="reference/monthly/{YYYYMM}/数据采集",
                file_patterns="*.xlsx",  # Should be list, not string
                sheet_name="Sheet1",
            )

        assert "file_patterns" in str(exc_info.value)

    def test_template_variables_allowed_in_base_path(self):
        """AC-5: Template variables allowed in paths."""
        config = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/收集数据/{YYYY}/{MM}",
            file_patterns=["*.xlsx"],
            sheet_name="Sheet1",
        )

        # Should not raise, template variables preserved
        assert "{YYYYMM}" in config.base_path
        assert "{YYYY}" in config.base_path
        assert "{MM}" in config.base_path

    def test_directory_traversal_in_base_path_raises_error(self):
        """AC-1: Security validation prevents directory traversal."""
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                base_path="reference/monthly/../../etc/passwd",
                file_patterns=["*.xlsx"],
                sheet_name="Sheet1",
            )

        assert "directory traversal" in str(exc_info.value).lower()

    def test_empty_file_patterns_raises_error(self):
        """AC-1: At least one file pattern required."""
        with pytest.raises(ValidationError) as exc_info:
            DomainConfigV2(
                base_path="reference/monthly/{YYYYMM}/数据采集",
                file_patterns=[],  # Empty list
                sheet_name="Sheet1",
            )

        assert "file_patterns" in str(exc_info.value)
        assert "at least 1" in str(exc_info.value).lower()

    def test_sheet_name_as_integer_index(self):
        """AC-1: sheet_name supports both string and int."""
        config = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/数据采集",
            file_patterns=["*.xlsx"],
            sheet_name=0,  # Integer index
        )

        assert config.sheet_name == 0

    def test_sheet_name_as_string(self):
        """AC-1: sheet_name supports string sheet names."""
        config = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/数据采集",
            file_patterns=["*.xlsx"],
            sheet_name="规模明细",
        )

        assert config.sheet_name == "规模明细"

    def test_chinese_characters_in_file_patterns(self):
        """Subtask 4.7: Test Chinese characters in file_patterns (Unicode handling)."""
        config = DomainConfigV2(
            base_path="reference/monthly/{YYYYMM}/数据采集",
            file_patterns=["*年金终稿*.xlsx", "*规模明细*.xlsx", "*万能险*.xlsx"],
            sheet_name="规模明细",
        )

        assert "*年金终稿*.xlsx" in config.file_patterns
        assert "*规模明细*.xlsx" in config.file_patterns
        assert "*万能险*.xlsx" in config.file_patterns

    def test_windows_max_path_limit_handling(self):
        """Subtask 4.8: Test Windows MAX_PATH (260 char) limit handling."""
        # Create a path that's close to 260 characters
        long_path = "reference/monthly/{YYYYMM}/" + "a" * 200 + "/数据采集"

        config = DomainConfigV2(
            base_path=long_path,
            file_patterns=["*.xlsx"],
            sheet_name="Sheet1",
        )

        # Should not raise - validation allows long paths
        # (actual path length validation happens at runtime, not schema validation)
        assert len(config.base_path) > 200

    def test_special_characters_in_sheet_name(self):
        """Subtask 4.9: Test special characters in sheet_name (edge cases)."""
        # Test various special characters that might appear in sheet names
        special_names = [
            "Sheet-1",
            "Sheet_1",
            "Sheet (1)",
            "Sheet[1]",
            "规模明细-2024",
            "Data/Summary",  # Forward slash
        ]

        for sheet_name in special_names:
            config = DomainConfigV2(
                base_path="reference/monthly/{YYYYMM}/数据采集",
                file_patterns=["*.xlsx"],
                sheet_name=sheet_name,
            )
            assert config.sheet_name == sheet_name

    def test_invalid_template_variables_rejected(self):
        """Subtask 4.10: Test invalid template variables rejected (security: whitelist enforcement)."""
        # Test various invalid template variables
        invalid_paths = [
            "reference/monthly/{INVALID}/数据采集",
            "reference/monthly/{YYYYMMDD}/数据采集",
            "reference/monthly/{USER}/数据采集",
            "reference/monthly/{PATH}/数据采集",
        ]

        for invalid_path in invalid_paths:
            with pytest.raises(ValidationError) as exc_info:
                DomainConfigV2(
                    base_path=invalid_path,
                    file_patterns=["*.xlsx"],
                    sheet_name="Sheet1",
                )

            assert "Invalid template variables" in str(exc_info.value)


class TestDataSourceConfigV2:
    """Test cases for Epic 3 DataSourceConfigV2 validation."""

    def test_valid_config_with_single_domain(self):
        """AC-1: Valid config with 1 domain."""
        config = DataSourceConfigV2(
            domains={
                "annuity_performance": DomainConfigV2(
                    base_path="reference/monthly/{YYYYMM}/数据采集",
                    file_patterns=["*.xlsx"],
                    sheet_name="规模明细",
                )
            }
        )

        assert len(config.domains) == 1
        assert "annuity_performance" in config.domains
        assert config.schema_version == "1.0"  # Default value

    def test_valid_config_with_multiple_domains(self):
        """AC-1: Valid config with multiple domains."""
        config = DataSourceConfigV2(
            domains={
                "annuity_performance": DomainConfigV2(
                    base_path="reference/monthly/{YYYYMM}/数据采集",
                    file_patterns=["*年金*.xlsx"],
                    sheet_name="规模明细",
                ),
                "universal_insurance": DomainConfigV2(
                    base_path="reference/monthly/{YYYYMM}/业务收集",
                    file_patterns=["*万能险*.xlsx"],
                    sheet_name="明细",
                ),
            }
        )

        assert len(config.domains) == 2
        assert "annuity_performance" in config.domains
        assert "universal_insurance" in config.domains

    def test_empty_domains_raises_error(self):
        """Subtask 4.6: At least one domain required."""
        with pytest.raises(ValidationError) as exc_info:
            DataSourceConfigV2(domains={})

        assert "domains" in str(exc_info.value)
        assert "at least 1 domain" in str(exc_info.value).lower()

    def test_schema_version_validation(self):
        """AC-1: Schema version validation."""
        config = DataSourceConfigV2(
            schema_version="1.0",
            domains={
                "test": DomainConfigV2(
                    base_path="test/{YYYYMM}",
                    file_patterns=["*.xlsx"],
                    sheet_name="Sheet1",
                )
            },
        )

        assert config.schema_version == "1.0"

    def test_unsupported_schema_version_raises_error(self):
        """AC-1: Unsupported schema version raises error."""
        with pytest.raises(ValidationError) as exc_info:
            DataSourceConfigV2(
                schema_version="2.0",  # Not supported
                domains={
                    "test": DomainConfigV2(
                        base_path="test/{YYYYMM}",
                        file_patterns=["*.xlsx"],
                        sheet_name="Sheet1",
                    )
                },
            )

        assert "schema_version" in str(exc_info.value) or "Unsupported" in str(
            exc_info.value
        )


class TestValidateDataSourcesConfigV2:
    """Test cases for validate_data_sources_config_v2 function."""

    def test_validate_with_valid_config_file(self, config_file_v2):
        """AC-4: Valid configuration logs success."""
        result = validate_data_sources_config_v2(config_file_v2)
        assert result is True

    def test_validate_file_not_found(self):
        """AC-2: Missing config file raises error."""
        with pytest.raises(
            DataSourcesValidationError, match="Configuration file not found"
        ):
            validate_data_sources_config_v2("/nonexistent/config.yml")

    def test_validate_invalid_yaml(self, tmp_path):
        """AC-2: Invalid YAML file raises error."""
        bad_config = tmp_path / "bad_config.yml"
        bad_config.write_text("invalid: yaml: content: [")

        with pytest.raises(DataSourcesValidationError, match="Invalid YAML"):
            validate_data_sources_config_v2(str(bad_config))

    def test_validate_missing_required_fields(self, tmp_path):
        """AC-2: Missing required fields raises ValidationError."""
        invalid_config = {
            "domains": {
                "bad_domain": {
                    "base_path": "test/{YYYYMM}",
                    # Missing file_patterns and sheet_name
                }
            }
        }

        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config_v2(str(config_path))

    def test_validate_invalid_enum_value(self, tmp_path):
        """AC-3: Invalid enum value raises ValidationError."""
        invalid_config = {
            "domains": {
                "bad_domain": {
                    "base_path": "test/{YYYYMM}",
                    "file_patterns": ["*.xlsx"],
                    "sheet_name": "Sheet1",
                    "version_strategy": "newest",  # Invalid
                }
            }
        }

        config_path = tmp_path / "invalid_enum.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config_v2(str(config_path))


class TestGetDomainConfigV2:
    """Test cases for get_domain_config_v2 function."""

    def test_get_existing_domain_config(self, config_file_v2):
        """AC-1: Retrieve configuration for existing domain."""
        domain_config = get_domain_config_v2("annuity_performance", config_file_v2)

        assert isinstance(domain_config, DomainConfigV2)
        assert domain_config.base_path == "reference/monthly/{YYYYMM}/收集数据/数据采集"
        assert domain_config.file_patterns == ["*年金终稿*.xlsx"]
        assert domain_config.sheet_name == "规模明细"

    def test_get_domain_config_not_found(self, config_file_v2):
        """AC-2: Error when requested domain doesn't exist."""
        with pytest.raises(
            DataSourcesValidationError, match="Domain 'nonexistent' not found"
        ):
            get_domain_config_v2("nonexistent", config_file_v2)

    def test_get_domain_config_invalid_file(self):
        """AC-2: Error when config file doesn't exist."""
        with pytest.raises(
            DataSourcesValidationError, match="Configuration file not found"
        ):
            get_domain_config_v2("any_domain", "/nonexistent/config.yml")


class TestIntegration:
    """Integration test cases for Epic 3 schema validation."""

    def test_end_to_end_validation_workflow(self, config_file_v2):
        """AC-1: Complete validation workflow."""
        # First validate the entire config
        assert validate_data_sources_config_v2(config_file_v2) is True

        # Then get specific domain configs
        annuity = get_domain_config_v2("annuity_performance", config_file_v2)
        universal = get_domain_config_v2("universal_insurance", config_file_v2)

        # Verify domain configurations
        assert annuity.base_path == "reference/monthly/{YYYYMM}/收集数据/数据采集"
        assert universal.base_path == "reference/monthly/{YYYYMM}/收集数据/业务收集"

        assert annuity.version_strategy == "highest_number"
        assert universal.version_strategy == "highest_number"  # Default

    def test_real_config_file_validation(self):
        """AC-4: Validation of actual config/data_sources.yml file.

        Story 6.2-P14 AC-4: get_domain_config_v2 merges defaults/overrides.
        """
        config_path = "config/data_sources.yml"

        # Check if file exists (it should after Story 3.0)
        if Path(config_path).exists():
            result = validate_data_sources_config_v2(config_path)
            assert result is True

            # Test getting the annuity_performance domain with defaults merged
            annuity_config = get_domain_config_v2("annuity_performance", config_path)

            assert annuity_config.sheet_name == "规模明细"
            assert annuity_config.version_strategy == "highest_number"  # From defaults
            assert "*规模收入数据*.xlsx" in annuity_config.file_patterns

            # Verify output configuration
            assert annuity_config.output is not None
            assert annuity_config.output.table == "annuity_performance"
            assert annuity_config.output.schema_name == "business"  # From defaults

            # Verify exclude_patterns extended from defaults
            assert "~$*" in annuity_config.exclude_patterns  # From defaults
            assert "*.eml" in annuity_config.exclude_patterns  # From defaults
            assert "*回复*" in annuity_config.exclude_patterns  # Extended via +

            # Test getting the annuity_income domain
            income_config = get_domain_config_v2("annuity_income", config_path)
            assert income_config.output is not None
            assert income_config.output.table == "annuity_income"
            assert income_config.output.schema_name == "business"  # From defaults
