"""
Tests for data sources schema validation.

This module tests the schema validation functionality for data_sources.yml
configuration, including validation of domain configurations and error handling.
"""

import pytest
import yaml

from src.work_data_hub.config.schema import (
    DataSourcesConfig,
    DataSourcesValidationError,
    DiscoveryConfig,
    DomainConfig,
    get_domain_config,
    validate_data_sources_config,
)


@pytest.fixture
def valid_domain_config():
    """Sample valid domain configuration."""
    return {
        "description": "Test domain configuration",
        "pattern": r"(?P<year>20\d{2}).*test.*\.xlsx$",
        "select": "latest_by_year_month",
        "sheet": 0,
        "table": "test_table",
        "pk": ["id", "date"],
        "required_columns": ["col1", "col2"],
        "validation": {"min_rows": 1},
    }


@pytest.fixture
def valid_discovery_config():
    """Sample valid discovery configuration."""
    return {
        "file_extensions": [".xlsx", ".xlsm"],
        "exclude_directories": ["temp", "backup"],
        "ignore_patterns": ["~$*", "*.tmp"],
        "max_depth": 10,
        "follow_symlinks": False,
    }


@pytest.fixture
def valid_data_sources_config(valid_domain_config, valid_discovery_config):
    """Sample valid complete data sources configuration."""
    return {
        "domains": {
            "test_domain": valid_domain_config,
            "another_domain": {
                "pattern": r"another.*\.xlsx$",
                "select": "latest_by_mtime",
                "sheet": "Sheet1",
                "table": "another_table",
                "pk": ["key"],
            },
        },
        "discovery": valid_discovery_config,
    }


@pytest.fixture
def config_file(tmp_path, valid_data_sources_config):
    """Create a temporary data sources config file for testing."""
    config_path = tmp_path / "test_data_sources.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(valid_data_sources_config, f, allow_unicode=True)
    return str(config_path)


class TestDomainConfig:
    """Test cases for DomainConfig validation."""

    def test_valid_domain_config(self, valid_domain_config):
        """Test that valid domain config passes validation."""
        config = DomainConfig(**valid_domain_config)

        assert config.description == "Test domain configuration"
        assert config.pattern == r"(?P<year>20\d{2}).*test.*\.xlsx$"
        assert config.select == "latest_by_year_month"
        assert config.sheet == 0
        assert config.table == "test_table"
        assert config.pk == ["id", "date"]
        assert config.required_columns == ["col1", "col2"]
        assert config.validation == {"min_rows": 1}

    def test_minimal_domain_config(self):
        """Test minimal valid domain config."""
        minimal_config = {
            "pattern": r"test.*\.xlsx$",
            "select": "latest_by_mtime",
            "table": "test_table",
            "pk": ["id"],
        }

        config = DomainConfig(**minimal_config)
        assert config.pattern == r"test.*\.xlsx$"
        assert config.select == "latest_by_mtime"
        assert config.table == "test_table"
        assert config.pk == ["id"]
        assert config.sheet == 0  # Default value
        assert config.description is None  # Optional field

    def test_domain_config_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        # Missing pattern
        with pytest.raises(Exception):  # Pydantic ValidationError
            DomainConfig(select="latest_by_mtime", table="test", pk=["id"])

        # Missing select
        with pytest.raises(Exception):
            DomainConfig(pattern="test", table="test", pk=["id"])

        # Missing table
        with pytest.raises(Exception):
            DomainConfig(pattern="test", select="latest_by_mtime", pk=["id"])

        # Missing pk
        with pytest.raises(Exception):
            DomainConfig(pattern="test", select="latest_by_mtime", table="test")

    def test_domain_config_invalid_select_value(self):
        """Test that invalid select values are rejected."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            DomainConfig(
                pattern="test", select="invalid_selection_strategy", table="test", pk=["id"]
            )

    def test_domain_config_empty_pk_list(self):
        """Test that empty primary key list is rejected."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            DomainConfig(
                pattern="test",
                select="latest_by_mtime",
                table="test",
                pk=[],  # Empty pk list should be rejected
            )

    def test_domain_config_sheet_types(self):
        """Test that sheet accepts both int and string values."""
        # Integer sheet
        config1 = DomainConfig(
            pattern="test", select="latest_by_mtime", table="test", pk=["id"], sheet=1
        )
        assert config1.sheet == 1

        # String sheet name
        config2 = DomainConfig(
            pattern="test", select="latest_by_mtime", table="test", pk=["id"], sheet="Sheet1"
        )
        assert config2.sheet == "Sheet1"


class TestDiscoveryConfig:
    """Test cases for DiscoveryConfig validation."""

    def test_valid_discovery_config(self, valid_discovery_config):
        """Test that valid discovery config passes validation."""
        config = DiscoveryConfig(**valid_discovery_config)

        assert config.file_extensions == [".xlsx", ".xlsm"]
        assert config.exclude_directories == ["temp", "backup"]
        assert config.ignore_patterns == ["~$*", "*.tmp"]
        assert config.max_depth == 10
        assert config.follow_symlinks is False

    def test_minimal_discovery_config(self):
        """Test that discovery config with all optional fields works."""
        config = DiscoveryConfig()

        assert config.file_extensions is None
        assert config.exclude_directories is None
        assert config.ignore_patterns is None
        assert config.max_depth == 10  # Default value
        assert config.follow_symlinks is False  # Default value


class TestDataSourcesConfig:
    """Test cases for DataSourcesConfig validation."""

    def test_valid_data_sources_config(self, valid_data_sources_config):
        """Test that valid complete config passes validation."""
        config = DataSourcesConfig(**valid_data_sources_config)

        assert len(config.domains) == 2
        assert "test_domain" in config.domains
        assert "another_domain" in config.domains
        assert config.discovery is not None

    def test_data_sources_config_without_discovery(self):
        """Test that config without discovery section is valid."""
        config_data = {
            "domains": {
                "test_domain": {
                    "pattern": "test",
                    "select": "latest_by_mtime",
                    "table": "test",
                    "pk": ["id"],
                }
            }
        }

        config = DataSourcesConfig(**config_data)
        assert len(config.domains) == 1
        assert config.discovery is None

    def test_data_sources_config_empty_domains(self):
        """Test that empty domains dict is rejected."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            DataSourcesConfig(domains={})

    def test_data_sources_config_missing_domains(self):
        """Test that missing domains section is rejected."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            DataSourcesConfig(discovery={"max_depth": 5})


class TestValidateDataSourcesConfig:
    """Test cases for validate_data_sources_config function."""

    def test_validate_current_data_sources_succeeds(self):
        """Test that current data_sources.yml passes validation."""
        result = validate_data_sources_config("src/work_data_hub/config/data_sources.yml")
        assert result is True

    def test_validate_data_sources_with_custom_path(self, config_file):
        """Test validation with custom config path."""
        result = validate_data_sources_config(config_file)
        assert result is True

    def test_validate_data_sources_file_not_found(self):
        """Test validation with non-existent file."""
        with pytest.raises(DataSourcesValidationError, match="Configuration file not found"):
            validate_data_sources_config("/nonexistent/config.yml")

    def test_validate_data_sources_invalid_yaml(self, tmp_path):
        """Test validation with invalid YAML file."""
        bad_config = tmp_path / "bad_config.yml"
        bad_config.write_text("invalid: yaml: content: [")

        with pytest.raises(DataSourcesValidationError, match="Invalid YAML"):
            validate_data_sources_config(str(bad_config))

    def test_validate_data_sources_missing_required_fields(self, tmp_path):
        """Test validation fails with missing required fields."""
        invalid_config = {
            "domains": {
                "bad_domain": {
                    # Missing required fields: pattern, select, table, pk
                    "description": "Missing required fields"
                }
            }
        }

        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config(str(config_path))

    def test_validate_data_sources_invalid_domain_structure(self, tmp_path):
        """Test validation fails with invalid domain structure."""
        invalid_config = {
            "domains": {
                "bad_domain": {
                    "pattern": "test",
                    "select": "invalid_strategy",  # Invalid select value
                    "table": "test",
                    "pk": ["id"],
                }
            }
        }

        config_path = tmp_path / "invalid_domain.yml"
        with open(config_path, "w") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config(str(config_path))


class TestGetDomainConfig:
    """Test cases for get_domain_config function."""

    def test_get_existing_domain_config(self, config_file):
        """Test retrieving configuration for an existing domain."""
        domain_config = get_domain_config("test_domain", config_file)

        assert isinstance(domain_config, DomainConfig)
        assert domain_config.description == "Test domain configuration"
        assert domain_config.table == "test_table"
        assert domain_config.pk == ["id", "date"]

    def test_get_domain_config_not_found(self, config_file):
        """Test error when requested domain doesn't exist."""
        with pytest.raises(DataSourcesValidationError, match="Domain 'nonexistent' not found"):
            get_domain_config("nonexistent", config_file)

    def test_get_domain_config_invalid_file(self):
        """Test error when config file doesn't exist."""
        with pytest.raises(DataSourcesValidationError, match="Configuration file not found"):
            get_domain_config("any_domain", "/nonexistent/config.yml")


class TestIntegration:
    """Integration test cases."""

    def test_end_to_end_validation_workflow(self, config_file):
        """Test complete validation workflow."""
        # First validate the entire config
        assert validate_data_sources_config(config_file) is True

        # Then get specific domain configs
        test_domain = get_domain_config("test_domain", config_file)
        another_domain = get_domain_config("another_domain", config_file)

        # Verify domain configurations
        assert test_domain.table == "test_table"
        assert another_domain.table == "another_table"

        assert test_domain.select == "latest_by_year_month"
        assert another_domain.select == "latest_by_mtime"

    def test_real_data_sources_yml_validation(self):
        """Test validation of the actual data_sources.yml file in the project."""
        # This should pass if the real file is properly structured
        result = validate_data_sources_config("src/work_data_hub/config/data_sources.yml")
        assert result is True

        # Test getting the sample_trustee_performance domain
        sample_config = get_domain_config(
            "sample_trustee_performance", "src/work_data_hub/config/data_sources.yml"
        )

        assert sample_config.table == "sample_trustee_performance"
        assert sample_config.select == "latest_by_year_month"
        assert "report_date" in sample_config.pk
        assert "plan_code" in sample_config.pk
        assert "company_code" in sample_config.pk
