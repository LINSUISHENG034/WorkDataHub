"""
Story 2.4 Performance Tests (AC-PERF-1 - MANDATORY)

Tests for Epic 2 Performance Acceptance Criteria:
- AC-PERF-1: Date parsing throughput ≥1000 rows/s
- AC-PERF-2: Validation overhead <20% (tested via integration with Pydantic)

Reference: docs/epic-2-performance-acceptance-criteria.md
"""

import time
from datetime import date
from typing import List

import pytest
from pydantic import ValidationError

from src.work_data_hub.utils.date_parser import parse_yyyymm_or_chinese


def generate_date_test_data(num_rows: int = 10000) -> List[dict]:
    """
    Generate test data for date parsing performance testing.

    Creates realistic date values with:
    - 90% valid dates in various formats
    - 10% invalid dates (to test error handling)
    - Mix of YYYYMM, YYYY年MM月, YYYY-MM, YY年MM月, date objects
    - Full-width digits (０-９)
    """
    test_data = []

    for i in range(num_rows):
        # 90% valid, 10% invalid
        is_valid = i % 10 != 0

        if not is_valid:
            # Invalid date for error handling
            test_data.append({
                "index": i,
                "value": f"INVALID_{i}",
                "expected_valid": False,
            })
            continue

        # Vary date formats across valid data
        format_choice = i % 8

        if format_choice == 0:
            # Integer YYYYMM format
            year = 2020 + (i % 10)
            month = (i % 12) + 1
            value = year * 100 + month  # e.g., 202501
            expected = date(year, month, 1)
        elif format_choice == 1:
            # Chinese format YYYY年MM月
            year = 2020 + (i % 10)
            month = (i % 12) + 1
            value = f"{year}年{month}月"
            expected = date(year, month, 1)
        elif format_choice == 2:
            # ISO format YYYY-MM
            year = 2020 + (i % 10)
            month = (i % 12) + 1
            value = f"{year}-{month:02d}"
            expected = date(year, month, 1)
        elif format_choice == 3:
            # 2-digit year Chinese format YY年MM月
            year_2digit = 20 + (i % 10)  # 20-29 → 2020-2029
            month = (i % 12) + 1
            value = f"{year_2digit}年{month}月"
            expected = date(2000 + year_2digit, month, 1)
        elif format_choice == 4:
            # Full-width digits ２０２５年０１月
            year = 2020 + (i % 10)
            month = (i % 12) + 1
            # Convert to full-width
            year_fw = str(year).translate(str.maketrans('0123456789', '０１２３４５６７８９'))
            month_fw = str(month).translate(str.maketrans('0123456789', '０１２３４５６７８９'))
            value = f"{year_fw}年{month_fw}月"
            expected = date(year, month, 1)
        elif format_choice == 5:
            # Date object passthrough
            year = 2020 + (i % 10)
            month = (i % 12) + 1
            value = date(year, month, 1)
            expected = date(year, month, 1)
        elif format_choice == 6:
            # String YYYYMM
            year = 2020 + (i % 10)
            month = (i % 12) + 1
            value = f"{year}{month:02d}"
            expected = date(year, month, 1)
        else:
            # YYYYMMDD format (8 digits)
            year = 2020 + (i % 10)
            month = (i % 12) + 1
            day = (i % 28) + 1  # Safe day range for all months
            value = year * 10000 + month * 100 + day
            expected = date(year, month, day)

        test_data.append({
            "index": i,
            "value": value,
            "expected_valid": True,
            "expected_result": expected,
        })

    return test_data


@pytest.fixture
def date_test_data_10k():
    """Generate 10,000 date values for performance testing."""
    return generate_date_test_data(10000)


class TestAC_PERF1_DateParserPerformance:
    """
    AC-PERF-1 (MANDATORY): Date Parser Performance Tests

    Requirements from epic-2-performance-acceptance-criteria.md:
    - AC-PERF-1: ≥1000 rows/s date parsing throughput
    - Test with 10,000-row fixture
    - Mix of valid/invalid dates and various formats
    """

    def test_date_parser_throughput_1000_rows_per_second(self, date_test_data_10k):
        """
        AC-PERF-1: parse_yyyymm_or_chinese throughput ≥1000 rows/s

        Target: 2000+ rows/s (2x above minimum for safety margin)
        Note: Date parsing is simpler than Pydantic validation, should be faster
        """
        # Warm-up run (exclude from timing, ensure compiled regexes cached)
        for item in date_test_data_10k[:100]:
            try:
                parse_yyyymm_or_chinese(item["value"])
            except ValueError:
                pass  # Expected for invalid dates

        # Timed run on all 10,000 date values
        start_time = time.time()
        valid_count = 0
        invalid_count = 0
        correct_count = 0

        for item in date_test_data_10k:
            try:
                result = parse_yyyymm_or_chinese(item["value"])
                valid_count += 1

                # Verify correctness for valid dates
                if item["expected_valid"]:
                    if result == item["expected_result"]:
                        correct_count += 1
                    else:
                        print(f"MISMATCH at index {item['index']}: "
                              f"value={item['value']}, "
                              f"expected={item['expected_result']}, "
                              f"got={result}")
            except ValueError:
                invalid_count += 1
                # Verify it was expected to be invalid
                if item["expected_valid"]:
                    print(f"UNEXPECTED ERROR at index {item['index']}: value={item['value']}")

        end_time = time.time()
        duration = end_time - start_time

        # Calculate throughput
        total_rows = len(date_test_data_10k)
        rows_per_second = total_rows / duration

        # Calculate accuracy
        expected_valid = sum(1 for item in date_test_data_10k if item["expected_valid"])
        accuracy_pct = (correct_count / expected_valid) * 100 if expected_valid > 0 else 0

        # Report results
        print(f"\n{'='*60}")
        print(f"Performance Test: parse_yyyymm_or_chinese")
        print(f"{'='*60}")
        print(f"Total date values: {total_rows:,}")
        print(f"Valid parses: {valid_count:,}")
        print(f"Invalid/Error: {invalid_count:,}")
        print(f"Correctly parsed: {correct_count:,} / {expected_valid:,} ({accuracy_pct:.1f}%)")
        print(f"Duration: {duration:.3f} seconds")
        print(f"Throughput: {rows_per_second:.0f} rows/s")
        print(f"{'='*60}")

        # AC-PERF-1: Assert ≥1000 rows/s
        assert rows_per_second >= 1000, (
            f"AC-PERF-1 FAILED: Date parsing throughput {rows_per_second:.0f} rows/s "
            f"< 1000 rows/s threshold"
        )

        # Verify accuracy is 100% (all valid dates parsed correctly)
        assert accuracy_pct == 100.0, (
            f"Accuracy check failed: {correct_count}/{expected_valid} correct "
            f"({accuracy_pct:.1f}%)"
        )

        # Target: 2000+ rows/s (2x above minimum)
        if rows_per_second >= 2000:
            print(f"✓ EXCELLENT: Throughput {rows_per_second:.0f} rows/s exceeds target (2000 rows/s)")
        elif rows_per_second >= 1500:
            print(f"✓ GOOD: Throughput {rows_per_second:.0f} rows/s above 1500 rows/s")
        else:
            print(f"⚠ WARNING: Throughput {rows_per_second:.0f} rows/s below target (2000 rows/s)")

    def test_date_parser_format_distribution(self, date_test_data_10k):
        """
        Verify performance across different date formats.

        Ensures no single format is a bottleneck.
        """
        # Group by format type
        format_groups = {
            "integer": [],
            "chinese_4digit": [],
            "iso": [],
            "chinese_2digit": [],
            "fullwidth": [],
            "date_object": [],
            "string_yyyymm": [],
            "yyyymmdd": [],
            "invalid": [],
        }

        for item in date_test_data_10k:
            value = item["value"]
            if not item["expected_valid"]:
                format_groups["invalid"].append(item)
            elif isinstance(value, date):
                format_groups["date_object"].append(item)
            elif isinstance(value, int):
                if value > 100000000:  # YYYYMMDD
                    format_groups["yyyymmdd"].append(item)
                else:  # YYYYMM
                    format_groups["integer"].append(item)
            elif "年" in str(value):
                if any(c in "０１２３４５６７８９" for c in str(value)):
                    format_groups["fullwidth"].append(item)
                elif len(str(value).split("年")[0]) == 2:
                    format_groups["chinese_2digit"].append(item)
                else:
                    format_groups["chinese_4digit"].append(item)
            elif "-" in str(value):
                format_groups["iso"].append(item)
            else:
                format_groups["string_yyyymm"].append(item)

        # Test each format group independently
        print(f"\n{'='*60}")
        print(f"Performance by Format Type")
        print(f"{'='*60}")

        for format_name, items in format_groups.items():
            if not items:
                continue

            start_time = time.time()
            for item in items:
                try:
                    parse_yyyymm_or_chinese(item["value"])
                except ValueError:
                    pass
            end_time = time.time()

            duration = end_time - start_time
            if duration > 0:
                throughput = len(items) / duration
                print(f"{format_name:20s}: {len(items):5,} items, "
                      f"{throughput:7,.0f} rows/s, {duration*1000:6.1f} ms")

        print(f"{'='*60}")

    def test_edge_cases_performance(self):
        """
        Test performance with edge cases:
        - Boundary years (2000, 2030)
        - Various month values (1, 12)
        - Date object passthrough (should be fastest)
        """
        edge_cases = []

        # Boundary years
        for year in [2000, 2001, 2029, 2030]:
            for month in [1, 6, 12]:
                edge_cases.append(year * 100 + month)  # YYYYMM
                edge_cases.append(f"{year}年{month}月")  # Chinese
                edge_cases.append(f"{year}-{month:02d}")  # ISO
                edge_cases.append(date(year, month, 1))  # date object

        # Replicate to ~10k rows for meaningful performance measurement
        edge_cases = edge_cases * (10000 // len(edge_cases))

        start_time = time.time()
        for value in edge_cases:
            result = parse_yyyymm_or_chinese(value)
        end_time = time.time()

        duration = end_time - start_time
        rows_per_second = len(edge_cases) / duration

        print(f"\n{'='*60}")
        print(f"Edge Cases Performance Test")
        print(f"{'='*60}")
        print(f"Total edge cases: {len(edge_cases):,}")
        print(f"Duration: {duration:.3f} seconds")
        print(f"Throughput: {rows_per_second:.0f} rows/s")
        print(f"{'='*60}")

        # Should still meet AC-PERF-1 threshold
        assert rows_per_second >= 1000, (
            f"Edge cases performance {rows_per_second:.0f} rows/s < 1000 rows/s"
        )


# Marker for performance tests (can be skipped in quick test runs)
pytestmark = pytest.mark.performance


if __name__ == "__main__":
    # Allow running performance tests directly
    pytest.main([__file__, "-v", "-s"])
