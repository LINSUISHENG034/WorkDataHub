"""
Tests for cache warming functionality.

Story 7.1-14: EQC API Performance Optimization
Task 2: Cache Optimization (AC-2)

Code Review Fix (2025-12-26):
- H2: Fixed mock return type to match Dict[tuple[LookupType, str], EnrichmentIndexRecord]
- H3: Fixed lookup_type to use LookupType Enum instead of string
"""

import pytest
import pandas as pd

from work_data_hub.infrastructure.enrichment.resolver.cache_warming import (
    CacheWarmer,
    extract_unique_customer_names,
    warm_cache_with_customer_names,
)
from work_data_hub.infrastructure.enrichment.types import LookupType


@pytest.fixture
def mock_mapping_repository():
    """Create a mock mapping repository."""
    from unittest.mock import Mock

    mock = Mock()
    mock.lookup_enrichment_index_batch.return_value = []
    return mock


class TestExtractUniqueCustomerNames:
    """Tests for extract_unique_customer_names function."""

    def test_extract_unique_names_basic(self):
        """Test basic extraction of unique customer names."""
        df = pd.DataFrame(
            {
                "客户名称": ["公司A", "公司B", "公司A", "公司C"],
            }
        )

        names = extract_unique_customer_names(df, "客户名称")

        # Should return 3 unique names (公司A, 公司B, 公司C)
        assert len(names) == 3

    def test_extract_with_null_values(self):
        """Test extraction with null values."""
        df = pd.DataFrame(
            {
                "客户名称": ["公司A", None, "公司B", pd.NA, "公司A"],
            }
        )

        names = extract_unique_customer_names(df, "客户名称")

        # Should skip null values
        assert len(names) == 2
        assert all(n is not None for n in names)

    def test_extract_with_empty_dataframe(self):
        """Test extraction with empty DataFrame."""
        df = pd.DataFrame({"客户名称": []})

        names = extract_unique_customer_names(df, "客户名称")

        assert names == []

    def test_extract_with_missing_column(self):
        """Test extraction when column doesn't exist."""
        df = pd.DataFrame({"其他列": ["a", "b"]})

        names = extract_unique_customer_names(df, "客户名称")

        assert names == []


class TestCacheWarmer:
    """Tests for CacheWarmer class."""

    def test_cache_warmer_init(self, mock_mapping_repository):
        """Test CacheWarmer initialization."""
        warmer = CacheWarmer(mock_mapping_repository)

        assert warmer.mapping_repository == mock_mapping_repository
        assert warmer.cache == {}

    def test_warm_cache_basic(self, mock_mapping_repository):
        """Test basic cache warming."""
        # Setup mock repository with correct return type:
        # Dict[tuple[LookupType, str], EnrichmentIndexRecord]
        # H2/H3 Fix: Use dict with tuple keys and LookupType Enum
        mock_record = type(
            "Record",
            (),
            {
                "lookup_type": LookupType.CUSTOMER_NAME,  # H3 Fix: Use Enum
                "lookup_key": "gongsia",  # Normalized form of 公司A
                "company_id": "123456",
            },
        )()
        mock_mapping_repository.lookup_enrichment_index_batch.return_value = {
            (LookupType.CUSTOMER_NAME, "gongsia"): mock_record,
        }

        df = pd.DataFrame(
            {
                "客户名称": ["公司A", "公司B"],
            }
        )

        warmer = CacheWarmer(mock_mapping_repository)
        cache = warmer.warm_cache(df, "客户名称")

        # Verify cache was built with correct structure
        assert isinstance(cache, dict)
        # Should have 1 hit (公司A -> gongsia found in mock)
        assert len(cache) == 1
        assert cache.get("gongsia") == "123456"

        # Verify repository was called
        mock_mapping_repository.lookup_enrichment_index_batch.assert_called_once()

    def test_cache_lookup(self, mock_mapping_repository):
        """Test cache lookup functionality."""
        warmer = CacheWarmer(mock_mapping_repository)

        # Manually set cache with correct normalized key
        # normalize_for_temp_id("test_company") returns "test_company"
        warmer._cache = {"test_company": "123456"}

        # Test lookup
        result = warmer.lookup("test_company")

        assert result == "123456"

    def test_cache_lookup_miss(self, mock_mapping_repository):
        """Test cache lookup miss."""
        warmer = CacheWarmer(mock_mapping_repository)

        # Empty cache
        result = warmer.lookup("nonexistent_company")

        assert result is None

    def test_cache_hit_rate(self, mock_mapping_repository):
        """Test cache hit rate calculation."""
        warmer = CacheWarmer(mock_mapping_repository)

        # Set cache with 3 entries
        warmer._cache = {
            "company_a": "1",
            "company_b": "2",
            "company_c": "3",
        }

        # Calculate hit rate for 5 total names
        hit_rate = warmer.cache_hit_rate(5)

        assert hit_rate == 0.6  # 3/5 = 0.6

    def test_cache_hit_rate_empty(self, mock_mapping_repository):
        """Test cache hit rate with empty cache."""
        warmer = CacheWarmer(mock_mapping_repository)

        hit_rate = warmer.cache_hit_rate(10)

        assert hit_rate == 0.0
