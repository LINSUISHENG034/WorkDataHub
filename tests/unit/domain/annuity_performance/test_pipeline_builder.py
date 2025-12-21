"""
Unit tests for pipeline_builder module.

Story 5.7: Refactor AnnuityPerformanceService to Lightweight Orchestrator
AC 5.7.3: Create Pipeline Builder Module

Tests:
- build_bronze_to_silver_pipeline() creates valid pipeline
- CompanyIdResolutionStep resolves company IDs correctly
- Pipeline executes all steps in order
- Integration with infrastructure transforms
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from work_data_hub.domain.annuity_performance.pipeline_builder import (
    CompanyIdResolutionStep,
    build_bronze_to_silver_pipeline,
    load_plan_override_mapping,
)
from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.enrichment import EqcLookupConfig
from work_data_hub.infrastructure.transforms import Pipeline


def make_context(pipeline_name: str = "test_pipeline") -> PipelineContext:
    """Helper to create a valid PipelineContext for testing."""
    return PipelineContext(
        pipeline_name=pipeline_name,
        execution_id="test-run-001",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_performance"},
    )


class TestBuildBronzeToSilverPipeline:
    """Tests for build_bronze_to_silver_pipeline function."""

    def test_returns_pipeline_instance(self):
        """Pipeline builder returns a Pipeline instance."""
        pipeline = build_bronze_to_silver_pipeline(eqc_config=EqcLookupConfig.disabled())
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_has_expected_steps(self):
        """Pipeline contains all expected transformation steps."""
        pipeline = build_bronze_to_silver_pipeline(eqc_config=EqcLookupConfig.disabled())

        # Should include all documented steps (7+) plus recent additions
        assert len(pipeline.steps) >= 7

        # Verify step names (case-insensitive check)
        step_names = [s.name.lower() for s in pipeline.steps]
        assert any("mapping" in name for name in step_names)  # Column renaming
        assert "company_id_resolution" in step_names
        assert any("drop" in name for name in step_names)  # Legacy column removal

    def test_pipeline_with_enrichment_service(self):
        """Pipeline accepts optional enrichment service."""
        # Mock enrichment service
        mock_enrichment = None  # Would be a mock in real test

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled(),
            enrichment_service=mock_enrichment,
            plan_override_mapping={"FP0001": "614810477"},
        )

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) >= 7

    def test_pipeline_with_plan_override_mapping(self):
        """Pipeline uses plan override mapping for company ID resolution."""
        mapping = {"FP0001": "614810477", "FP0002": "123456789"}

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled(),
            plan_override_mapping=mapping,
        )

        # Find the CompanyIdResolutionStep
        resolution_step = None
        for step in pipeline.steps:
            if step.name == "company_id_resolution":
                resolution_step = step
                break

        assert resolution_step is not None
        assert isinstance(resolution_step, CompanyIdResolutionStep)


class TestCompanyIdResolutionStep:
    """Tests for CompanyIdResolutionStep."""

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame(
            {
                "计划代码": ["FP0001", "FP0002", "UNKNOWN"],
                "客户名称": ["公司A", "公司B", "公司C"],
                "年金账户名": ["账户1", "账户2", "账户3"],
                "公司代码": [None, "EXISTING123", None],
            }
        )

    @pytest.fixture
    def context(self):
        """Create pipeline context for testing."""
        return make_context("test_pipeline")

    def test_step_name(self):
        """Step has correct name."""
        step = CompanyIdResolutionStep(eqc_config=EqcLookupConfig.disabled())
        assert step.name == "company_id_resolution"

    def test_resolves_via_plan_override(self, sample_df, context):
        """Step resolves company ID via plan override mapping."""
        step = CompanyIdResolutionStep(
            eqc_config=EqcLookupConfig.disabled(),
            plan_override_mapping={"FP0001": "614810477"},
        )

        result_df = step.apply(sample_df, context)

        assert "company_id" in result_df.columns
        assert result_df.loc[0, "company_id"] == "614810477"

    def test_preserves_existing_company_id(self, context):
        """Step preserves existing company_id values when no YAML override exists."""
        # Use a plan_code that is NOT in YAML mappings to test existing column passthrough
        df = pd.DataFrame(
            {
                "计划代码": ["UNMAPPED_PLAN"],
                "客户名称": ["公司B"],
                "年金账户名": ["账户2"],
                "公司代码": ["EXISTING123"],
            }
        )
        step = CompanyIdResolutionStep(eqc_config=EqcLookupConfig.disabled())

        result_df = step.apply(df, context)

        # Row 0 has existing company_id "EXISTING123" and no YAML override
        assert result_df.loc[0, "company_id"] == "EXISTING123"

    def test_generates_temp_id_for_unresolved(self, sample_df, context):
        """Step generates temp ID for unresolved rows."""
        step = CompanyIdResolutionStep(eqc_config=EqcLookupConfig.disabled())

        result_df = step.apply(sample_df, context)

        # Row 2 (UNKNOWN plan code, no existing ID) should get temp ID
        temp_id = result_df.loc[2, "company_id"]
        assert temp_id is not None
        assert temp_id.startswith("IN_")

    def test_temp_id_is_deterministic(self, sample_df, context):
        """Same customer name produces same temp ID."""
        step = CompanyIdResolutionStep(eqc_config=EqcLookupConfig.disabled())

        result1 = step.apply(sample_df.copy(), context)
        result2 = step.apply(sample_df.copy(), context)

        # Same customer name should produce same temp ID
        assert result1.loc[2, "company_id"] == result2.loc[2, "company_id"]


class TestLoadPlanOverrideMapping:
    """Tests for load_plan_override_mapping function."""

    def test_returns_empty_dict_for_missing_file(self, tmp_path):
        """Returns empty dict when mapping file doesn't exist."""
        result = load_plan_override_mapping(str(tmp_path / "nonexistent.yml"))
        assert result == {}

    def test_loads_valid_yaml_file(self, tmp_path):
        """Loads mapping from valid YAML file."""
        mapping_file = tmp_path / "test_mapping.yml"
        mapping_file.write_text(
            "plan_overrides:\n  FP0001: '614810477'\n  FP0002: '123456789'\n"
        )

        result = load_plan_override_mapping(str(mapping_file))

        assert result == {"FP0001": "614810477", "FP0002": "123456789"}

    def test_returns_empty_dict_for_invalid_yaml(self, tmp_path):
        """Returns empty dict when YAML file is malformed."""
        mapping_file = tmp_path / "invalid.yml"
        mapping_file.write_text("invalid: yaml: content: [unclosed")

        result = load_plan_override_mapping(str(mapping_file))

        assert result == {}

    def test_returns_empty_dict_when_plan_overrides_key_missing(self, tmp_path):
        """Returns empty dict when plan_overrides key is missing."""
        mapping_file = tmp_path / "no_key.yml"
        mapping_file.write_text("other_key:\n  FP0001: '614810477'\n")

        result = load_plan_override_mapping(str(mapping_file))

        assert result == {}


class TestPipelineExecution:
    """Integration tests for pipeline execution."""

    @pytest.fixture
    def sample_bronze_df(self):
        """Create sample Bronze layer DataFrame."""
        return pd.DataFrame(
            {
                "月度": ["202411", "202411"],
                "计划代码": ["FP0001", "FP0002"],
                "客户名称": ["测试公司A", "测试公司B"],
                "年金账户名": ["账户A", "账户B"],
                "业务类型": ["企年投资", "职年受托"],
                "机构名称": ["北京", "上海"],
                "期初资产规模": [1000000.0, 2000000.0],
                "期末资产规模": [1100000.0, 2200000.0],
                "流失(含待遇支付)": [50000.0, 100000.0],
                "id": [1, 2],  # Legacy column to be dropped
                "备注": ["备注1", "备注2"],  # Legacy column to be dropped
            }
        )

    @pytest.fixture
    def context(self):
        """Create pipeline context."""
        return make_context("bronze_to_silver")

    def test_full_pipeline_execution(self, sample_bronze_df, context):
        """Pipeline executes all steps and produces valid output."""
        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled(),
            plan_override_mapping={"FP0001": "614810477"},
        )

        result_df = pipeline.execute(sample_bronze_df, context)

        # Verify company_id resolution
        assert "company_id" in result_df.columns
        assert result_df.loc[0, "company_id"] == "614810477"

        # Verify legacy columns dropped
        assert "id" not in result_df.columns
        assert "备注" not in result_df.columns

        # Verify column alias mapping applied
        assert "流失_含待遇支付" in result_df.columns

    def test_pipeline_preserves_data_integrity(self, sample_bronze_df, context):
        """Pipeline preserves original data values."""
        pipeline = build_bronze_to_silver_pipeline(eqc_config=EqcLookupConfig.disabled())

        result_df = pipeline.execute(sample_bronze_df, context)

        # Financial values should be preserved
        assert result_df.loc[0, "期初资产规模"] == 1000000.0
        assert result_df.loc[1, "期末资产规模"] == 2200000.0

        # Customer names should be preserved
        assert result_df.loc[0, "客户名称"] == "测试公司A"


class TestAnnuityAccountNumberDerivation:
    """Tests for 年金账户号 derivation from 集团企业客户号 (Story 6.2-P11).
    
    Verifies that Step 10 correctly copies the cleaned 集团企业客户号 value
    to 年金账户号 before the legacy column is dropped.
    """

    @pytest.fixture
    def context(self):
        """Create pipeline context for testing."""
        return make_context("test_pipeline")

    def test_annuity_account_number_derived_correctly(self, context):
        """集团企业客户号 'C12345' → 年金账户号 '12345'.
        
        Story 6.2-P11 T2.2: Verify the derivation chain:
        1. Step 9: 集团企业客户号.lstrip('C') → '12345'
        2. Step 10: 年金账户号 = 集团企业客户号.copy() → '12345'
        """
        df = pd.DataFrame({
            "月度": ["202510"],
            "计划代码": ["FP0001"],
            "客户名称": ["测试公司"],
            "业务类型": ["企年投资"],
            "机构名称": ["北京"],
            "集团企业客户号": ["C12345678"],  # Original value with "C" prefix
        })

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled(),
            plan_override_mapping={"FP0001": "614810477"},
        )
        result_df = pipeline.execute(df, context)

        # 年金账户号 should be derived from cleaned 集团企业客户号
        assert "年金账户号" in result_df.columns
        assert result_df.loc[0, "年金账户号"] == "12345678"

        # 集团企业客户号 should be dropped (legacy column)
        assert "集团企业客户号" not in result_df.columns

    def test_annuity_account_number_handles_missing_column(self, context):
        """Missing 集团企业客户号 → 年金账户号 is None.
        
        Story 6.2-P11 T2.2: Verify graceful handling when source column is missing.
        """
        df = pd.DataFrame({
            "月度": ["202510"],
            "计划代码": ["FP0001"],
            "客户名称": ["测试公司"],
            "业务类型": ["企年投资"],
            "机构名称": ["北京"],
            # 集团企业客户号 column intentionally missing
        })

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled(),
            plan_override_mapping={"FP0001": "614810477"},
        )
        result_df = pipeline.execute(df, context)

        # 年金账户号 column should exist but be None
        assert "年金账户号" in result_df.columns
        assert pd.isna(result_df.loc[0, "年金账户号"]) or result_df.loc[0, "年金账户号"] is None

    def test_annuity_account_number_handles_null_values(self, context):
        """集团企业客户号 with null → 年金账户号 is null.
        
        Verify that null/empty values are handled correctly.
        """
        df = pd.DataFrame({
            "月度": ["202510", "202510"],
            "计划代码": ["FP0001", "FP0002"],
            "客户名称": ["测试公司A", "测试公司B"],
            "业务类型": ["企年投资", "职年受托"],
            "机构名称": ["北京", "上海"],
            "集团企业客户号": ["C12345678", None],  # Mix of valid and null
        })

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled(),
            plan_override_mapping={"FP0001": "614810477"},
        )
        result_df = pipeline.execute(df, context)

        # First row should have valid value
        assert result_df.loc[0, "年金账户号"] == "12345678"
        # Second row should have null
        assert pd.isna(result_df.loc[1, "年金账户号"])
