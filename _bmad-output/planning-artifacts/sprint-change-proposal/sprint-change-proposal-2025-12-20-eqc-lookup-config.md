# Sprint Change Proposal: EQC Lookup Configuration Unification

**Date**: 2025-12-20
**Triggered by**: Story 6.2-P16 validation blocked by `--no-enrichment` propagation failure
**Scope**: Minor (Development team implementation)
**Epic**: 6.2 - Generic Reference Data Management

---

## 1. Issue Summary

### Problem Statement

The `--no-enrichment` CLI flag does not fully disable EQC (Enterprise Query Center) API calls. Even when a user specifies `--no-enrichment`, EQC requests are still made during ETL execution.

**Expected Behavior:**
```bash
python -m work_data_hub.cli etl --domains annuity_performance --no-enrichment --execute
# → Zero EQC API calls
```

**Actual Behavior:**
```
EQC client initialized
Searching companies via EQC (with raw response)
EQC request forbidden; retrying with minimal headers
```

### Context

This issue was discovered during validation of Story 6.2-P16 (ETL Execution Robustness). The 6.2-P16 implementation has been committed, but full validation is blocked by this deeper architectural issue.

### Evidence

1. **6-Layer Propagation Chain**: CLI parameter must flow through 6 distinct layers, each with different interpretation of "enrichment enabled"
2. **Root Cause**: `CompanyIdResolver` auto-creates `EqcProvider` when `mapping_repository` exists, completely ignoring `enrichment_enabled` and `sync_budget` parameters
3. **No Single Source of Truth**: Each layer interprets "enrichment enabled" differently

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact | Action |
|------|--------|--------|
| **Epic 6.2** (current) | Validation blocked | Add Story 6.2-P17 to fix |
| **Epic 7** (future) | No blocking impact | P17 fix enables validation |

### Story Impact

| Story | Status | Impact |
|-------|--------|--------|
| 6.2-P16 | Committed | Full validation pending P17 |
| 6.2-P17 | **New** | Fix `--no-enrichment` propagation |

### Artifact Conflicts

- **None**: This is an implementation bug, not a design conflict
- PRD, Architecture, UI/UX documents remain valid

### Technical Impact

| Area | Impact |
|------|--------|
| CLI | Add `EqcLookupConfig.from_cli_args()` factory |
| Orchestration | Pass config through Dagster ops |
| Domain Service | Thread config to pipeline builder |
| Infrastructure | `CompanyIdResolver` respects config |

---

## 3. Recommended Approach

**Selected Path**: Direct Adjustment (New Story 6.2-P17)

### Rationale

1. **Localized Fix**: Issue is architectural but fixable without major refactoring
2. **Single Source of Truth**: `EqcLookupConfig` dataclass provides centralized control
3. **Backward Compatible**: Default behavior unchanged for existing code
4. **Low Risk**: Clear implementation path with unit test coverage

### Alternatives Considered

| Option | Description | Rejected Because |
|--------|-------------|------------------|
| Minimal parameter passthrough | Add `disable_eqc_auto_create` flag | Doesn't solve semantic overlap |
| Remove auto-create entirely | Pure dependency injection | Too invasive, breaks existing callers |

---

## 4. Detailed Change Proposals

### Story 6.2-P17: EQC Lookup Configuration Dataclass

#### New File: `infrastructure/enrichment/eqc_lookup_config.py`

```python
"""EQC Lookup Configuration - Single Source of Truth for EQC API behavior."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class EqcLookupConfig:
    """
    Configuration for EQC (Enterprise Query Center) API lookups.

    This dataclass serves as the single source of truth for all EQC-related
    behavior, flowing from CLI through all layers to CompanyIdResolver.
    """
    enabled: bool = False
    sync_budget: int = 0
    auto_create_provider: bool = False
    export_unknown_names: bool = True
    auto_refresh_token: bool = True

    @classmethod
    def disabled(cls) -> "EqcLookupConfig":
        """Factory for completely disabled EQC lookups (--no-enrichment)."""
        return cls(
            enabled=False,
            sync_budget=0,
            auto_create_provider=False
        )

    @classmethod
    def from_cli_args(cls, args) -> "EqcLookupConfig":
        """Create config from CLI arguments with semantic enforcement."""
        enabled = getattr(args, "enrichment_enabled", False)

        if not enabled:
            return cls.disabled()

        sync_budget = getattr(args, "enrichment_sync_budget", 0)
        return cls(
            enabled=True,
            sync_budget=sync_budget,
            auto_create_provider=sync_budget > 0,
            export_unknown_names=getattr(args, "export_unknown_names", True),
            auto_refresh_token=not getattr(args, "no_auto_refresh_token", False),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EqcLookupConfig":
        """Reconstruct from Dagster config dict."""
        return cls(
            enabled=data.get("enabled", False),
            sync_budget=data.get("sync_budget", 0),
            auto_create_provider=data.get("auto_create_provider", False),
            export_unknown_names=data.get("export_unknown_names", True),
            auto_refresh_token=data.get("auto_refresh_token", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Dagster config."""
        return {
            "enabled": self.enabled,
            "sync_budget": self.sync_budget,
            "auto_create_provider": self.auto_create_provider,
            "export_unknown_names": self.export_unknown_names,
            "auto_refresh_token": self.auto_refresh_token,
        }

    @property
    def should_auto_create_provider(self) -> bool:
        """Derived: Should CompanyIdResolver auto-create EqcProvider?"""
        return self.enabled and self.auto_create_provider and self.sync_budget > 0
```

---

#### Modify: `company_id_resolver.py`

**Section: `__init__` method**

OLD:
```python
def __init__(
    self,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    yaml_overrides: Optional[Dict[str, Dict[str, str]]] = None,
    mapping_repository: Optional["CompanyMappingRepository"] = None,
    eqc_provider: Optional["EqcProvider"] = None,
) -> None:
    ...
    if (
        eqc_provider is None
        and mapping_repository is not None
        and enrichment_service is None
    ):
        self.eqc_provider = EqcProvider(...)  # Always auto-creates!
```

NEW:
```python
def __init__(
    self,
    enrichment_service: Optional["CompanyEnrichmentService"] = None,
    yaml_overrides: Optional[Dict[str, Dict[str, str]]] = None,
    mapping_repository: Optional["CompanyMappingRepository"] = None,
    eqc_provider: Optional["EqcProvider"] = None,
    eqc_config: Optional["EqcLookupConfig"] = None,  # NEW
) -> None:
    ...
    # Import and set default config
    if eqc_config is None:
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig
        eqc_config = EqcLookupConfig()  # Default: disabled

    self.eqc_config = eqc_config

    # FIX: Respect eqc_config before auto-creating
    if (
        eqc_provider is None
        and mapping_repository is not None
        and enrichment_service is None
        and eqc_config.should_auto_create_provider  # NEW CONDITION
    ):
        self.eqc_provider = EqcProvider(...)
```

Rationale: Config controls whether auto-creation happens, not just repository existence.

---

#### Modify: `cli/etl.py`

**Section: `build_run_config` function**

OLD:
```python
enrichment_enabled = getattr(args, "enrichment_enabled", False)
sync_budget = getattr(args, "enrichment_sync_budget", 0) if enrichment_enabled else 0
run_config["ops"]["process_annuity_performance_op"] = {
    "config": {
        "enrichment_enabled": enrichment_enabled,
        "enrichment_sync_budget": sync_budget,
        ...
    }
}
```

NEW:
```python
from work_data_hub.infrastructure.enrichment import EqcLookupConfig

eqc_config = EqcLookupConfig.from_cli_args(args)
run_config["ops"]["process_annuity_performance_op"] = {
    "config": {
        "eqc_lookup_config": eqc_config.to_dict(),
        # Zero Legacy: No backward-compat fields - all consumers use eqc_lookup_config
        ...
    }
}
```

Rationale: Single factory method enforces semantic rules. Zero Legacy Policy prohibits maintaining deprecated fields.

---

#### Modify: `orchestration/ops.py`

**Section: `process_annuity_performance_op`**

OLD:
```python
use_enrichment = (
    (not config.plan_only)
    and config.enrichment_enabled
    and settings.enrich_enabled
)
# ... later passes sync_lookup_budget without checking use_enrichment
```

NEW:
```python
from work_data_hub.infrastructure.enrichment import EqcLookupConfig

# Reconstruct config from Dagster run config
eqc_config_dict = config.get("eqc_lookup_config", {})
eqc_config = EqcLookupConfig.from_dict(eqc_config_dict) if eqc_config_dict else EqcLookupConfig.disabled()

# Pass config to service layer
result = service.process_with_enrichment(
    ...,
    eqc_config=eqc_config,
)
```

Rationale: Config object flows through, eliminating manual field handling.

---

#### Modify: `domain/annuity_performance/service.py`

**Section: `process_with_enrichment` method**

OLD:
```python
def process_with_enrichment(
    self,
    ...,
    sync_lookup_budget: int = 0,
) -> ProcessingResult:
    # Always creates mapping_repository
    mapping_repository = CompanyMappingRepository(engine)
```

NEW:
```python
def process_with_enrichment(
    self,
    ...,
    eqc_config: Optional["EqcLookupConfig"] = None,
) -> ProcessingResult:
    if eqc_config is None:
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig
        eqc_config = EqcLookupConfig.disabled()

    # Only create mapping_repository if EQC is enabled
    mapping_repository = CompanyMappingRepository(engine) if eqc_config.enabled else None
```

Rationale: Respects config at service level, prevents downstream issues.

---

### Files Changed Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `infrastructure/enrichment/eqc_lookup_config.py` | **NEW** | EqcLookupConfig dataclass |
| `infrastructure/enrichment/__init__.py` | MODIFY | Export EqcLookupConfig |
| `infrastructure/enrichment/company_id_resolver.py` | MODIFY | Add eqc_config parameter |
| `cli/etl.py` | MODIFY | Use EqcLookupConfig.from_cli_args() |
| `orchestration/ops.py` | MODIFY | Pass eqc_config to service |
| `domain/annuity_performance/service.py` | MODIFY | Accept eqc_config parameter |
| `domain/annuity_performance/pipeline_builder.py` | MODIFY | Pass eqc_config to step |
| `tests/unit/infrastructure/enrichment/test_eqc_lookup_config.py` | **NEW** | Unit tests |
| `tests/integration/test_no_enrichment_flag.py` | **NEW** | E2E validation |

---

## 5. Implementation Handoff

### Change Scope Classification

**Scope: Minor** - Direct implementation by development team

### Handoff Recipients

| Role | Responsibility |
|------|----------------|
| **Development Team** | Implement EqcLookupConfig, modify 7 files |
| **SM (on approval)** | Create story file, update sprint status |

### Success Criteria

1. `--no-enrichment` flag results in zero EQC API calls
2. All existing tests pass (no regression)
3. New unit tests for EqcLookupConfig
4. Integration test validates end-to-end behavior

### Verification Commands

```bash
# Unit tests
PYTHONPATH=src uv run pytest tests/unit/infrastructure/enrichment/test_eqc_lookup_config.py -v

# Integration test (manual)
PYTHONPATH=src uv run python -m work_data_hub.cli etl \
    --domains annuity_performance \
    --period 202510 \
    --no-enrichment \
    --execute
# Expected: No "EQC client initialized" or "Searching companies via EQC" in logs
```

---

## 6. Effort Estimate

| Task | Effort | Risk |
|------|--------|------|
| Create EqcLookupConfig dataclass | 1-2 hours | Low |
| Modify CompanyIdResolver | 1-2 hours | Low |
| Modify CLI + ops.py | 2-3 hours | Low |
| Modify service + pipeline_builder | 2-3 hours | Low |
| Testing | 2-3 hours | Low |
| **Total** | **8-12 hours** | **Low** |

---

## 7. References

- [CLI Architecture Assessment](../../../specific/cli/cli-architecture-assessment.md)
- [Enrichment Flag Propagation Issue](../../../specific/cli/enrichment-flag-propagation-issue.md)
- [Story 6.2-P16](../stories/6.2-p16-etl-execution-robustness.md) - Trigger story
- PRD FR-2.1: Reliable pipeline execution
