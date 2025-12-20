# CLI Enrichment Flag Propagation Issue

> **Status:** Open  
> **Date:** 2025-12-20  
> **Related Story:** 6.2-P16 ETL Execution Robustness  
> **Type:** Architecture Case Study

## Executive Summary

This document serves as a **case study** demonstrating the architectural complexity of CLI parameter propagation in the current system. The `--no-enrichment` flag failure is a symptom of a deeper design issue: **parameters must traverse 6+ layers with inconsistent interpretation at each level**.

This analysis is intended for architects evaluating CLI redesign priorities.

---

## Problem Statement

The `--no-enrichment` CLI flag does not fully disable EQC (Enterprise Query Center) lookups. Even when a user specifies `--no-enrichment`, EQC requests are still being made during ETL execution.

**Expected Behavior:**
```bash
python -m work_data_hub.cli etl --domains annuity_performance --no-enrichment --execute
# → Zero EQC API calls
```

**Actual Behavior:**
```bash
# EQC requests still appear in logs:
EQC client initialized
Searching companies via EQC (with raw response)
EQC request forbidden; retrying with minimal headers
```

---

## Root Cause Analysis

### The 6-Layer Propagation Chain

The issue spans **6 distinct layers** of the codebase, each with its own configuration interpretation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: CLI Argument Parsing (etl.py)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Input:  --no-enrichment                                                     │
│ Output: args.enrichment_enabled = False                                     │
│         args.enrichment_sync_budget = 500 (DEFAULT - NOT AFFECTED!)         │
│                                                                             │
│ ⚠️ ISSUE: Two parameters control one feature, no coordination              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: Run Config Builder (etl.py:build_run_config)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ Input:  args.enrichment_enabled, args.enrichment_sync_budget                │
│ Output: config = {                                                          │
│           "enrichment_enabled": False,                                      │
│           "enrichment_sync_budget": 0    # ✅ FIXED: Now zeroed             │
│         }                                                                   │
│                                                                             │
│ ✅ FIX APPLIED: sync_budget = budget if enrichment_enabled else 0           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: Dagster Op (ops.py:process_annuity_performance_op)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Input:  config.enrichment_enabled, config.enrichment_sync_budget            │
│ Logic:  use_enrichment = (                                                  │
│           (not config.plan_only)                                            │
│           and config.enrichment_enabled                                     │
│           and settings.enrich_enabled                                       │
│         )                                                                   │
│ Output: enrichment_service = None (when use_enrichment=False)               │
│         BUT: sync_lookup_budget still passed to service layer               │
│                                                                             │
│ ✅ FIX APPLIED: Condition now correctly requires ALL conditions             │
│ ⚠️ ISSUE: sync_lookup_budget passed regardless of use_enrichment            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: Domain Service (service.py:process_with_enrichment)                │
├─────────────────────────────────────────────────────────────────────────────┤
│ Input:  enrichment_service=None, sync_lookup_budget=0                       │
│ Action: ALWAYS creates mapping_repository for DB cache lookups              │
│ Output: build_bronze_to_silver_pipeline(                                    │
│           enrichment_service=None,                                          │
│           sync_lookup_budget=0,                                             │
│           mapping_repository=<CompanyMappingRepository>,  # ALWAYS EXISTS   │
│         )                                                                   │
│                                                                             │
│ ⚠️ ISSUE: No distinction between "DB cache only" vs "EQC enabled"           │
│         mapping_repository existence triggers downstream EQC creation       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: Pipeline Step (pipeline_builder.py:CompanyIdResolutionStep)        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Input:  enrichment_service=None, sync_lookup_budget=0, mapping_repository=X │
│ Logic:  _use_enrichment = (                                                 │
│           enrichment_service is not None                                    │
│           OR (sync_lookup_budget > 0 AND mapping_repository is not None)    │
│         )                                                                   │
│ Result: _use_enrichment = False (when sync_budget=0) ✓                      │
│                                                                             │
│ ✅ CORRECT: This layer properly respects sync_budget=0                      │
│ BUT: Passes mapping_repository to CompanyIdResolver anyway                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 6: Company ID Resolver (company_id_resolver.py:CompanyIdResolver)     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Input:  enrichment_service=None, mapping_repository=X, eqc_provider=None    │
│ Logic:  if (                                                                │
│           eqc_provider is None                                              │
│           and mapping_repository is not None  # ← TRIGGERED!               │
│           and enrichment_service is None                                    │
│         ):                                                                  │
│           self.eqc_provider = EqcProvider(...)  # AUTO-CREATE!              │
│                                                                             │
│ ❌ BUG: Auto-creates EqcProvider based on mapping_repository existence      │
│        COMPLETELY IGNORES: sync_lookup_budget, enrichment_enabled           │
│        RESULT: EQC calls happen despite --no-enrichment                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Summary of Issues Per Layer

| Layer | File | Issue | Status |
|-------|------|-------|--------|
| 1 | `etl.py` argument parsing | Two params control one feature | ⚠️ Design debt |
| 2 | `etl.py` build_run_config | sync_budget not zeroed | ✅ Fixed |
| 3 | `ops.py` use_enrichment | Wrong OR logic | ✅ Fixed |
| 4 | `service.py` | Always creates mapping_repository | ⚠️ Design debt |
| 5 | `pipeline_builder.py` | Passes mapping_repository always | ✅ Correct behavior |
| 6 | `company_id_resolver.py` | Auto-creates EqcProvider | ❌ **Root cause bug** |

---

## Why This Is Hard to Debug

### 1. No Central Authority on "Enrichment Enabled"

The concept of "enrichment enabled" is interpreted differently at each layer:

| Layer | Interpretation |
|-------|----------------|
| CLI | `--no-enrichment` flag |
| build_run_config | `enrichment_enabled` boolean + separate `sync_budget` |
| ops.py | Checks 3 conditions: `plan_only`, `enrichment_enabled`, `settings.enrich_enabled` |
| service.py | `enrichment_service is not None` |
| pipeline_builder | `sync_lookup_budget > 0` |
| CompanyIdResolver | `mapping_repository is not None` |

**There is no single source of truth.**

### 2. Implicit vs Explicit Dependencies

- **Explicit:** `enrichment_service` is passed when EQC is wanted
- **Implicit:** `mapping_repository` existence implies EQC should be available

The CompanyIdResolver uses the **implicit** rule, while the CLI uses **explicit** semantics.

### 3. Parameters Don't Flow Together

| Parameter | Flows to ops.py? | Flows to service.py? | Flows to CompanyIdResolver? |
|-----------|-----------------|---------------------|----------------------------|
| `enrichment_enabled` | ✓ | ✗ (only service=None) | ✗ (lost) |
| `sync_budget` | ✓ | ✓ | ✗ (not checked in init) |
| `mapping_repository` | N/A | Created here | ✓ (but without context) |

---

## Impact on Development Velocity

### Debugging Time
- Initial bug report: `--no-enrichment` doesn't work
- Time to identify 6-layer chain: ~45 minutes
- Fixes attempted: 3 (only 2 correct)
- Remaining unfixed layers: 2

### Cognitive Load for New Developers
To understand "how to disable EQC", a developer must:
1. Read CLI argument definitions
2. Trace through build_run_config
3. Understand ops.py condition logic
4. Know that service.py creates mapping_repository
5. Understand pipeline_builder's _use_enrichment
6. Know CompanyIdResolver's auto-create behavior

**This is unacceptable complexity for a single boolean flag.**

---

## Recommended Solutions

### Option 1: Minimal Change (Parameter Passthrough)
Add explicit `disable_eqc_auto_create` parameter that propagates from CLI down to CompanyIdResolver:

```python
# In CompanyIdResolver.__init__
def __init__(
    self,
    ...,
    disable_eqc_auto_create: bool = False,  # NEW
):
    if (
        not disable_eqc_auto_create  # NEW condition
        and eqc_provider is None
        and mapping_repository is not None
        and enrichment_service is None
    ):
        # Auto-create EqcProvider logic
```

**Pros:** Explicit control, backward compatible  
**Cons:** Parameter needs to pass through 4+ layers (increases coupling)

**Effort:** Low (~2 hours)  
**Risk:** Low

### Option 2: Sync Budget-Based (Simpler)
Change CompanyIdResolver to never auto-create EqcProvider. Caller must explicitly provide it:

```python
# In CompanyIdResolver.__init__
# Remove the auto-create block entirely
# EqcProvider must be injected by caller if EQC lookups are needed
```

**Pros:** Simpler, follows Dependency Injection principles  
**Cons:** Requires updating call sites to create EqcProvider

**Effort:** Medium (~4 hours)  
**Risk:** Medium (callers may break)

### Option 3: Comprehensive CLI Refactoring (Recommended for Long-term)
Consolidate enrichment-related flags into a single configuration object:

```python
@dataclass
class EnrichmentConfig:
    enabled: bool = False
    sync_budget: int = 0
    auto_create_eqc_provider: bool = False
    export_unknown_names: bool = True
    
    @classmethod
    def from_cli_args(cls, args) -> "EnrichmentConfig":
        if not args.enrichment_enabled:
            return cls(enabled=False, sync_budget=0, auto_create_eqc_provider=False)
        return cls(
            enabled=True,
            sync_budget=args.enrichment_sync_budget,
            auto_create_eqc_provider=args.enrichment_sync_budget > 0,
            export_unknown_names=args.export_unknown_names,
        )
```

This object flows through all layers, providing a **single source of truth**.

**Pros:** Clear separation of concerns, easier testing, self-documenting  
**Cons:** Larger refactoring effort, requires touching 6+ files

**Effort:** High (~16 hours)  
**Risk:** Medium (extensive changes)

---

## Recommendations for Architects

### Immediate (P0)
1. Apply **Option 1** to fix the current bug
2. Add integration test: `test_no_enrichment_flag_disables_eqc`

### Short-term (P1)
1. Create `EnrichmentConfig` dataclass
2. Refactor all enrichment-related parameter passing

### Medium-term (P2)
1. Audit all CLI parameters for similar propagation issues
2. Consider subcommand structure for CLI (`etl run`, `etl backfill`, `etl diagnose`)

### Long-term (P3)
1. Implement `ETLRunConfig` pattern (see cli-architecture-assessment.md)
2. Add parameter validation layer at CLI entry point

---

## Related CLI Parameters

| Parameter | Default | Purpose | Propagation Issue? |
|-----------|---------|---------|-------------------|
| `--enrichment/--no-enrichment` | True (enabled) | Enable/disable EQC lookups | **Yes (this doc)** |
| `--enrichment-sync-budget` | 500 | Max sync EQC lookups | Partially fixed |
| `--export-unknown-names` | True | Export unknowns to CSV | No |
| `--plan-only/--execute` | plan-only | Dry run vs execute | No |

---

## Files Involved in This Issue

| File | Lines | Role |
|------|-------|------|
| `src/work_data_hub/cli/etl.py` | 344-360 | build_run_config |
| `src/work_data_hub/orchestration/ops.py` | 442-449 | use_enrichment condition |
| `src/work_data_hub/domain/annuity_performance/service.py` | 183-208 | process_with_enrichment |
| `src/work_data_hub/domain/annuity_performance/pipeline_builder.py` | 134-166 | CompanyIdResolutionStep |
| `src/work_data_hub/infrastructure/enrichment/company_id_resolver.py` | 122-157 | Auto-create EqcProvider |

---

## See Also

- [cli-architecture-assessment.md](./cli-architecture-assessment.md) - Comprehensive CLI evaluation
- Story 6.2-P16: ETL Execution Robustness
- `docs/specific/company-enrichment-service/` - Enrichment architecture
- `docs/guides/infrastructure/eqc-query-parameters-guide.md` - EQC parameter docs
