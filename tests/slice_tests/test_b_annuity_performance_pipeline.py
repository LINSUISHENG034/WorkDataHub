"""Phase B: annuity_performance Bronze→Silver pipeline tests (B-1 through B-13).

Verifies each step of the 13-step pipeline using real slice data.
"""

from __future__ import annotations

import pandas as pd
import pytest

from tests.slice_tests.conftest import FIXTURE_ROOT
from work_data_hub.domain.annuity_performance.constants import (
    COLUMN_MAPPING,
    DEFAULT_INSTITUTION_CODE,
    LEGACY_COLUMNS_TO_DELETE,
)
from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.mappings import (
    BUSINESS_TYPE_CODE_MAPPING,
    COMPANY_BRANCH_MAPPING,
    PLAN_CODE_CORRECTIONS,
)
from work_data_hub.infrastructure.transforms import (
    CalculationStep,
    CleansingStep,
    DropStep,
    MappingStep,
    ReplacementStep,
)
from work_data_hub.infrastructure.transforms.plan_portfolio_helpers import (
    apply_plan_code_defaults,
    apply_portfolio_code_defaults,
)
from work_data_hub.utils.date_parser import parse_chinese_date

pytestmark = pytest.mark.slice_test


# ===================================================================
# B-1: Column name standardization (MappingStep)
# ===================================================================
class TestB1ColumnMapping:
    """Verify 机构→机构名称, 计划号→计划代码, 流失（含待遇支付）→流失_含待遇支付."""

    def test_mapping_step_renames_columns(
        self, annuity_performance_slice_df, make_pipeline_context
    ):
        step = MappingStep(COLUMN_MAPPING)
        ctx = make_pipeline_context("annuity_performance")
        result = step.apply(annuity_performance_slice_df, ctx)

        # Original names should be gone if they existed
        for old_name in COLUMN_MAPPING:
            if old_name in annuity_performance_slice_df.columns:
                assert old_name not in result.columns
                assert COLUMN_MAPPING[old_name] in result.columns


# ===================================================================
# B-2: Preserve original customer name (年金账户名)
# ===================================================================
class TestB2PreserveCustomerName:
    """客户名称 copied to 年金账户名 before cleansing."""

    def test_account_name_copied(
        self, annuity_performance_slice_df, make_pipeline_context
    ):
        df = annuity_performance_slice_df.copy()
        if "客户名称" not in df.columns:
            pytest.skip("No 客户名称 column in slice")

        step = CalculationStep({"年金账户名": lambda d: d["客户名称"].copy()})
        result = step.apply(df, make_pipeline_context("annuity_performance"))
        assert "年金账户名" in result.columns
        pd.testing.assert_series_equal(
            result["年金账户名"], df["客户名称"], check_names=False
        )


# ===================================================================
# B-3: Plan code corrections (ReplacementStep)
# ===================================================================
class TestB3PlanCodeCorrections:
    """Known erroneous plan codes corrected: 1P0290→P0290, 1P0807→P0807."""

    def test_corrections_applied(self, make_pipeline_context):
        df = pd.DataFrame({"计划代码": ["1P0290", "1P0807", "P0100", None]})
        step = ReplacementStep({"计划代码": PLAN_CODE_CORRECTIONS})
        result = step.apply(df, make_pipeline_context("annuity_performance"))
        assert result["计划代码"].iloc[0] == "P0290"
        assert result["计划代码"].iloc[1] == "P0807"
        assert result["计划代码"].iloc[2] == "P0100"  # unchanged


# ===================================================================
# B-4: Plan code defaults (集合计划→AN001, 单一计划→AN002)
# ===================================================================
class TestB4PlanCodeDefaults:
    """Empty 计划代码 filled by 计划类型."""

    def test_collective_gets_an001(self):
        df = pd.DataFrame(
            {
                "计划代码": [None, "", "P0100"],
                "计划类型": ["集合计划", "集合计划", "集合计划"],
            }
        )
        result = apply_plan_code_defaults(df)
        assert result.iloc[0] == "AN001"
        assert result.iloc[1] == "AN001"
        assert result.iloc[2] == "P0100"  # preserved

    def test_single_gets_an002(self):
        df = pd.DataFrame(
            {
                "计划代码": [None],
                "计划类型": ["单一计划"],
            }
        )
        result = apply_plan_code_defaults(df)
        assert result.iloc[0] == "AN002"


# ===================================================================
# B-5: Branch code mapping (机构名称→机构代码, fallback G00)
# ===================================================================
class TestB5BranchCodeMapping:
    """机构名称 maps to 机构代码; unknown/blank→G00."""

    def test_known_branch_maps(self):
        df = pd.DataFrame({"机构名称": ["北京", "上海"]})
        result = df["机构名称"].map(COMPANY_BRANCH_MAPPING)
        assert result.notna().all()

    def test_blank_branch_fallback_g00(self):
        df = pd.DataFrame({"机构名称": [None, "", "(空白)"]})
        result = (
            df["机构名称"].map(COMPANY_BRANCH_MAPPING).fillna(DEFAULT_INSTITUTION_CODE)
        )
        assert (result == "G00").all()


# ===================================================================
# B-6: Product line code derivation (业务类型→产品线代码)
# ===================================================================
class TestB6ProductLineCode:
    """企年受托→PL202, 企年投资→PL201."""

    def test_trustee_maps_to_pl202(self):
        assert BUSINESS_TYPE_CODE_MAPPING["企年受托"] == "PL202"

    def test_investee_maps_to_pl201(self):
        assert BUSINESS_TYPE_CODE_MAPPING["企年投资"] == "PL201"

    def test_slice_data_has_known_types(self, annuity_performance_slice_df):
        df = annuity_performance_slice_df
        if "业务类型" not in df.columns:
            pytest.skip("No 业务类型 column")
        types = df["业务类型"].dropna().unique()
        mapped = [t for t in types if t in BUSINESS_TYPE_CODE_MAPPING]
        assert len(mapped) >= 1, f"No known 业务类型 in slice: {types}"


# ===================================================================
# B-7: Date parsing (月度 column, Chinese date formats)
# ===================================================================
class TestB7DateParsing:
    """Parse YYYY年MM月, YYYYMM, YYYY-MM formats."""

    def test_chinese_date_format(self):
        result = parse_chinese_date("2025年10月")
        assert result is not None
        assert "2025" in str(result)

    def test_numeric_date_format(self):
        result = parse_chinese_date("202510")
        assert result is not None

    def test_dash_date_format(self):
        result = parse_chinese_date("2025-10")
        assert result is not None


# ===================================================================
# B-8: Portfolio code defaults (组合代码 cleaning + defaults)
# ===================================================================
class TestB8PortfolioCodeDefaults:
    """Clean 组合代码, strip F prefix, fill defaults by 业务类型."""

    def test_strip_f_prefix(self):
        df = pd.DataFrame(
            {
                "组合代码": ["F001", "QTAN001"],
                "业务类型": ["企年受托", "企年受托"],
                "计划类型": ["集合计划", "集合计划"],
            }
        )
        result = apply_portfolio_code_defaults(df)
        assert result.iloc[0] == "001"

    def test_empty_fills_default(self):
        df = pd.DataFrame(
            {
                "组合代码": [None, ""],
                "业务类型": ["企年受托", "企年投资"],
                "计划类型": ["集合计划", "集合计划"],
            }
        )
        result = apply_portfolio_code_defaults(df)
        assert result.notna().all()


# ===================================================================
# B-9: 集团企业客户号 cleaning (strip C prefix, nan→None)
# ===================================================================
class TestB9GroupCustomerIdCleaning:
    """Strip 'C' prefix, convert 'nan' string to None."""

    def test_strip_c_prefix(self):
        df = pd.DataFrame({"集团企业客户号": ["C12345", "67890", "nan", None]})
        result = df["集团企业客户号"].apply(
            lambda x: (
                str(x).lstrip("C")
                if isinstance(x, str) and x not in ("nan", "")
                else None
            )
        )
        assert result.iloc[0] == "12345"
        assert result.iloc[1] == "67890"
        assert result.iloc[2] is None
        assert result.iloc[3] is None


# ===================================================================
# B-10: 年金账户号 derivation (cleaned 集团企业客户号 → 年金账户号)
# ===================================================================
class TestB10AccountNumberDerivation:
    """Cleaned 集团企业客户号 copied to 年金账户号."""

    def test_account_number_derived(self):
        df = pd.DataFrame({"集团企业客户号": ["12345", None]})
        df["年金账户号"] = df["集团企业客户号"]
        assert df["年金账户号"].iloc[0] == "12345"
        assert pd.isna(df["年金账户号"].iloc[1])


# ===================================================================
# B-11: Domain cleansing rules (CleansingStep)
# ===================================================================
class TestB11CleansingStep:
    """CleansingStep with domain='annuity_performance'."""

    def test_cleansing_step_runs(
        self, annuity_performance_slice_df, make_pipeline_context
    ):
        step = CleansingStep(domain="annuity_performance")
        ctx = make_pipeline_context("annuity_performance")
        result = step.apply(annuity_performance_slice_df.copy(), ctx)
        assert len(result) == len(annuity_performance_slice_df)


# ===================================================================
# B-12: Company ID resolution (mock — YAML + temp ID only)
# ===================================================================
class TestB12CompanyIdResolution:
    """CompanyIdResolver with disabled EQC generates temp IDs."""

    def test_resolver_generates_temp_ids(self, disabled_eqc_config):
        resolver = CompanyIdResolver(eqc_config=disabled_eqc_config)
        df = pd.DataFrame(
            {
                "计划代码": ["P0100", "P0200"],
                "客户名称": ["测试公司A", "测试公司B"],
                "年金账户名": ["测试A", "测试B"],
                "年金账户号": ["111", "222"],
            }
        )
        strategy = ResolutionStrategy(
            plan_code_column="计划代码",
            customer_name_column="客户名称",
            account_name_column="年金账户名",
            account_number_column="年金账户号",
            generate_temp_ids=True,
        )
        result = resolver.resolve_batch(df, strategy)
        assert "company_id" in result.data.columns
        # With no DB/EQC, should get temp IDs for all rows
        assert result.data["company_id"].notna().all()


# ===================================================================
# B-13: Drop legacy columns (DropStep)
# ===================================================================
class TestB13DropColumns:
    """Drop 'id' and '备注' columns."""

    def test_drop_step_removes_columns(self, make_pipeline_context):
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "备注": ["note1", "note2"],
                "月度": ["202510", "202510"],
            }
        )
        step = DropStep(list(LEGACY_COLUMNS_TO_DELETE))
        result = step.apply(df, make_pipeline_context("annuity_performance"))
        assert "id" not in result.columns
        assert "备注" not in result.columns
        assert "月度" in result.columns
