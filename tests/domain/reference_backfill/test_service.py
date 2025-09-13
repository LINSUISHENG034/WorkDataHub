"""
Tests for reference backfill domain service functions.

Tests candidate derivation logic, deduplication, field mapping,
and validation for both plan and portfolio candidates.
"""

import pytest

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
            {"组合代码": "PORT002", "组合名称": "Missing Plan Code"},  # Missing 计划代码
            {"计划代码": "PLAN001", "组合名称": "Missing Portfolio Code"},  # Missing 组合代码
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