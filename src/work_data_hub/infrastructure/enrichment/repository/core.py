"""
Core CompanyMappingRepository class.

This module contains the main repository class that composes operations
from sibling modules using mixins.

Story 7.3: Infrastructure Layer Decomposition
"""

from sqlalchemy import Connection

from work_data_hub.utils.logging import get_logger

from ..normalizer import normalize_for_temp_id
from ..types import LookupType
from .company_mapping_ops import CompanyMappingOpsMixin
from .enrichment_index_ops import EnrichmentIndexOpsMixin
from .other_ops import OtherOpsMixin

logger = get_logger(__name__)


class CompanyMappingRepository(
    CompanyMappingOpsMixin,
    EnrichmentIndexOpsMixin,
    OtherOpsMixin,
):
    """
    Database access layer for enterprise schema tables.

    This repository provides batch-optimized operations for company mapping
    lookups and inserts, following the repository pattern with explicit
    transaction management by the caller.

    Composed using mixins for maintainability:
    - CompanyMappingOpsMixin: company_mapping table operations
    - EnrichmentIndexOpsMixin: enrichment_index table operations
    - OtherOpsMixin: Other table operations (company_name_index, base_info, etc.)

    Attributes:
        connection: SQLAlchemy Connection for database operations.

    Example:
        >>> from sqlalchemy import create_engine
        >>> engine = create_engine(database_url)
        >>> with engine.connect() as conn:
        ...     repo = CompanyMappingRepository(conn)
        ...     results = repo.lookup_batch(["FP0001", "FP0002"])
        ...     conn.commit()
    """

    def __init__(self, connection: Connection) -> None:
        """
        Initialize the repository with a database connection.

        Args:
            connection: SQLAlchemy Connection. Caller owns transaction lifecycle.
        """
        self.connection = connection

    @staticmethod
    def _normalize_lookup_key(lookup_key: str, lookup_type: LookupType) -> str:
        """
        Normalize lookup keys for enrichment_index operations.

        AC7: Reuse shared normalizer for customer_name/plan_customer keys.
        """
        if lookup_key is None:
            return ""

        if lookup_type == LookupType.CUSTOMER_NAME:
            return normalize_for_temp_id(str(lookup_key))

        if lookup_type == LookupType.PLAN_CUSTOMER:
            # Expect format {plan_code}|{customer_name}; normalize customer_name
            raw = str(lookup_key)
            if "|" in raw:
                plan_code, customer = raw.split("|", 1)
                normalized_customer = normalize_for_temp_id(customer)
                return f"{plan_code}|{normalized_customer}"
            # Fallback: normalize whole key to avoid missing hits
            return normalize_for_temp_id(raw)

        return str(lookup_key)
