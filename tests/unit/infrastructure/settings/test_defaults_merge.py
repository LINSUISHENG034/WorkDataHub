"""
Unit tests for Story 6.2-P14 AC-4: Defaults/Overrides mechanism.

Tests the _merge_with_defaults() function and defaults merge via get_domain_config_v2().
"""

from pathlib import Path
import pytest

from work_data_hub.infrastructure.settings.data_source_schema import (
    _merge_with_defaults,
    get_domain_config_v2,
    DataSourcesValidationError,
)


class TestMergeWithDefaults:
    """Test suite for _merge_with_defaults function."""

    def test_scalar_domain_wins(self):
        """AC: Domain scalar values should override defaults."""
        defaults = {"version_strategy": "highest_number", "fallback": "error"}
        domain = {"version_strategy": "manual"}

        result = _merge_with_defaults(domain, defaults)

        assert result["version_strategy"] == "manual"
        assert result["fallback"] == "error"  # Inherited from defaults

    def test_scalar_new_key_added(self):
        """AC: Domain-only keys should be added to result."""
        defaults = {"fallback": "error"}
        domain = {"base_path": "/some/path", "sheet_name": "Sheet1"}

        result = _merge_with_defaults(domain, defaults)

        assert result["fallback"] == "error"
        assert result["base_path"] == "/some/path"
        assert result["sheet_name"] == "Sheet1"

    def test_list_replace_default(self):
        """AC: List without + prefix should replace defaults."""
        defaults = {"file_patterns": ["*.xlsx"]}
        domain = {"file_patterns": ["*规模*.xlsx", "*收入*.xlsx"]}

        result = _merge_with_defaults(domain, defaults)

        assert result["file_patterns"] == ["*规模*.xlsx", "*收入*.xlsx"]

    def test_list_extend_with_plus_prefix(self):
        """AC: '+pattern' should append to defaults, not replace."""
        defaults = {"exclude_patterns": ["~$*", "*.eml"]}
        domain = {"exclude_patterns": ["+*回复*", "+*.tmp"]}

        result = _merge_with_defaults(domain, defaults)

        assert result["exclude_patterns"] == ["~$*", "*.eml", "*回复*", "*.tmp"]

    def test_list_mixed_replace_and_extend(self):
        """AC: Mix of + and non-+ items should work correctly."""
        defaults = {"exclude_patterns": ["~$*", "*.eml"]}
        domain = {"exclude_patterns": ["*.old", "+*回复*"]}

        result = _merge_with_defaults(domain, defaults)

        # Replace items first, then extends
        assert result["exclude_patterns"] == ["*.old", "*回复*"]

    def test_list_empty_clears_defaults(self):
        """AC: Empty list should clear defaults."""
        defaults = {"exclude_patterns": ["~$*", "*.eml"]}
        domain = {"exclude_patterns": []}

        result = _merge_with_defaults(domain, defaults)

        assert result["exclude_patterns"] == []

    def test_deep_merge_nested_dicts(self):
        """AC: output.table override should not lose output.schema_name."""
        defaults = {"output": {"schema_name": "business", "pk": ["id"]}}
        domain = {"output": {"table": "my_table"}}

        result = _merge_with_defaults(domain, defaults)

        assert result["output"]["table"] == "my_table"
        assert result["output"]["schema_name"] == "business"
        assert result["output"]["pk"] == ["id"]

    def test_deep_merge_override_nested(self):
        """AC: Domain nested values should override default nested values."""
        defaults = {"output": {"schema_name": "business"}}
        domain = {"output": {"schema_name": "sandbox", "table": "test"}}

        result = _merge_with_defaults(domain, defaults)

        assert result["output"]["schema_name"] == "sandbox"
        assert result["output"]["table"] == "test"

    def test_non_string_in_list_handled(self):
        """AC: Non-string items in list should not cause failures."""
        defaults = {"file_patterns": ["*.xlsx"]}
        domain = {"file_patterns": ["*.csv", 123]}  # 123 is not a string

        result = _merge_with_defaults(domain, defaults)

        # Non-string items are treated as regular replace items
        assert result["file_patterns"] == ["*.csv", 123]

    def test_no_defaults_returns_domain(self):
        """AC: Empty defaults should return domain config as-is."""
        defaults = {}
        domain = {"base_path": "/path", "file_patterns": ["*.xlsx"]}

        result = _merge_with_defaults(domain, defaults)

        assert result == domain

    def test_no_domain_returns_defaults(self):
        """AC: Empty domain config should return defaults."""
        defaults = {"version_strategy": "highest_number", "fallback": "error"}
        domain = {}

        result = _merge_with_defaults(domain, defaults)

        assert result == defaults


class TestGetDomainConfigV2DefaultsMerge:
    """Test suite for defaults merge behavior in get_domain_config_v2."""

    @pytest.fixture
    def sample_config_with_defaults(self, tmp_path: Path) -> Path:
        """Create a sample data_sources.yml with defaults."""
        config_content = """
schema_version: "1.1"

defaults:
  exclude_patterns:
    - "~$*"
    - "*.eml"
  version_strategy: "highest_number"
  fallback: "error"
  output:
    schema_name: "business"

domains:
  test_domain:
    base_path: "test/path/{YYYYMM}"
    file_patterns:
      - "*.xlsx"
    exclude_patterns:
      - "+*回复*"
    sheet_name: "Sheet1"
    output:
      table: "test_table"

  minimal_domain:
    base_path: "minimal/path"
    file_patterns:
      - "*.csv"
    sheet_name: 0
    output:
      table: "minimal_table"
"""
        config_path = tmp_path / "data_sources.yml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    def test_loads_with_defaults_merged(self, sample_config_with_defaults):
        """AC: Domain config should have defaults merged in."""
        config = get_domain_config_v2("test_domain", str(sample_config_with_defaults))

        # From defaults
        assert config.version_strategy == "highest_number"
        assert config.fallback == "error"

        # Extended (+ prefix)
        assert "~$*" in config.exclude_patterns
        assert "*.eml" in config.exclude_patterns
        assert "*回复*" in config.exclude_patterns

        # From domain
        assert config.base_path == "test/path/{YYYYMM}"
        assert config.sheet_name == "Sheet1"
        assert config.output.table == "test_table"
        assert config.output.schema_name == "business"  # From defaults

    def test_minimal_domain_inherits_all_defaults(self, sample_config_with_defaults):
        """AC: Minimal domain should inherit all defaults."""
        config = get_domain_config_v2(
            "minimal_domain", str(sample_config_with_defaults)
        )

        # All from defaults
        assert config.version_strategy == "highest_number"
        assert config.fallback == "error"
        assert config.exclude_patterns == ["~$*", "*.eml"]
        assert config.output.schema_name == "business"

        # From domain
        assert config.base_path == "minimal/path"

    def test_missing_domain_raises_error(self, sample_config_with_defaults):
        """AC: Unknown domain should raise clear error."""
        with pytest.raises(DataSourcesValidationError, match="not found"):
            get_domain_config_v2("nonexistent_domain", str(sample_config_with_defaults))

    def test_missing_file_raises_error(self):
        """AC: Missing config file should raise clear error."""
        with pytest.raises(DataSourcesValidationError, match="not found"):
            get_domain_config_v2("any_domain", "/nonexistent/path/config.yml")

    @pytest.fixture
    def config_without_defaults(self, tmp_path: Path) -> Path:
        """Create a sample data_sources.yml without defaults section."""
        config_content = """
schema_version: "1.0"

domains:
  legacy_domain:
    base_path: "legacy/path"
    file_patterns:
      - "*.xlsx"
    exclude_patterns:
      - "~$*"
    sheet_name: "Sheet1"
    version_strategy: "highest_number"
    fallback: "error"
    output:
      table: "legacy_table"
      schema_name: "public"
"""
        config_path = tmp_path / "data_sources_no_defaults.yml"
        config_path.write_text(config_content, encoding="utf-8")
        return config_path

    def test_works_without_defaults_section(self, config_without_defaults):
        """AC: Should work when defaults section is missing (backward compat)."""
        config = get_domain_config_v2("legacy_domain", str(config_without_defaults))

        assert config.base_path == "legacy/path"
        assert config.version_strategy == "highest_number"
        assert config.output.table == "legacy_table"
