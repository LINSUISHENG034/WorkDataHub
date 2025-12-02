"""
Integration test to verify the major fixes are working correctly.

This test demonstrates that the two critical issues have been resolved:
1. Import path normalization (work_data_hub vs src.work_data_hub)
2. Factory method support (CleansingRuleStep.from_registry)
"""

import pytest
from unittest.mock import patch

from src.work_data_hub.domain.pipelines import build_pipeline


def test_major_issues_fixed():
    """
    Integration test that would have failed before the fixes.

    This test verifies that:
    1. Config-driven pipelines work with work_data_hub import paths
    2. Factory methods like CleansingRuleStep.from_registry work correctly
    """

    # This would have failed before due to import path mismatch
    with patch('work_data_hub.domain.pipelines.adapters.registry') as mock_registry:
        from work_data_hub.infrastructure.cleansing.registry import CleansingRule, RuleCategory

        # Mock the registry
        mock_rule = CleansingRule(
            name="test_rule",
            category=RuleCategory.NUMERIC,
            func=lambda x: str(x) + "_cleaned",
            description="Test cleaning rule"
        )
        mock_registry.get_rule.return_value = mock_rule

        # Configuration that would have failed before both fixes:
        # 1. Uses work_data_hub import path (not src.work_data_hub)
        # 2. Uses .from_registry factory method
        config = {
            "name": "integration_test_pipeline",
            "steps": [
                {
                    "name": "registry_cleansing_step",
                    "import_path": "work_data_hub.domain.pipelines.adapters.CleansingRuleStep.from_registry",
                    "options": {
                        "rule_name": "test_rule",
                        "target_fields": ["test_field"]
                    }
                }
            ],
            "stop_on_error": True
        }

        # This would have raised PipelineAssemblyError before the fixes
        pipeline = build_pipeline(config)

        # Verify the pipeline was built correctly
        assert len(pipeline.steps) == 1
        step = pipeline.steps[0]
        assert step.name == "test_rule"

        # Test execution works
        test_data = {"test_field": "input_value", "other_field": "unchanged"}
        result = pipeline.execute(test_data)

        # Verify the transformation was applied
        assert result.row["test_field"] == "input_value_cleaned"
        assert result.row["other_field"] == "unchanged"
        assert len(result.errors) == 0


if __name__ == "__main__":
    test_major_issues_fixed()
    print("✅ All major issues have been fixed!")