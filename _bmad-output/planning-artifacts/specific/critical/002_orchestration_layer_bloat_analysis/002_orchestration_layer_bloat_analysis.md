# Orchestration Layer Bloat Analysis

> **Status:** Draft - Pending Discussion
> **Created:** 2026-01-12
> **Authors:** Correct-Course Workflow Analysis
> **Related Epic:** Epic 7.4 (Domain Registry Architecture)

---

## Executive Summary

The orchestration layer (`pipeline_ops.py` and `jobs.py`) exhibits structural bloat that increases maintenance difficulty as domain count grows. Despite Epic 7.4's registry pattern addressing "adding new domains" complexity, the existing per-domain ops and jobs remain, causing continued code duplication and violation of DRY principles.

**Key Metrics:**
| File | Current Lines | 800-Line Limit | Status |
|------|---------------|----------------|--------|
| `pipeline_ops.py` | 604 | 800 | ⚠️ Growing |
| `jobs.py` | 687 | 800 | ⚠️ Near limit |

---

## Problem Statement

### 1. Symptom: Module Bloat

Two files in the orchestration layer grow linearly with each new domain:

- `src/work_data_hub/orchestration/ops/pipeline_ops.py` (604 lines)
- `src/work_data_hub/orchestration/jobs.py` (687 lines)

### 2. Root Cause Analysis

#### 2.1 Domain Service Interface Inconsistency

Each domain service has different parameter signatures and return types:

| Domain | Service Function | Parameters | Return Type |
|--------|------------------|------------|-------------|
| `annuity_performance` | `process_with_enrichment()` | `rows, data_source, eqc_config, enrichment_service, sync_budget, ...` | `ProcessingResultWithEnrichment` |
| `annuity_income` | `process_with_enrichment()` | `rows, data_source, enrichment_service, sync_budget, ...` (no eqc_config) | `ProcessingResultWithEnrichment` |
| `sandbox_trustee_performance` | `process()` | `rows, data_source` (minimal) | `List[TrusteePerformanceOut]` |
| `annual_award` | Pipeline-based | DataFrame + PipelineContext | DataFrame |

**Impact:** Generic ops cannot use uniform call signature - must adapt per domain.

#### 2.2 Enrichment Logic Leakage to Ops Layer

The `process_annuity_performance_op` contains ~260 lines, but only ~10 lines call the domain service. The rest (~250 lines) handles:

| Concern | Lines | Should Be In |
|---------|-------|--------------|
| Enrichment service initialization | ~100 | Infrastructure/Factory |
| Database connection validation | ~20 | Infrastructure |
| psycopg2 lazy loading | ~15 | Infrastructure |
| EqcLookupConfig deserialization | ~15 | Infrastructure |
| Observer stats logging | ~30 | Domain/Infrastructure |
| CSV export | ~20 | Infrastructure |
| Error handling & logging | ~50 | Distributed |

**Violation:** Ops layer (orchestration) doing infrastructure work.

#### 2.3 Jobs Are Nearly Identical

```python
# annuity_performance_job
discovered_paths = discover_files_op()
excel_rows = read_excel_op(discovered_paths)
processed_data = process_annuity_performance_op(excel_rows, discovered_paths)  # ← Only difference
backfill_result = generic_backfill_refs_op(processed_data)
gated_rows = gate_after_backfill(processed_data, backfill_result)
load_op(gated_rows)

# annuity_income_job (identical structure)
discovered_paths = discover_files_op()
excel_rows = read_excel_op(discovered_paths)
processed_data = process_annuity_income_op(excel_rows, discovered_paths)  # ← Only difference
backfill_result = generic_backfill_refs_op(processed_data)
gated_rows = gate_after_backfill(processed_data, backfill_result)
load_op(gated_rows)
```

**All 4 jobs differ only in which `process_*_op` they call.**

### 3. Epic 7.4 Analysis

Epic 7.4 introduced:
- ✅ `JOB_REGISTRY` - eliminates CLI dispatch if/elif chains
- ✅ `DOMAIN_SERVICE_REGISTRY` - metadata for domain services
- ✅ `process_domain_op` - generic op (created but NOT used)
- ✅ `requires_backfill` config - replaces hardcoded list

**What Epic 7.4 did NOT do:**
- ❌ Migrate existing jobs to use `process_domain_op`
- ❌ Remove per-domain ops
- ❌ Standardize domain service interfaces

From Story 7.4-3 documentation:
> "**OUT OF SCOPE:** Migrating existing jobs to use generic op (optional future story)"

---

## Current Module Size Baseline

### Enrichment-Related Modules

| Location | Module | Lines | Status |
|----------|--------|-------|--------|
| domain/ | company_enrichment/service.py | **846** | ❌ Exceeds 800 |
| domain/ | company_enrichment/lookup_queue.py | 733 | ⚠️ Near limit |
| domain/ | company_enrichment/models.py | 755 | ⚠️ Near limit |
| infrastructure/ | enrichment/domain_learning_service.py | **812** | ❌ Exceeds 800 |
| infrastructure/ | enrichment/eqc_provider.py | 764 | ⚠️ Near limit |
| ops/ | pipeline_ops.py (enrichment portion) | ~120 | Leaked to ops |

### Domain Service Sizes

| Domain | service.py Lines | Status |
|--------|------------------|--------|
| annual_award | 278 | ✅ Healthy |
| annuity_performance | 335 | ✅ Healthy |
| sandbox_trustee_performance | 389 | ✅ Healthy |
| annuity_income | 410 | ✅ Healthy |
| reference_backfill | 459 | ⚠️ Medium |
| company_enrichment | **846** | ❌ Exceeds limit |

---

## Proposed Solutions

### Solution C: EnrichmentServiceFactory (Recommended for Phase 1)

#### Concept

Extract enrichment initialization logic from ops into a dedicated factory class in the infrastructure layer.

#### Design

**New File:** `src/work_data_hub/infrastructure/enrichment/factory.py`

```python
"""
EnrichmentServiceFactory - Dependency injection for enrichment services.

Story: Orchestration Layer Bloat Resolution
Location: infrastructure/enrichment/factory.py
Lines: ~120 (estimated)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from work_data_hub.config.settings import get_settings
from work_data_hub.io.loader.warehouse_loader import DataWarehouseLoaderError

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.observability import EnrichmentObserver
    from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
    from work_data_hub.infrastructure.enrichment.eqc_lookup_config import EqcLookupConfig

logger = logging.getLogger(__name__)

# Sentinel for lazy psycopg2 loading
_PSYCOPG2_NOT_LOADED = object()
_psycopg2_module = _PSYCOPG2_NOT_LOADED


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
    """
    Factory for creating configured EnrichmentService instances.

    Centralizes:
    - Database connection validation and creation
    - psycopg2 lazy loading
    - Dependency injection for CompanyEnrichmentService
    - Resource cleanup management

    Usage:
        context = EnrichmentServiceFactory.create(eqc_config, plan_only=False)
        try:
            result = domain_service.process(rows, enrichment_service=context.service)
        finally:
            context.cleanup()
    """

    @classmethod
    def create(
        cls,
        eqc_config: "EqcLookupConfig",
        plan_only: bool = True,
        sync_lookup_budget: int = 0,
    ) -> EnrichmentContext:
        """
        Create enrichment context with all dependencies wired.

        Args:
            eqc_config: EQC lookup configuration (SSOT for enrichment behavior)
            plan_only: If True, returns empty context (no DB operations)
            sync_lookup_budget: Budget for synchronous EQC lookups

        Returns:
            EnrichmentContext with service, observer, and connection

        Raises:
            DataWarehouseLoaderError: If database connection fails
        """
        settings = get_settings()

        # Guard: Only create service in execute mode with enrichment enabled
        use_enrichment = (
            not plan_only
            and eqc_config.enabled
            and settings.enrich_enabled
        )

        if not use_enrichment:
            return EnrichmentContext(service=None, observer=None, connection=None)

        # Validate and create connection
        conn = cls._create_connection(settings)

        # Import and assemble dependencies (lazy to avoid circular imports)
        from work_data_hub.domain.company_enrichment.lookup_queue import LookupQueue
        from work_data_hub.domain.company_enrichment.observability import EnrichmentObserver
        from work_data_hub.domain.company_enrichment.service import CompanyEnrichmentService
        from work_data_hub.io.connectors.eqc_client import EQCClient
        from work_data_hub.io.loader.company_enrichment_loader import CompanyEnrichmentLoader

        observer = EnrichmentObserver()
        service = CompanyEnrichmentService(
            loader=CompanyEnrichmentLoader(conn),
            queue=LookupQueue(conn),
            eqc_client=EQCClient(),
            sync_lookup_budget=sync_lookup_budget,
            observer=observer,
            enrich_enabled=settings.enrich_enabled,
        )

        logger.info(
            "enrichment_service.created",
            extra={
                "sync_budget": sync_lookup_budget,
                "eqc_enabled": eqc_config.enabled,
            },
        )

        return EnrichmentContext(service=service, observer=observer, connection=conn)

    @classmethod
    def _create_connection(cls, settings):
        """Create and validate database connection."""
        # Validate required settings
        missing = []
        if not settings.database_host:
            missing.append("WDH_DATABASE__HOST")
        if not settings.database_port:
            missing.append("WDH_DATABASE__PORT")
        if not settings.database_db:
            missing.append("WDH_DATABASE__DB")
        if not settings.database_user:
            missing.append("WDH_DATABASE__USER")
        if not settings.database_password:
            missing.append("WDH_DATABASE__PASSWORD")

        if missing:
            raise DataWarehouseLoaderError(
                f"Database settings missing for enrichment: {', '.join(missing)}. "
                "Set them in .wdh_env and try again."
            )

        # Lazy load psycopg2
        global _psycopg2_module
        if _psycopg2_module is _PSYCOPG2_NOT_LOADED:
            try:
                import psycopg2
                _psycopg2_module = psycopg2
            except ImportError:
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for enrichment database operations"
                )

        # Create connection
        dsn = settings.get_database_connection_string()
        try:
            return _psycopg2_module.connect(dsn)
        except Exception as e:
            raise DataWarehouseLoaderError(
                f"Database connection failed for enrichment: {e}"
            ) from e
```

#### Impact Analysis

| Module | Before | After | Change |
|--------|--------|-------|--------|
| `infrastructure/enrichment/factory.py` | 0 | ~120 | +120 (new file) |
| `ops/pipeline_ops.py` | 604 | ~480 | -124 |
| Domain services | unchanged | unchanged | 0 |

**Net effect:** Code moved to proper layer, no new bloat introduced.

#### Benefits

1. **Single Responsibility:** Factory handles only service assembly
2. **Testability:** Factory can be mocked in tests
3. **Reusability:** Any code needing enrichment service uses same factory
4. **Clean Architecture:** Infrastructure layer handles infrastructure concerns

#### Risks

| Risk | Mitigation |
|------|------------|
| Circular imports | Use TYPE_CHECKING + lazy imports (pattern already established) |
| Connection lifecycle | EnrichmentContext.cleanup() ensures proper release |
| Breaking changes | Ops refactoring is internal; external API unchanged |

---

### Solution D: Interface Standardization + Generic Ops/Jobs

#### Concept

Standardize domain service interfaces to enable truly generic orchestration.

#### Phase D.1: Unified Service Interface

**Target Interface:**

```python
# domain/protocols.py (new file)

from typing import Protocol, List, Dict, Any, Optional
from work_data_hub.domain.pipelines.types import DomainProcessingResult

class DomainServiceProtocol(Protocol):
    """Standard interface for all domain processing services."""

    def process(
        self,
        rows: List[Dict[str, Any]],
        data_source: str,
        config: "DomainProcessingConfig",
    ) -> DomainProcessingResult:
        """
        Process rows through domain transformation pipeline.

        Args:
            rows: Raw data rows from source file
            data_source: Identifier for source file/system
            config: Unified configuration for processing

        Returns:
            Standardized result with records, stats, and metadata
        """
        ...


@dataclass
class DomainProcessingConfig:
    """Unified configuration for domain processing."""

    # Core settings
    plan_only: bool = True
    session_id: Optional[str] = None

    # Enrichment settings (optional, ignored if domain doesn't support)
    eqc_config: Optional["EqcLookupConfig"] = None
    enrichment_service: Optional["CompanyEnrichmentService"] = None
    export_unknown_names: bool = True


@dataclass
class DomainProcessingResult:
    """Unified result from domain processing."""

    records: List[Any]  # Processed Pydantic models
    total_input: int
    total_output: int
    failed_count: int
    processing_time_ms: float

    # Optional enrichment stats
    enrichment_stats: Optional[Dict[str, Any]] = None
    unknown_names_csv: Optional[str] = None

    def to_dicts(self) -> List[Dict[str, Any]]:
        """Convert records to JSON-serializable dicts."""
        return [
            record.model_dump(mode="json", by_alias=True, exclude_none=True)
            for record in self.records
        ]
```

#### Phase D.2: Domain Service Adaptation

Each domain service wraps existing logic with standardized interface:

```python
# domain/annuity_performance/service.py

class AnnuityPerformanceService:
    """Standardized service wrapper for annuity_performance domain."""

    def process(
        self,
        rows: List[Dict[str, Any]],
        data_source: str,
        config: DomainProcessingConfig,
    ) -> DomainProcessingResult:
        """Delegate to existing process_with_enrichment with interface adaptation."""

        # Resolve EqcLookupConfig
        eqc_config = config.eqc_config or EqcLookupConfig.disabled()

        # Call existing function
        result = process_with_enrichment(
            rows,
            data_source=data_source,
            eqc_config=eqc_config,
            enrichment_service=config.enrichment_service,
            export_unknown_names=config.export_unknown_names,
            session_id=config.session_id,
        )

        # Adapt to standard result
        return DomainProcessingResult(
            records=result.records,
            total_input=len(rows),
            total_output=len(result.records),
            failed_count=len(rows) - len(result.records),
            processing_time_ms=result.processing_time_ms,
            enrichment_stats=result.enrichment_stats.to_dict() if result.enrichment_stats else None,
            unknown_names_csv=result.unknown_names_csv,
        )
```

#### Phase D.3: Generic Op Implementation

```python
# orchestration/ops/pipeline_ops.py

@op
def process_domain_op(
    context: OpExecutionContext,
    config: ProcessDomainOpConfig,
    excel_rows: List[Dict[str, Any]],
    file_paths: List[str],
) -> List[Dict[str, Any]]:
    """
    Generic domain processing op using standardized interface.

    Replaces all per-domain ops (process_annuity_performance_op, etc.)
    """
    domain = config.domain
    file_path = file_paths[0] if file_paths else "unknown"

    # Get domain service from registry
    service = DOMAIN_SERVICE_REGISTRY.get(domain)
    if not service:
        raise ValueError(f"Unknown domain: {domain}")

    # Create enrichment context using factory
    eqc_config = EqcLookupConfig.from_dict(config.eqc_lookup_config) if config.eqc_lookup_config else EqcLookupConfig.disabled()
    enrichment_ctx = EnrichmentServiceFactory.create(
        eqc_config=eqc_config,
        plan_only=config.plan_only,
        sync_lookup_budget=config.enrichment_sync_budget,
    )

    try:
        # Build unified config
        processing_config = DomainProcessingConfig(
            plan_only=config.plan_only,
            session_id=config.session_id,
            eqc_config=eqc_config,
            enrichment_service=enrichment_ctx.service,
            export_unknown_names=config.export_unknown_names,
        )

        # Call domain service with standard interface
        result = service.process(excel_rows, data_source=file_path, config=processing_config)

        # Log results
        context.log.info(
            "domain_processing.completed",
            extra={
                "domain": domain,
                "input_rows": result.total_input,
                "output_records": result.total_output,
                "failed": result.failed_count,
            },
        )

        return result.to_dicts()

    finally:
        enrichment_ctx.cleanup()
```

#### Phase D.4: Generic Job

```python
# orchestration/jobs.py

@job
def generic_domain_job() -> Any:
    """
    Generic ETL job for all domains.

    Replaces all per-domain jobs (annuity_performance_job, annuity_income_job, etc.)
    Domain is specified via run_config.
    """
    discovered_paths = discover_files_op()
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_domain_op(excel_rows, discovered_paths)  # Generic!
    backfill_result = generic_backfill_refs_op(processed_data)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)
```

#### Impact Analysis

| Module | Before | After | Change |
|--------|--------|-------|--------|
| `domain/protocols.py` | 0 | ~80 | +80 (new) |
| `infrastructure/enrichment/factory.py` | 0 | ~120 | +120 (new) |
| `ops/pipeline_ops.py` | 604 | ~200 | -404 |
| `jobs.py` | 687 | ~300 | -387 |
| Per-domain service wrappers | 0 | ~50 each | +200 total |

**Net reduction:** ~400 lines removed from orchestration layer

#### Implementation Phases

| Phase | Scope | Effort | Risk |
|-------|-------|--------|------|
| D.1 | Define protocols and interfaces | Low | Low |
| D.2 | Add wrapper classes to 4 domains | Medium | Medium |
| D.3 | Implement generic op (already exists, needs update) | Medium | Medium |
| D.4 | Create generic job, migrate CLI | Medium | Medium |
| D.5 | Remove legacy per-domain ops/jobs | Low | Low (after testing) |

---

## Recommended Approach

### Phased Implementation

| Phase | Solution | Deliverable | Risk |
|-------|----------|-------------|------|
| **Phase 1** | Solution C | `EnrichmentServiceFactory` | Low |
| **Phase 2** | Solution D.1-D.2 | Protocol + Service wrappers | Medium |
| **Phase 3** | Solution D.3-D.5 | Generic ops/jobs, cleanup | Medium |

### Phase 1 is Independently Valuable

- Reduces `pipeline_ops.py` by ~124 lines
- Establishes factory pattern for future use
- No changes to public API
- Can be completed in single story

### Success Criteria

1. **Phase 1:** `pipeline_ops.py` < 500 lines, no functional changes
2. **Phase 2:** All domain services implement `DomainServiceProtocol`
3. **Phase 3:** Only 1 generic op and 1 generic job remain, all tests pass

---

## Open Questions

1. **Service wrapper overhead:** Is adding wrapper classes to each domain worth the orchestration simplification?
2. **Migration strategy:** Should we deprecate old ops/jobs gradually or remove in one release?
3. **Testing burden:** How to ensure parity between old and new implementations during transition?
4. **annual_award special case:** This domain uses DataFrame-based pipeline, not row-based. How to unify?

---

## References

- [Epic 7.4 Domain Registry Architecture](../../architecture/domain-registry.md)
- [Epic 7 Retrospective](../../sprint-artifacts/retrospective/epic-7-retro-2025-12-23.md)
- [Story 7.4-3 Generic Process Domain Op](../../sprint-artifacts/stories/epic-7/7.4-3-generic-process-domain-op.md)
- [Implementation Patterns - Pattern 6](../../architecture/implementation-patterns.md#pattern-6-package-modularization-epic-7)

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2026-01-12 | Correct-Course Workflow | Initial draft |
