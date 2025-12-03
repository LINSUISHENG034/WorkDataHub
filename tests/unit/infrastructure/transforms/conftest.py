"""Test fixtures for infrastructure/transforms tests."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from work_data_hub.domain.pipelines.types import PipelineContext


@pytest.fixture
def pipeline_context() -> PipelineContext:
    """Create a standard pipeline context for testing."""
    return PipelineContext(
        pipeline_name="test_pipeline",
        execution_id="test-001",
        timestamp=datetime.now(timezone.utc),
        config={},
    )


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        "old_col": ["value1", "value2", "value3"],
        "status": ["draft", "active", "draft"],
        "a": [10, 20, 30],
        "b": [5, 10, 15],
    })


@pytest.fixture
def empty_dataframe() -> pd.DataFrame:
    """Create an empty DataFrame for edge case testing."""
    return pd.DataFrame({"col1": [], "col2": []})
