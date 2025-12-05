# Epic 5.5 – Optimization Recommendations

## Executive Summary

Story 5.5.4 completed the phased optimization strategy by extracting shared code to the Infrastructure layer. This document captures completed extractions, their impact, and remaining optimization opportunities for Epic 6.

## Completed Extractions (Story 5.5.4)

### 1. Shared Mappings Module

**Location:** `src/work_data_hub/infrastructure/mappings/shared.py`

**Extracted Constants:**
| Constant | Description | Lines Reduced |
|----------|-------------|---------------|
| `BUSINESS_TYPE_CODE_MAPPING` | Business type to product line code | ~15 lines × 2 domains |
| `DEFAULT_PORTFOLIO_CODE_MAPPING` | Plan type to portfolio code | ~5 lines × 2 domains |
| `PORTFOLIO_QTAN003_BUSINESS_TYPES` | Business types for QTAN003 | ~1 line × 2 domains |
| `COMPANY_BRANCH_MAPPING` | Branch name to institution code (superset with legacy overrides) | ~30 lines × 2 domains |

**Impact:**
- **Code Reduction:** ~100 lines of duplicated code eliminated
- **Single Source of Truth:** All domains now use identical mappings
- **Legacy Override Consolidation:** 6 legacy overrides from annuity_income merged into canonical mapping
- **Maintainability:** Future mapping changes only need to be made in one place

### 2. Shared Helpers Module

**Location:** `src/work_data_hub/infrastructure/helpers/shared.py`

**Extracted Functions:**
| Function | Description | Lines Reduced |
|----------|-------------|---------------|
| `normalize_month()` | Validate YYYYMM format | ~25 lines × 2 domains |

**Impact:**
- **Code Reduction:** ~50 lines of duplicated code eliminated
- **Consistent Validation:** Both domains use identical month validation logic
- **Test Coverage:** Shared helper has comprehensive unit tests

### 3. Test Infrastructure

**New Test Files:**
- `tests/unit/infrastructure/mappings/test_shared.py` - 18 tests for shared mappings
- `tests/unit/infrastructure/helpers/test_shared.py` - 12 tests for shared helpers
- `tests/integration/test_multi_domain_pipeline.py` - 10 integration tests for multi-domain validation

**Total New Tests:** 40 tests added

## Reuse Candidates & Tradeoffs

| Candidate | Current Location | Reuse Potential | Cost/Risk | Recommended Action | Owner |
|-----------|------------------|-----------------|-----------|-------------------|-------|
| `EnrichmentStats` model | `domain/*/models.py` | High (identical) | Low; update imports | Epic 6 – extract to `infrastructure/models/shared.py` | Epic 6 |
| `load_plan_override_mapping` | Both `pipeline_builder.py` | High (identical) | Low; logging domain change | Epic 6 – move to shared helper | Epic 6 |
| `convert_dataframe_to_models` | Both helpers | Medium | Medium; requires parameterizing | Epic 6 – design generic factory | Epic 6 |
| `CompanyIdResolutionStep` | Both `pipeline_builder.py` | Medium/High | Medium; configurable columns | Epic 6 – create configurable base | Epic 6 |
| Bronze→Silver scaffold | Both `pipeline_builder.py` | Medium | High; templating complexity | Epic 6 – design pipeline template | Epic 6 |
| `FileDiscoveryProtocol` | Both helpers | High (identical) | Low | Epic 6 – move to infrastructure | Epic 6 |
| `run_discovery` | Both helpers | High (identical) | Low | Epic 6 – move to infrastructure | Epic 6 |
| `export_unknown_names_csv` | Both helpers | High (similar) | Low | Epic 6 – parameterize domain name | Epic 6 |

## Recommendations for Epic 6 Batch Migrations

### 1. Domain Template/Scaffolding

**Recommendation:** Create a domain scaffolding tool that generates the 6-file structure with:
- Pre-configured imports from infrastructure modules
- Boilerplate for models, schemas, constants, helpers, pipeline_builder, service
- Standard test file templates

**Benefits:**
- Consistent domain structure across all new domains
- Reduced setup time for new domain migrations
- Built-in best practices from Epic 5.5 learnings

### 2. Shared Infrastructure Usage Patterns

**Pattern 1: Mapping Imports**
```python
# In domain/*/constants.py
from work_data_hub.infrastructure.mappings import (
    BUSINESS_TYPE_CODE_MAPPING,
    COMPANY_BRANCH_MAPPING,
    DEFAULT_PORTFOLIO_CODE_MAPPING,
    PORTFOLIO_QTAN003_BUSINESS_TYPES,
)
```

**Pattern 2: Helper Imports**
```python
# In domain/*/helpers.py
from work_data_hub.infrastructure.helpers import normalize_month
```

**Pattern 3: Domain-Specific Extensions**
```python
# Domain-specific constants remain in domain/*/constants.py
COLUMN_ALIAS_MAPPING: Dict[str, str] = {"机构": "机构代码"}  # Domain-specific
```

### 3. Testing Strategy for New Domains

**Unit Tests:**
- Test domain-specific logic only
- Rely on infrastructure module tests for shared functionality
- Use mock data matching domain schema

**Integration Tests:**
- Add domain to `test_multi_domain_pipeline.py`
- Verify domain isolation (no cross-contamination)
- Record performance baseline for new domain

**Parity Tests:**
- Create domain-specific parity validation script
- Compare against legacy system output
- Document intentional differences (e.g., company_id resolution)

## Performance Baseline

**Location:** `tests/fixtures/performance_baseline.json`

**Metrics Captured:**
- `processing_time_ms` - Measured using `time.perf_counter()`
- `memory_mb_peak` - Measured using `psutil.Process().memory_info().rss`
- `rows_processed` - Count of output rows
- `throughput_rows_per_sec` - Calculated throughput

**Regression Threshold:** 10% (configurable)

**Test Data Source:**
- Default fixture: `tests/fixtures/real_data/202412/收集数据/数据采集/V2/【for年金分战区经营分析】24年12月年金终稿数据0109采集-补充企年投资收入.xlsx`
- Default sheet: `收入明细`
- Default month: `202412`

## Architecture Validation Summary

Epic 5.5 successfully validated the Infrastructure Layer architecture by:

1. **Implementing a second domain (annuity_income)** using the same patterns as annuity_performance
2. **Achieving 100% parity** with legacy system (excluding intentional company_id differences)
3. **Extracting shared code** to infrastructure modules without breaking existing functionality
4. **Creating comprehensive tests** for multi-domain scenarios

The architecture is now proven to support multiple domains with:
- Shared infrastructure for common functionality
- Domain isolation for business-specific logic
- Consistent patterns for future domain migrations

## References

- Epic: `docs/epics/epic-5.5-pipeline-architecture-validation.md`
- Tech Spec: `docs/sprint-artifacts/tech-spec/tech-spec-epic-5.5-pipeline-architecture-validation.md`
- Story 5.5.3: `docs/sprint-artifacts/stories/5.5-3-legacy-parity-validation.md`
- Story 5.5.4: `docs/sprint-artifacts/stories/5.5-4-multi-domain-integration-test-and-optimization.md`

## Environment Baseline

- Python: 3.12.10
- pandas: 2.3.2
- pandera: 0.26.1
- pydantic: 2.11.7
- numpy: 2.3.3
- Platform: Windows-AMD64 (16 cores)
