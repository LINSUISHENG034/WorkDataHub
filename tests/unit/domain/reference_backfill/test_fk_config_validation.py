"""
Unit tests for foreign key configuration validation models.

Tests the Pydantic models for foreign key backfill configuration,
including validation of required fields, optional columns, dependencies,
and error handling for invalid configurations.
"""

import pytest
from pydantic import ValidationError

from work_data_hub.domain.reference_backfill.models import (
    BackfillColumnMapping,
    ForeignKeyConfig,
    DomainForeignKeysConfig
)


class TestBackfillColumnMapping:
    """Test BackfillColumnMapping validation."""

    def test_valid_backfill_column_mapping(self):
        """Test valid backfill column mapping creation."""
        mapping = BackfillColumnMapping(
            source="计划代码",
            target="年金计划号",
            optional=False
        )
        assert mapping.source == "计划代码"
        assert mapping.target == "年金计划号"
        assert mapping.optional is False

    def test_optional_backfill_column_mapping(self):
        """Test backfill column mapping with optional field."""
        mapping = BackfillColumnMapping(
            source="计划名称",
            target="计划名称",
            optional=True
        )
        assert mapping.optional is True

    def test_empty_source_column(self):
        """Test validation fails for empty source column."""
        with pytest.raises(ValidationError) as exc_info:
            BackfillColumnMapping(
                source="",
                target="目标列"
            )
        assert "Column names must be non-empty strings" in str(exc_info.value)

    def test_empty_target_column(self):
        """Test validation fails for empty target column."""
        with pytest.raises(ValidationError) as exc_info:
            BackfillColumnMapping(
                source="源列",
                target="  "
            )
        assert "Column names must be non-empty strings" in str(exc_info.value)

    def test_whitespace_column_names(self):
        """Test whitespace in column names is trimmed."""
        mapping = BackfillColumnMapping(
            source="  计划代码  ",
            target="  年金计划号  "
        )
        assert mapping.source == "计划代码"
        assert mapping.target == "年金计划号"


class TestForeignKeyConfig:
    """Test ForeignKeyConfig validation."""

    def test_valid_foreign_key_config(self):
        """Test valid foreign key configuration creation."""
        fk_config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(source="计划名称", target="计划名称", optional=True)
            ]
        )
        assert fk_config.name == "fk_plan"
        assert fk_config.source_column == "计划代码"
        assert fk_config.target_table == "年金计划"
        assert fk_config.target_key == "年金计划号"
        assert len(fk_config.backfill_columns) == 2
        assert fk_config.mode == "insert_missing"
        assert fk_config.depends_on == []

    def test_foreign_key_config_with_dependencies(self):
        """Test foreign key configuration with dependencies."""
        fk_config = ForeignKeyConfig(
            name="fk_portfolio",
            source_column="组合代码",
            target_table="组合计划",
            target_key="组合代码",
            mode="fill_null_only",
            depends_on=["fk_plan"],
            backfill_columns=[
                BackfillColumnMapping(source="组合代码", target="组合代码"),
                BackfillColumnMapping(source="计划代码", target="年金计划号")
            ]
        )
        assert fk_config.mode == "fill_null_only"
        assert fk_config.depends_on == ["fk_plan"]

    def test_empty_foreign_key_name(self):
        """Test validation fails for empty foreign key name."""
        with pytest.raises(ValidationError) as exc_info:
            ForeignKeyConfig(
                name="",
                source_column="源列",
                target_table="目标表",
                target_key="主键",
                backfill_columns=[BackfillColumnMapping(source="a", target="b")]
            )
        assert "Foreign key name must be a non-empty string" in str(exc_info.value)

    def test_empty_source_column(self):
        """Test validation fails for empty source column."""
        with pytest.raises(ValidationError) as exc_info:
            ForeignKeyConfig(
                name="test_fk",
                source_column="  ",
                target_table="目标表",
                target_key="主键",
                backfill_columns=[BackfillColumnMapping(source="a", target="b")]
            )
        assert "Source column, target table, and target key must be non-empty strings" in str(exc_info.value)

    def test_empty_target_table(self):
        """Test validation fails for empty target table."""
        with pytest.raises(ValidationError) as exc_info:
            ForeignKeyConfig(
                name="test_fk",
                source_column="源列",
                target_table="",
                target_key="主键",
                backfill_columns=[BackfillColumnMapping(source="a", target="b")]
            )
        assert "Source column, target table, and target key must be non-empty strings" in str(exc_info.value)

    def test_empty_target_key(self):
        """Test validation fails for empty target key."""
        # Test with None - Pydantic v2 raises type error before custom validator
        with pytest.raises(ValidationError) as exc_info:
            ForeignKeyConfig(
                name="test_fk",
                source_column="源列",
                target_table="目标表",
                target_key=None,
                backfill_columns=[BackfillColumnMapping(source="a", target="b")]
            )
        assert "target_key" in str(exc_info.value)

        # Test with empty string - triggers custom validator
        with pytest.raises(ValidationError) as exc_info:
            ForeignKeyConfig(
                name="test_fk",
                source_column="源列",
                target_table="目标表",
                target_key="",
                backfill_columns=[BackfillColumnMapping(source="a", target="b")]
            )
        assert "Source column, target table, and target key must be non-empty strings" in str(exc_info.value)

    def test_empty_backfill_columns(self):
        """Test validation fails for empty backfill columns."""
        with pytest.raises(ValidationError) as exc_info:
            ForeignKeyConfig(
                name="test_fk",
                source_column="源列",
                target_table="目标表",
                target_key="主键",
                backfill_columns=[]
            )
        assert "At least one backfill column mapping must be provided" in str(exc_info.value)

    def test_invalid_mode(self):
        """Test validation fails for invalid mode."""
        with pytest.raises(ValidationError) as exc_info:
            ForeignKeyConfig(
                name="test_fk",
                source_column="源列",
                target_table="目标表",
                target_key="主键",
                mode="invalid_mode",
                backfill_columns=[BackfillColumnMapping(source="a", target="b")]
            )
        assert "Input should be" in str(exc_info.value)  # Pydantic v2 error message

    def test_whitespace_identifiers(self):
        """Test whitespace in identifiers is trimmed."""
        fk_config = ForeignKeyConfig(
            name="  test_fk  ",
            source_column="  源列  ",
            target_table="  目标表  ",
            target_key="  主键  ",
            backfill_columns=[BackfillColumnMapping(source="a", target="b")]
        )
        assert fk_config.name == "test_fk"
        assert fk_config.source_column == "源列"
        assert fk_config.target_table == "目标表"
        assert fk_config.target_key == "主键"


class TestDomainForeignKeysConfig:
    """Test DomainForeignKeysConfig validation."""

    def test_empty_domain_config(self):
        """Test empty domain configuration."""
        config = DomainForeignKeysConfig()
        assert config.foreign_keys == []

    def test_domain_config_with_multiple_fks(self):
        """Test domain configuration with multiple foreign keys."""
        fk_plan = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[BackfillColumnMapping(source="计划代码", target="年金计划号")]
        )

        fk_portfolio = ForeignKeyConfig(
            name="fk_portfolio",
            source_column="组合代码",
            target_table="组合计划",
            target_key="组合代码",
            depends_on=["fk_plan"],
            backfill_columns=[
                BackfillColumnMapping(source="组合代码", target="组合代码"),
                BackfillColumnMapping(source="计划代码", target="年金计划号")
            ]
        )

        config = DomainForeignKeysConfig(foreign_keys=[fk_plan, fk_portfolio])
        assert len(config.foreign_keys) == 2
        assert config.foreign_keys[0].name == "fk_plan"
        assert config.foreign_keys[1].name == "fk_portfolio"

    def test_duplicate_foreign_key_names(self):
        """Test validation fails for duplicate foreign key names."""
        fk1 = ForeignKeyConfig(
            name="duplicate_fk",
            source_column="源列1",
            target_table="目标表1",
            target_key="主键1",
            backfill_columns=[BackfillColumnMapping(source="a", target="b")]
        )

        fk2 = ForeignKeyConfig(
            name="duplicate_fk",
            source_column="源列2",
            target_table="目标表2",
            target_key="主键2",
            backfill_columns=[BackfillColumnMapping(source="c", target="d")]
        )

        with pytest.raises(ValidationError) as exc_info:
            DomainForeignKeysConfig(foreign_keys=[fk1, fk2])
        # Validator lists all occurrences of duplicate names
        assert "Duplicate foreign key names found:" in str(exc_info.value)
        assert "duplicate_fk" in str(exc_info.value)

    def test_domain_config_from_dict(self):
        """Test creating domain config from dictionary (YAML parsing scenario)."""
        config_dict = {
            "foreign_keys": [
                {
                    "name": "fk_plan",
                    "source_column": "计划代码",
                    "target_table": "年金计划",
                    "target_key": "年金计划号",
                    "mode": "insert_missing",
                    "depends_on": [],
                    "backfill_columns": [
                        {
                            "source": "计划代码",
                            "target": "年金计划号"
                        },
                        {
                            "source": "计划名称",
                            "target": "计划名称",
                            "optional": True
                        }
                    ]
                }
            ]
        }

        config = DomainForeignKeysConfig(**config_dict)
        assert len(config.foreign_keys) == 1
        fk = config.foreign_keys[0]
        assert fk.name == "fk_plan"
        assert len(fk.backfill_columns) == 2
        assert fk.backfill_columns[1].optional is True

    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden in configuration."""
        with pytest.raises(ValidationError) as exc_info:
            BackfillColumnMapping(
                source="源列",
                target="目标列",
                extra_field="not_allowed"
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)


