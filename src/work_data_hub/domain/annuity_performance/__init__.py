import logging
from typing import Any

from .models import AnnuityPerformanceIn, AnnuityPerformanceOut
from .service import process_with_enrichment

logger = logging.getLogger(__name__)

# Type hints for optional schema imports
BronzeAnnuitySchema: Any
GoldAnnuitySchema: Any
validate_bronze_dataframe: Any
validate_gold_dataframe: Any

try:  # Optional heavy dependencies (pandas/pandera)
    from .schemas import (
        BronzeAnnuitySchema,
        GoldAnnuitySchema,
        validate_bronze_dataframe,
        validate_gold_dataframe,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in minimal envs
    logger.debug(
        "Skipping annuity schema imports because optional dependency is missing: %s",
        exc,
    )
    BronzeAnnuitySchema = None
    GoldAnnuitySchema = None
    validate_bronze_dataframe = None
    validate_gold_dataframe = None

__all__ = [
    "AnnuityPerformanceIn",
    "AnnuityPerformanceOut",
    "BronzeAnnuitySchema",
    "GoldAnnuitySchema",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    "process_with_enrichment",
]
