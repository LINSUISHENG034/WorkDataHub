"""
Tests for reference backfill domain service functions.

Tests candidate derivation logic, deduplication, field mapping,
and validation for both plan and portfolio candidates.
"""

import pytest
from datetime import datetime

from src.work_data_hub.domain.reference_backfill.service import (
    derive_plan_candidates,
    derive_portfolio_candidates,
    validate_plan_candidates,
    validate_portfolio_candidates,
)
from src.work_data_hub.domain.reference_backfill.models import (
    AnnuityPlanCandidate,
    PortfolioCandidate,
)


class TestDerivePlanCandidates:
    """Test derive_plan_candidates function."""

    def test_derive_plan_candidates_basic(self):
        """Test basic plan candidate derivation."""
        input_rows = [
            {"计划代码": "PLAN001", "计划名称": "Test Plan", "计划类型": "DC"},
            {"计划代码": "PLAN001", "客户名称": "Client A"},  # Merge test
            {"计划代码": "PLAN002", "计划名称": "Another Plan"},
        ]

        candidates = derive_plan_candidates(input_rows)

        assert len(candidates) == 2
        plan001 = next(c for c in candidates if c["年金计划号"] == "PLAN001")
        assert plan001["计划全称"] == "Test Plan"
        assert plan001["客户名称"] == "Client A"  # Merged

        plan002 = next(c for c in candidates if c["年金计划号"] == "PLAN002")
        assert plan002["计划全称"] == "Another Plan"
        assert plan002["客户名称"] is None

    def test_derive_plan_candidates_empty_input(self):
        """Test handling of empty input."""
        assert derive_plan_candidates([]) == []

    def test_derive_plan_candidates_invalid_input(self):
        """Test error handling for invalid input."""
        with pytest.raises(ValueError, match="must be a list"):
            derive_plan_candidates("not a list")

    def test_derive_plan_candidates_missing_plan_code(self):
        """Test filtering of rows with missing plan codes."""
        input_rows = [
            {"计划代码": "PLAN001", "计划名称": "Valid Plan"},
            {"计划名称": "Invalid Plan"},  # Missing 计划代码
            {"计划代码": "", "计划名称": "Empty Plan Code"},  # Empty 计划代码
            {"计划代码": "   ", "计划名称": "Whitespace Plan Code"},  # Whitespace only
        ]

        candidates = derive_plan_candidates(input_rows)

        assert len(candidates) == 1
        assert candidates[0]["年金计划号"] == "PLAN001"

    def test_derive_plan_candidates_field_merging(self):
        """Test field merging behavior (last non-null wins)."""
        input_rows = [
            {
                "计划代码": "PLAN001",
                "计划名称": "First Name",
                "计划类型": "DC",
                "客户名称": None,
                "company_id": "COMP1",
            },
            {
                "计划代码": "PLAN001",
                "计划名称": None,  # Should not overwrite existing
                "计划类型": "DB",  # Should not overwrite existing
                "客户名称": "Client A",  # Should fill empty field
                "company_id": "COMP2",  # Should not overwrite existing
            },
            {
                "计划代码": "PLAN001",
                "客户名称": "Client B",  # Should not overwrite existing
            },
        ]

        candidates = derive_plan_candidates(input_rows)

        assert len(candidates) == 1
        plan = candidates[0]
        assert plan["年金计划号"] == "PLAN001"
        assert plan["计划全称"] == "First Name"  # Kept first non-null
        assert plan["计划类型"] == "DC"  # Kept first non-null
        assert plan["客户名称"] == "Client A"  # Filled empty field
        assert plan["company_id"] == "COMP1"  # Kept first non-null

    def test_derive_plan_candidates_deduplication(self):
        """Test deduplication by plan code."""
        input_rows = [
            {"计划代码": "PLAN001", "计划名称": "Plan A"},
            {"计划代码": "PLAN002", "计划名称": "Plan B"},
            {"计划代码": "PLAN001", "客户名称": "Client A"},  # Duplicate plan code
            {"计划代码": "PLAN003", "计划名称": "Plan C"},
            {"计划代码": "PLAN002", "计划类型": "DC"},  # Another duplicate
        ]

        candidates = derive_plan_candidates(input_rows)

        assert len(candidates) == 3
        plan_codes = {c["年金计划号"] for c in candidates}
        assert plan_codes == {"PLAN001", "PLAN002", "PLAN003"}


class TestEnhancedPlanDerivation:
    """Test enhanced plan derivation logic with sophisticated business rules."""

    def test_enhanced_plan_derivation_tie_breaking(self):
        """Test tie-breaking logic for most frequent values."""
        # Setup rows with tied frequencies but different 期末资产规模
        rows = [
            {"计划代码": "PLAN001", "客户名称": "Client A", "期末资产规模": 1000000},
            {"计划代码": "PLAN001", "客户名称": "Client A", "期末资产规模": 2000000},
            {"计划代码": "PLAN001", "客户名称": "Client B", "期末资产规模": 1500000},
            {"计划代码": "PLAN001", "客户名称": "Client B", "期末资产规模": 500000},
        ]
        # Both clients appear twice (tied), but Client A has max 期末资产规模 (2M)

        candidates = derive_plan_candidates(rows)
        assert len(candidates) == 1
        assert candidates[0]["客户名称"] == "Client A"  # Won tie-break

    def test_enhanced_plan_derivation_max_row_selection(self):
        """Test 主拓代码 and 主拓机构 from max 期末资产规模 row."""
        rows = [
            {
                "计划代码": "PLAN001",
                "期末资产规模": 1000000,
                "主拓代码": "AGENT001",
                "主拓机构": "BRANCH001",
            },
            {
                "计划代码": "PLAN001",
                "期末资产规模": 3000000,  # Maximum
                "主拓代码": "AGENT002",
                "主拓机构": "BRANCH002",
            },
            {
                "计划代码": "PLAN001",
                "期末资产规模": 2000000,
                "主拓代码": "AGENT003",
                "主拓机构": "BRANCH003",
            },
        ]

        candidates = derive_plan_candidates(rows)
        assert len(candidates) == 1
        plan = candidates[0]
        assert plan["主拓代码"] == "AGENT002"  # From max row
        assert plan["主拓机构"] == "BRANCH002"  # From max row

    def test_enhanced_plan_derivation_remark_formatting(self):
        """Test 备注 formatting from various date inputs."""
        test_cases = [
            {"月度": 202411, "expected": "2411_新建"},
            {"月度": "202412", "expected": "2412_新建"},
            {"月度": "2024-01", "expected": "2401_新建"},
            {"月度": "2024-12-15", "expected": "2412_新建"},
            {"月度": None, "expected": None},
            {"月度": "invalid", "expected": None},
        ]

        for case in test_cases:
            rows = [{"计划代码": "PLAN001", "月度": case["月度"]}]
            candidates = derive_plan_candidates(rows)
            assert len(candidates) == 1
            assert candidates[0]["备注"] == case["expected"]

    def test_enhanced_plan_derivation_qualification_ordering(self):
        """Test 资格 filtering and ordering from business types."""
        test_cases = [
            {
                "business_types": {"职年投资", "其他类型", "企年受托", "年"},
                "expected": "企年受托+年+职年投资",  # Correct order, "其他类型" filtered out
            },
            {
                "business_types": {"职年受托", "企年投资"},
                "expected": "企年投资+职年受托",  # Correct order
            },
            {
                "business_types": {"年"},
                "expected": "年",  # Single type
            },
            {
                "business_types": {"其他类型", "无效类型"},
                "expected": None,  # No valid types
            },
            {
                "business_types": set(),
                "expected": None,  # Empty set
            },
        ]

        for case in test_cases:
            rows = [
                {"计划代码": "PLAN001", "业务类型": bt}
                for bt in case["business_types"]
                if bt  # Filter out None/empty
            ]
            if not rows:  # Handle empty business_types case
                rows = [{"计划代码": "PLAN001"}]

            candidates = derive_plan_candidates(rows)
            assert len(candidates) == 1
            assert candidates[0]["资格"] == case["expected"]

    def test_enhanced_plan_derivation_edge_cases(self):
        """Test enhanced derivation with edge cases."""
        # Test with null/empty values in key fields
        rows = [
            {
                "计划代码": "PLAN001",
                "客户名称": None,  # Null value
                "期末资产规模": None,  # Null value
                "月度": None,  # Null date
                "业务类型": None,  # Null business type
            },
            {
                "计划代码": "PLAN001",
                "客户名称": "",  # Empty string
                "期末资产规模": "not_a_number",  # Invalid numeric
                "月度": "",  # Empty date
                "业务类型": "",  # Empty business type
            },
        ]

        candidates = derive_plan_candidates(rows)
        assert len(candidates) == 1
        plan = candidates[0]
        assert plan["年金计划号"] == "PLAN001"
        assert plan["客户名称"] is None  # No valid values
        assert plan["主拓代码"] is None  # No valid values
        assert plan["主拓机构"] is None  # No valid values
        assert plan["备注"] is None  # No valid date
        assert plan["资格"] is None  # No valid business types

    def test_enhanced_plan_derivation_numeric_edge_cases(self):
        """Test numeric handling with various formats."""
        rows = [
            {
                "计划代码": "PLAN001",
                "客户名称": "Client A",
                "期末资产规模": "1000000",
            },  # String number
            {
                "计划代码": "PLAN001",
                "客户名称": "Client B",
                "期末资产规模": 2000000.5,
            },  # Float
            {
                "计划代码": "PLAN001",
                "客户名称": "Client C",
                "期末资产规模": 1500000,
            },  # Int
        ]

        candidates = derive_plan_candidates(rows)
        assert len(candidates) == 1
        # Client B should win due to highest numeric value (2000000.5)
        assert candidates[0]["客户名称"] == "Client B"


class TestDerivePortfolioCandidates:
    """Test derive_portfolio_candidates function."""

    def test_derive_portfolio_candidates_basic(self):
        """Test basic portfolio candidate derivation."""
        input_rows = [
            {
                "组合代码": "PORT001",
                "计划代码": "PLAN001",
                "组合名称": "Test Portfolio",
                "组合类型": "Equity",
            },
            {
                "组合代码": "PORT002",
                "计划代码": "PLAN001",
                "组合名称": "Another Portfolio",
            },
        ]

        candidates = derive_portfolio_candidates(input_rows)

        assert len(candidates) == 2
        port001 = next(c for c in candidates if c["组合代码"] == "PORT001")
        assert port001["年金计划号"] == "PLAN001"
        assert port001["组合名称"] == "Test Portfolio"
        assert port001["组合类型"] == "Equity"

    def test_derive_portfolio_candidates_empty_input(self):
        """Test handling of empty input."""
        assert derive_portfolio_candidates([]) == []

    def test_derive_portfolio_candidates_missing_required_fields(self):
        """Test filtering of rows with missing required fields."""
        input_rows = [
            {
                "组合代码": "PORT001",
                "计划代码": "PLAN001",
                "组合名称": "Valid Portfolio",
            },
            {
                "组合代码": "PORT002",
                "组合名称": "Missing Plan Code",
            },  # Missing 计划代码
            {
                "计划代码": "PLAN001",
                "组合名称": "Missing Portfolio Code",
            },  # Missing 组合代码
            {"组合代码": "", "计划代码": "PLAN001"},  # Empty 组合代码
            {"组合代码": "PORT003", "计划代码": ""},  # Empty 计划代码
        ]

        candidates = derive_portfolio_candidates(input_rows)

        assert len(candidates) == 1
        assert candidates[0]["组合代码"] == "PORT001"
        assert candidates[0]["年金计划号"] == "PLAN001"

    def test_derive_portfolio_candidates_plan_consistency_check(self):
        """Test plan consistency checking for same portfolio code."""
        input_rows = [
            {
                "组合代码": "PORT001",
                "计划代码": "PLAN001",
                "组合名称": "Portfolio A",
            },
            {
                "组合代码": "PORT001",
                "计划代码": "PLAN002",  # Different plan for same portfolio
                "组合名称": "Portfolio A",
            },
            {
                "组合代码": "PORT001",
                "计划代码": "PLAN001",  # Same plan, should merge
                "组合类型": "Equity",
            },
        ]

        candidates = derive_portfolio_candidates(input_rows)

        # Should keep first plan and not create duplicate
        assert len(candidates) == 1
        portfolio = candidates[0]
        assert portfolio["组合代码"] == "PORT001"
        assert portfolio["年金计划号"] == "PLAN001"  # Kept first plan
        assert portfolio["组合类型"] == "Equity"  # Merged additional field

    def test_derive_portfolio_candidates_field_merging(self):
        """Test field merging for same portfolio code and plan."""
        input_rows = [
            {
                "组合代码": "PORT001",
                "计划代码": "PLAN001",
                "组合名称": "First Name",
                "组合类型": None,
            },
            {
                "组合代码": "PORT001",
                "计划代码": "PLAN001",
                "组合名称": None,  # Should not overwrite
                "组合类型": "Equity",  # Should fill empty field
            },
        ]

        candidates = derive_portfolio_candidates(input_rows)

        assert len(candidates) == 1
        portfolio = candidates[0]
        assert portfolio["组合代码"] == "PORT001"
        assert portfolio["年金计划号"] == "PLAN001"
        assert portfolio["组合名称"] == "First Name"  # Kept first non-null
        assert portfolio["组合类型"] == "Equity"  # Filled empty field


class TestValidateCandidates:
    """Test candidate validation functions."""

    def test_validate_plan_candidates_success(self):
        """Test successful plan candidate validation."""
        candidates = [
            {
                "年金计划号": "PLAN001",
                "计划全称": "Test Plan",
                "计划类型": "DC",
                "客户名称": "Client A",
                "company_id": "COMP1",
            }
        ]

        validated = validate_plan_candidates(candidates)

        assert len(validated) == 1
        assert isinstance(validated[0], AnnuityPlanCandidate)
        assert validated[0].年金计划号 == "PLAN001"
        assert validated[0].计划全称 == "Test Plan"

    def test_validate_plan_candidates_missing_required_field(self):
        """Test validation failure for missing required field."""
        candidates = [
            {
                "计划全称": "Test Plan",  # Missing required 年金计划号
                "计划类型": "DC",
            }
        ]

        with pytest.raises(Exception):  # ValidationError or similar
            validate_plan_candidates(candidates)

    def test_validate_portfolio_candidates_success(self):
        """Test successful portfolio candidate validation."""
        candidates = [
            {
                "组合代码": "PORT001",
                "年金计划号": "PLAN001",
                "组合名称": "Test Portfolio",
                "组合类型": "Equity",
                "运作开始日": None,
            }
        ]

        validated = validate_portfolio_candidates(candidates)

        assert len(validated) == 1
        assert isinstance(validated[0], PortfolioCandidate)
        assert validated[0].组合代码 == "PORT001"
        assert validated[0].年金计划号 == "PLAN001"

    def test_validate_portfolio_candidates_missing_required_field(self):
        """Test validation failure for missing required field."""
        candidates = [
            {
                "组合代码": "PORT001",  # Missing required 年金计划号
                "组合名称": "Test Portfolio",
            }
        ]

        with pytest.raises(Exception):  # ValidationError or similar
            validate_portfolio_candidates(candidates)
