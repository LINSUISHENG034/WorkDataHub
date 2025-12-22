from dataclasses import dataclass, field
from typing import List

class DataWarehouseLoaderError(Exception):
    """Raised when data warehouse loader encounters an error."""

@dataclass
class LoadResult:
    """Structured response for WarehouseLoader operations (Story 1.8)."""

    success: bool
    rows_inserted: int
    rows_updated: int
    duration_ms: float
    execution_id: str
    query_count: int = 0
    errors: List[str] = field(default_factory=list)
