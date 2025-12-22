"""
Models for File Discovery connectors.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pandas as pd


@dataclass
class DiscoveryMatch:
    """Result of discovery-only operation (no Excel loading)."""

    file_path: Path
    version: str
    sheet_name: str
    resolved_base_path: Path


@dataclass
class DataDiscoveryResult:
    """Result of file discovery operation with rich metadata."""

    df: pd.DataFrame
    file_path: Path
    version: str
    sheet_name: str
    row_count: int
    column_count: int
    duration_ms: int
    columns_renamed: Dict[str, str]
    stage_durations: Dict[str, int]
