"""Sample parameter parsing for ETL CLI data slicing.

This module provides utilities for parsing the --sample parameter
which enables processing a subset of data for quick ETL validation.

Syntax: 'index/count' where index is 1-indexed
Example: '1/10' = first 10% of rows, '3/10' = rows 20%-30%
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SampleConfig:
    """Configuration for data sampling/slicing.

    Attributes:
        slice_index: Which slice to read (1-indexed, 1 = first slice)
        slice_count: Total number of slices to divide data into
    """

    slice_index: int
    slice_count: int

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.slice_count < 1:
            raise ValueError(f"slice_count must be >= 1, got {self.slice_count}")
        if self.slice_index < 1 or self.slice_index > self.slice_count:
            raise ValueError(
                f"slice_index must be 1 <= index <= {self.slice_count}, "
                f"got {self.slice_index}"
            )


def parse_sample(value: str) -> SampleConfig:
    """Parse sample parameter in 'index/count' format.

    Args:
        value: Sample specification string, e.g., '1/10' or '3/10'

    Returns:
        SampleConfig with parsed slice_index and slice_count

    Raises:
        ValueError: If format is invalid or values out of range

    Examples:
        >>> parse_sample('1/10')
        SampleConfig(slice_index=1, slice_count=10)
        >>> parse_sample('5/10')
        SampleConfig(slice_index=5, slice_count=10)
    """
    if "/" not in value:
        raise ValueError(
            f"Invalid sample format: '{value}'. Expected 'index/count' format, "
            f"e.g., '1/10' for first 10% of data"
        )

    parts = value.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid sample format: '{value}'. Must contain exactly one '/', "
            f"e.g., '1/10'"
        )

    try:
        slice_index = int(parts[0])
        slice_count = int(parts[1])
    except ValueError as e:
        raise ValueError(
            f"Invalid sample format: '{value}'. Both index and count must be "
            f"integers, e.g., '1/10'"
        ) from e

    return SampleConfig(slice_index=slice_index, slice_count=slice_count)


def calculate_slice_range(total_rows: int, config: SampleConfig) -> Tuple[int, int]:
    """Calculate skip_rows and max_rows for pandas read operations.

    Args:
        total_rows: Total number of data rows (excluding header)
        config: SampleConfig specifying which slice to extract

    Returns:
        Tuple of (skip_rows, max_rows) for pandas nrows/skiprows parameters

    Examples:
        >>> calculate_slice_range(1000, SampleConfig(1, 10))
        (0, 100)  # First 100 rows
        >>> calculate_slice_range(1000, SampleConfig(3, 10))
        (200, 100)  # Skip 200, read 100
        >>> calculate_slice_range(1000, SampleConfig(10, 10))
        (900, 100)  # Last 100 rows (includes remainder)
    """
    if total_rows <= 0:
        return 0, 0

    rows_per_slice = total_rows // config.slice_count
    remainder = total_rows % config.slice_count

    # Calculate skip_rows (0-indexed offset)
    skip_rows = (config.slice_index - 1) * rows_per_slice

    # Calculate max_rows
    # Last slice includes any remainder rows
    if config.slice_index == config.slice_count:
        max_rows = rows_per_slice + remainder
    else:
        max_rows = rows_per_slice

    return skip_rows, max_rows
