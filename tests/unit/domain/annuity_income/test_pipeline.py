"""
Unit tests for AnnuityIncome pipeline_builder module.

Story 5.5.2: AnnuityIncome Domain Implementation
AC 4, 5, 6, 7: Uses infrastructure components and follows patterns

Tests:
- build_bronze_to_silver_pipeline() creates valid pipeline
- CompanyIdResolutionStep resolves company IDs correctly
- Pipeline executes all steps in order
- AnnuityIncome-specific transformations (组合代码 regex, etc.)
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

# Import Pipeline first to avoid circular import
from work_data_hub.infrastructure.transforms import Pipeline
from work_data_hub.domain.pipelines.types import PipelineContext

# Import from pipeline_builder module directly
from work_data_hub.domain.annuity_income.pipeline_builder import (
    CompanyIdResolutionStep,
    build_bronze_to_silver_pipeline,
    load_plan_override_mapping,
    _apply_portfolio_code_defaults,
)


def make_context(pipeline_name: str = "test_pipeline") -> PipelineContext:
    """Helper to create a valid PipelineContext for testing."""
    return PipelineContext(
        pipeline_name=pipeline_name,
        execution_id="test-run-001",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_income"},
    )


class TestBuildBronzeToSilverPipeline:
    """Tests for build_bronze_to_silver_pipeline function."""

    def test_returns_pipeline_instance(self):
        """Pipeline builder returns a Pipeline instance."""
        pipeline = build_bronze_to_silver_pipeline()
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_has_expected_steps(self):
        """Pipeline contains all expected transformation steps."""
        pipeline = build_bronze_to_silver_pipeline()

        # Should have 12 steps as documented in Story 5.5.2 Task 6
        assert len(pipeline.steps) == 12

        # Verify step names
        step_names = [s.name.lower() for s in pipeline.steps]
        assert any("mapping" in name for name in step_names)  # Column renaming
        assert "company_id_resolution" in step_names
        assert any("drop" in name for name in step_names)  # Legacy column removal
        assert any("cleansing" in name for name in step_names)  # CleansingStep

    def test_pipeline_with_enrichment_service(self):
        """Pipeline accepts optional enrichment service."""
        pipeline = build_bronze_to_silver_pipeline(
            enrichment_service=None,
            plan_override_mapping={"FP0001": "614810477"},
            sync_lookup_budget=10,
        )

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) == 12

    def test_pipeline_with_plan_override_mapping(self):
        """Pipeline uses plan override mapping for company ID resolution."""
        mapping = {"FP0001": "614810477", "FP0002": "123456789"}

        pipeline = build_bronze_to_silver_pipeline(
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


class TestApplyPortfolioCodeDefaults:
    """Tests for _apply_portfolio_code_defaults helper function."""

    def test_removes_f_prefix(self):
        """Removes 'F' prefix from portfolio codes."""
        df = pd.DataFrame({
            "组合代码": ["FQTAN001", "qtan002", "fqtan003"],
            "业务类型": ["企年投资", "企年投资", "企年投资"],
            "计划类型": ["单一计划", "单一计划", "单一计划"],
        })
        result = _apply_portfolio_code_defaults(df)
        assert result.iloc[0] == "QTAN001"
        assert result.iloc[1] == "QTAN002"
        assert result.iloc[2] == "QTAN003"

    def test_applies_qtan003_for_zhinian(self):
        """Applies QTAN003 for 职年受托/职年投资 business types."""
        df = pd.DataFrame({
            "组合代码": [None, None],
            "业务类型": ["职年受托", "职年投资"],
            "计划类型": ["单一计划", "单一计划"],
        })
        result = _apply_portfolio_code_defaults(df)
        assert result.iloc[0] == "QTAN003"
        assert result.iloc[1] == "QTAN003"

    def test_applies_default_based_on_plan_type(self):
        """Applies default portfolio code based on plan type."""
        df = pd.DataFrame({
            "组合代码": [None, None],
            "业务类型": ["企年投资", "企年投资"],
            "计划类型": ["集合计划", "单一计划"],
        })
        result = _apply_portfolio_code_defaults(df)
        assert result.iloc[0] == "QTAN001"
        assert result.iloc[1] == "QTAN002"

    def test_applies_default_for_professional_pension_plan_type(self):
        """职业年金 plan type should default when empty and not matched by business type."""
        df = pd.DataFrame({
            "组合代码": [None],
            "业务类型": ["企年投资"],
            "计划类型": ["职业年金"],
        })
        result = _apply_portfolio_code_defaults(df)
        assert result.iloc[0] == "QTAN003"

    def test_preserves_existing_codes(self):
        """Preserves existing non-empty portfolio codes."""
        df = pd.DataFrame({
            "组合代码": ["EXISTING", "ANOTHER"],
            "业务类型": ["企年投资", "职年受托"],
            "计划类型": ["单一计划", "单一计划"],
        })
        result = _apply_portfolio_code_defaults(df)
        assert result.iloc[0] == "EXISTING"
        assert result.iloc[1] == "ANOTHER"


class TestCompanyIdResolutionStep:
    """Tests for CompanyIdResolutionStep."""

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            "计划号": ["FP0001", "FP0002", "UNKNOWN"],
            "客户名称": ["公司A", "公司B", "公司C"],
            "年金账户名": ["账户1", "账户2", "账户3"],
        })

    @pytest.fixture
    def context(self):
        """Create pipeline context for testing."""
        return make_context("test_pipeline")

    def test_step_name(self):
        """Step has correct name."""
        step = CompanyIdResolutionStep()
        assert step.name == "company_id_resolution"

    def test_resolves_via_plan_override(self, sample_df, context):
        """Step resolves company ID via plan override mapping."""
        step = CompanyIdResolutionStep(
            plan_override_mapping={"FP0001": "614810477"},
        )

        result_df = step.apply(sample_df, context)

        assert "company_id" in result_df.columns
        assert result_df.loc[0, "company_id"] == "614810477"

    def test_generates_temp_id_for_unresolved(self, sample_df, context):
        """Step generates temp ID for unresolved rows."""
        step = CompanyIdResolutionStep()

        result_df = step.apply(sample_df, context)

        # Row 2 (UNKNOWN plan code) should get temp ID
        temp_id = result_df.loc[2, "company_id"]
        assert temp_id is not None
        assert temp_id.startswith("IN_")

    def test_temp_id_is_deterministic(self, sample_df, context):
        """Same customer name produces same temp ID."""
        step = CompanyIdResolutionStep()

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


class TestPipelineExecution:
    """Integration tests for pipeline execution."""

    @pytest.fixture
    def sample_bronze_df(self):
        """Create sample Bronze layer DataFrame for AnnuityIncome."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        return pd.DataFrame({
            "月度": ["202411", "202411"],
            "计划号": ["FP0001", "FP0002"],
            "客户名称": ["测试公司A", "测试公司B"],
            "年金账户名": ["账户A", "账户B"],
            "业务类型": ["企年投资", "职年受托"],
            "计划类型": ["单一计划", "单一计划"],
            "机构名称": ["北京", "上海"],
            "机构": ["北京", "上海"],  # Will be renamed to 机构代码
            "组合代码": ["FQTAN001", None],  # F prefix to remove, None to default
            "固费": [500000.0, 1000000.0],
            "浮费": [300000.0, 600000.0],
            "回补": [200000.0, 400000.0],
            "税": [50000.0, 100000.0],
            "id": [1, 2],  # Legacy column to be dropped
            "备注": ["备注1", "备注2"],  # Legacy column to be dropped
        })

    @pytest.fixture
    def context(self):
        """Create pipeline context."""
        return make_context("bronze_to_silver")

    def test_full_pipeline_execution(self, sample_bronze_df, context):
        """Pipeline executes all steps and produces valid output."""
        pipeline = build_bronze_to_silver_pipeline(
            plan_override_mapping={"FP0001": "614810477"},
        )

        result_df = pipeline.execute(sample_bronze_df, context)

        # Verify company_id resolution
        assert "company_id" in result_df.columns
        assert result_df.loc[0, "company_id"] == "614810477"

        # Verify legacy columns dropped
        assert "id" not in result_df.columns
        assert "备注" not in result_df.columns

        # Verify 机构名称 dropped (used for mapping then removed)
        assert "机构名称" not in result_df.columns

    def test_pipeline_applies_institution_code_mapping(self, sample_bronze_df, context):
        """Pipeline maps institution names to codes."""
        pipeline = build_bronze_to_silver_pipeline()

        result_df = pipeline.execute(sample_bronze_df, context)

        # 北京 → G01, 上海 → G02
        assert result_df.loc[0, "机构代码"] == "G01"
        assert result_df.loc[1, "机构代码"] == "G02"

    def test_pipeline_applies_product_line_mapping(self, sample_bronze_df, context):
        """Pipeline maps business type to product line code."""
        pipeline = build_bronze_to_silver_pipeline()

        result_df = pipeline.execute(sample_bronze_df, context)

        # 企年投资 → PL201, 职年受托 → PL204
        assert result_df.loc[0, "产品线代码"] == "PL201"
        assert result_df.loc[1, "产品线代码"] == "PL204"

    def test_pipeline_preserves_customer_name_to_account_name(self, sample_bronze_df, context):
        """Pipeline copies 客户名称 to 年金账户名 before cleansing."""
        pipeline = build_bronze_to_silver_pipeline()

        result_df = pipeline.execute(sample_bronze_df, context)

        # 年金账户名 should contain original customer name
        assert "年金账户名" in result_df.columns

    def test_pipeline_applies_portfolio_code_defaults(self, sample_bronze_df, context):
        """Pipeline applies portfolio code defaults for 职年受托."""
        pipeline = build_bronze_to_silver_pipeline()

        result_df = pipeline.execute(sample_bronze_df, context)

        # Row 0: FQTAN001 → QTAN001 (F removed)
        assert result_df.loc[0, "组合代码"] == "QTAN001"
        # Row 1: None + 职年受托 → QTAN003
        assert result_df.loc[1, "组合代码"] == "QTAN003"

    def test_pipeline_preserves_data_integrity(self, sample_bronze_df, context):
        """Pipeline preserves original data values."""
        # Story 5.5.5: Updated to use four income fields instead of 收入金额
        pipeline = build_bronze_to_silver_pipeline()

        result_df = pipeline.execute(sample_bronze_df, context)

        # Financial values should be preserved
        assert result_df.loc[0, "固费"] == 500000.0
        assert result_df.loc[1, "固费"] == 1000000.0
        assert result_df.loc[0, "浮费"] == 300000.0
        assert result_df.loc[1, "浮费"] == 600000.0

    def test_pipeline_handles_column_aliases(self, context):
        """Pipeline normalizes 计划代码→计划号 and 机构→机构代码 before processing."""
        alias_df = pd.DataFrame({
            "月度": ["202412"],
            "计划代码": ["fp0003"],  # Alias column that should become 计划号
            "客户名称": ["测试公司C"],
            "年金账户名": ["账户C"],
            "业务类型": ["企年投资"],
            "计划类型": ["单一计划"],
            "机构": ["北京"],  # Alias that should become 机构代码
            "机构名称": ["北京"],
            "组合代码": ["FQTAN010"],
            "固费": [120000.0],
            "浮费": [34000.0],
            "回补": [5600.0],
            "税": [1700.0],
        })

        pipeline = build_bronze_to_silver_pipeline()
        result_df = pipeline.execute(alias_df, context)

        # Aliases should be normalized (both plan columns uppercase and aligned)
        assert "计划号" in result_df.columns
        assert "计划代码" in result_df.columns
        assert result_df.loc[0, "计划号"] == "FP0003"
        assert result_df.loc[0, "计划代码"] == "FP0003"

        assert "机构代码" in result_df.columns
        assert "机构" not in result_df.columns
        assert result_df.loc[0, "机构代码"] == "G01"  # Derived from mapping
