"""Dagster ops that inject I/O adapters into domain services (Story 1.6).

This package provides backward-compatible exports for all ops and config classes.
All existing imports of the form `from work_data_hub.orchestration.ops import X`
continue to work without modification.

Story 7.1: This monolithic module was decomposed into focused sub-modules:
- file_processing: File discovery and Excel reading ops
- pipeline_ops: Domain processing pipeline ops
- loading: Database loading ops
- reference_backfill: Reference backfill ops
- company_enrichment: Company enrichment queue ops
- _internal: Shared internal utilities
"""

# Re-export all public symbols for backward compatibility

# File processing ops and configs
# ============================================================================
# Re-exports for test mocking compatibility (Story 7.1)
# ============================================================================
# Tests may patch these at work_data_hub.orchestration.ops.<name>
# so we need to re-export them from the sub-modules where they were imported.
# From file_processing module
from work_data_hub.config.settings import get_settings
from work_data_hub.domain.annuity_income.service import (
    process_with_enrichment as process_annuity_income_with_enrichment,
)

# From pipeline_ops module - for test patching compatibility
from work_data_hub.domain.annuity_performance.service import (
    process_with_enrichment,
)
from work_data_hub.domain.reference_backfill.config_loader import (
    load_foreign_keys_config,
)
from work_data_hub.domain.sandbox_trustee_performance.service import process
from work_data_hub.io.connectors.file_connector import (
    FileDiscoveryService,
)
from work_data_hub.io.loader.warehouse_loader import (
    fill_null_only,
    insert_missing,
    load,
)
from work_data_hub.io.readers.excel_reader import read_excel_rows

# Internal utilities - only expose for test patching compatibility
from ._internal import (
    _PSYCOPG2_NOT_LOADED,
    _load_valid_domains,
    psycopg2,
)

# Company enrichment ops and configs
from .company_enrichment import (
    QueueProcessingConfig,
    process_company_lookup_queue_op,
)

# Demonstration/sample ops
from .demo_ops import load_to_db_op, read_csv_op, validate_op

# Generic domain processing (Story 7.4-3)
from .domain_processing import (
    ProcessDomainOpConfig,
    process_domain_op,
)
from .file_processing import (
    DiscoverFilesConfig,
    ReadExcelConfig,
    ReadProcessConfig,
    discover_files_op,
    read_and_process_sandbox_trustee_files_op,
    read_excel_op,
)

# Generic backfill ops and configs (extracted to separate module for size limits)
from .generic_backfill import (
    GenericBackfillConfig,
    gate_after_backfill,
    generic_backfill_refs_op,
)

# Hybrid reference ops
from .hybrid_reference import HybridReferenceConfig, hybrid_reference_op

# Database loading ops and configs
from .loading import (
    LoadConfig,
    load_op,
)

# Domain processing ops and configs
from .pipeline_ops import (
    DOMAIN_SERVICE_REGISTRY,
    DomainServiceEntry,
    ProcessingConfig,
    process_annual_award_op,
    process_annuity_income_op,
    process_annuity_performance_op,
    process_sandbox_trustee_performance_op,
)

# Reference backfill ops and configs
from .reference_backfill import (
    BackfillRefsConfig,
    backfill_refs_op,
    derive_plan_refs_op,
    derive_portfolio_refs_op,
)

__all__ = [
    # File processing
    "DiscoverFilesConfig",
    "discover_files_op",
    "ReadExcelConfig",
    "read_excel_op",
    "ReadProcessConfig",
    "read_and_process_sandbox_trustee_files_op",
    # Domain processing
    "ProcessingConfig",
    "process_sandbox_trustee_performance_op",
    "process_annuity_performance_op",
    "process_annuity_income_op",
    "process_annual_award_op",
    "read_csv_op",
    "validate_op",
    "load_to_db_op",
    # Loading
    "LoadConfig",
    "load_op",
    # Reference backfill
    "BackfillRefsConfig",
    "GenericBackfillConfig",
    "derive_plan_refs_op",
    "derive_portfolio_refs_op",
    "backfill_refs_op",
    "generic_backfill_refs_op",
    "gate_after_backfill",
    "HybridReferenceConfig",
    "hybrid_reference_op",
    # Company enrichment
    "QueueProcessingConfig",
    "process_company_lookup_queue_op",
    # Internal (for test patching)
    "_PSYCOPG2_NOT_LOADED",
    "psycopg2",
    "_load_valid_domains",
    # Test mocking compatibility re-exports
    "get_settings",
    "FileDiscoveryService",
    "read_excel_rows",
    "process",
    "load",
    "insert_missing",
    "fill_null_only",
    "load_foreign_keys_config",
    "process_with_enrichment",
    "process_annuity_income_with_enrichment",
    # Story 7.4-3: Domain Registry pattern
    "DOMAIN_SERVICE_REGISTRY",
    "DomainServiceEntry",
    "ProcessDomainOpConfig",
    "process_domain_op",
]
