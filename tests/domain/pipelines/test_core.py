"""
Tests for core pipeline execution and step orchestration.

This module tests the core Pipeline class, TransformStep interface,
and execution mechanics including step ordering, error handling,
and metrics collection.
"""

import pytest
from unittest.mock import Mock

from src.work_data_hub.domain.pipelines.core import Pipeline, TransformStep
from src.work_data_hub.domain.pipelines.config import PipelineConfig, StepConfig
from src.work_data_hub.domain.pipelines.exceptions import PipelineStepError
from src.work_data_hub.domain.pipelines.types import PipelineResult, StepResult


class TestTransformStepInterface:
    """Test the TransformStep abstract base class."""

    def test_transform_step_is_abstract(self):
        """Test that TransformStep cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TransformStep()

    def test_transform_step_requires_name_property(self):
        """Test that concrete steps must implement name property."""

        class IncompleteStep(TransformStep):
            def apply(self, row, context):
                return StepResult(row=row, warnings=[], errors=[], metadata={})

        with pytest.raises(TypeError):
            IncompleteStep()

    def test_transform_step_requires_apply_method(self):
        """Test that concrete steps must implement apply method."""

        class IncompleteStep(TransformStep):
            @property
            def name(self):
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteStep()


class TestPipelineInitialization:
    """Test Pipeline class initialization."""

    def test_pipeline_initialization(self, mock_steps, sample_config):
        """Test basic pipeline initialization."""
        pipeline = Pipeline(steps=mock_steps[:2], config=sample_config)

        assert pipeline.steps == mock_steps[:2]
        assert pipeline.config == sample_config
        assert hasattr(pipeline, 'logger')

    def test_pipeline_step_count_mismatch_warning(self, mock_steps, sample_config, caplog):
        """Test warning when step count doesn't match configuration."""
        # Create pipeline with different number of steps than config
        pipeline = Pipeline(steps=mock_steps[:1], config=sample_config)

        assert "Step count mismatch" in caplog.text


class TestPipelineExecution:
    """Test pipeline execution mechanics."""

    def test_pipeline_executes_steps_in_order(self, mock_steps):
        """Test that pipeline executes steps in declared order."""
        config = PipelineConfig(
            name="test_pipeline",
            steps=[
                StepConfig(name="step1", import_path="mock.Step1", options={}),
                StepConfig(name="step2", import_path="mock.Step2", options={}),
                StepConfig(name="step3", import_path="mock.Step3", options={})
            ],
            stop_on_error=True
        )

        pipeline = Pipeline(steps=mock_steps, config=config)
        result = pipeline.execute({"test": "data"})

        # Verify all steps were called
        assert all(step.call_count == 1 for step in mock_steps)

        # Verify execution order in metrics
        assert result.metrics.executed_steps == ["step1", "step2", "step3"]

        # Verify final row contains all transformations
        assert result.row["step1_value"] == "processed"
        assert result.row["step2_value"] == "processed"
        assert result.row["step3_value"] == "processed"

    def test_pipeline_preserves_row_immutability(self, mock_steps, sample_config):
        """Test that pipeline doesn't mutate original row."""
        original_row = {"name": "test", "value": 123}
        original_copy = original_row.copy()

        pipeline = Pipeline(steps=mock_steps[:1], config=sample_config)
        result = pipeline.execute(original_row)

        # Original row should be unchanged
        assert original_row == original_copy

        # Result should contain transformations
        assert "step1_value" in result.row
        assert result.row["name"] == "test"
        assert result.row["value"] == 123

    def test_pipeline_execution_with_context(self, mock_steps, sample_config):
        """Test pipeline execution with context parameter."""
        context = {"execution_id": "test_123", "debug": True}

        pipeline = Pipeline(steps=mock_steps[:1], config=sample_config)
        result = pipeline.execute({"test": "data"}, context=context)

        # Pipeline should execute successfully
        assert isinstance(result, PipelineResult)
        assert len(result.errors) == 0

    def test_pipeline_execution_without_context(self, mock_steps, sample_config):
        """Test pipeline execution without explicit context."""
        pipeline = Pipeline(steps=mock_steps[:1], config=sample_config)
        result = pipeline.execute({"test": "data"})

        # Pipeline should execute successfully with default context
        assert isinstance(result, PipelineResult)
        assert len(result.errors) == 0

    def test_pipeline_execution_metrics_collection(self, mock_steps, sample_config):
        """Test that pipeline collects execution metrics correctly."""
        pipeline = Pipeline(steps=mock_steps[:2], config=sample_config)
        result = pipeline.execute({"test": "data"})

        # Verify metrics are collected
        assert result.metrics.executed_steps == ["step1", "step2"]
        assert result.metrics.duration_ms >= 0  # Changed from > 0 to >= 0 since execution can be very fast
        assert isinstance(result.metrics.duration_ms, int)

    def test_pipeline_aggregates_warnings_and_errors(self, sample_config):
        """Test that pipeline aggregates warnings and errors from steps."""
        # Create steps that return warnings and errors
        warning_step = Mock(spec=TransformStep)
        warning_step.name = "warning_step"
        warning_step.apply.return_value = StepResult(
            row={"test": "data"},
            warnings=["Warning 1", "Warning 2"],
            errors=[],
            metadata={}
        )

        error_step = Mock(spec=TransformStep)
        error_step.name = "error_step"
        error_step.apply.return_value = StepResult(
            row={"test": "data"},
            warnings=["Warning 3"],
            errors=["Error 1"],
            metadata={}
        )

        config = PipelineConfig(
            name="test_pipeline",
            steps=[
                StepConfig(name="warning_step", import_path="mock.WarningStep", options={}),
                StepConfig(name="error_step", import_path="mock.ErrorStep", options={})
            ],
            stop_on_error=False  # Continue despite errors
        )

        pipeline = Pipeline(steps=[warning_step, error_step], config=config)
        result = pipeline.execute({"test": "data"})

        # Verify warnings and errors are aggregated
        assert result.warnings == ["Warning 1", "Warning 2", "Warning 3"]
        assert result.errors == ["Error 1"]


class TestPipelineErrorHandling:
    """Test pipeline error handling behavior."""

    def test_pipeline_stops_on_error_when_configured(self, mock_steps, failing_step):
        """Test that pipeline stops on first error when stop_on_error=True."""
        config = PipelineConfig(
            name="test_pipeline",
            steps=[
                StepConfig(name="step1", import_path="mock.Step1", options={}),
                StepConfig(name="failing_step", import_path="mock.FailingStep", options={}),
                StepConfig(name="step2", import_path="mock.Step2", options={})
            ],
            stop_on_error=True
        )

        steps = [mock_steps[0], failing_step, mock_steps[1]]
        pipeline = Pipeline(steps=steps, config=config)

        with pytest.raises(PipelineStepError, match="Test failure"):
            pipeline.execute({"test": "data"})

        # First step should have been called
        assert mock_steps[0].call_count == 1

        # Second step should not have been called due to failure
        assert mock_steps[1].call_count == 0

    def test_pipeline_continues_on_error_when_configured(self, mock_steps, failing_step):
        """Test that pipeline continues on error when stop_on_error=False."""
        config = PipelineConfig(
            name="test_pipeline",
            steps=[
                StepConfig(name="step1", import_path="mock.Step1", options={}),
                StepConfig(name="failing_step", import_path="mock.FailingStep", options={}),
                StepConfig(name="step2", import_path="mock.Step2", options={})
            ],
            stop_on_error=False
        )

        steps = [mock_steps[0], failing_step, mock_steps[1]]
        pipeline = Pipeline(steps=steps, config=config)

        result = pipeline.execute({"test": "data"})

        # All steps should have been attempted
        assert mock_steps[0].call_count == 1
        assert mock_steps[1].call_count == 1

        # Error should be recorded in result
        assert len(result.errors) == 1
        assert "failing_step" in result.errors[0]
        assert "Test failure" in result.errors[0]

        # Only successful steps should be in metrics
        assert result.metrics.executed_steps == ["step1", "step2"]

    def test_pipeline_handles_step_result_errors_with_stop_on_error(self, sample_config):
        """Test pipeline handles StepResult errors with stop_on_error=True."""
        error_step = Mock(spec=TransformStep)
        error_step.name = "error_step"
        error_step.apply.return_value = StepResult(
            row={"test": "data"},
            warnings=[],
            errors=["Step result error"],
            metadata={}
        )

        config = PipelineConfig(
            name="test_pipeline",
            steps=[StepConfig(name="error_step", import_path="mock.ErrorStep", options={})],
            stop_on_error=True
        )

        pipeline = Pipeline(steps=[error_step], config=config)

        with pytest.raises(PipelineStepError, match="Step result error"):
            pipeline.execute({"test": "data"})

    def test_pipeline_handles_step_result_errors_without_stop_on_error(self, sample_config):
        """Test pipeline handles StepResult errors with stop_on_error=False."""
        error_step = Mock(spec=TransformStep)
        error_step.name = "error_step"
        error_step.apply.return_value = StepResult(
            row={"test": "data"},
            warnings=[],
            errors=["Step result error"],
            metadata={}
        )

        config = PipelineConfig(
            name="test_pipeline",
            steps=[StepConfig(name="error_step", import_path="mock.ErrorStep", options={})],
            stop_on_error=False
        )

        pipeline = Pipeline(steps=[error_step], config=config)
        result = pipeline.execute({"test": "data"})

        # Error should be recorded but execution should continue
        assert result.errors == ["Step result error"]
        assert result.metrics.executed_steps == ["error_step"]


class TestRealStepExecution:
    """Test pipeline execution with real step implementations."""

    def test_pipeline_with_uppercase_and_trim_steps(self, sample_row):
        """Test pipeline execution with actual transformation steps."""
        from tests.domain.pipelines.conftest import UpperCaseStep, TrimStep

        steps = [
            TrimStep(fields=["name"]),  # First trim whitespace
            UpperCaseStep(fields=["name"])  # Then convert to uppercase
        ]

        config = PipelineConfig(
            name="text_processing",
            steps=[
                StepConfig(name="trim", import_path="tests.domain.pipelines.conftest.TrimStep", options={}),
                StepConfig(name="uppercase", import_path="tests.domain.pipelines.conftest.UpperCaseStep", options={})
            ],
            stop_on_error=True
        )

        pipeline = Pipeline(steps=steps, config=config)
        result = pipeline.execute(sample_row)

        # Verify transformation was applied correctly
        assert result.row["name"] == "TEST COMPANY"  # Trimmed and uppercased
        assert result.metrics.executed_steps == ["trim", "uppercase"]
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_pipeline_execution_empty_row(self, mock_steps, sample_config):
        """Test pipeline execution with empty input row."""
        pipeline = Pipeline(steps=mock_steps[:1], config=sample_config)
        result = pipeline.execute({})

        # Pipeline should handle empty row gracefully
        assert isinstance(result, PipelineResult)
        assert result.metrics.executed_steps == ["step1"]
        assert len(result.errors) == 0