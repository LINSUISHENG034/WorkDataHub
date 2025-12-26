"""
Progress reporting for CompanyIdResolver.

This module provides progress tracking and ETA calculation for long-running
EQC enrichment operations, improving user visibility into batch processing.

Story 7.1-14: EQC API Performance Optimization
Task 4: Progress Reporting (AC-4)

Features:
- Progress bar showing completed/total rows
- ETA based on moving average of processing time
- Cache hit/miss statistics display
"""

import time
from typing import Optional

from tqdm import tqdm

from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


class ProgressReporter:
    """
    Progress reporter for EQC enrichment operations.

    Provides real-time progress tracking with ETA calculation and
    cache statistics display.

    Usage:
        >>> reporter = ProgressReporter(total_rows=1000, verbose=True)
        >>> for i, row in enumerate(df.iterrows()):
        ...     reporter.update(cache_hit=True)
        >>> reporter.finish()
    """

    def __init__(
        self,
        total_rows: int,
        verbose: bool = False,
        desc: str = "Enriching companies",
    ) -> None:
        """
        Initialize progress reporter.

        Args:
            total_rows: Total number of rows to process.
            verbose: Whether to show detailed timing breakdown.
            desc: Description for progress bar.
        """
        self.total_rows = total_rows
        self.verbose = verbose
        self.desc = desc

        # Statistics tracking
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls = 0

        # Timing tracking
        self.start_time: Optional[float] = None
        self.last_update_time: Optional[float] = None

        # Progress bar (lazy initialization)
        self._pbar: Optional[tqdm] = None

    def start(self) -> None:
        """Start progress tracking."""
        self.start_time = time.time()
        self.last_update_time = self.start_time

        if self.verbose:
            self._pbar = tqdm(
                total=self.total_rows,
                desc=self.desc,
                unit="row",
                ncols=100,
            )

            # Show initial cache stats
            self._update_stats_display()

    def update(
        self,
        cache_hit: bool = False,
        api_call: bool = False,
        n: int = 1,
    ) -> None:
        """
        Update progress after processing a row or batch.

        Args:
            cache_hit: Whether this row was a cache hit.
            api_call: Whether an EQC API call was made.
            n: Number of rows processed (default: 1).
        """
        if cache_hit:
            self.cache_hits += n
        else:
            self.cache_misses += n

        if api_call:
            self.api_calls += n

        if self._pbar:
            self._pbar.update(n)
            self._update_stats_display()

        self.last_update_time = time.time()

    def _update_stats_display(self) -> None:
        """Update statistics display on progress bar."""
        if not self._pbar:
            return

        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0
            else 0
        )

        stats_str = f"Cache: {cache_hit_rate:.1%} | API Calls: {self.api_calls}"

        self._pbar.set_postfix_str(stats_str)

    def finish(self) -> None:
        """Finish progress tracking and display final statistics."""
        if self._pbar:
            self._pbar.close()

        elapsed = self._elapsed_seconds()
        total_processed = self.cache_hits + self.cache_misses

        cache_hit_rate = self.cache_hits / total_processed if total_processed > 0 else 0

        logger.info(
            "company_id_resolver.enrichment_complete",
            total_rows=self.total_rows,
            processed_rows=total_processed,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            cache_hit_rate=f"{cache_hit_rate:.1%}",
            api_calls=self.api_calls,
            elapsed_seconds=f"{elapsed:.2f}",
            avg_time_per_row=f"{elapsed / total_processed:.4f}"
            if total_processed > 0
            else "N/A",
        )

    def _elapsed_seconds(self) -> float:
        """Get elapsed time since start."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time

    def eta_seconds(self) -> float:
        """
        Calculate estimated time remaining (ETA).

        Returns:
            ETA in seconds, or 0 if cannot calculate.
        """
        if self.start_time is None or self.last_update_time is None:
            return 0.0

        total_processed = self.cache_hits + self.cache_misses
        if total_processed == 0:
            return 0.0

        elapsed = self._elapsed_seconds()
        avg_time_per_row = elapsed / total_processed
        remaining_rows = self.total_rows - total_processed

        return avg_time_per_row * remaining_rows

    @property
    def cache_hit_rate(self) -> float:
        """
        Calculate current cache hit rate.

        Returns:
            Cache hit rate as a percentage (0.0 to 1.0).
        """
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0
