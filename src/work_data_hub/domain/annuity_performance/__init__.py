"""
Annuity Performance Domain.

This package handles processing and validation of annuity performance data
from Excel files containing Chinese "规模明细" data into PostgreSQL.
"""

from .models import AnnuityPerformanceIn, AnnuityPerformanceOut
from .service import process, process_with_enrichment
from .schemas import (
    BronzeAnnuitySchema,
    GoldAnnuitySchema,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)

__all__ = [
    "AnnuityPerformanceIn",
    "AnnuityPerformanceOut",
    "BronzeAnnuitySchema",
    "GoldAnnuitySchema",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    "process",
    "process_with_enrichment",
]
