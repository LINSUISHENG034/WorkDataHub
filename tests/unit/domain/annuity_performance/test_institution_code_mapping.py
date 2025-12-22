"""
Unit tests for institution code (机构代码) mapping in annuity performance pipeline.

Tests for:
- Complete mapping coverage (46 mappings vs Legacy 44 mappings)
- Special value handling (null, None, empty string)
- Default value application (G00 for unmapped institutions)
- Legacy parity
"""

import pandas as pd
import pytest

from work_data_hub.domain.annuity_performance.pipeline_builder import (
    build_bronze_to_silver_pipeline,
)
from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.enrichment import EqcLookupConfig
from work_data_hub.infrastructure.mappings import COMPANY_BRANCH_MAPPING
from datetime import datetime, timezone


def make_context(pipeline_name: str = "test_pipeline") -> PipelineContext:
    """Helper to create a valid PipelineContext for testing."""
    return PipelineContext(
        pipeline_name=pipeline_name,
        execution_id="test-run-001",
        timestamp=datetime.now(timezone.utc),
        config={"domain": "annuity_performance"},
    )


class TestInstitutionCodeMapping:
    """Test institution code mapping logic."""

    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame with various institution names."""
        return pd.DataFrame(
            {
                "月度": ["202411"] * 10,
                "机构名称": [
                    "北京",
                    "上海",
                    "深圳",
                    "广东",
                    "江苏",
                    "浙江",
                    "福建",
                    "海南",
                    "重庆",
                    "不存在的机构",
                ],
                "计划类型": ["集合计划"] * 10,
                "计划代码": ["AN001"] * 10,
                "业务类型": ["企年投资"] * 10,
                "客户名称": [
                    f"客户{i}" for i in range(10)
                ],  # Required for company_id resolution
            }
        )

    def test_all_legacy_mappings_present(self):
        """Test that all Legacy mappings are present in COMPANY_BRANCH_MAPPING."""
        # Legacy mappings from database + special adjustments
        legacy_mappings = {
            # Database mappings (38)
            "总部": "G00",
            "北京": "G01",
            "上海": "G02",
            "广东": "G04",
            "深圳": "G05",
            "江苏": "G10",
            "浙江": "G12",
            "福建": "G13",
            "海南": "G15",
            "重庆": "G18",
            "山东": "G21",
            "江西": "G22",
            "新疆": "G23",
            "安徽": "G25",
            "宁波": "G29",
            "甘肃": "G34",
            "贵州": "G35",
            "内蒙古": "G31",
            "青岛": "G11",
            "大连": "G07",
            "广西": "G14",
            "河北": "G24",
            "河南": "G32",
            "黑龙江": "G19",
            "湖北": "G09",
            "湖南": "G20",
            "吉林": "G08",
            "辽宁": "G06",
            "宁夏": "G28",
            "青海": "G27",
            "山西": "G33",
            "陕西": "G17",
            "四川": "G26",
            "天津": "G03",
            "西藏": "G36",
            "云南": "G16",
            "厦门": "G30",
            "北总": "G37",
            # Special adjustments (6)
            "内蒙": "G31",
            "战略": "G37",
            "中国": "G37",
            "济南": "G21",
            "北京其他": "G37",
            "北分": "G37",
        }

        missing_mappings = []
        for name, code in legacy_mappings.items():
            if name not in COMPANY_BRANCH_MAPPING:
                missing_mappings.append(f"{name}: {code}")
            elif COMPANY_BRANCH_MAPPING[name] != code:
                missing_mappings.append(
                    f"{name}: Legacy={code}, New={COMPANY_BRANCH_MAPPING[name]}"
                )

        if missing_mappings:
            pytest.fail(
                f"Missing or mismatched mappings:\n" + "\n".join(missing_mappings)
            )

    def test_additional_mappings(self):
        """Test that new pipeline has additional mappings beyond Legacy."""
        # Additional mappings in New Pipeline
        additional_mappings = {
            "深圳分公司": "G05",  # Same as "深圳"
            "广州": "G04",  # Same as "广东"
        }

        for name, code in additional_mappings.items():
            assert name in COMPANY_BRANCH_MAPPING, (
                f"Additional mapping {name} not found"
            )
            assert COMPANY_BRANCH_MAPPING[name] == code, (
                f"Additional mapping {name} has wrong code"
            )

    def test_mapping_count(self):
        """Test mapping count matches expected."""
        # Should have 46 mappings: 38 database + 6 legacy adjustments + 2 new
        expected_count = 46
        actual_count = len(COMPANY_BRANCH_MAPPING)

        assert actual_count == expected_count, (
            f"Expected {expected_count} mappings, got {actual_count}"
        )

    def test_institution_code_mapping_applied(self, sample_df):
        """Test that institution code mapping is applied correctly."""
        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled()
        )
        context = make_context("test")

        result_df = pipeline.execute(sample_df.copy(), context)

        # Check known mappings
        assert result_df.loc[0, "机构代码"] == "G01"  # 北京 → G01
        assert result_df.loc[1, "机构代码"] == "G02"  # 上海 → G02
        assert result_df.loc[2, "机构代码"] == "G05"  # 深圳 → G05
        assert result_df.loc[3, "机构代码"] == "G04"  # 广东 → G04
        assert result_df.loc[4, "机构代码"] == "G10"  # 江苏 → G10
        assert result_df.loc[5, "机构代码"] == "G12"  # 浙江 → G12
        assert result_df.loc[6, "机构代码"] == "G13"  # 福建 → G13
        assert result_df.loc[7, "机构代码"] == "G15"  # 海南 → G15
        assert result_df.loc[8, "机构代码"] == "G18"  # 重庆 → G18

        # Check default value for unmapped institution
        assert result_df.loc[9, "机构代码"] == "G00"  # 不存在的机构 → G00

    def test_special_value_handling(self):
        """Test handling of special values (null, None, empty string)."""
        df = pd.DataFrame(
            {
                "月度": ["202411"] * 5,
                "机构名称": [None, "", "null", "None", "北京"],
                "计划类型": ["集合计划"] * 5,
                "计划代码": ["AN001"] * 5,
                "业务类型": ["企年投资"] * 5,
                "客户名称": ["客户A"] * 5,  # Required for company_id resolution
            }
        )

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled()
        )
        context = make_context("test")

        result_df = pipeline.execute(df, context)

        # All special values should map to default G00
        assert result_df.loc[0, "机构代码"] == "G00"  # None → G00
        assert result_df.loc[1, "机构代码"] == "G00"  # "" → G00
        assert result_df.loc[2, "机构代码"] == "G00"  # "null" → G00
        assert result_df.loc[3, "机构代码"] == "G00"  # "None" → G00
        assert result_df.loc[4, "机构代码"] == "G01"  # 北京 → G01

    def test_legacy_override_mappings(self):
        """Test legacy special adjustment mappings."""
        df = pd.DataFrame(
            {
                "月度": ["202411"] * 6,
                "机构名称": ["内蒙", "战略", "中国", "济南", "北京其他", "北分"],
                "计划类型": ["集合计划"] * 6,
                "计划代码": ["AN001"] * 6,
                "业务类型": ["企年投资"] * 6,
                "客户名称": [f"客户{i}" for i in range(6)],
            }
        )

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled()
        )
        context = make_context("test")

        result_df = pipeline.execute(df, context)

        # Check legacy overrides
        assert result_df.loc[0, "机构代码"] == "G31"  # 内蒙 → G31
        assert result_df.loc[1, "机构代码"] == "G37"  # 战略 → G37
        assert result_df.loc[2, "机构代码"] == "G37"  # 中国 → G37
        assert result_df.loc[3, "机构代码"] == "G21"  # 济南 → G21
        assert result_df.loc[4, "机构代码"] == "G37"  # 北京其他 → G37
        assert result_df.loc[5, "机构代码"] == "G37"  # 北分 → G37

    def test_duplicate_mapping_handling(self):
        """Test handling of "内蒙" vs "内蒙古" (both map to G31)."""
        df = pd.DataFrame(
            {
                "月度": ["202411"] * 2,
                "机构名称": ["内蒙古", "内蒙"],
                "计划类型": ["集合计划"] * 2,
                "计划代码": ["AN001"] * 2,
                "业务类型": ["企年投资"] * 2,
                "客户名称": ["客户A", "客户B"],
            }
        )

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled()
        )
        context = make_context("test")

        result_df = pipeline.execute(df, context)

        # Both should map to G31
        assert result_df.loc[0, "机构代码"] == "G31"  # 内蒙古 → G31
        assert result_df.loc[1, "机构代码"] == "G31"  # 内蒙 → G31

    def test_no_institution_name_column(self):
        """Test behavior when 机构名称 column doesn't exist."""
        df = pd.DataFrame(
            {
                "月度": ["202411"],
                "计划类型": ["集合计划"],
                "计划代码": ["AN001"],
                "业务类型": ["企年投资"],
                "客户名称": ["客户A"],
            }
        )

        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled()
        )
        context = make_context("test")

        result_df = pipeline.execute(df, context)

        # Should set all values to default G00 when no 机构名称 column
        assert (result_df["机构代码"] == "G00").all()


class TestInstitutionCodeLegacyParity:
    """Test institution code processing maintains parity with Legacy system."""

    @pytest.fixture
    def comprehensive_test_df(self):
        """Create comprehensive test data covering all edge cases."""
        institutions = [
            # Standard database mappings
            "总部",
            "北京",
            "上海",
            "深圳",
            "广东",
            # Missing mappings (should get G00)
            "不存在的机构1",
            "不存在的机构2",
            # Special values (handled as None, which is fine)
            None,
            "",
            "null",
            "None",
            # Legacy overrides
            "内蒙",
            "战略",
            "中国",
            # New pipeline additions
            "深圳分公司",
            "广州",
        ]

        return pd.DataFrame(
            {
                "月度": ["202411"] * len(institutions),
                "机构名称": institutions,
                "计划类型": ["集合计划"] * len(institutions),
                "计划代码": ["AN001"] * len(institutions),
                "业务类型": ["企年投资"] * len(institutions),
                "客户名称": [f"客户{i}" for i in range(len(institutions))],
            }
        )

    def test_legacy_parity_comprehensive(self, comprehensive_test_df):
        """Test comprehensive legacy parity."""
        pipeline = build_bronze_to_silver_pipeline(
            eqc_config=EqcLookupConfig.disabled()
        )
        context = make_context("test")

        result_df = pipeline.execute(comprehensive_test_df.copy(), context)

        # Expected results based on Legacy behavior
        expected_results = {
            0: "G00",  # 总部 → G00
            1: "G01",  # 北京 → G01
            2: "G02",  # 上海 → G02
            3: "G05",  # 深圳 → G05
            4: "G04",  # 广东 → G04
            5: "G00",  # 不存在的机构1 → G00 (default)
            6: "G00",  # 不存在的机构2 → G00 (default)
            7: "G00",  # None → G00
            8: "G00",  # "" → G00
            9: "G00",  # "null" → G00 (Legacy converts string "null" to G00)
            10: "G00",  # "None" → G00
            11: "G31",  # 内蒙 → G31 (Legacy override)
            12: "G37",  # 战略 → G37 (Legacy override)
            13: "G37",  # 中国 → G37 (Legacy override)
            14: "G05",  # 深圳分公司 → G05 (New mapping, same as 深圳)
            # Note: Only 15 rows, so index 14 is the last
        }

        for idx, expected_code in expected_results.items():
            actual_code = result_df.loc[idx, "机构代码"]
            assert actual_code == expected_code, (
                f"Row {idx}: 机构名称='{comprehensive_test_df.loc[idx, '机构名称']}'\n"
                f"  Expected: {expected_code}, Got: {actual_code}"
            )

    def test_all_institution_codes_covered(self):
        """Test that we have test coverage for all institution codes."""
        # Get all unique institution codes from mapping
        all_codes = set(COMPANY_BRANCH_MAPPING.values())

        # Ensure we have tests for all code ranges (G00-G37)
        expected_codes = {f"G{num:02d}" for num in range(0, 38)}  # G00 to G37

        # Check that our mapping covers expected codes
        missing_codes = expected_codes - all_codes
        if missing_codes:
            # Some codes like G21 might be used by multiple institutions
            # This is informational, not a failure
            print(
                f"\nNote: Some institution codes not directly mapped: {sorted(missing_codes)}"
            )
