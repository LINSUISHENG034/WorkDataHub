"""
Tests for Annuity Domain Configuration and Migration Validation.

Story 4.6: Annuity Domain Configuration and Documentation
AC-4.6.5: Configuration Validation Test

This module tests:
- Configuration loads successfully from config/data_sources.yml
- Configuration passes Epic 3 Story 3.0 schema validation
- Database migration applies cleanly (syntax validation)
- Migration is idempotent
- Table schema matches Gold schema expectations
"""

import ast
import importlib.util
from pathlib import Path

import pytest
import yaml

from src.work_data_hub.config.schema import (
    DataSourceConfigV2,
    DataSourcesValidationError,
    DomainConfigV2,
    get_domain_config_v2,
    validate_data_sources_config_v2,
)


# =============================================================================
# AC-4.6.5: Configuration Loading Tests
# =============================================================================


class TestAnnuityConfigLoading:
    """Test annuity domain configuration loading and validation."""

    def test_config_file_exists(self):
        """Verify config/data_sources.yml exists."""
        config_path = Path("config/data_sources.yml")
        assert config_path.exists(), f"Configuration file not found: {config_path}"

    def test_config_loads_successfully(self):
        """AC-4.6.5: Configuration loads successfully from config/data_sources.yml."""
        result = validate_data_sources_config_v2("config/data_sources.yml")
        assert result is True, "Configuration validation should pass"

    def test_annuity_domain_exists(self):
        """Verify annuity_performance domain is defined in configuration."""
        with open("config/data_sources.yml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert "domains" in config, "Configuration must have 'domains' section"
        assert (
            "annuity_performance" in config["domains"]
        ), "annuity_performance domain must be defined"

    def test_annuity_domain_config_validates(self):
        """AC-4.6.5: Configuration passes Epic 3 Story 3.0 schema validation."""
        config = get_domain_config_v2("annuity_performance", "config/data_sources.yml")

        assert isinstance(config, DomainConfigV2)
        assert config.base_path is not None
        assert len(config.file_patterns) > 0
        assert config.sheet_name is not None
        assert config.version_strategy in ["highest_number", "latest_modified", "manual"]
        assert config.fallback in ["error", "use_latest_modified"]


class TestAnnuityConfigFields:
    """Test specific field values in annuity configuration."""

    @pytest.fixture
    def annuity_config(self):
        """Load annuity domain configuration."""
        return get_domain_config_v2("annuity_performance", "config/data_sources.yml")

    def test_base_path_has_template_variable(self, annuity_config):
        """Verify base_path contains {YYYYMM} template variable."""
        assert "{YYYYMM}" in annuity_config.base_path, (
            "base_path should contain {YYYYMM} template variable"
        )

    def test_file_patterns_not_empty(self, annuity_config):
        """Verify at least one file pattern is defined."""
        assert len(annuity_config.file_patterns) >= 1, (
            "At least one file pattern must be defined"
        )

    def test_exclude_patterns_include_temp_files(self, annuity_config):
        """Verify exclude_patterns includes Excel temp files."""
        assert "~$*" in annuity_config.exclude_patterns, (
            "exclude_patterns should include '~$*' for Excel temp files"
        )

    def test_sheet_name_is_规模明细(self, annuity_config):
        """Verify sheet_name is '规模明细' as per AC-4.6.1."""
        assert annuity_config.sheet_name == "规模明细", (
            "sheet_name should be '规模明细'"
        )

    def test_version_strategy_is_highest_number(self, annuity_config):
        """Verify version_strategy is 'highest_number' for V3 > V2 > V1 selection."""
        assert annuity_config.version_strategy == "highest_number", (
            "version_strategy should be 'highest_number'"
        )

    def test_fallback_is_error(self, annuity_config):
        """Verify fallback is 'error' for safe behavior."""
        assert annuity_config.fallback == "error", (
            "fallback should be 'error' for safe behavior"
        )


class TestConfigValidationErrors:
    """Test configuration validation catches invalid configs."""

    def test_invalid_version_strategy_rejected(self, tmp_path):
        """Verify invalid version_strategy is rejected."""
        invalid_config = {
            "schema_version": "1.0",
            "domains": {
                "test_domain": {
                    "base_path": "test/path/{YYYYMM}",
                    "file_patterns": ["*.xlsx"],
                    "sheet_name": "Sheet1",
                    "version_strategy": "invalid_strategy",  # Invalid
                    "fallback": "error",
                }
            },
        }

        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config_v2(str(config_path))

    def test_missing_file_patterns_rejected(self, tmp_path):
        """Verify missing file_patterns is rejected."""
        invalid_config = {
            "schema_version": "1.0",
            "domains": {
                "test_domain": {
                    "base_path": "test/path/{YYYYMM}",
                    # Missing file_patterns
                    "sheet_name": "Sheet1",
                    "version_strategy": "highest_number",
                    "fallback": "error",
                }
            },
        }

        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config_v2(str(config_path))

    def test_empty_file_patterns_rejected(self, tmp_path):
        """Verify empty file_patterns list is rejected."""
        invalid_config = {
            "schema_version": "1.0",
            "domains": {
                "test_domain": {
                    "base_path": "test/path/{YYYYMM}",
                    "file_patterns": [],  # Empty list
                    "sheet_name": "Sheet1",
                    "version_strategy": "highest_number",
                    "fallback": "error",
                }
            },
        }

        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config_v2(str(config_path))

    def test_path_traversal_rejected(self, tmp_path):
        """Verify path traversal in base_path is rejected (security)."""
        invalid_config = {
            "schema_version": "1.0",
            "domains": {
                "test_domain": {
                    "base_path": "../../../etc/passwd",  # Path traversal
                    "file_patterns": ["*.xlsx"],
                    "sheet_name": "Sheet1",
                    "version_strategy": "highest_number",
                    "fallback": "error",
                }
            },
        }

        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config_v2(str(config_path))

    def test_invalid_template_variable_rejected(self, tmp_path):
        """Verify invalid template variables are rejected (security)."""
        invalid_config = {
            "schema_version": "1.0",
            "domains": {
                "test_domain": {
                    "base_path": "test/{INVALID_VAR}/path",  # Invalid variable
                    "file_patterns": ["*.xlsx"],
                    "sheet_name": "Sheet1",
                    "version_strategy": "highest_number",
                    "fallback": "error",
                }
            },
        }

        config_path = tmp_path / "invalid_config.yml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(DataSourcesValidationError, match="validation failed"):
            validate_data_sources_config_v2(str(config_path))


# =============================================================================
# AC-4.6.2: Database Migration Tests
# =============================================================================


class TestAnnuityMigration:
    """Test annuity_performance_NEW database migration."""

    MIGRATION_PATH = Path(
        "io/schema/migrations/versions/20251129_000001_create_annuity_performance_new.py"
    )

    def test_migration_file_exists(self):
        """Verify migration file exists."""
        assert self.MIGRATION_PATH.exists(), (
            f"Migration file not found: {self.MIGRATION_PATH}"
        )

    def test_migration_syntax_valid(self):
        """Verify migration file has valid Python syntax."""
        with open(self.MIGRATION_PATH, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"Migration file has syntax error: {e}")

    def test_migration_has_required_attributes(self):
        """Verify migration has revision, down_revision, upgrade, downgrade."""
        spec = importlib.util.spec_from_file_location("migration", self.MIGRATION_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert hasattr(module, "revision"), "Migration must have 'revision' attribute"
        assert hasattr(module, "down_revision"), "Migration must have 'down_revision'"
        assert hasattr(module, "upgrade"), "Migration must have 'upgrade' function"
        assert hasattr(module, "downgrade"), "Migration must have 'downgrade' function"
        assert callable(module.upgrade), "'upgrade' must be callable"
        assert callable(module.downgrade), "'downgrade' must be callable"

    def test_migration_revision_format(self):
        """Verify migration revision follows naming convention."""
        spec = importlib.util.spec_from_file_location("migration", self.MIGRATION_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Revision should be in format YYYYMMDD_NNNNNN
        assert module.revision.startswith("2025"), "Revision should start with year"
        assert "_" in module.revision, "Revision should contain underscore separator"

    def test_migration_down_revision_links_to_previous(self):
        """Verify migration links to previous migration."""
        spec = importlib.util.spec_from_file_location("migration", self.MIGRATION_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Should link to the core tables migration
        assert module.down_revision == "20251113_000001", (
            "down_revision should link to core tables migration"
        )


class TestMigrationSchemaDefinition:
    """Test migration defines correct table schema."""

    @pytest.fixture
    def migration_source(self):
        """Load migration source code."""
        migration_path = Path(
            "io/schema/migrations/versions/20251129_000001_create_annuity_performance_new.py"
        )
        with open(migration_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_creates_annuity_performance_new_table(self, migration_source):
        """Verify migration creates annuity_performance_new table."""
        assert "annuity_performance_new" in migration_source.lower(), (
            "Migration should create annuity_performance_new table"
        )

    def test_defines_composite_primary_key(self, migration_source):
        """Verify migration defines composite PK: (reporting_month, plan_code, company_id)."""
        assert "reporting_month" in migration_source
        assert "plan_code" in migration_source
        assert "company_id" in migration_source
        assert "PrimaryKeyConstraint" in migration_source

    def test_defines_check_constraints(self, migration_source):
        """Verify migration defines CHECK constraints for non-negative assets."""
        assert "CheckConstraint" in migration_source
        assert "starting_assets >= 0" in migration_source
        assert "ending_assets >= 0" in migration_source

    def test_defines_indexes(self, migration_source):
        """Verify migration creates required indexes."""
        assert "create_index" in migration_source
        assert "reporting_month" in migration_source
        assert "company_id" in migration_source

    def test_defines_audit_columns(self, migration_source):
        """Verify migration includes audit columns."""
        assert "pipeline_run_id" in migration_source
        assert "created_at" in migration_source
        assert "updated_at" in migration_source

    def test_migration_is_idempotent(self, migration_source):
        """Verify migration checks for existing table (idempotent)."""
        # Migration should check if table exists before creating
        assert "get_table_names" in migration_source or "inspector" in migration_source, (
            "Migration should check for existing table to be idempotent"
        )


# =============================================================================
# AC-4.6.3 & AC-4.6.4: Documentation Tests
# =============================================================================


class TestDocumentation:
    """Test documentation files exist and have required content."""

    def test_domain_documentation_exists(self):
        """Verify domain documentation file exists."""
        doc_path = Path("docs/domains/annuity_performance.md")
        assert doc_path.exists(), f"Domain documentation not found: {doc_path}"

    def test_runbook_exists(self):
        """Verify operational runbook exists."""
        runbook_path = Path("docs/runbooks/annuity_performance.md")
        assert runbook_path.exists(), f"Runbook not found: {runbook_path}"

    def test_domain_doc_has_required_sections(self):
        """Verify domain documentation has required sections per AC-4.6.3."""
        doc_path = Path("docs/domains/annuity_performance.md")
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        required_sections = [
            "overview",
            "input format",
            "transformation",
            "output schema",
            "configuration",
        ]

        for section in required_sections:
            assert section in content, (
                f"Domain documentation missing required section: {section}"
            )

    def test_runbook_has_required_sections(self):
        """Verify runbook has required sections per AC-4.6.4."""
        runbook_path = Path("docs/runbooks/annuity_performance.md")
        with open(runbook_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        required_sections = [
            "manual execution",
            "common errors",
            "verification",
            "rollback",
        ]

        for section in required_sections:
            assert section in content, (
                f"Runbook missing required section: {section}"
            )


# =============================================================================
# Integration Tests
# =============================================================================


class TestAnnuityConfigIntegration:
    """Integration tests for annuity configuration."""

    def test_full_config_validation_workflow(self):
        """Test complete configuration validation workflow."""
        # 1. Validate entire config file
        assert validate_data_sources_config_v2("config/data_sources.yml") is True

        # 2. Get specific domain config
        config = get_domain_config_v2("annuity_performance", "config/data_sources.yml")

        # 3. Verify all required fields are present and valid
        assert config.base_path is not None
        assert len(config.file_patterns) > 0
        assert config.sheet_name == "规模明细"
        assert config.version_strategy == "highest_number"
        assert config.fallback == "error"

        # 4. Verify security constraints
        assert ".." not in config.base_path, "base_path should not contain path traversal"

    def test_config_matches_gold_schema_expectations(self):
        """Verify configuration aligns with AnnuityPerformanceOut model expectations."""
        config = get_domain_config_v2("annuity_performance", "config/data_sources.yml")

        # Sheet name should match what AnnuityPerformanceOut expects
        assert config.sheet_name == "规模明细"

        # File patterns should match annuity data files
        patterns_str = " ".join(config.file_patterns)
        assert "年金" in patterns_str or "xlsx" in patterns_str.lower()
