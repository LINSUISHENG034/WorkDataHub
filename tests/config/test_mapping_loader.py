"""
Tests for mapping loader functionality.

This module tests the mapping_loader with various YAML structures,
including Chinese character handling and comprehensive error scenarios.
"""

import os
from pathlib import Path

import pytest
import yaml

from src.work_data_hub.infrastructure.settings.loader import (
    MappingLoaderError,
    get_mappings_dir,
    load_business_type_code,
    load_company_branch,
    load_company_id_overrides_plan,
    load_default_portfolio_code,
    load_yaml_mapping,
)


@pytest.fixture
def sample_mapping():
    """Sample mapping data for testing."""
    return {
        "内蒙": "G31",
        "战略": "G37",
        "济南": "G21",
        "北京其他": "G37",
    }


@pytest.fixture
def sample_mapping_file(tmp_path, sample_mapping):
    """Create a temporary mapping file for testing."""
    mapping_path = tmp_path / "test_mapping.yml"
    with open(mapping_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_mapping, f, allow_unicode=True)
    return str(mapping_path)


@pytest.fixture
def invalid_yaml_file(tmp_path):
    """Create a file with invalid YAML content."""
    invalid_path = tmp_path / "invalid.yml"
    invalid_path.write_text("invalid: yaml: content: [", encoding="utf-8")
    return str(invalid_path)


@pytest.fixture
def non_dict_yaml_file(tmp_path):
    """Create a YAML file that's not a dictionary."""
    non_dict_path = tmp_path / "non_dict.yml"
    non_dict_path.write_text("- not\n- a\n- dictionary", encoding="utf-8")
    return str(non_dict_path)


@pytest.fixture
def invalid_value_types_file(tmp_path):
    """Create a YAML file with invalid value types."""
    invalid_values = {
        "valid_key": "valid_value",
        "invalid_key": {"nested": "dict"},
        "another_key": ["list", "value"],
    }

    invalid_path = tmp_path / "invalid_values.yml"
    with open(invalid_path, "w", encoding="utf-8") as f:
        yaml.dump(invalid_values, f, allow_unicode=True)
    return str(invalid_path)


class TestLoadYamlMapping:
    """Test cases for load_yaml_mapping function."""

    def test_load_yaml_mapping_happy_path(self, sample_mapping_file, sample_mapping):
        """Test successful loading of YAML mapping."""
        mapping = load_yaml_mapping(sample_mapping_file)

        # Assert known entries from sample mapping
        assert mapping["内蒙"] == "G31"
        assert mapping["战略"] == "G37"
        assert mapping["济南"] == "G21"
        assert mapping["北京其他"] == "G37"

        # Assert all values are converted to strings
        for key, value in mapping.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_load_yaml_mapping_with_integer_values(self, tmp_path):
        """Test that integer values are converted to strings."""
        mapping_data = {
            "FP0001": 614810477,
            "FP0002": 614810477,
            "P0809": 608349737,
        }

        mapping_path = tmp_path / "int_values.yml"
        with open(mapping_path, "w", encoding="utf-8") as f:
            yaml.dump(mapping_data, f)

        mapping = load_yaml_mapping(str(mapping_path))

        # All values should be converted to strings
        assert mapping["FP0001"] == "614810477"
        assert mapping["FP0002"] == "614810477"
        assert mapping["P0809"] == "608349737"

        for key, value in mapping.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_load_yaml_mapping_file_not_found(self):
        """Test error when mapping file doesn't exist."""
        with pytest.raises(MappingLoaderError, match="Mapping file not found"):
            load_yaml_mapping("/nonexistent/path.yml")

    def test_load_yaml_mapping_invalid_yaml(self, invalid_yaml_file):
        """Test error with invalid YAML content."""
        with pytest.raises(MappingLoaderError, match="Invalid YAML mapping"):
            load_yaml_mapping(invalid_yaml_file)

    def test_load_yaml_mapping_not_dictionary(self, non_dict_yaml_file):
        """Test error when YAML content is not a dictionary."""
        with pytest.raises(MappingLoaderError, match="Mapping must be a dictionary"):
            load_yaml_mapping(non_dict_yaml_file)

    def test_load_yaml_mapping_invalid_key_types(self, tmp_path):
        """Test error with non-string keys."""
        # Create YAML with non-string keys
        invalid_data = {123: "numeric_key", "valid_key": "valid_value"}

        invalid_path = tmp_path / "invalid_keys.yml"
        with open(invalid_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_data, f)

        with pytest.raises(MappingLoaderError, match="Mapping key must be string"):
            load_yaml_mapping(str(invalid_path))

    def test_load_yaml_mapping_invalid_value_types(self, invalid_value_types_file):
        """Test error with invalid value types."""
        with pytest.raises(
            MappingLoaderError, match="Mapping value must be string or int"
        ):
            load_yaml_mapping(invalid_value_types_file)

    def test_load_yaml_mapping_empty_file(self, tmp_path):
        """Test loading empty YAML file returns empty dict."""
        empty_path = tmp_path / "empty.yml"
        empty_path.write_text("", encoding="utf-8")

        mapping = load_yaml_mapping(str(empty_path))
        assert mapping == {}

    def test_load_yaml_mapping_chinese_characters_preserved(self, sample_mapping_file):
        """Test that Chinese characters are correctly preserved."""
        mapping = load_yaml_mapping(sample_mapping_file)

        # Check Chinese keys are preserved
        assert "内蒙" in mapping
        assert "战略" in mapping
        assert "济南" in mapping
        assert "北京其他" in mapping

        # Verify the actual Chinese characters are correct
        assert len("内蒙") == 2  # Two Chinese characters
        assert len("北京其他") == 4  # Four Chinese characters


class TestSpecificLoaderFunctions:
    """Test cases for specific loader functions."""

    def test_load_company_branch_happy_path(self):
        """Test successful loading of company branch mapping."""
        mapping = load_company_branch()

        # Assert known sample entries from YAML
        assert "内蒙" in mapping
        assert mapping["内蒙"] == "G31"
        assert "济南" in mapping
        assert mapping["济南"] == "G21"
        assert "战略" in mapping
        assert mapping["战略"] == "G37"

        # Verify all values are strings
        for key, value in mapping.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_load_default_portfolio_code_happy_path(self):
        """Test successful loading of default portfolio code mapping."""
        mapping = load_default_portfolio_code()

        # Assert known sample entries from YAML
        assert "集合计划" in mapping
        assert mapping["集合计划"] == "QTAN001"
        assert "单一计划" in mapping
        assert mapping["单一计划"] == "QTAN002"
        assert "职业年金" in mapping
        assert mapping["职业年金"] == "QTAN003"

        # Verify all values are strings
        for key, value in mapping.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_load_company_id_overrides_plan_happy_path(self):
        """Test successful loading of company ID overrides mapping."""
        mapping = load_company_id_overrides_plan()

        # Assert known sample entries from YAML
        assert "FP0001" in mapping
        assert mapping["FP0001"] == "614810477"
        assert "FP0002" in mapping
        assert mapping["FP0002"] == "614810477"
        assert "P0809" in mapping
        assert mapping["P0809"] == "608349737"

        # Verify all values are strings (even though they're numbers)
        for key, value in mapping.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_load_business_type_code_happy_path(self):
        """Test successful loading of business type code mapping."""
        mapping = load_business_type_code()

        # Assert known sample entries from YAML (updated to match current mapping file)
        assert "职年受托" in mapping
        assert mapping["职年受托"] == "PL204"
        assert "职年投资" in mapping
        assert mapping["职年投资"] == "PL203"

        # Verify all values are strings
        for key, value in mapping.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_specific_loaders_file_not_found_error(self, monkeypatch):
        """Test that specific loaders raise error when files are missing."""

        # Mock the mapping files to not exist
        def mock_load_yaml_mapping(path):
            raise MappingLoaderError(f"Mapping file not found: {path}")

        monkeypatch.setattr(
            "src.work_data_hub.infrastructure.settings.loader.load_yaml_mapping",
            mock_load_yaml_mapping,
        )

        with pytest.raises(MappingLoaderError, match="Mapping file not found"):
            load_company_branch()

        with pytest.raises(MappingLoaderError, match="Mapping file not found"):
            load_default_portfolio_code()

        with pytest.raises(MappingLoaderError, match="Mapping file not found"):
            load_company_id_overrides_plan()

        with pytest.raises(MappingLoaderError, match="Mapping file not found"):
            load_business_type_code()


class TestIntegration:
    """Integration test cases."""

    def test_all_mappings_load_successfully(self):
        """Integration test - all mappings load without errors."""
        mappings = {
            "company_branch": load_company_branch(),
            "portfolio_code": load_default_portfolio_code(),
            "id_overrides": load_company_id_overrides_plan(),
            "business_type": load_business_type_code(),
        }

        # Verify each mapping has expected structure
        for name, mapping in mappings.items():
            assert isinstance(mapping, dict)
            assert len(mapping) > 0

            # All keys and values should be strings
            for key, value in mapping.items():
                assert isinstance(key, str)
                assert isinstance(value, str)

    def test_chinese_characters_preserved_across_all_mappings(self):
        """Verify Chinese characters are preserved in all mappings."""
        # Test company branch mapping
        branch_mapping = load_company_branch()
        assert "内蒙" in branch_mapping
        assert "济南" in branch_mapping

        # Test portfolio code mapping
        portfolio_mapping = load_default_portfolio_code()
        assert "集合计划" in portfolio_mapping
        assert "职业年金" in portfolio_mapping

        # Test business type mapping
        business_mapping = load_business_type_code()
        assert "职年受托" in business_mapping
        assert "职年投资" in business_mapping


class TestPortabilityAndEnvironmentOverride:
    """Test cases for path portability and environment override functionality."""

    def test_module_relative_paths_portable(self, tmp_path):
        """Test that loaders work when invoked from any working directory."""
        original_cwd = os.getcwd()
        try:
            # Change to different directory
            os.chdir(tmp_path)

            # Should still work - test known values from repo seeds
            mapping = load_company_branch()
            assert "内蒙" in mapping
            assert mapping["内蒙"] == "G31"
            assert "济南" in mapping
            assert mapping["济南"] == "G21"
        finally:
            # CRITICAL: Always restore
            os.chdir(original_cwd)

    def test_env_override_directory(self, tmp_path, monkeypatch):
        """Test that WDH_MAPPINGS_DIR override works with valid directory."""
        # Create temp mappings directory with minimal YAML
        temp_mappings = tmp_path / "mappings"
        temp_mappings.mkdir()
        (temp_mappings / "company_branch.yml").write_text(
            "test_key: test_value\noverride_key: override_value", encoding="utf-8"
        )

        monkeypatch.setenv("WDH_MAPPINGS_DIR", str(temp_mappings))

        mapping = load_company_branch()
        assert mapping["test_key"] == "test_value"
        assert mapping["override_key"] == "override_value"
        # Should use override, not repo
        assert "内蒙" not in mapping

    def test_env_override_missing_dir(self, monkeypatch):
        """Test that WDH_MAPPINGS_DIR with missing directory raises error."""
        monkeypatch.setenv("WDH_MAPPINGS_DIR", "/nonexistent/path")

        with pytest.raises(
            MappingLoaderError, match="WDH_MAPPINGS_DIR not found or not a directory"
        ):
            load_company_branch()

    def test_env_override_file_not_directory(self, tmp_path, monkeypatch):
        """Test that WDH_MAPPINGS_DIR pointing to file (not directory) raises error."""
        # Create a file instead of directory
        temp_file = tmp_path / "not_a_directory.txt"
        temp_file.write_text("not a directory", encoding="utf-8")

        monkeypatch.setenv("WDH_MAPPINGS_DIR", str(temp_file))

        with pytest.raises(
            MappingLoaderError, match="WDH_MAPPINGS_DIR not found or not a directory"
        ):
            get_mappings_dir()

    def test_get_mappings_dir_default_path(self):
        """Test that get_mappings_dir returns correct default path."""
        # Clear any environment variable
        if "WDH_MAPPINGS_DIR" in os.environ:
            del os.environ["WDH_MAPPINGS_DIR"]

        mappings_dir = get_mappings_dir()

        # Should be project root / data / mappings (Story 5.3)
        expected_path = Path(__file__).parent.parent.parent / "data" / "mappings"

        # Check that both paths exist and resolve to same location
        assert mappings_dir.exists()
        assert expected_path.exists()
        assert mappings_dir.resolve() == expected_path.resolve()
