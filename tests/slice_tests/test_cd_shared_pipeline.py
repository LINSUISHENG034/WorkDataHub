"""Shared pipeline tests parametrized over annual_award and annual_loss domains.

Covers steps that are identical across both domains:
- 2: BusinessTypeNormalization
- 3: ProductLineCode
- 4: PlanTypeMapping
- 5: ReportMonthParsing
- 7: BranchCodeMapping
- 10: CompanyIdResolution
- 12: PlanCodeDefaults
"""

from __future__ import annotations

import importlib

import pandas as pd
import pytest

from work_data_hub.infrastructure.enrichment import (
    CompanyIdResolver,
    ResolutionStrategy,
)
from work_data_hub.infrastructure.mappings import (
    BUSINESS_TYPE_CODE_MAPPING,
    COMPANY_BRANCH_MAPPING,
    PLAN_CODE_DEFAULTS,
)
from work_data_hub.utils.date_parser import parse_chinese_date

pytestmark = pytest.mark.slice_test

DOMAINS = ("annual_award", "annual_loss")


def _load_constant(domain: str, name: str):
    mod = importlib.import_module(f"work_data_hub.domain.{domain}.constants")
    return getattr(mod, name)


# ===================================================================
# 2: Business type normalization
# ===================================================================
class TestSharedBusinessTypeNormalization:
    @pytest.mark.parametrize("domain", DOMAINS)
    def test_normalization_mapping(self, domain):
        mapping = _load_constant(domain, "BUSINESS_TYPE_NORMALIZATION")
        assert mapping["受托"] == "企年受托"
        assert mapping["投资"] == "企年投资"

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_normalization_applied_to_series(self, domain):
        mapping = _load_constant(domain, "BUSINESS_TYPE_NORMALIZATION")
        s = pd.Series(["受托", "投资", "投管", "企年受托"])
        result = s.map(mapping).fillna(s)
        assert result.iloc[0] == "企年受托"
        assert result.iloc[1] == "企年投资"
        assert result.iloc[2] == "企年投资"
        assert result.iloc[3] == "企年受托"


# ===================================================================
# 3: Product line code
# ===================================================================
class TestSharedProductLineCode:
    def test_product_line_from_normalized(self):
        assert BUSINESS_TYPE_CODE_MAPPING["企年受托"] == "PL202"
        assert BUSINESS_TYPE_CODE_MAPPING["企年投资"] == "PL201"


# ===================================================================
# 4: Plan type mapping
# ===================================================================
class TestSharedPlanTypeMapping:
    @pytest.mark.parametrize("domain", DOMAINS)
    def test_plan_type_mapping(self, domain):
        mapping = _load_constant(domain, "PLAN_TYPE_MAPPING")
        assert mapping["集合"] == "集合计划"
        assert mapping["单一"] == "单一计划"

    @pytest.mark.parametrize("domain", DOMAINS)
    def test_already_canonical_passes_through(self, domain):
        mapping = _load_constant(domain, "PLAN_TYPE_MAPPING")
        s = pd.Series(["集合", "单一", "集合计划"])
        result = s.map(mapping).fillna(s)
        assert result.iloc[2] == "集合计划"


# ===================================================================
# 5: Report month parsing
# ===================================================================
class TestSharedReportMonthParsing:
    def test_parse_report_month(self):
        assert parse_chinese_date("2025年10月") is not None
        assert parse_chinese_date("202510") is not None


# ===================================================================
# 7: Branch code mapping
# ===================================================================
class TestSharedBranchCodeMapping:
    def test_known_branch(self):
        assert COMPANY_BRANCH_MAPPING.get("北京") is not None

    def test_unknown_fallback(self):
        assert COMPANY_BRANCH_MAPPING.get("不存在的机构") is None


# ===================================================================
# 10: Company ID resolution
# ===================================================================
class TestSharedCompanyIdResolution:
    def test_resolver_with_plan_code_column(self, disabled_eqc_config):
        resolver = CompanyIdResolver(eqc_config=disabled_eqc_config)
        df = pd.DataFrame(
            {
                "年金计划号": ["P0100", None],
                "客户名称": ["测试公司", "另一公司"],
            }
        )
        strategy = ResolutionStrategy(
            plan_code_column="年金计划号",
            customer_name_column="客户名称",
            account_name_column=None,
            account_number_column=None,
            generate_temp_ids=True,
        )
        result = resolver.resolve_batch(df, strategy)
        assert "company_id" in result.data.columns


# ===================================================================
# 12: Plan code defaults
# ===================================================================
class TestSharedPlanCodeDefaults:
    def test_defaults_applied(self):
        assert PLAN_CODE_DEFAULTS["集合计划"] == "AN001"
        assert PLAN_CODE_DEFAULTS["单一计划"] == "AN002"
