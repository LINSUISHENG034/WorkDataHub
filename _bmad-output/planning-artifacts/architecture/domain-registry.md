# Domain Registry Architecture

> **Epic:** 7.4 - Domain Registry Architecture
> **Status:** ✅ Implemented (2025-12-30)
> **Authors:** Correct-Course Workflow, Development Team

---

## Overview

### Problem Statement

Prior to Epic 7.4, the ETL system used **hardcoded if/elif dispatch chains** to route domain processing requests. Adding a new domain required modifications to **5-7 files minimum**:

1. `domain/{new_domain}/` - Create domain package (Required)
2. `orchestration/ops/pipeline_ops.py` - Add `process_{domain}_op` (Required)
3. `orchestration/jobs.py` - Add `{domain}_job` function (Required)
4. `cli/etl/executors.py` - Add elif branch (Required)
5. `cli/etl/config.py` - Update backfill domain list (Conditional)
6. `config/data_sources.yml` - Add domain config (Required)
7. `config/foreign_keys.yml` - Add FK config (Conditional)

This violated:
- **Open/Closed Principle (OCP)**: System must be modified for new domains
- **Single Responsibility Principle (SRP)**: Domain capabilities scattered across files
- **KISS Principle**: Unnecessary complexity for domain addition

### Solution: Registry Pattern

Epic 7.4 introduced **configuration-driven registries** that serve as the single source of truth for domain metadata and capabilities.

**Benefits:**
- ✅ Add new domain in **2-3 files** (domain package + config)
- ✅ Eliminate if/elif dispatch chains
- ✅ Declarative domain capabilities in `data_sources.yml`
- ✅ Self-documenting supported domains
- ✅ Better testability (registry can be mocked)

---

## Registry Entry Types

### JobEntry (`orchestration/jobs.py`)

Encapsulates Dagster Job metadata for a domain.

```python
@dataclass(frozen=True)
class JobEntry:
    """Registry entry for a domain's Dagster job(s).

    Attributes:
        job: The primary Dagster JobDefinition (required, must not be None)
        multi_file_job: Optional job for max_files > 1 scenarios
        supports_backfill: Whether domain has FK backfill configured in foreign_keys.yml
    """

    job: Any  # Dagster JobDefinition - MUST be a valid job, never None
    multi_file_job: Optional[Any] = None  # For max_files > 1 scenarios
    supports_backfill: bool = False  # Whether domain has FK backfill configured
```

**Purpose:** Enables CLI executor to dispatch jobs dynamically without hardcoded branches.

### DomainServiceEntry (`orchestration/ops/pipeline_ops.py`)

Encapsulates domain processing service metadata.

```python
@dataclass(frozen=True)
class DomainServiceEntry:
    """Registry entry for a domain's processing service.

    Attributes:
        service_fn: Callable that processes rows and returns models/results.
            Expected signature: (rows: List[Dict], data_source: str, **kwargs) -> Any
        supports_enrichment: Whether the domain supports company enrichment
            (EQC lookup, cache queries, etc.)
        domain_name: Human-readable domain name for logging and error messages
    """

    service_fn: Callable[[List[Dict[str, Any]], str], Any]
    supports_enrichment: bool = False
    domain_name: str = ""
```

**Purpose:** Enables `process_domain_op` to delegate to domain services dynamically, eliminating per-domain op functions.

---

## JOB_REGISTRY

### Location

`src/work_data_hub/orchestration/jobs.py`

### Structure

```python
JOB_REGISTRY: Dict[str, JobEntry] = {
    "annuity_performance": JobEntry(
        job=generic_domain_job,
        supports_backfill=True,
    ),
    "annuity_income": JobEntry(
        job=generic_domain_job,
        supports_backfill=True,
    ),
    "annual_award": JobEntry(
        job=generic_domain_job,
        supports_backfill=True,
    ),
    "annual_loss": JobEntry(
        job=generic_domain_job,
        supports_backfill=True,
    ),
    "sandbox_trustee_performance": JobEntry(
        job=generic_domain_job,
        multi_file_job=generic_domain_multi_file_job,
        supports_backfill=True,
    ),
}
```

> **Note (Phase 4 update):** All domains now use `generic_domain_job` via Protocol registry pattern, replacing per-domain job functions.

### How CLI Uses It (Story 7.4-1)

**Before (Epic 7.4):**
```python
# cli/etl/executors.py:200-232
if domain_key == "annuity_performance":
    from work_data_hub.orchestration.jobs import annuity_performance_job
    selected_job = annuity_performance_job
elif domain_key == "annuity_income":
    from work_data_hub.orchestration.jobs import annuity_income_job
    selected_job = annuity_income_job
elif domain_key == "sandbox_trustee_performance":
    # ... more imports
else:
    raise ValueError(f"Unsupported domain: {domain}...")
```

**After (Epic 7.4):**
```python
# cli/etl/executors.py
from work_data_hub.orchestration.jobs import JOB_REGISTRY

# Special domains (non-registry)
if domain_key in ("company_lookup_queue", "reference_sync"):
    return _execute_special_job(domain_key, args)

# Registry-based dispatch
job_entry = JOB_REGISTRY.get(domain_key)
if not job_entry:
    supported = ", ".join(JOB_REGISTRY.keys())
    raise ValueError(f"Unsupported domain: {domain}. Supported: {supported}")

selected_job = job_entry.job
if max_files > 1 and job_entry.multi_file_job:
    selected_job = job_entry.multi_file_job
```

**Impact:** Eliminated MD-001 (High Severity) - hardcoded if/elif chain.

---

## DOMAIN_SERVICE_REGISTRY

### Location

`src/work_data_hub/domain/registry.py` (moved from `orchestration/ops/pipeline_ops.py` in Phase 4 refactor)

### Structure

> **Phase 4 update:** Registry now uses `DomainServiceProtocol` instead of `DomainServiceEntry` dataclass. Services are adapter classes implementing the protocol, registered at module load time.

```python
# domain/registry.py
from work_data_hub.domain.protocols import DomainServiceProtocol

DOMAIN_SERVICE_REGISTRY: Dict[str, DomainServiceProtocol] = {}

def register_domain(name: str, service: DomainServiceProtocol) -> None:
    DOMAIN_SERVICE_REGISTRY[name] = service

# Auto-registration at import time
def _register_all_domains() -> None:
    register_domain("annuity_performance", AnnuityPerformanceService())
    register_domain("annuity_income", AnnuityIncomeService())
    register_domain("sandbox_trustee_performance", SandboxTrusteePerformanceService())
    register_domain("annual_award", AnnualAwardService())
    register_domain("annual_loss", AnnualLossService())

_register_all_domains()
```

### How Ops Uses It (Story 7.4-3)

**Generic `process_domain_op`** replaces per-domain `process_{domain}_op` functions:

```python
# orchestration/ops/pipeline_ops.py
@op
def process_domain_op(
    context: OpExecutionContext,
    excel_rows: List[Dict[str, Any]],
    discovered_paths: List[str],
    config: ProcessDomainOpConfig,
) -> DomainPipelineResult:
    """Generic domain processing op that delegates to domain service."""
    domain = config.domain

    # Lookup domain service from registry
    service_entry = DOMAIN_SERVICE_REGISTRY.get(domain)
    if not service_entry:
        raise ValueError(f"Unsupported domain: {domain}")

    # Delegate to domain service
    return service_entry.service_fn(
        excel_rows=excel_rows,
        data_source=domain,
        context=context,
    )
```

**Impact:** Eliminated MD-003 (Medium Severity) - per-domain op functions.

---

## Adding a New Domain

### Before Epic 7.4 (5-7 files)

| Step | File | Change |
|------|------|--------|
| 1 | `domain/{new_domain}/` | Create package (models, service, __init__) |
| 2 | `orchestration/ops/pipeline_ops.py` | Add `process_{domain}_op` function |
| 3 | `orchestration/jobs.py` | Add `{domain}_job` function |
| 4 | `cli/etl/executors.py` | Add elif branch to dispatch |
| 5 | `cli/etl/config.py` | Add domain to backfill list |
| 6 | `config/data_sources.yml` | Add domain config |
| 7 | `config/foreign_keys.yml` | Add FK config (if needed) |

### After Epic 7.4 (2-3 files)

| Step | File | Change |
|------|------|--------|
| 1 | `domain/{new_domain}/` | Create package (models, service, __init__) |
| 2 | `config/data_sources.yml` | Add domain config with `requires_backfill` |
| 3 | `config/foreign_keys.yml` | Add FK config (if needed) |

**What Changed:**
- ❌ No longer modify `orchestration/jobs.py` - Register in `JOB_REGISTRY` within domain package
- ❌ No longer modify `cli/etl/executors.py` - Registry lookup handles dispatch
- ❌ No longer modify `cli/etl/config.py` - Use `requires_backfill` in `data_sources.yml`
- ❌ No longer add per-domain ops - Generic `process_domain_op` delegates via `DOMAIN_SERVICE_REGISTRY`

### Step-by-Step Guide

#### Step 1: Create Domain Package

```bash
mkdir -p src/work_data_hub/domain/{new_domain}
```

**`__init__.py`:**
```python
from work_data_hub.orchestration.jobs import JOB_REGISTRY
from work_data_hub.orchestration.ops.pipeline_ops import DOMAIN_SERVICE_REGISTRY
from .service import process_{new_domain}_rows
from .models import {NewDomain}Model

# Register job
from work_data_hub.orchestration.jobs import job, generic_backfill_refs_op, gate_after_backfill, load_op

@job
def {new_domain}_job() -> Any:
    discovered_paths = discover_files_op()
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_domain_op(excel_rows, discovered_paths)
    backfill_result = generic_backfill_refs_op(processed_data)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)

# Register in JOB_REGISTRY
JOB_REGISTRY["{new_domain}"] = JobEntry(
    job={new_domain}_job,
    supports_backfill=True,  # Or False
)

# Register in DOMAIN_SERVICE_REGISTRY
DOMAIN_SERVICE_REGISTRY["{new_domain}"] = DomainServiceEntry(
    service_fn=process_{new_domain}_rows,
    supports_enrichment=False,  # Or True
    domain_name="{Human Readable Name}",
)
```

**`models.py`:**
```python
from pydantic import BaseModel

class {NewDomain}Model(BaseModel):
    """Domain-specific data model."""
    field1: str
    field2: int
```

**`service.py`:**
```python
from typing import List, Dict, Any
from .models import {NewDomain}Model

def process_{new_domain}_rows(
    rows: List[Dict[str, Any]],
    data_source: str,
    **kwargs
) -> List[{NewDomain}Model]:
    """Process rows into domain models."""
    return [
        {NewDomain}Model(**row)
        for row in rows
    ]
```

#### Step 2: Configure Data Source

**`config/data_sources.yml`:**
```yaml
defaults:
  requires_backfill: false  # Default to no backfill

domains:
  {new_domain}:
    base_path: "path/to/{YYYYMM}/data"
    file_patterns:
      - "*pattern*.xlsx"
    sheet_name: "Sheet1"
    requires_backfill: true  # Enable if FK backfill needed
    output:
      table: "target_table_name"
      schema_name: "business"
      pk:
        - "id_column"
```

#### Step 3: Configure Foreign Keys (Optional)

**`config/foreign_keys.yml`:**
```yaml
domains:
  {new_domain}:
    foreign_keys:
      fk_reference:
        table: "reference_table"
        schema_name: "business"
        source_columns:
          source_col: "target_col"
        lookup_column: "id"
```

---

## Configuration Options

### `requires_backfill` (Story 7.4-2)

**Location:** `config/data_sources.yml`

**Purpose:** Declarative configuration for FK backfill requirement.

**Before (Hardcoded):**
```python
# cli/etl/config.py:157
if domain in ["annuity_performance", "annuity_income", "sandbox_trustee_performance"]:
    run_config["ops"]["generic_backfill_refs_op"] = {...}
```

**After (Config-Driven):**
```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    requires_backfill: true  # Explicit opt-in
  annuity_income:
    requires_backfill: true
  simple_domain:
    requires_backfill: false  # Default behavior
```

**Usage:**
```python
# cli/etl/config.py
domain_cfg = load_domain_config(domain)
if domain_cfg.requires_backfill:
    run_config["ops"]["generic_backfill_refs_op"] = {...}
```

**Impact:** Eliminated MD-002 (Medium Severity) - hardcoded backfill domain list.

### Foreign Keys Configuration

**Location:** `config/foreign_keys.yml`

**Purpose:** Define FK relationships for backfill operations.

**Example:**
```yaml
domains:
  annuity_performance:
    foreign_keys:
      fk_customer:
        table: "enterprise"
        schema_name: "enterprise"
        source_columns:
          customer_name: "company_name"
        lookup_column: "company_name"
      fk_product_line:
        table: "产品线"
        schema_name: "mapping"
        source_columns:
          product_line_name: "name"
        lookup_column: "id"
```

---

## Startup Validation

### `validate_domain_registry()` (Story 7.4-4)

**Location:** `src/work_data_hub/cli/etl/domain_validation.py`

**Purpose:** Ensure `data_sources.yml` domains have corresponding jobs in `JOB_REGISTRY`.

**Implementation:**
```python
def validate_domain_registry() -> None:
    """Validate domain configuration completeness at startup.

    Raises:
        ValueError: If domains in data_sources.yml lack job registry entries.
    """
    from work_data_hub.orchestration.jobs import JOB_REGISTRY
    from work_data_hub.io.connectors.discovery.service import FileDiscoveryService

    discovery_service = FileDiscoveryService()
    data_sources_domains = set(discovery_service.get_registered_domains())
    registry_domains = set(JOB_REGISTRY.keys())

    # Exclude special domains
    SPECIAL_DOMAINS = {"company_lookup_queue", "reference_sync"}
    expected_domains = data_sources_domains - SPECIAL_DOMAINS

    missing = expected_domains - registry_domains
    if missing:
        raise ValueError(
            f"Domains in data_sources.yml without JOB_REGISTRY entries: {missing}\n"
            f"Please register these domains in orchestration/jobs.py"
        )

    # Report registered but not configured
    unconfigured = registry_domains - expected_domains
    if unconfigured:
        warnings.warn(
            f"JOB_REGISTRY has domains not in data_sources.yml: {unconfigured}"
        )
```

**Called By:** CLI executor at startup (before job execution).

**Impact:** Addresses MD-005 (Low Severity) - no validation that config domains have jobs.

---

## Related Documentation

### Architecture Documents
- **[Project Context](../project-context.md)** - Section 6: Domain Registry Architecture
- **[Infrastructure Layer](infrastructure-layer.md)** - Orchestration and CLI patterns
- **[Implementation Patterns](implementation-patterns.md)** - Story patterns and conventions

### Epic 7.4 Stories
- **[Story 7.4-1](../sprint-artifacts/stories/7.4-1-job-registry-pattern.md)** - JOB_REGISTRY implementation
- **[Story 7.4-2](../sprint-artifacts/stories/7.4-2-config-driven-backfill-list.md)** - Config-driven backfill
- **[Story 7.4-3](../sprint-artifacts/stories/7.4-3-generic-process-domain-op.md)** - Generic domain op
- **[Story 7.4-4](../sprint-artifacts/stories/7.4-4-domain-autodiscovery-validation.md)** - Startup validation
- **[Story 7.4-5](../sprint-artifacts/stories/7.4-5-documentation-update.md)** - This story

### Sprint Change Proposals
- **[Epic 7.4 Sprint Change Proposal](../sprint-artifacts/sprint-change-proposal/sprint-change-proposal-2025-12-30-domain-registry-architecture.md)** - Complete architecture evolution plan

### Resolved Technical Debt
- **[New Domain Checklist (✅ RESOLVED)](../specific/multi-domain/new-domain-checklist.md)** - Pre-Epic 7.4 technical debt analysis

---

## Issue Resolution Matrix

| Issue ID | Severity | Description | Resolution Story |
|----------|----------|-------------|------------------|
| MD-001 | **High** | Job dispatch uses hardcoded if/elif chain | ✅ Story 7.4-1 |
| MD-002 | Medium | Backfill domain list hardcoded | ✅ Story 7.4-2 |
| MD-003 | Medium | Each domain requires dedicated op function | ✅ Story 7.4-3 |
| MD-004 | Low | Error message lists domains manually | ✅ Story 7.4-1 |
| MD-005 | Low | No validation config domains have jobs | ✅ Story 7.4-4 |

---

## Success Criteria

From Epic 7.4 Sprint Change Proposal Section 5:

1. ✅ **Adding new domain requires ≤2 file changes** (domain package + config)
2. ✅ **No if/elif chains in domain dispatch logic**
3. ✅ **All existing tests pass without modification**
4. ✅ **CLI interface remains backward compatible**
5. ✅ **`new-domain-checklist.md` marked as RESOLVED**

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2025-12-30 | Development Team | Initial documentation (Epic 7.4 completion) |
