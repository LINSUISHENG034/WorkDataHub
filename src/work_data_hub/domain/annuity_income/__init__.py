import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular import issues
# These will be imported when first accessed
AnnuityIncomeIn: Any = None
AnnuityIncomeOut: Any = None
process_with_enrichment: Any = None
BronzeAnnuityIncomeSchema: Any = None
GoldAnnuityIncomeSchema: Any = None
validate_bronze_dataframe: Any = None
validate_gold_dataframe: Any = None

_imports_loaded = False


def _load_imports() -> None:
    """Lazy load all imports to avoid circular import issues."""
    global _imports_loaded, AnnuityIncomeIn, AnnuityIncomeOut, process_with_enrichment
    global BronzeAnnuityIncomeSchema, GoldAnnuityIncomeSchema
    global validate_bronze_dataframe, validate_gold_dataframe

    if _imports_loaded:
        return

    from .models import AnnuityIncomeIn as _AnnuityIncomeIn
    from .models import AnnuityIncomeOut as _AnnuityIncomeOut
    from .service import process_with_enrichment as _process_with_enrichment

    AnnuityIncomeIn = _AnnuityIncomeIn
    AnnuityIncomeOut = _AnnuityIncomeOut
    process_with_enrichment = _process_with_enrichment

    try:  # Optional heavy dependencies (pandas/pandera)
        from .schemas import (
            BronzeAnnuityIncomeSchema as _BronzeAnnuityIncomeSchema,
            GoldAnnuityIncomeSchema as _GoldAnnuityIncomeSchema,
            validate_bronze_dataframe as _validate_bronze_dataframe,
            validate_gold_dataframe as _validate_gold_dataframe,
        )
        BronzeAnnuityIncomeSchema = _BronzeAnnuityIncomeSchema
        GoldAnnuityIncomeSchema = _GoldAnnuityIncomeSchema
        validate_bronze_dataframe = _validate_bronze_dataframe
        validate_gold_dataframe = _validate_gold_dataframe
    except ModuleNotFoundError as exc:  # pragma: no cover
        logger.debug(
            "Skipping annuity_income schema imports because optional dependency is missing: %s",
            exc,
        )

    _imports_loaded = True


def __getattr__(name: str) -> Any:
    """Lazy load attributes on first access."""
    _load_imports()
    if name in __all__:
        return globals().get(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AnnuityIncomeIn",
    "AnnuityIncomeOut",
    "BronzeAnnuityIncomeSchema",
    "GoldAnnuityIncomeSchema",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    "process_with_enrichment",
]
