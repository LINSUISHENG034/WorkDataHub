"""
Annuity Performance Domain.

This package handles processing and validation of annuity performance data from Excel files
containing Chinese "规模明细" data into PostgreSQL.
"""

from .models import AnnuityPerformanceIn, AnnuityPerformanceOut
from .service import process, process_with_enrichment

__all__ = ["AnnuityPerformanceIn", "AnnuityPerformanceOut", "process", "process_with_enrichment"]
