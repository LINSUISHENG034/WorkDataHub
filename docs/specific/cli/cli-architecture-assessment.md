# CLI Architecture Assessment

> **Date:** 2025-12-20  
> **Purpose:** Comprehensive evaluation of CLI parameter design, propagation, and recommendations

## Current CLI Parameters Overview

### Parameter Categories

| Category | Parameters | Count |
|----------|------------|-------|
| **Domain Selection** | `--domains`, `--all-domains` | 2 |
| **Execution Mode** | `--plan-only`, `--execute` | 2 |
| **Data Loading** | `--mode`, `--pk`, `--skip-facts` | 3 |
| **File Discovery** | `--sheet`, `--period`, `--max-files`, `--file-selection` | 4 |
| **Enrichment** | `--enrichment/--no-enrichment`, `--enrichment-sync-budget`, `--export-unknown-names` | 3 |
| **Backfill** | `--backfill-refs`, `--backfill-mode` | 2 |
| **Pipeline Control** | `--use-pipeline/--no-use-pipeline` | 1 |
| **Queue Processing** | `--batch-size` | 1 |
| **Diagnostics** | `--debug`, `--raise-on-error`, `--check-db` | 3 |
| **Authentication** | `--no-auto-refresh-token` | 1 |

**Total: 22 parameters**

---

## Identified Issues

### Issue 1: Parameter Explosion
22 parameters is too many for a single CLI command. Users struggle to understand which parameters apply to which scenarios.

### Issue 2: Semantic Overlap
- `--plan-only` vs `--execute` are mutually exclusive but not enforced as such
- `--enrichment` (boolean) and `--enrichment-sync-budget` (numeric) control the same feature
- When `--no-enrichment`, should `--enrichment-sync-budget` be ignored?

### Issue 3: Deep Propagation Required
Parameters must flow through 4-6 layers:
```
CLI → build_run_config → ops.py → service.py → pipeline_builder.py → CompanyIdResolver
```

Each layer may have its own config objects, increasing coupling.

### Issue 4: Default Value Inconsistency
| Parameter | CLI Default | Code Default | Comment |
|-----------|-------------|--------------|---------|
| `--enrichment` | True | ProcessingConfig.enrichment_enabled=False | Mismatch! |
| `--enrichment-sync-budget` | 500 | ProcessingConfig.enrichment_sync_budget=0 | Mismatch! |

### Issue 5: Domain-Specific Parameters Exposed Globally
- `--backfill-refs`, `--backfill-mode` only apply to `annuity_performance`
- `--sheet` only applies to Excel-based domains
- `--batch-size` only applies to `company_lookup_queue`

### Issue 6: Missing Parameter Validation
No validation that parameters are compatible:
- `--all-domains` + `--period` should fail (period is domain-specific)
- `--skip-facts` without `--backfill-refs` is meaningless

---

## Recommended Improvements

### 1. Parameter Grouping via Subcommands

```bash
# Current (monolithic)
python -m work_data_hub.cli etl --domains annuity_performance --execute --enrichment --enrichment-sync-budget 100

# Proposed (subcommands)
python -m work_data_hub.cli etl run annuity_performance --execute
python -m work_data_hub.cli etl backfill annuity_performance --execute
python -m work_data_hub.cli etl diagnose --check-db
python -m work_data_hub.cli etl queue process --batch-size 100
```

### 2. Configuration Object Pattern

Replace multiple related parameters with a configuration object:

```python
@dataclass
class EnrichmentConfig:
    enabled: bool = False
    sync_budget: int = 0
    export_unknown_names: bool = True
    auto_refresh_token: bool = True

    @classmethod
    def from_cli_args(cls, args: argparse.Namespace) -> "EnrichmentConfig":
        if not args.enrichment_enabled:
            # Enforce: disabled enrichment means zero budget
            return cls(enabled=False, sync_budget=0, ...)
        return cls(
            enabled=True,
            sync_budget=args.enrichment_sync_budget,
            ...
        )
```

### 3. Domain-Aware Parameter Validation

```python
def validate_args_for_domain(args, domain: str) -> List[str]:
    """Return list of warnings/errors for incompatible parameters."""
    warnings = []
    
    if domain != "annuity_performance":
        if args.backfill_refs:
            warnings.append(f"--backfill-refs ignored for domain {domain}")
    
    if domain == "company_lookup_queue":
        if args.period:
            warnings.append("--period is not used for queue processing")
    
    return warnings
```

### 4. Simplified Boolean Flags

Replace `--no-enrichment` + `--enrichment-sync-budget 0` with single intent:

```bash
# Current (confusing)
--no-enrichment --enrichment-sync-budget 0

# Proposed (clear)
--skip-eqc  # Single flag that disables all EQC-related behavior
```

### 5. Layered Config Propagation

Create a single config container that flows through all layers:

```python
@dataclass
class ETLRunConfig:
    domain: str
    period: Optional[str]
    execute: bool = False
    enrichment: EnrichmentConfig = field(default_factory=EnrichmentConfig)
    file_selection: FileSelectionConfig = field(default_factory=FileSelectionConfig)
    backfill: BackfillConfig = field(default_factory=BackfillConfig)
    
    def to_dagster_run_config(self) -> Dict[str, Any]:
        """Convert to Dagster ops configuration."""
        ...
```

---

## Priority Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|----------------|--------|--------|
| P0 | Fix `--no-enrichment` propagation (current issue) | Low | High |
| P1 | Add parameter validation for domain compatibility | Medium | Medium |
| P2 | Create EnrichmentConfig object | Medium | High |
| P3 | Implement subcommand structure | High | High |
| P4 | Consolidate to ETLRunConfig pattern | High | Very High |

---

## Next Steps

1. **Immediate (Story 6.2-P16):** Fix `--no-enrichment` by passing `disable_eqc=True` down the chain
2. **Short-term:** Create EnrichmentConfig dataclass and refactor enrichment-related code
3. **Medium-term:** Add subcommands for logical grouping
4. **Long-term:** Full CLI architecture refactoring with ETLRunConfig pattern

---

## Related Documentation

- [enrichment-flag-propagation-issue.md](./enrichment-flag-propagation-issue.md) - Current bug details
- `docs/guides/infrastructure/eqc-query-parameters-guide.md` - EQC parameter usage
- Story 6.2-P6: CLI Architecture Unification
