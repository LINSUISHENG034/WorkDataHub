"""EnrichmentServiceFactory - Dependency injection for enrichment services.

Story: Orchestration Layer Refactor - Phase 2
Location: infrastructure/enrichment/factory.py

集中处理 enrichment 服务的创建和依赖注入。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.observability import EnrichmentObserver
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentContext:
    """Container for enrichment service and related resources."""

    service: Optional["CompanyEnrichmentService"]
    observer: Optional["EnrichmentObserver"]
    connection: Optional[object]  # psycopg2 connection

    def cleanup(self) -> None:
        """Release database connection."""
        if self.connection is not None:
            self.connection.close()


class EnrichmentServiceFactory:
    """Factory for creating EnrichmentService instances."""

    @classmethod
    def create(
        cls,
        plan_only: bool = True,
        sync_lookup_budget: int = 0,
    ) -> EnrichmentContext:
        """Create enrichment context.

        Args:
            plan_only: If True, returns empty context
            sync_lookup_budget: Budget for sync lookups

        Returns:
            EnrichmentContext
        """
        if plan_only:
            return EnrichmentContext(service=None, observer=None, connection=None)

        return cls._create_full_context(sync_lookup_budget)

    @classmethod
    def _create_full_context(cls, sync_lookup_budget: int) -> EnrichmentContext:
        """Create full context with DB connection."""
        from work_data_hub.config.settings import get_settings

        settings = get_settings()

        if not settings.enrich_enabled:
            return EnrichmentContext(service=None, observer=None, connection=None)

        conn = cls._create_connection(settings)

        from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
        from work_data_hub.domain.company_enrichment.observability import (
            EnrichmentObserver,
        )
        from work_data_hub.domain.company_enrichment.service import (
            CompanyEnrichmentService,
        )
        from work_data_hub.io.connectors.eqc_client import EQCClient
        from work_data_hub.io.loader.company_enrichment_loader import (
            CompanyEnrichmentLoader,
        )

        observer = EnrichmentObserver()
        service = CompanyEnrichmentService(
            loader=CompanyEnrichmentLoader(conn),
            queue=LookupQueue(conn),
            eqc_client=EQCClient(),
            sync_lookup_budget=sync_lookup_budget,
            observer=observer,
            enrich_enabled=settings.enrich_enabled,
        )

        return EnrichmentContext(service=service, observer=observer, connection=conn)

    @classmethod
    def _create_connection(cls, settings):
        """Create database connection."""
        from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

        try:
            import psycopg2
        except ImportError:
            raise DataWarehouseLoaderError("psycopg2 not available")

        dsn = settings.get_database_connection_string()
        try:
            return psycopg2.connect(dsn)
        except Exception as e:
            raise DataWarehouseLoaderError(f"Connection failed: {e}") from e
