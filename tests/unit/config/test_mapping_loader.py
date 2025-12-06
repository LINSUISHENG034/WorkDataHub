"""
Unit tests for multi-file YAML mapping loader (Story 6.3).

This module tests the load_company_id_overrides() function and related
utilities for loading company ID mapping configurations from YAML files.
"""

import pytest
import time
from pathlib import Path

from src.work_data_hub.config.mapping_loader import (
    load_company_id_overrides,
    get_flat_overrides,
    PRIORITY_LEVELS,
    _load_single_yaml_file,
)


@pytest.fixture
def temp_mappings_dir(tmp_path):
    """Create a temporary mappings directory for testing."""
    mappings_dir = tmp_path / "mappings"
    mappings_dir.mkdir()
    return mappings_dir


@pytest.fixture
def valid_plan_mappings(temp_mappings_dir):
    """Create a valid plan mappings file."""
    content = """FP0001: "614810477"
FP0002: "614810477"
FP0003: "610081428"
"""
    file_path = temp_mappings_dir / "company_id_overrides_plan.yml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def valid_name_mappings(temp_mappings_dir):
    """Create a valid name mappings file with Chinese characters."""
    content = """中国平安: "600866980"
平安保险: "600866980"
招商银行: "600036000"
"""
    file_path = temp_mappings_dir / "company_id_overrides_name.yml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def empty_mappings_file(temp_mappings_dir):
    """Create an empty mappings file."""
    file_path = temp_mappings_dir / "company_id_overrides_account.yml"
    file_path.write_text("", encoding="utf-8")
    return file_path


@pytest.fixture
def invalid_yaml_file(temp_mappings_dir):
    """Create a file with invalid YAML syntax."""
    content = """invalid: yaml: syntax:
  - missing
  colon here
"""
    file_path = temp_mappings_dir / "company_id_overrides_hardcode.yml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def invalid_format_file(temp_mappings_dir):
    """Create a file with valid YAML but invalid format (list instead of dict)."""
    content = """- item1
- item2
- item3
"""
    file_path = temp_mappings_dir / "company_id_overrides_account_name.yml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def whitespace_mappings(temp_mappings_dir):
    """Create a mappings file with whitespace in values (YAML strips key whitespace)."""
    # Note: YAML naturally strips leading/trailing whitespace from unquoted keys
    # We test that our code strips whitespace from values
    content = """FP0001: "  614810477  "
FP0002: "614810478  "
"""
    file_path = temp_mappings_dir / "company_id_overrides_plan.yml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def non_string_value_file(temp_mappings_dir):
    """Create a file with non-string value to validate type enforcement."""
    content = """FP0001: 614810477
FP0002: "614810478"
"""
    file_path = temp_mappings_dir / "company_id_overrides_plan.yml"
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestLoadSingleYamlFile:
    """Test cases for _load_single_yaml_file function."""

    def test_missing_file_returns_empty_dict(self, temp_mappings_dir):
        """Missing file returns empty dict without exception."""
        non_existent = temp_mappings_dir / "non_existent.yml"
        result = _load_single_yaml_file(non_existent, "test")
        assert result == {}

    def test_empty_file_returns_empty_dict(self, empty_mappings_file):
        """Empty file returns empty dict."""
        result = _load_single_yaml_file(empty_mappings_file, "account")
        assert result == {}

    def test_valid_file_returns_mappings(self, valid_plan_mappings):
        """Valid file returns correct mappings."""
        result = _load_single_yaml_file(valid_plan_mappings, "plan")
        assert result == {
            "FP0001": "614810477",
            "FP0002": "614810477",
            "FP0003": "610081428",
        }

    def test_chinese_characters_supported(self, valid_name_mappings):
        """Chinese characters in keys and values are supported."""
        result = _load_single_yaml_file(valid_name_mappings, "name")
        assert result["中国平安"] == "600866980"
        assert result["平安保险"] == "600866980"
        assert result["招商银行"] == "600036000"

    def test_invalid_yaml_raises_value_error(self, invalid_yaml_file):
        """Invalid YAML syntax raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _load_single_yaml_file(invalid_yaml_file, "hardcode")
        assert "Invalid YAML" in str(exc_info.value)

    def test_invalid_format_raises_value_error(self, invalid_format_file):
        """Non-dict YAML raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _load_single_yaml_file(invalid_format_file, "account_name")
        assert "expected dict" in str(exc_info.value)

    def test_non_string_values_raise_value_error(self, non_string_value_file):
        """Non-string mapping values raise ValueError (enforce str->str contract)."""
        with pytest.raises(ValueError) as exc_info:
            _load_single_yaml_file(non_string_value_file, "plan")
        assert "string key/value" in str(exc_info.value)

    def test_whitespace_stripped(self, whitespace_mappings):
        """Whitespace is stripped from keys and values."""
        result = _load_single_yaml_file(whitespace_mappings, "plan")
        assert "FP0001" in result
        assert result["FP0001"] == "614810477"
        assert "FP0002" in result


class TestLoadCompanyIdOverrides:
    """Test cases for load_company_id_overrides function."""

    def test_returns_all_priority_levels(self, temp_mappings_dir, valid_plan_mappings):
        """Returns dict with all 5 priority level keys."""
        result = load_company_id_overrides(temp_mappings_dir)
        assert set(result.keys()) == set(PRIORITY_LEVELS)

    def test_loads_existing_files(
        self, temp_mappings_dir, valid_plan_mappings, valid_name_mappings
    ):
        """Loads data from existing files."""
        result = load_company_id_overrides(temp_mappings_dir)
        assert result["plan"]["FP0001"] == "614810477"
        assert result["name"]["中国平安"] == "600866980"

    def test_missing_files_return_empty_dicts(self, temp_mappings_dir):
        """Missing files result in empty dicts for those priorities."""
        result = load_company_id_overrides(temp_mappings_dir)
        for priority in PRIORITY_LEVELS:
            assert isinstance(result[priority], dict)

    def test_invalid_yaml_raises_value_error(
        self, temp_mappings_dir, invalid_yaml_file
    ):
        """Invalid YAML in any file raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            load_company_id_overrides(temp_mappings_dir)
        assert "Invalid YAML" in str(exc_info.value)

    def test_invalid_format_raises_value_error(
        self, temp_mappings_dir, invalid_format_file
    ):
        """Invalid format in any file raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            load_company_id_overrides(temp_mappings_dir)
        assert "expected dict" in str(exc_info.value)

    def test_performance_under_50ms(
        self, temp_mappings_dir, valid_plan_mappings, valid_name_mappings
    ):
        """Loading 5 files completes in under 50ms (relaxed for CI variability)."""
        # Create all 5 files with some content
        for priority in PRIORITY_LEVELS:
            file_path = temp_mappings_dir / f"company_id_overrides_{priority}.yml"
            if not file_path.exists():
                file_path.write_text("key1: value1\nkey2: value2\n", encoding="utf-8")

        start_time = time.perf_counter()
        load_company_id_overrides(temp_mappings_dir)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Relaxed threshold for CI environments; typical local runs are <10ms
        assert elapsed_ms < 50, f"YAML loading took {elapsed_ms:.2f}ms, expected <50ms"


class TestGetFlatOverrides:
    """Test cases for get_flat_overrides convenience function."""

    def test_returns_plan_mappings_only(
        self, temp_mappings_dir, valid_plan_mappings, valid_name_mappings
    ):
        """Returns only plan priority mappings."""
        result = get_flat_overrides(temp_mappings_dir)
        assert result == {
            "FP0001": "614810477",
            "FP0002": "614810477",
            "FP0003": "610081428",
        }
        # Should not include name mappings
        assert "中国平安" not in result

    def test_returns_empty_dict_when_no_plan_file(self, temp_mappings_dir):
        """Returns empty dict when plan file doesn't exist."""
        result = get_flat_overrides(temp_mappings_dir)
        assert result == {}


class TestPriorityLevels:
    """Test cases for priority level constants."""

    def test_priority_levels_count(self):
        """There are exactly 5 priority levels."""
        assert len(PRIORITY_LEVELS) == 5

    def test_priority_levels_order(self):
        """Priority levels are in correct order."""
        assert PRIORITY_LEVELS == [
            "plan",
            "account",
            "hardcode",
            "name",
            "account_name",
        ]
