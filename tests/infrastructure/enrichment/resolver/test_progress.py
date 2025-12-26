"""
Tests for progress reporting functionality.

Story 7.1-14: EQC API Performance Optimization
Task 4: Progress Reporting (AC-4)
"""

import time
from unittest.mock import patch

import pytest

from work_data_hub.infrastructure.enrichment.resolver.progress import (
    ProgressReporter,
)


class TestProgressReporter:
    """Tests for ProgressReporter class."""

    def test_init_default_values(self):
        """Test ProgressReporter initialization with default values."""
        reporter = ProgressReporter(total_rows=100)

        assert reporter.total_rows == 100
        assert reporter.verbose is False
        assert reporter.desc == "Enriching companies"
        assert reporter.cache_hits == 0
        assert reporter.cache_misses == 0
        assert reporter.api_calls == 0
        assert reporter.start_time is None

    def test_init_custom_values(self):
        """Test ProgressReporter initialization with custom values."""
        reporter = ProgressReporter(
            total_rows=500,
            verbose=True,
            desc="Custom description",
        )

        assert reporter.total_rows == 500
        assert reporter.verbose is True
        assert reporter.desc == "Custom description"

    def test_start_sets_time(self):
        """Test that start() sets start_time."""
        reporter = ProgressReporter(total_rows=10, verbose=False)

        assert reporter.start_time is None
        reporter.start()
        assert reporter.start_time is not None
        assert isinstance(reporter.start_time, float)

    def test_update_cache_hit(self):
        """Test update with cache hit."""
        reporter = ProgressReporter(total_rows=10)
        reporter.start()

        reporter.update(cache_hit=True)

        assert reporter.cache_hits == 1
        assert reporter.cache_misses == 0

    def test_update_cache_miss(self):
        """Test update with cache miss."""
        reporter = ProgressReporter(total_rows=10)
        reporter.start()

        reporter.update(cache_hit=False)

        assert reporter.cache_hits == 0
        assert reporter.cache_misses == 1

    def test_update_with_api_call(self):
        """Test update with API call flag."""
        reporter = ProgressReporter(total_rows=10)
        reporter.start()

        reporter.update(cache_hit=False, api_call=True)

        assert reporter.api_calls == 1

    def test_update_batch(self):
        """Test update with batch size n > 1."""
        reporter = ProgressReporter(total_rows=100)
        reporter.start()

        reporter.update(cache_hit=True, n=10)

        assert reporter.cache_hits == 10

    def test_cache_hit_rate_property(self):
        """Test cache_hit_rate property calculation."""
        reporter = ProgressReporter(total_rows=10)
        reporter.start()

        # Simulate 3 hits, 2 misses
        reporter.update(cache_hit=True, n=3)
        reporter.update(cache_hit=False, n=2)

        assert reporter.cache_hit_rate == 0.6  # 3/5

    def test_cache_hit_rate_zero_processed(self):
        """Test cache_hit_rate with no rows processed."""
        reporter = ProgressReporter(total_rows=10)
        reporter.start()

        assert reporter.cache_hit_rate == 0.0

    def test_eta_calculation(self):
        """Test ETA calculation."""
        reporter = ProgressReporter(total_rows=10)
        reporter.start()

        # Simulate some processing time
        time.sleep(0.1)
        reporter.update(cache_hit=True, n=5)

        eta = reporter.eta_seconds()

        # ETA should be positive (we have 5 rows remaining)
        assert eta >= 0

    def test_eta_before_start(self):
        """Test ETA returns 0 before start."""
        reporter = ProgressReporter(total_rows=10)

        assert reporter.eta_seconds() == 0.0

    def test_elapsed_seconds(self):
        """Test elapsed time calculation."""
        reporter = ProgressReporter(total_rows=10)
        reporter.start()

        time.sleep(0.05)
        elapsed = reporter._elapsed_seconds()

        assert elapsed >= 0.05

    def test_elapsed_before_start(self):
        """Test elapsed returns 0 before start."""
        reporter = ProgressReporter(total_rows=10)

        assert reporter._elapsed_seconds() == 0.0

    def test_finish_logs_statistics(self):
        """Test finish() logs final statistics."""
        reporter = ProgressReporter(total_rows=10, verbose=False)
        reporter.start()

        reporter.update(cache_hit=True, n=7)
        reporter.update(cache_hit=False, n=3)

        # finish() should not raise
        reporter.finish()

        assert reporter.cache_hits == 7
        assert reporter.cache_misses == 3

    def test_verbose_mode_creates_progress_bar(self):
        """Test verbose mode creates tqdm progress bar."""
        reporter = ProgressReporter(total_rows=10, verbose=True)
        reporter.start()

        # Progress bar should be created
        assert reporter._pbar is not None

        reporter.finish()

    def test_non_verbose_mode_no_progress_bar(self):
        """Test non-verbose mode does not create progress bar."""
        reporter = ProgressReporter(total_rows=10, verbose=False)
        reporter.start()

        assert reporter._pbar is None


class TestProgressReporterIntegration:
    """Integration tests for ProgressReporter."""

    def test_full_workflow(self):
        """Test complete workflow: start -> updates -> finish."""
        reporter = ProgressReporter(total_rows=100, verbose=False)

        reporter.start()

        # Simulate processing 100 rows
        for i in range(100):
            is_cache_hit = i % 2 == 0  # 50% cache hit rate
            reporter.update(cache_hit=is_cache_hit)

        reporter.finish()

        assert reporter.cache_hits == 50
        assert reporter.cache_misses == 50
        assert reporter.cache_hit_rate == 0.5

    def test_workflow_with_api_calls(self):
        """Test workflow tracking API calls."""
        reporter = ProgressReporter(total_rows=10, verbose=False)

        reporter.start()

        # Simulate: 7 cache hits, 3 misses triggering API calls
        reporter.update(cache_hit=True, n=7)
        reporter.update(cache_hit=False, api_call=True, n=3)

        reporter.finish()

        assert reporter.cache_hits == 7
        assert reporter.cache_misses == 3
        assert reporter.api_calls == 3
