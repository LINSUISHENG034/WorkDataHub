"""Unit tests for sample_parser module."""

import pytest

from work_data_hub.cli.etl.sample_parser import (
    SampleConfig,
    calculate_slice_range,
    parse_sample,
)


class TestParseSample:
    """Tests for parse_sample function."""

    def test_parse_sample_first_slice(self):
        """Parse '1/10' returns first slice."""
        config = parse_sample("1/10")
        assert config.slice_index == 1
        assert config.slice_count == 10

    def test_parse_sample_middle_slice(self):
        """Parse '5/10' returns middle slice."""
        config = parse_sample("5/10")
        assert config.slice_index == 5
        assert config.slice_count == 10

    def test_parse_sample_last_slice(self):
        """Parse '10/10' returns last slice."""
        config = parse_sample("10/10")
        assert config.slice_index == 10
        assert config.slice_count == 10

    def test_parse_sample_invalid_format_no_slash(self):
        """Raises ValueError for missing slash."""
        with pytest.raises(ValueError) as exc_info:
            parse_sample("invalid")
        assert "index/count" in str(exc_info.value)

    def test_parse_sample_invalid_format_multiple_slashes(self):
        """Raises ValueError for multiple slashes."""
        with pytest.raises(ValueError) as exc_info:
            parse_sample("1/2/3")
        assert "exactly one '/'" in str(exc_info.value)

    def test_parse_sample_invalid_non_integer(self):
        """Raises ValueError for non-integer values."""
        with pytest.raises(ValueError) as exc_info:
            parse_sample("one/ten")
        assert "integers" in str(exc_info.value)

    def test_parse_sample_index_out_of_range(self):
        """Raises ValueError for index > count."""
        with pytest.raises(ValueError) as exc_info:
            parse_sample("11/10")
        assert "slice_index" in str(exc_info.value)

    def test_parse_sample_zero_index(self):
        """Raises ValueError for zero index (1-indexed)."""
        with pytest.raises(ValueError) as exc_info:
            parse_sample("0/10")
        assert "slice_index" in str(exc_info.value)

    def test_parse_sample_zero_count(self):
        """Raises ValueError for zero count."""
        with pytest.raises(ValueError) as exc_info:
            parse_sample("1/0")
        assert "slice_count" in str(exc_info.value)


class TestCalculateSliceRange:
    """Tests for calculate_slice_range function."""

    def test_first_slice_of_ten(self):
        """First slice of 1000 rows divided by 10."""
        skip, max_rows = calculate_slice_range(1000, SampleConfig(1, 10))
        assert skip == 0
        assert max_rows == 100

    def test_third_slice_of_ten(self):
        """Third slice of 1000 rows divided by 10."""
        skip, max_rows = calculate_slice_range(1000, SampleConfig(3, 10))
        assert skip == 200
        assert max_rows == 100

    def test_last_slice_includes_remainder(self):
        """Last slice includes remainder rows."""
        # 105 rows / 10 = 10 per slice + 5 remainder
        skip, max_rows = calculate_slice_range(105, SampleConfig(10, 10))
        assert skip == 90
        assert max_rows == 15  # 10 + 5 remainder

    def test_single_slice(self):
        """Single slice returns all rows."""
        skip, max_rows = calculate_slice_range(100, SampleConfig(1, 1))
        assert skip == 0
        assert max_rows == 100

    def test_zero_rows(self):
        """Zero rows returns zero range."""
        skip, max_rows = calculate_slice_range(0, SampleConfig(1, 10))
        assert skip == 0
        assert max_rows == 0

    def test_fewer_rows_than_slices(self):
        """Fewer rows than slices gives small ranges."""
        # 5 rows / 10 = 0 per slice (integer division)
        skip, max_rows = calculate_slice_range(5, SampleConfig(1, 10))
        assert skip == 0
        assert max_rows == 0  # First slice gets 0 rows

        # Last slice gets remainder
        skip, max_rows = calculate_slice_range(5, SampleConfig(10, 10))
        assert skip == 0
        assert max_rows == 5  # All 5 go to last slice
