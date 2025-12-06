"""
Tests for pipeline configuration and builder functionality.

This module tests configuration validation, pipeline assembly from configuration,
and the PipelineBuilder fluent API.
"""

import pytest
from unittest.mock import patch

from src.work_data_hub.domain.pipelines.builder import (
    build_pipeline,
    PipelineBuilder,
    _import_step_class_or_factory,
    _create_step_instance,
    _validate_step_dependencies,
)
from src.work_data_hub.domain.pipelines.pipeline_config import (
    PipelineConfig,
    StepConfig,
)
from src.work_data_hub.domain.pipelines.core import Pipeline
from src.work_data_hub.domain.pipelines.exceptions import PipelineAssemblyError


class TestStepConfigValidation:
    """Test StepConfig validation."""

    def test_step_config_valid_configuration(self):
        """Test valid step configuration."""
        config = StepConfig(
            name="test_step",
            import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
            options={"rule_name": "decimal_quantization", "precision": 2},
            requires=[],
        )

        assert config.name == "test_step"
        assert (
            config.import_path
            == "work_data_hub.domain.pipelines.adapters.CleansingRuleStep"
        )
        assert config.options["precision"] == 2
        assert config.requires == []

    def test_step_config_empty_name_validation(self):
        """Test step config validation for empty names."""
        with pytest.raises(ValueError, match="Step name cannot be empty"):
            StepConfig(
                name="",
                import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                options={},
            )

        with pytest.raises(ValueError, match="Step name cannot be empty"):
            StepConfig(
                name="   ",
                import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                options={},
            )

    def test_step_config_invalid_name_format(self):
        """Test step config validation for invalid name formats."""
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            StepConfig(
                name="invalid/name",
                import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                options={},
            )

        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            StepConfig(
                name="invalid name with spaces",
                import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                options={},
            )

    def test_step_config_valid_name_formats(self):
        """Test step config accepts valid name formats."""
        valid_names = ["step1", "step_name", "step-name", "StepName", "step123"]

        for name in valid_names:
            config = StepConfig(
                name=name,
                import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                options={},
            )
            assert config.name == name

    def test_step_config_empty_import_path_validation(self):
        """Test step config validation for empty import paths."""
        with pytest.raises(ValueError, match="Import path cannot be empty"):
            StepConfig(name="test_step", import_path="", options={})

    def test_step_config_invalid_import_path_format(self):
        """Test step config validation for invalid import path formats."""
        with pytest.raises(ValueError, match="must be a valid Python module"):
            StepConfig(name="test_step", import_path="invalid.path.", options={})

        with pytest.raises(ValueError, match="must be a valid Python module"):
            StepConfig(name="test_step", import_path=".invalid.path", options={})


class TestPipelineConfigValidation:
    """Test PipelineConfig validation."""

    def test_pipeline_config_valid_configuration(self):
        """Test valid pipeline configuration."""
        config = PipelineConfig(
            name="test_pipeline",
            steps=[
                StepConfig(
                    name="step1",
                    import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                    options={},
                )
            ],
            stop_on_error=True,
        )

        assert config.name == "test_pipeline"
        assert len(config.steps) == 1
        assert config.stop_on_error is True

    def test_pipeline_config_empty_name_validation(self):
        """Test pipeline config validation for empty names."""
        with pytest.raises(ValueError, match="Pipeline name cannot be empty"):
            PipelineConfig(
                name="",
                steps=[
                    StepConfig(
                        name="step1",
                        import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                        options={},
                    )
                ],
            )

    def test_pipeline_config_empty_steps_validation(self):
        """Test pipeline config validation for empty steps."""
        with pytest.raises(ValueError, match="Pipeline must have at least one step"):
            PipelineConfig(name="test_pipeline", steps=[])

    def test_pipeline_config_duplicate_step_names_validation(self):
        """Test pipeline config validation for duplicate step names."""
        with pytest.raises(ValueError, match="Duplicate step names found"):
            PipelineConfig(
                name="test_pipeline",
                steps=[
                    StepConfig(
                        name="duplicate_step",
                        import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                        options={},
                    ),
                    StepConfig(
                        name="duplicate_step",
                        import_path="work_data_hub.domain.pipelines.adapters.FieldMapperStep",
                        options={},
                    ),
                ],
            )

    def test_pipeline_config_invalid_dependencies_validation(self):
        """Test pipeline config validation for invalid step dependencies."""
        with pytest.raises(ValueError, match="requires 'nonexistent_step'"):
            PipelineConfig(
                name="test_pipeline",
                steps=[
                    StepConfig(
                        name="step1",
                        import_path="work_data_hub.domain.pipelines.adapters.CleansingRuleStep",
                        options={},
                        requires=["nonexistent_step"],
                    )
                ],
            )


class TestDynamicImportFunctionality:
    """Test dynamic import of step classes."""

    def test_import_step_class_success(self):
        """Test successful import of step class."""
        # Import our test step class
        step_class = _import_step_class_or_factory(
            "tests.domain.pipelines.conftest.UpperCaseStep"
        )

        from tests.domain.pipelines.conftest import UpperCaseStep

        assert step_class == UpperCaseStep

    def test_import_step_class_invalid_format(self):
        """Test import with invalid path format."""
        with pytest.raises(PipelineAssemblyError, match="Invalid import path format"):
            _import_step_class_or_factory("invalid_path")

    def test_import_step_class_module_not_found(self):
        """Test import with non-existent module."""
        with pytest.raises(PipelineAssemblyError, match="Could not import"):
            _import_step_class_or_factory("nonexistent.module.ClassName")

    def test_import_step_class_class_not_found(self):
        """Test import with non-existent class."""
        with pytest.raises(PipelineAssemblyError, match="Could not import"):
            _import_step_class_or_factory(
                "tests.domain.pipelines.conftest.NonexistentClass"
            )

    def test_import_step_class_not_transform_step(self):
        """Test import of class that doesn't inherit from TransformStep."""
        with pytest.raises(PipelineAssemblyError, match="must have a 'name' property"):
            _import_step_class_or_factory("builtins.str")

    def test_import_factory_method_success(self):
        """Test successful import of factory method."""
        # Test importing a factory method
        factory = _import_step_class_or_factory(
            "tests.domain.pipelines.conftest.MockTransformStep"
        )

        # Should return the class itself
        from tests.domain.pipelines.conftest import MockTransformStep

        assert factory == MockTransformStep

    def test_import_nonexistent_factory_method(self):
        """Test import of non-existent factory method."""
        with pytest.raises(PipelineAssemblyError, match="Could not import"):
            _import_step_class_or_factory(
                "tests.domain.pipelines.conftest.UpperCaseStep.nonexistent_method"
            )

    def test_create_step_instance_success(self):
        """Test successful step instance creation."""
        config = StepConfig(
            name="uppercase",
            import_path="tests.domain.pipelines.conftest.UpperCaseStep",
            options={"fields": ["name", "description"]},
        )

        step = _create_step_instance(config)

        assert step.name == "uppercase"
        assert step.fields == ["name", "description"]

    def test_create_step_instance_import_failure(self):
        """Test step instance creation with import failure."""
        config = StepConfig(
            name="failing_step", import_path="nonexistent.module.ClassName", options={}
        )

        with pytest.raises(
            PipelineAssemblyError, match="Failed to create step 'failing_step'"
        ):
            _create_step_instance(config)


class TestDependencyValidation:
    """Test step dependency validation."""

    def test_validate_step_dependencies_success(self):
        """Test successful dependency validation."""
        steps = [
            StepConfig(
                name="step1",
                import_path="tests.domain.pipelines.conftest.UpperCaseStep",
                options={},
                requires=[],
            ),
            StepConfig(
                name="step2",
                import_path="tests.domain.pipelines.conftest.TrimStep",
                options={},
                requires=["step1"],
            ),
            StepConfig(
                name="step3",
                import_path="tests.domain.pipelines.conftest.UpperCaseStep",
                options={},
                requires=["step1", "step2"],
            ),
        ]

        # Should not raise any exception
        _validate_step_dependencies(steps)

    def test_validate_step_dependencies_missing_dependency(self):
        """Test dependency validation with missing dependency."""
        steps = [
            StepConfig(
                name="step1",
                import_path="tests.domain.pipelines.conftest.UpperCaseStep",
                options={},
                requires=["nonexistent_step"],
            )
        ]

        with pytest.raises(PipelineAssemblyError, match="requires 'nonexistent_step'"):
            _validate_step_dependencies(steps)

    def test_validate_step_dependencies_wrong_order(self):
        """Test dependency validation with wrong step order."""
        steps = [
            StepConfig(
                name="step1",
                import_path="tests.domain.pipelines.conftest.UpperCaseStep",
                options={},
                requires=["step2"],  # step2 comes after step1
            ),
            StepConfig(
                name="step2",
                import_path="tests.domain.pipelines.conftest.TrimStep",
                options={},
                requires=[],
            ),
        ]

        with pytest.raises(PipelineAssemblyError, match="is defined after"):
            _validate_step_dependencies(steps)


class TestPipelineBuilder:
    """Test PipelineBuilder fluent API."""

    def test_pipeline_builder_fluent_api(self, mock_steps, sample_config):
        """Test pipeline builder fluent API."""
        builder = PipelineBuilder()
        pipeline = (
            builder.add_step(mock_steps[0])
            .add_step(mock_steps[1])
            .with_config(sample_config)
            .build()
        )

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) == 2
        assert pipeline.config == sample_config

    def test_pipeline_builder_build_without_config(self, mock_steps):
        """Test pipeline builder build without configuration."""
        builder = PipelineBuilder()
        builder.add_step(mock_steps[0])

        with pytest.raises(
            PipelineAssemblyError, match="Pipeline configuration is required"
        ):
            builder.build()

    def test_pipeline_builder_build_without_steps(self, sample_config):
        """Test pipeline builder build without steps."""
        builder = PipelineBuilder()
        builder.with_config(sample_config)

        with pytest.raises(
            PipelineAssemblyError, match="Pipeline must have at least one step"
        ):
            builder.build()


class TestFactoryMethodSupport:
    """Test factory method support in pipeline building."""

    def test_build_pipeline_with_registry_factory_method(self):
        """Test building pipeline with CleansingRuleStep.from_registry factory method."""
        with patch(
            "src.work_data_hub.domain.pipelines.adapters.registry"
        ) as mock_registry:
            from work_data_hub.infrastructure.cleansing.registry import (
                CleansingRule,
                RuleCategory,
            )

            # Mock the registry to return a test rule
            mock_rule = CleansingRule(
                name="test_rule",
                category=RuleCategory.NUMERIC,
                func=lambda x: x,
                description="Test rule",
            )
            mock_registry.get_rule.return_value = mock_rule

            config = {
                "name": "test_pipeline_with_factory",
                "steps": [
                    {
                        "name": "cleansing_step",
                        "import_path": "src.work_data_hub.domain.pipelines.adapters.CleansingRuleStep.from_registry",
                        "options": {
                            "rule_name": "test_rule",
                            "target_fields": ["field1"],
                        },
                    }
                ],
                "stop_on_error": True,
            }

            pipeline = build_pipeline(config)

            assert isinstance(pipeline, Pipeline)
            assert len(pipeline.steps) == 1
            assert pipeline.steps[0].name == "test_rule"

            # Test execution
            result = pipeline.execute({"field1": "test_value"})
            assert "field1" in result.row


class TestBuildPipelineFunction:
    """Test the main build_pipeline function."""

    def test_build_pipeline_from_dict_config(self, sample_config_dict):
        """Test building pipeline from dictionary configuration."""
        with patch(
            "src.work_data_hub.domain.pipelines.builder._create_step_instance"
        ) as mock_create:
            from tests.domain.pipelines.conftest import UpperCaseStep, TrimStep

            mock_create.side_effect = [UpperCaseStep(), TrimStep()]

            pipeline = build_pipeline(sample_config_dict)

            assert isinstance(pipeline, Pipeline)
            assert pipeline.config.name == "test_pipeline"
            assert len(pipeline.steps) == 2

    def test_build_pipeline_from_config_object(self, sample_config):
        """Test building pipeline from PipelineConfig object."""
        with patch(
            "src.work_data_hub.domain.pipelines.builder._create_step_instance"
        ) as mock_create:
            from tests.domain.pipelines.conftest import UpperCaseStep, TrimStep

            mock_create.side_effect = [UpperCaseStep(), TrimStep()]

            pipeline = build_pipeline(sample_config)

            assert isinstance(pipeline, Pipeline)
            assert pipeline.config.name == "test_pipeline"
            assert len(pipeline.steps) == 2

    def test_build_pipeline_with_provided_steps(self, sample_config_dict, mock_steps):
        """Test building pipeline with pre-built steps."""
        pipeline = build_pipeline(sample_config_dict, steps=mock_steps[:2])

        assert isinstance(pipeline, Pipeline)
        assert pipeline.steps == mock_steps[:2]
        assert pipeline.config.name == "test_pipeline"

    def test_build_pipeline_step_count_mismatch(self, sample_config_dict, mock_steps):
        """Test building pipeline with mismatched step count."""
        with pytest.raises(PipelineAssemblyError, match="Step count mismatch"):
            build_pipeline(
                sample_config_dict, steps=mock_steps[:1]
            )  # Config expects 2 steps

    def test_build_pipeline_invalid_config_dict(self):
        """Test building pipeline with invalid configuration dictionary."""
        invalid_config = {
            "name": "",  # Invalid empty name
            "steps": [],
        }

        with pytest.raises(
            PipelineAssemblyError, match="Invalid pipeline configuration"
        ):
            build_pipeline(invalid_config)

    def test_build_pipeline_real_step_integration(self):
        """Test building pipeline with real step classes."""
        config = {
            "name": "text_processing",
            "steps": [
                {
                    "name": "uppercase",
                    "import_path": "tests.domain.pipelines.conftest.UpperCaseStep",
                    "options": {"fields": ["name"]},
                },
                {
                    "name": "trim",
                    "import_path": "tests.domain.pipelines.conftest.TrimStep",
                    "options": {"fields": ["name"]},
                },
            ],
            "stop_on_error": True,
        }

        pipeline = build_pipeline(config)

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) == 2
        assert pipeline.steps[0].name == "uppercase"
        assert pipeline.steps[1].name == "trim"

        # Test execution
        result = pipeline.execute({"name": "  test  "})
        assert result.row["name"] == "TEST"  # Uppercased first, then trimmed
