"""
Unit tests for BizLabelParser.

Story 6.2-P9: Raw Data Cleansing & Transformation
Task 5.2: Unit tests for BizLabelParser
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest


class TestBizLabelParser:
    """Tests for BizLabelParser service."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        from work_data_hub.infrastructure.cleansing.biz_label_parser import BizLabelParser
        return BizLabelParser()

    def test_parse_complete_labels_structure(self, parser):
        """Test parsing a complete labels structure."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "行业分类",
                    "labels": [
                        {
                            "companyId": "company_123",
                            "lv1Name": "信息传输、软件和信息技术服务业",
                            "lv2Name": "软件和信息技术服务业",
                            "lv3Name": "软件开发",
                            "lv4Name": None,
                        },
                    ],
                },
                {
                    "type": "经营范围",
                    "labels": [
                        {
                            "companyId": "company_123",
                            "lv1Name": "技术开发",
                            "lv2Name": "技术咨询",
                            "lv3Name": None,
                            "lv4Name": None,
                        },
                    ],
                },
            ],
        }

        result = parser.parse(raw, "fallback_id")

        assert len(result) == 2
        
        # First label
        assert result[0].company_id == "company_123"
        assert result[0].type == "行业分类"
        assert result[0].lv1_name == "信息传输、软件和信息技术服务业"
        assert result[0].lv2_name == "软件和信息技术服务业"
        assert result[0].lv3_name == "软件开发"
        assert result[0].lv4_name is None

        # Second label
        assert result[1].company_id == "company_123"
        assert result[1].type == "经营范围"
        assert result[1].lv1_name == "技术开发"
        assert result[1].lv2_name == "技术咨询"

    def test_parse_null_company_id_fallback_to_sibling(self, parser):
        """Test null companyId fallback to sibling value."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "行业分类",
                    "labels": [
                        {
                            "companyId": "company_123",
                            "lv1Name": "Category A",
                            "lv2Name": None,
                            "lv3Name": None,
                            "lv4Name": None,
                        },
                        {
                            "companyId": None,  # Should fallback to sibling
                            "lv1Name": "Category B",
                            "lv2Name": None,
                            "lv3Name": None,
                            "lv4Name": None,
                        },
                    ],
                },
            ],
        }

        result = parser.parse(raw, "fallback_id")

        assert len(result) == 2
        assert result[0].company_id == "company_123"
        assert result[1].company_id == "company_123"  # Fallback to sibling

    def test_parse_null_company_id_fallback_to_parameter(self, parser):
        """Test null companyId fallback to function parameter."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "行业分类",
                    "labels": [
                        {
                            "companyId": None,  # No sibling, use parameter
                            "lv1Name": "Category A",
                            "lv2Name": None,
                            "lv3Name": None,
                            "lv4Name": None,
                        },
                    ],
                },
            ],
        }

        result = parser.parse(raw, "fallback_company_id")

        assert len(result) == 1
        assert result[0].company_id == "fallback_company_id"

    def test_parse_empty_labels(self, parser):
        """Test parsing empty labels structure."""
        raw: Dict[str, Any] = {"labels": []}
        result = parser.parse(raw, "fallback_id")
        assert len(result) == 0

    def test_parse_none_input(self, parser):
        """Test parsing None input."""
        result = parser.parse(None, "fallback_id")
        assert len(result) == 0

    def test_parse_missing_labels_key(self, parser):
        """Test parsing structure without labels key."""
        raw: Dict[str, Any] = {"other": "data"}
        result = parser.parse(raw, "fallback_id")
        assert len(result) == 0

    def test_parse_invalid_labels_type(self, parser):
        """Test parsing invalid labels type (not a list)."""
        raw: Dict[str, Any] = {"labels": "not_a_list"}
        result = parser.parse(raw, "fallback_id")
        assert len(result) == 0

    def test_parse_multiple_categories(self, parser):
        """Test parsing multiple label categories."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "行业分类",
                    "labels": [
                        {"companyId": "c1", "lv1Name": "行业A", "lv2Name": None, "lv3Name": None, "lv4Name": None},
                        {"companyId": "c1", "lv1Name": "行业B", "lv2Name": None, "lv3Name": None, "lv4Name": None},
                    ],
                },
                {
                    "type": "资质认证",
                    "labels": [
                        {"companyId": "c1", "lv1Name": "ISO9001", "lv2Name": None, "lv3Name": None, "lv4Name": None},
                    ],
                },
            ],
        }

        result = parser.parse(raw, "fallback_id")

        assert len(result) == 3
        assert sum(1 for r in result if r.type == "行业分类") == 2
        assert sum(1 for r in result if r.type == "资质认证") == 1

    def test_parse_whitespace_trimming(self, parser):
        """Test whitespace trimming in label names."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "  行业分类  ",
                    "labels": [
                        {
                            "companyId": "c1",
                            "lv1Name": "  Category A  ",
                            "lv2Name": "  Subcategory B  ",
                            "lv3Name": None,
                            "lv4Name": None,
                        },
                    ],
                },
            ],
        }

        result = parser.parse(raw, "fallback_id")

        assert len(result) == 1
        assert result[0].type == "行业分类"
        assert result[0].lv1_name == "Category A"
        assert result[0].lv2_name == "Subcategory B"

    def test_parse_empty_string_to_none(self, parser):
        """Test that empty strings are converted to None."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "行业分类",
                    "labels": [
                        {
                            "companyId": "c1",
                            "lv1Name": "",
                            "lv2Name": "   ",
                            "lv3Name": "Valid",
                            "lv4Name": None,
                        },
                    ],
                },
            ],
        }

        result = parser.parse(raw, "fallback_id")

        assert len(result) == 1
        assert result[0].lv1_name is None
        assert result[0].lv2_name is None
        assert result[0].lv3_name == "Valid"

    def test_parse_skips_invalid_label_entries(self, parser):
        """Test that invalid label entries are skipped."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "行业分类",
                    "labels": [
                        {"companyId": "c1", "lv1Name": "Valid", "lv2Name": None, "lv3Name": None, "lv4Name": None},
                        "not_a_dict",  # Should be skipped
                        123,  # Should be skipped
                    ],
                },
                "not_a_dict_category",  # Should be skipped
            ],
        }

        result = parser.parse(raw, "fallback_id")

        assert len(result) == 1
        assert result[0].lv1_name == "Valid"

    def test_parse_four_level_labels(self, parser):
        """Test parsing labels with all four levels populated."""
        raw: Dict[str, Any] = {
            "labels": [
                {
                    "type": "详细分类",
                    "labels": [
                        {
                            "companyId": "c1",
                            "lv1Name": "Level 1",
                            "lv2Name": "Level 2",
                            "lv3Name": "Level 3",
                            "lv4Name": "Level 4",
                        },
                    ],
                },
            ],
        }

        result = parser.parse(raw, "fallback_id")

        assert len(result) == 1
        assert result[0].lv1_name == "Level 1"
        assert result[0].lv2_name == "Level 2"
        assert result[0].lv3_name == "Level 3"
        assert result[0].lv4_name == "Level 4"
