"""Domain processing pipeline ops.

This module contains shared configuration for domain processing operations.
Per-domain ops have been replaced by the generic process_domain_op_v2 in generic_ops.py.

See:
- orchestration/ops/generic_ops.py: Generic domain processing op
- domain/protocols.py: DomainServiceProtocol interface
- domain/registry.py: DOMAIN_SERVICE_REGISTRY
"""

from typing import Any, Dict, Optional

from dagster import Config
from pydantic import field_validator


class ProcessingConfig(Config):
    """Configuration for processing operations with optional enrichment."""

    enrichment_enabled: bool = False
    enrichment_sync_budget: int = 0
    # Story 6.2-P17: EqcLookupConfig serialized dict (preferred SSOT).
    # Kept optional for transition; if missing, we derive from legacy fields.
    eqc_lookup_config: Optional[Dict[str, Any]] = None
    export_unknown_names: bool = True
    plan_only: bool = True
    use_pipeline: Optional[bool] = (
        None  # CLI override for pipeline framework (None=respect setting)
    )
    # Story 7.5-5: Session ID for unified failure logging
    session_id: Optional[str] = None

    @field_validator("enrichment_sync_budget")
    @classmethod
    def validate_sync_budget(cls, v: int) -> int:
        """Validate sync budget is non-negative."""
        if v < 0:
            raise ValueError("Sync budget must be non-negative")
        return v
