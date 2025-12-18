# Sprint Change Proposal: Domain Comparison Framework Generalization

**Date:** 2025-12-18  
**Status:** ✅ Approved  
**Author:** Link (via Correct Course Workflow)  
**Scope:** Minor (Development Team Implementation)

---

## 1. Issue Summary

### Problem Statement

The `cleaner-comparison` module (`scripts/validation/CLI/`) was developed specifically for the `annuity_performance` domain during iterative validation work. The module successfully validates ETL strategy differences between Legacy System and New Pipeline through actual data write testing.

**Discovery Context:** During Epic 6.2 execution, the value of this validation approach was proven. Now seeking to generalize it for all domains to reduce adaptation effort for future domain migrations.

### Current Limitations

| Coupling Point | File | Hardcoded Content |
|----------------|------|-------------------|
| Field Configuration | `guimo_iter_config.py` | `NUMERIC_FIELDS`, `DERIVED_FIELDS` for 规模明细 only |
| Cleaner Executor | `guimo_iter_cleaner_compare.py` | Direct import of `AnnuityPerformanceCleaner` |
| Pipeline Executor | Same | Direct import of `annuity_performance.pipeline_builder` |
| Default Sheet | Same | `DEFAULT_SHEET_NAME = "规模明细"` |
| File Naming | All scripts | `guimo_iter_*` implies 规模明细 domain only |

---

## 2. Impact Analysis

### Epic Impact

| Epic | Impact Level | Details |
|------|--------------|---------|
| Epic 7: Testing & Validation | 🟡 Medium | Add "Domain Comparison Framework" as testing infrastructure |
| Epic 10: Growth Domains Migration | 🟢 Positive | Generalized module directly supports multi-domain validation |
| Epic 4, 5, 6 | ⚪ None | Current module continues serving annuity_performance |

### Artifact Impact

| Artifact | Impact | Action |
|----------|--------|--------|
| PRD | ✅ No conflict | Aligned with "Fearless Extensibility" goal |
| Architecture | ✅ No conflict | Follows existing domain patterns |
| `scripts/validation/CLI/` | 🔴 Major refactor | Core change area |
| CI/CD | ⚪ None | Existing test structure sufficient |

---

## 3. Recommended Approach

### Selected: Option 1 - Direct Adjustment

**Rationale:**
1. Minimal change scope, focused on decoupling and configuration
2. Incremental implementation: support `annuity_income` first, extend later
3. No impact on existing functionality or Epic progress
4. Follows project "Fearless Extensibility" principle

### Design Principle

```python
# Each domain only needs to define a config class
class AnnuityIncomeConfig(DomainComparisonConfig):
    domain_name = "annuity_income"
    sheet_name = "收入明细"
    numeric_fields = ["收入金额", "缴费金额", ...]
    derived_fields = ["月度", "机构代码", ...]
    legacy_cleaner = "AnnuityIncomeCleaner"
    pipeline_module = "annuity_income.pipeline_builder"
```

---

## 4. Detailed Change Proposals

### 4.1 Directory Restructure & Renaming

```diff
scripts/validation/CLI/
- ├── guimo_iter_cleaner_compare.py
- ├── guimo_iter_config.py
- ├── guimo_iter_report_generator.py
+ ├── cleaner_compare.py          # Main comparison script
+ ├── domain_config.py            # Generic config loader
+ ├── report_generator.py         # Report generation
+ ├── configs/                    # [NEW] Domain config directory
+ │   ├── __init__.py
+ │   ├── base.py                 # Base config class
+ │   ├── annuity_performance.py  # 规模明细 config
+ │   └── annuity_income.py       # 收入明细 config
  └── _artifacts/                 # Output (unchanged)
```

**No backward compatibility required** (per user confirmation).

---

### 4.2 Base Config Class

#### [NEW] `configs/base.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Type

class DomainComparisonConfig(ABC):
    """Base configuration for domain cleaner comparison."""

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """Domain identifier (e.g., 'annuity_performance')."""
        ...

    @property
    @abstractmethod
    def sheet_name(self) -> str:
        """Default Excel sheet name for this domain."""
        ...

    @property
    @abstractmethod
    def numeric_fields(self) -> List[str]:
        """Fields requiring zero-tolerance numeric comparison."""
        ...

    @property
    @abstractmethod
    def derived_fields(self) -> List[str]:
        """Fields derived from mappings/transformations."""
        ...

    @property
    def upgrade_fields(self) -> List[str]:
        """Fields with intentional enhancements (default: company_id)."""
        return ["company_id"]

    @property
    def column_name_mapping(self) -> Dict[str, str]:
        """Legacy → New column name mappings (default: empty)."""
        return {}

    @abstractmethod
    def get_legacy_cleaner(self) -> Type:
        """Return Legacy cleaner class."""
        ...

    @abstractmethod
    def build_new_pipeline(self, **kwargs):
        """Build New Pipeline for comparison."""
        ...
```

---

### 4.3 Domain Config Example

#### [NEW] `configs/annuity_performance.py`

```python
from typing import List, Dict, Type
from .base import DomainComparisonConfig

class AnnuityPerformanceConfig(DomainComparisonConfig):
    """Configuration for annuity_performance (规模明细) domain."""
    
    @property
    def domain_name(self) -> str:
        return "annuity_performance"
    
    @property
    def sheet_name(self) -> str:
        return "规模明细"
    
    @property
    def numeric_fields(self) -> List[str]:
        return [
            "期初资产规模", "期末资产规模", "供款",
            "流失(含待遇支付)", "流失", "待遇支付",
        ]
    
    @property
    def derived_fields(self) -> List[str]:
        return ["月度", "机构代码", "计划代码", "组合代码", "产品线代码"]
    
    @property
    def column_name_mapping(self) -> Dict[str, str]:
        return {"流失(含待遇支付)": "流失_含待遇支付"}
    
    def get_legacy_cleaner(self) -> Type:
        from annuity_hub.data_handler.data_cleaner import AnnuityPerformanceCleaner
        return AnnuityPerformanceCleaner
    
    def build_new_pipeline(self, **kwargs):
        from work_data_hub.domain.annuity_performance.pipeline_builder import (
            build_bronze_to_silver_pipeline,
        )
        return build_bronze_to_silver_pipeline(**kwargs)
```

---

### 4.4 CLI Changes

#### [MODIFY] `cleaner_compare.py`

**Key Changes:**
1. Add `--domain` CLI argument (required)
2. Load config dynamically based on domain
3. Use config for all domain-specific logic

```python
# NEW: Domain selection argument
parser.add_argument(
    "--domain", "-d",
    required=True,
    choices=["annuity_performance", "annuity_income"],
    help="Domain to compare",
)

# NEW: Config loading
def load_domain_config(domain: str) -> DomainComparisonConfig:
    """Load domain configuration by name."""
    from configs import DOMAIN_CONFIGS
    if domain not in DOMAIN_CONFIGS:
        raise ValueError(f"Unknown domain: {domain}")
    return DOMAIN_CONFIGS[domain]()
```

---

## 5. Implementation Handoff

### Scope Classification: **Minor**

Direct implementation by development team.

### Deliverables

1. ✅ Rename scripts (no backward compatibility)
2. ✅ Create `configs/` directory with base class
3. ✅ Migrate `annuity_performance` to config-driven
4. ⏸️ ~~Add first generalized domain: `annuity_income`~~ **(Deferred - YAGNI)**
5. ✅ Update usage guide documentation

> **YAGNI Note:** `annuity_income` config will be added when that domain migration actually begins (Epic 10). The framework will be ready; creating the config is trivial once needed.

---

### Implementation Steps

| Step | Description |
|------|-------------|
| 1 | Create `scripts/validation/CLI/configs/` directory structure |
| 2 | Implement `configs/base.py` with `DomainComparisonConfig` ABC |
| 3 | Create `configs/annuity_performance.py` migrating existing hardcoded values |
| 4 | Refactor `guimo_iter_cleaner_compare.py` → `cleaner_compare.py` with `--domain` argument |
| 5 | Refactor `guimo_iter_config.py` → `domain_config.py` as generic loader |
| 6 | Refactor `guimo_iter_report_generator.py` → `report_generator.py` (no logic changes) |
| 7 | Update `cleaner-comparison-usage-guide.md` with new CLI interface |
| 8 | Run validation tests (see Test Strategy below) |
| 9 | Delete old `guimo_iter_*` files after validation passes |

---

### Test Strategy

**Validation Commands:**

```bash
# 1. Functional equivalence test (CRITICAL)
# Compare old vs new script output for same input
PYTHONPATH=src uv run python scripts/validation/CLI/cleaner_compare.py \
    --domain annuity_performance --month 202311 --limit 100 --export

# 2. Unit tests for pipeline infrastructure
PYTHONPATH=src uv run pytest tests/unit/domain/annuity_performance/ -v

# 3. E2E pipeline tests
PYTHONPATH=src uv run pytest tests/e2e/test_pipeline_vs_legacy.py -v

# 4. Integration tests
PYTHONPATH=src uv run pytest tests/integration/test_pipeline_end_to_end.py -v
```

**Validation Criteria:**

| Test | Pass Condition |
|------|----------------|
| Functional equivalence | Output diff report identical to pre-refactor baseline |
| Unit tests | All `tests/unit/domain/annuity_performance/` pass |
| E2E tests | `test_pipeline_vs_legacy.py` passes |
| Config isolation | New script with `--domain annuity_performance` produces same CSV/MD artifacts |

---

### Rollback Strategy

| Scenario | Rollback Action |
|----------|-----------------|
| Refactor introduces bugs | `git revert` to commit before changes |
| Partial completion needed | Old `guimo_iter_*` files remain functional until Step 9 |
| Config class design issues | Iterate on `base.py` without affecting existing functionality |

**Git Safety:**
- Create feature branch: `feature/domain-comparison-generalization`
- Commit after each step (atomic commits)
- Old files deleted only after full validation (Step 9)

---

### Success Criteria

- [ ] `cleaner_compare.py --domain annuity_performance` works identically to current script
- [ ] Output artifacts (CSV, MD) are byte-for-byte identical for same input
- [ ] Adding new domain requires only creating a config file (framework verified)
- [ ] All test suites pass (unit, integration, e2e)

---

## 6. Approval

| Role | Status | Date |
|------|--------|------|
| Developer (Link) | ✅ Approved | 2025-12-18 |
| SM Review | ✅ Approved (with optimizations) | 2025-12-18 |

### SM Review Notes

**Optimizations Applied:**
1. ✅ **YAGNI:** Deferred `annuity_income` config to Epic 10 (when actually needed)
2. ✅ **Rollback Strategy:** Added Git-based rollback with atomic commits
3. ✅ **Test Strategy:** Added specific validation commands and pass criteria
4. ✅ **No Time Estimates:** Replaced day-based estimates with implementation steps
5. ✅ **Code Design:** Removed redundant `@dataclass` decorator from base class

---

*Generated by Correct Course Workflow on 2025-12-18*
*SM Review completed on 2025-12-18*
