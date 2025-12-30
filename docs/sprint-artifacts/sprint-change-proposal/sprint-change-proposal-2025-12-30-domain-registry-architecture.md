# Sprint Change Proposal: Domain Registry Architecture

> **Document Status:** Draft
> **Date:** 2025-12-30
> **Author:** Correct-Course Workflow
> **Triggered By:** `docs/specific/multi-domain/new-domain-checklist.md`
> **Classification:** Major

---

## 1. Issue Summary

### Problem Statement

The current ETL dispatch architecture uses **hardcoded if/elif chains** rather than a configuration-driven registry pattern. Adding a new domain requires modifications to **5-7 files minimum**, violating the Open/Closed Principle (OCP) and KISS principle.

### Context

During Epic 7.3 (Multi-Domain Consistency Fixes), a technical debt analysis document was created (`docs/specific/multi-domain/new-domain-checklist.md`) that identified architectural issues with the domain dispatch mechanism. The analysis revealed that adding a new domain requires touching:

1. `domain/{new_domain}/` - Create domain package (Required)
2. `orchestration/ops/pipeline_ops.py` - Add `process_{domain}_op` (Required)
3. `orchestration/jobs.py` - Add `{domain}_job` function (Required)
4. `cli/etl/executors.py` - Add elif branch (Required)
5. `cli/etl/config.py` - Update backfill domain list (Conditional)
6. `config/data_sources.yml` - Add domain config (Required)
7. `config/foreign_keys.yml` - Add FK config (Conditional)

### Evidence

**MD-001 (High Severity)** - `cli/etl/executors.py:200-232`:
```python
if domain_key == "annuity_performance":
    from work_data_hub.orchestration.jobs import annuity_performance_job
    selected_job = annuity_performance_job
elif domain_key == "annuity_income":
    from work_data_hub.orchestration.jobs import annuity_income_job
    selected_job = annuity_income_job
elif domain_key == "sandbox_trustee_performance":
    # ...
else:
    raise ValueError(f"Unsupported domain: {domain}...")
```

**MD-002 (Medium Severity)** - `cli/etl/config.py:157`:
```python
if domain in ["annuity_performance", "annuity_income", "sandbox_trustee_performance"]:
    run_config["ops"]["generic_backfill_refs_op"] = {...}
```

**MD-003 (Medium Severity)** - Each domain requires a dedicated `process_{domain}_op` function in `pipeline_ops.py`.

**MD-004 (Low Severity)** - Error message manually lists supported domains.

**MD-005 (Low Severity)** - No validation that `data_sources.yml` domain has corresponding job.

---

## 2. Impact Analysis

### Epic Impact

| Epic | Status | Impact |
|------|--------|--------|
| Epic 7.3 | ✅ Done | No impact (already completed) |
| **Epic 7.4** | 🆕 New | New epic for Domain Registry Architecture |
| Epic 8 | ⏸️ Blocked | Should wait for Epic 7.4 (cleaner test foundation) |

### Story Impact

**New Stories Required (Epic 7.4):**

| Story ID | Title | Priority | Effort |
|----------|-------|----------|--------|
| 7.4-1 | Job Registry Pattern - Replace if/elif dispatch | P0 | Medium |
| 7.4-2 | Config-Driven Backfill Domain List | P1 | Low |
| 7.4-3 | Generic Process Domain Op | P1 | Medium |
| 7.4-4 | Domain Autodiscovery Validation | P2 | Low |
| 7.4-5 | Documentation Update | P2 | Low |

### Artifact Conflicts

| Artifact | Conflict Type | Action Required |
|----------|--------------|-----------------|
| `docs/project-context.md` | Update needed | Add Domain Registry section |
| `docs/architecture/` | New document | Add registry pattern documentation |
| `new-domain-checklist.md` | Deprecation | Mark as resolved after Epic 7.4 |

### Technical Impact

**Files to Modify:**

| File | Change Type | Description |
|------|-------------|-------------|
| `cli/etl/executors.py` | Refactor | Replace if/elif with registry lookup |
| `cli/etl/config.py` | Refactor | Move backfill domains to config |
| `orchestration/jobs.py` | Refactor | Add `JOB_REGISTRY` dictionary |
| `config/data_sources.yml` | Extend | Add `requires_backfill: true` field |
| New: `infrastructure/registry/` | Create | Domain and Job registry classes |

---

## 3. Recommended Approach

### Selected Path: New Epic 7.4 - Domain Registry Architecture

**Approach:** Create a configuration-driven domain registry that eliminates hardcoded dispatch logic.

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Domain Registry (Single Source of Truth)                    │
│  config/data_sources.yml + infrastructure/schema/            │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  JOB_REGISTRY: Dict[str, JobDefinition]                      │
│  Maps domain name → job function + capabilities              │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  CLI Executor (executors.py)                                 │
│  job = JOB_REGISTRY.get(domain)  # No if/elif!              │
└─────────────────────────────────────────────────────────────┘
```

### Rationale

1. **Open/Closed Principle**: New domains can be added without modifying dispatcher code
2. **Single Source of Truth**: Domain capabilities defined in one place
3. **Reduced Maintenance**: Adding new domain requires fewer file changes
4. **Better Testability**: Registry can be easily mocked for unit tests
5. **Self-Documenting**: Registry makes supported domains explicit

### Effort Estimate: Medium (4-6 stories, ~2-3 days)

### Risk Assessment: Low

- Pure refactoring, no business logic changes
- All existing tests continue to pass
- Backward compatible CLI interface

---

## 4. Detailed Change Proposals

### Story 7.4-1: Job Registry Pattern (P0 Critical)

**Goal:** Replace if/elif chain in `executors.py` with dictionary-based job registry.

**OLD (executors.py:200-232):**
```python
if domain_key == "annuity_performance":
    from work_data_hub.orchestration.jobs import annuity_performance_job
    selected_job = annuity_performance_job
elif domain_key == "annuity_income":
    from work_data_hub.orchestration.jobs import annuity_income_job
    selected_job = annuity_income_job
# ... more elif branches
else:
    raise ValueError(f"Unsupported domain: {domain}...")
```

**NEW:**
```python
from work_data_hub.orchestration.jobs import JOB_REGISTRY

if domain_key in ("company_lookup_queue", "reference_sync"):
    return _execute_special_job(domain_key, args)

job_entry = JOB_REGISTRY.get(domain_key)
if not job_entry:
    supported = ", ".join(JOB_REGISTRY.keys())
    raise ValueError(f"Unsupported domain: {domain}. Supported: {supported}")

selected_job = job_entry.job
if max_files > 1 and job_entry.multi_file_job:
    selected_job = job_entry.multi_file_job
```

**Rationale:** Eliminates MD-001 (High Severity) - hardcoded if/elif chain.

---

### Story 7.4-2: Config-Driven Backfill Domain List (P1)

**Goal:** Move backfill domain list from code to configuration.

**OLD (config.py:157):**
```python
if domain in ["annuity_performance", "annuity_income", "sandbox_trustee_performance"]:
    run_config["ops"]["generic_backfill_refs_op"] = {...}
```

**NEW (config/data_sources.yml):**
```yaml
defaults:
  requires_backfill: false  # Default to no backfill

domains:
  annuity_performance:
    requires_backfill: true  # Explicit opt-in
  annuity_income:
    requires_backfill: true
  sandbox_trustee_performance:
    requires_backfill: true
```

**NEW (config.py):**
```python
if domain_cfg.requires_backfill:
    run_config["ops"]["generic_backfill_refs_op"] = {...}
```

**Rationale:** Eliminates MD-002 (Medium Severity) - hardcoded backfill domain list.

---

### Story 7.4-3: Generic Process Domain Op (P1)

**Goal:** Create factory function to generate domain-specific ops dynamically.

**Current Issue (MD-003):** Each domain requires a dedicated `process_{domain}_op` function.

**Approach:** Create `process_domain_op` that delegates to domain service based on registry.

```python
# orchestration/ops/domain_ops.py
@op
def process_domain_op(
    context: OpExecutionContext,
    excel_rows: List[Dict[str, Any]],
    discovered_paths: List[str],
    config: ProcessDomainOpConfig,
) -> DomainPipelineResult:
    """Generic domain processing op that delegates to domain service."""
    domain = config.domain
    service = DOMAIN_SERVICE_REGISTRY[domain]
    return service.process(excel_rows, discovered_paths, config)
```

**Rationale:** Reduces code duplication across domain ops.

---

### Story 7.4-4: Domain Autodiscovery Validation (P2)

**Goal:** Add startup validation that `data_sources.yml` domains have corresponding jobs.

**Implementation:**
```python
def validate_domain_registry():
    """Validate domain configuration completeness at startup."""
    data_sources_domains = load_data_sources_domains()
    registry_domains = set(JOB_REGISTRY.keys())

    missing = data_sources_domains - registry_domains
    if missing:
        warnings.warn(f"Domains in data_sources.yml without jobs: {missing}")
```

**Rationale:** Addresses MD-005 - no validation that config domains have jobs.

---

### Story 7.4-5: Documentation Update (P2)

**Goal:** Update architecture documentation to reflect new registry pattern.

**Files to Update:**
1. `docs/project-context.md` - Add Domain Registry section
2. `docs/specific/multi-domain/new-domain-checklist.md` - Mark as RESOLVED
3. New: `docs/architecture/domain-registry.md` - Registry pattern documentation

---

## 5. Implementation Handoff

### Change Scope Classification: **Moderate**

This change requires:
- Backlog reorganization (add Epic 7.4 before Epic 8)
- Multiple story implementation
- Architecture documentation updates

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Development Team** | Implement Stories 7.4-1 through 7.4-5 |
| **PM/Architect** | Approve Epic 7.4 scope and priority |

### Success Criteria

1. ✅ Adding new domain requires **≤2 file changes** (domain package + config)
2. ✅ No if/elif chains in domain dispatch logic
3. ✅ All existing tests pass without modification
4. ✅ CLI interface remains backward compatible
5. ✅ `new-domain-checklist.md` marked as RESOLVED

### Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Epic 7.3 | ✅ Done | No blocking dependencies |
| Epic 8 | ⏸️ Blocked by 7.4 | Should start after 7.4 completion |

---

## 6. Sprint Status Update Required

```yaml
# Add to sprint-status.yaml
epic-7.4: backlog  # Domain Registry Architecture
7.4-1-job-registry-pattern: backlog  # P0: Replace if/elif dispatch
7.4-2-config-driven-backfill-list: backlog  # P1: Move backfill domains to config
7.4-3-generic-process-domain-op: backlog  # P1: Factory for domain ops
7.4-4-domain-autodiscovery-validation: backlog  # P2: Startup validation
7.4-5-documentation-update: backlog  # P2: Update architecture docs
epic-7.4-retrospective: optional

# Update Epic 8 blocking comment
epic-8: backlog  # BLOCKED BY: Epic 7.4 (Domain Registry Architecture)
```

---

## Appendix: Issue Matrix from Trigger Document

| Issue ID | Severity | Description | Resolution Story |
|----------|----------|-------------|------------------|
| MD-001 | **High** | Job dispatch uses hardcoded if/elif chain | Story 7.4-1 |
| MD-002 | Medium | Backfill domain list hardcoded | Story 7.4-2 |
| MD-003 | Medium | Each domain requires dedicated op function | Story 7.4-3 |
| MD-004 | Low | Error message lists domains manually | Story 7.4-1 |
| MD-005 | Low | No validation config domains have jobs | Story 7.4-4 |

---

## Document History

| Date | Author | Change |
|------|--------|--------|
| 2025-12-30 | Correct-Course Workflow | Initial proposal |
