# Story 2.3: Cleansing Registry Framework

Status: done

## Story

As a **data engineer**,
I want **a centralized registry of reusable cleansing rules**,
so that **value-level transformations are standardized across all domains without code duplication**.

## Acceptance Criteria

### AC1: CleansingRegistry Core Implementation

**Given** I have Pydantic models from Story 2.1 and Pandera schemas from Story 2.2
**When** I implement `CleansingRegistry` in `cleansing/registry.py`
**Then** it should provide:
- Rule registration: `registry.register(name: str, func: CleansingRule) -> None`
- Single rule application: `registry.apply_rule(value: Any, rule_name: str) -> Any`
- Multiple rule composition: `registry.apply_rules(value: Any, rule_names: List[str]) -> Any`
- Domain configuration support: `registry.get_domain_rules(domain: str, field: str) -> List[str]`
- Singleton instance: `get_cleansing_registry() -> CleansingRegistry` for global access

**And** When I register a cleansing rule
**Then** It should be callable via rule name throughout the application

**And** When I apply multiple rules in sequence
**Then** Rules execute in order: `apply_rules(value, ['trim', 'normalize'])` applies trim first, then normalize to trim output

**And** When unknown rule is requested
**Then** Raise `ValueError`: "Cleansing rule 'unknown_rule' not registered. Available rules: [list]"

### AC2: Built-in Cleansing Rules

**Given** I have the CleansingRegistry framework
**When** I implement built-in rules in `cleansing/rules/`
**Then** I should have functional rules for:

**String Rules** (`cleansing/rules/string_rules.py`):
- `trim_whitespace(value: str) -> str`: Remove leading/trailing whitespace
  - Example: `"  公司有限  "` → `"公司有限"`
- `normalize_company_name(value: str) -> str`: Standardize company names
  - Remove special characters: `「」『』""`
  - Replace full-width spaces with half-width: `'　'` → `' '`
  - Collapse multiple spaces: `"公司  有限"` → `"公司 有限"`
  - Example: `"「公司　有限」"` → `"公司 有限"`

**Numeric Rules** (`cleansing/rules/numeric_rules.py`):
- `remove_currency_symbols(value: str) -> str`: Remove currency symbols for parsing
  - Remove: `¥`, `$`, `,` (comma)
  - Example: `"¥1,234.56"` → `"1234.56"`
- `clean_comma_separated_number(value: str) -> str`: Remove thousand separators
  - Example: `"1,234,567.89"` → `"1234567.89"`

**And** When I apply `trim_whitespace` to `"  test  "`
**Then** Returns `"test"`

**And** When I apply `normalize_company_name` to `"「公司　有限」"`
**Then** Returns `"公司 有限"` (normalized spacing and no decorative brackets)

**And** When I apply `remove_currency_symbols` to `"¥1,234.56"`
**Then** Returns `"1234.56"`

**And** When rule receives non-string input (e.g., `None`, `123`)
**Then** Rule handles gracefully: return value unchanged or handle appropriately per rule

### AC3: YAML Configuration for Per-Domain Rules

**Given** I have built-in rules registered
**When** I create `cleansing/config/cleansing_rules.yml`
**Then** configuration should support:

```yaml
domains:
  annuity_performance:
    客户名称: [trim_whitespace, normalize_company_name]
    计划代码: [trim_whitespace]
    期末资产规模: [remove_currency_symbols]

  # Default rules applied if domain not specified
  default:
    - trim_whitespace
```

**And** When I load configuration with `ConfigLoader`
**Then** `registry.get_domain_rules('annuity_performance', '客户名称')` returns `['trim_whitespace', 'normalize_company_name']`

**And** When field not configured for domain
**Then** `registry.get_domain_rules('annuity_performance', 'unknown_field')` returns `[]` (empty list, no default rules)

**And** When domain not in configuration
**Then** `registry.get_domain_rules('unknown_domain', 'field')` returns default rules

### AC4: Integration with Pydantic Validators

**Given** I have CleansingRegistry with rules configured
**When** I use registry in Pydantic `@field_validator`
**Then** rules should apply automatically during model validation:

```python
from work_data_hub.cleansing.registry import get_cleansing_registry

class AnnuityPerformanceOut(BaseModel):
    客户名称: str

    @field_validator('客户名称', mode='before')
    def clean_company_name(cls, v):
        registry = get_cleansing_registry()
        return registry.apply_rules(v, ['trim_whitespace', 'normalize_company_name'])
```

**And** When Pydantic model validates input with `客户名称 = "「  公司　有限  」"`
**Then** Cleansing rules execute before validation, output is `"公司 有限"`

**And** When cleansing rule raises exception
**Then** Pydantic validation fails with clear error: `"Cleansing rule 'normalize_company_name' failed for field '客户名称': [error details]"`

**And** When I update `AnnuityPerformanceOut` model from Story 2.1
**Then** Replace inline placeholders (`clean_company_name_inline`, `clean_comma_separated_number`) with registry calls

### AC5: Integration with Pandera Custom Checks (Optional)

**Given** I have CleansingRegistry and Pandera schemas from Story 2.2
**When** I create custom Pandera checks using cleansing rules
**Then** rules can apply to entire DataFrame columns:

```python
import pandera as pa
from work_data_hub.cleansing.registry import get_cleansing_registry

def clean_company_names_check(series: pd.Series) -> pd.Series:
    """Apply cleansing rules to DataFrame column"""
    registry = get_cleansing_registry()
    return series.apply(lambda x: registry.apply_rules(x, ['trim_whitespace', 'normalize_company_name']))

# Use in Pandera schema
bronze_check = pa.Check(clean_company_names_check, element_wise=False)
```

**And** When Pandera schema includes cleansing check
**Then** Entire column is cleaned before Bronze validation

**Note**: This AC is optional - primary integration is via Pydantic validators (AC4).

### AC6: Performance Compliance (MANDATORY - Epic 2 Performance AC)

**Given** I have implemented CleansingRegistry with built-in rules
**When** I run performance tests per `docs/epic-2-performance-acceptance-criteria.md`
**Then** cleansing must meet:
- **AC-PERF-1**: Cleansing processes ≥1000 rows/second (vectorized string operations)
- **AC-PERF-2**: Cleansing overhead <20% of total pipeline execution time
- **AC-PERF-3**: Baseline recorded in `tests/.performance_baseline.json`

**And** When performance tests run with 10,000-row fixture
**Then** Target throughput: 1500+ rows/s for rule application (string operations are fast)

**And** When throughput falls below 1000 rows/s
**Then** Story is BLOCKED - must optimize before review (vectorize operations, reduce redundant calls, cache compiled regex)

## Tasks / Subtasks

- [x] **Task 1: Implement CleansingRegistry Core** (AC: 1)
  - [x] Subtask 1.1: Create `cleansing/registry.py` with `CleansingRegistry` class
  - [x] Subtask 1.2: Implement rule registration: `register(name, func)` with duplicate detection
  - [x] Subtask 1.3: Implement single rule application: `apply_rule(value, rule_name)` with error handling
  - [x] Subtask 1.4: Implement rule composition: `apply_rules(value, rule_names)` sequential application
  - [x] Subtask 1.5: Implement singleton pattern: `get_cleansing_registry()` returns cached instance
  - [x] Subtask 1.6: Add domain configuration support: `get_domain_rules(domain, field)` with YAML loader

- [x] **Task 2: Implement Built-in String Rules** (AC: 2)
  - [x] Subtask 2.1: Create `cleansing/rules/string_rules.py` module
  - [x] Subtask 2.2: Implement `trim_whitespace(value)` with type checking (handle None, non-strings)
  - [x] Subtask 2.3: Implement `normalize_company_name(value)` with full-width/special char handling
  - [x] Subtask 2.4: Register built-in string rules on module import
  - [x] Subtask 2.5: Add comprehensive unit tests for string rules (edge cases: None, empty, special chars)

- [x] **Task 3: Implement Built-in Numeric Rules** (AC: 2)
  - [x] Subtask 3.1: Create `cleansing/rules/numeric_rules.py` module
  - [x] Subtask 3.2: Implement `remove_currency_symbols(value)` for ¥, $, comma
  - [x] Subtask 3.3: Implement `clean_comma_separated_number(value)` to remove thousand separators
  - [x] Subtask 3.4: Register built-in numeric rules on module import
  - [x] Subtask 3.5: Add unit tests for numeric rules (currency symbols, thousand separators, edge cases)

- [x] **Task 4: Create YAML Configuration System** (AC: 3)
  - [x] Subtask 4.1: Create `cleansing/config/cleansing_rules.yml` with annuity_performance domain
  - [x] Subtask 4.2: Implement YAML loader in `cleansing/registry.py` (use PyYAML or stdlib)
  - [x] Subtask 4.3: Implement `get_domain_rules(domain, field)` to lookup rules from config
  - [x] Subtask 4.4: Add default rules fallback when domain/field not configured
  - [x] Subtask 4.5: Add configuration validation: ensure referenced rules exist in registry

- [x] **Task 5: Integrate with Pydantic Models (Story 2.1)** (AC: 4)
  - [x] Subtask 5.1: Update `domain/annuity_performance/models.py` to import `get_cleansing_registry()`
  - [x] Subtask 5.2: Replace `clean_company_name_inline()` with registry call in `@field_validator`
  - [x] Subtask 5.3: Replace `clean_comma_separated_number()` with registry call
  - [x] Subtask 5.4: Test Pydantic model validation with cleansing rules (integration test)
  - [x] Subtask 5.5: Remove inline placeholder functions from models.py (technical debt cleanup)

- [x] **Task 6: Add Unit Tests** (AC: 1-5)
  - [x] Subtask 6.1: Test `CleansingRegistry` rule registration, retrieval, error handling
  - [x] Subtask 6.2: Test rule composition: multiple rules apply in correct order
  - [x] Subtask 6.3: Test YAML configuration loading and domain rule lookup
  - [x] Subtask 6.4: Test Pydantic integration: cleansing rules execute during validation
  - [x] Subtask 6.5: Test edge cases: None values, empty strings, non-string inputs
  - [x] Subtask 6.6: Mark tests with `@pytest.mark.unit` per Story 1.11 testing framework

- [x] **Task 7: Add Performance Tests (MANDATORY)** (AC: 6)
  - [x] Subtask 7.1: Create `tests/integration/test_story_2_3_performance.py` per Epic 2 performance criteria
  - [x] Subtask 7.2: Test with 10,000-row fixture (reuse Story 2.1 fixture)
  - [x] Subtask 7.3: Measure cleansing throughput and validate ≥1000 rows/s (target 1500+ rows/s)
  - [x] Subtask 7.4: Measure cleansing overhead in full pipeline and validate <20%
  - [x] Subtask 7.5: Update `tests/.performance_baseline.json` with cleansing rule baselines
  - [x] Subtask 7.6: Profile hot paths if performance below target (optimize regex, vectorize operations)

- [x] **Task 8: Documentation and Integration**
  - [x] Subtask 8.1: Add docstrings to `CleansingRegistry` class and public methods
  - [x] Subtask 8.2: Document built-in rules with examples in module docstrings
  - [x] Subtask 8.3: Add usage examples: standalone registry, Pydantic integration, configuration
  - [x] Subtask 8.4: Update story file with Completion Notes, File List, and Change Log

## Dev Notes

### Architecture and Patterns

**Clean Architecture Boundaries (Story 1.6)**:
- **Location**: `src/work_data_hub/cleansing/` (domain layer utility)
- **No I/O dependencies**: Cleansing rules are pure functions - no database, file, or Dagster imports
- **Dependency injection**: Registry injected into Pydantic validators via `get_cleansing_registry()`

**Design Patterns**:
- **Singleton Pattern**: `get_cleansing_registry()` ensures single registry instance across application
- **Strategy Pattern**: CleansingRule type alias defines contract: `Callable[[Any], Any]`
- **Composition Pattern**: Multiple rules compose via `apply_rules()` sequential execution

**Integration Points**:
- **Story 2.1 (Pydantic Models)**: Replace inline placeholders with registry calls in `@field_validator`
- **Story 2.2 (Pandera Schemas)**: Optional integration via custom Pandera checks (AC5)
- **Story 2.4 (Date Parser)**: Date rules can wrap `parse_yyyymm_or_chinese()` for registry use

### Learnings from Previous Story

**From Story 2.2: Pandera Schemas for DataFrame Validation (Status: done)**

**Inline Placeholders to Replace** (Technical Debt from Story 2.1):
- `clean_company_name_inline()` in `models.py` → Replace with `registry.apply_rules(v, ['trim_whitespace', 'normalize_company_name'])`
- `clean_comma_separated_number()` in `models.py` → Replace with `registry.apply_rule(v, 'remove_currency_symbols')`
- This story resolves technical debt created in Stories 2.1 and 2.2

**Performance Patterns Established**:
- **Performance baseline tracking**: Update `tests/.performance_baseline.json` with cleansing rule metrics
- **10,000-row fixtures**: Use programmatic fixture generation (established pattern from Story 2.1)
- **Overhead measurement**: Simulate realistic pipeline (cleansing + validation) to measure <20% overhead
- **Story 2.1 achieved**: 83,937 rows/s (Pydantic input), 59,409 rows/s (Pydantic output)
- **Story 2.2 achieved**: 5000+ rows/s (Pandera Bronze/Gold)
- **Target for Story 2.3**: 1500+ rows/s (string operations, slightly slower than DataFrame ops)

**Testing Patterns**:
- **Test organization**: Separate test classes per AC (`TestAC1_RegistryCore`, `TestAC2_BuiltinRules`, etc.)
- **Pytest markers**: Use `@pytest.mark.unit` and `@pytest.mark.integration` per Story 1.11
- **Coverage targets**: Domain layer >90% coverage (Epic 1 retrospective learning)

**Pending Review Items from Story 2.2**:
- Story 2.2 has changes requested (decorator pattern, documentation)
- These do not block Story 2.3 development (cleansing is independent concern)
- Story 2.3 should follow established documentation patterns from review feedback

**Files Created in Story 2.2** (reference for patterns):
- `src/work_data_hub/domain/annuity_performance/schemas.py` - Pandera schemas
- `tests/unit/domain/annuity_performance/test_schemas.py` - Unit tests
- `tests/performance/test_story_2_2_performance.py` - Performance tests

[Source: stories/2-2-pandera-schemas-for-dataframe-validation-bronze-gold-layers.md#Dev-Agent-Record]

### Dependencies from Other Stories

**Epic 2 Story 2.1: Pydantic Models** (Prerequisite):
- **Status**: done ✅
- **Integration**: Cleansing registry will replace inline placeholders in Pydantic validators
- **Inline functions to replace**:
  - `clean_company_name_inline()` → registry call
  - `clean_comma_separated_number()` → registry call
- **File**: `src/work_data_hub/domain/annuity_performance/models.py`

**Epic 2 Story 2.2: Pandera Schemas** (Parallel):
- **Status**: done ✅
- **Integration**: Optional - cleansing rules can be used in custom Pandera checks (AC5)
- **Not blocking**: Story 2.2 waiting for changes, but Story 2.3 can proceed independently

**Epic 2 Story 2.4: Chinese Date Parsing** (Parallel):
- **Status**: backlog (not yet implemented)
- **Integration**: Story 2.4's `parse_yyyymm_or_chinese()` can be wrapped as cleansing rule
- **Approach**: Story 2.3 provides framework, Story 2.4 adds date-specific rule

**Epic 2 Story 2.5: Validation Error Handling** (Integration Point):
- **Status**: backlog (depends on Stories 2.1-2.4)
- **Integration**: Cleansing errors (e.g., rule raises exception) will be captured by Story 2.5 error reporter
- **Error format**: Return cleansing failures with field name, value, rule name

**Epic 1 Story 1.5: Pipeline Framework** (Foundation):
- **Status**: done ✅
- **Integration**: Cleansing rules are stateless transformations (fit `TransformStep` pattern if needed)
- **File**: `src/work_data_hub/domain/pipelines/types.py`

### Technical Constraints

**Cleansing Rule Contract**:
All cleansing rules must follow this contract:
```python
from typing import Any, Callable

CleansingRule = Callable[[Any], Any]

def example_rule(value: Any) -> Any:
    """
    Pure function: no side effects, no external dependencies

    Args:
        value: Raw value (can be None, str, int, float, etc.)

    Returns:
        Cleansed value (same or different type)

    Raises:
        ValueError: If value cannot be cleansed (caught by error reporter)
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    # Perform cleansing
    return value.strip()
```

**Performance Optimization Strategies** (if AC-PERF-1 fails):
1. **Vectorize operations**: Use Pandas `.str.replace()` instead of row-by-row apply
2. **Cache compiled regex**: Use `@lru_cache` for regex pattern compilation
3. **Reduce function call overhead**: Inline hot-path rules if needed
4. **Profile hot paths**: Use `cProfile` to identify bottlenecks

**Configuration Loading**:
- Use PyYAML or stdlib `yaml.safe_load()` for YAML parsing
- Cache loaded configuration (reload only on file change)
- Validate configuration on load (ensure referenced rules exist)

### Testing Standards

**Unit Test Coverage (>90% target per Story 1.11)**:
- Test registry core: registration, retrieval, composition, error handling
- Test built-in rules: all rules with valid/invalid inputs, edge cases
- Test YAML configuration: domain rule lookup, defaults, validation
- Test Pydantic integration: rules execute during validation, errors propagate
- Test edge cases: None, empty strings, non-string inputs, special characters

**Performance Test Requirements (Mandatory per Epic 2 Performance AC)**:
- Reuse `tests/fixtures/performance/annuity_performance_10k.csv` from Story 2.1
- Measure cleansing throughput: `throughput = 10000 / duration`, assert `>= 1000 rows/s`
- Target 1500+ rows/s for string operations (faster than Pydantic row validation)
- Update `tests/.performance_baseline.json` with cleansing baselines

**Integration with CI (Story 1.11)**:
- Unit tests run in <30s (enforced by CI timing check)
- Performance tests run in <3min (integration test stage)
- Coverage validated per module (cleansing/ >90%)

### Project Structure Notes

**File Locations**:
```
src/work_data_hub/
├── cleansing/
│   ├── __init__.py         # Export get_cleansing_registry
│   ├── registry.py         # NEW: CleansingRegistry class
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── string_rules.py # NEW: String cleansing rules
│   │   └── numeric_rules.py # NEW: Numeric cleansing rules
│   └── config/
│       └── cleansing_rules.yml # NEW: Per-domain rule configuration
├── domain/annuity_performance/
│   ├── models.py           # MODIFIED: Replace inline placeholders with registry
│   └── pipeline_steps.py   # (unchanged from Story 2.2)

tests/unit/cleansing/
├── test_registry.py         # NEW: Registry core tests
└── test_rules.py            # NEW: Built-in rule tests

tests/integration/
└── test_story_2_3_performance.py # NEW: Cleansing performance tests
```

**Module Dependencies**:
- `cleansing/registry.py` imports:
  - `import yaml` (for configuration loading)
  - `from typing import Callable, Any, List, Dict, Optional`
  - `from functools import lru_cache` (for singleton pattern)
  - NO imports from `io/`, `orchestration/`, or domain models
- `cleansing/rules/*.py` imports:
  - `import re` (for regex operations)
  - `from cleansing.registry import get_cleansing_registry` (auto-registration)
  - NO imports from domain models (rules are pure utilities)

### Security Considerations

**Data Validation Security**:
- Cleansing rules prevent injection attacks by normalizing input before validation
- String normalization reduces homograph attacks (e.g., full-width vs half-width characters)
- Regex patterns are hardcoded (not user-configurable) to prevent ReDoS attacks

**PII Handling**:
- `客户名称` field contains company names (low PII risk)
- Cleansing rules log input/output for debugging - use Epic 1 Story 1.3 log sanitization

**Dependency Security**:
- PyYAML is actively maintained with security updates
- No external API calls or network operations (offline cleansing only)

### References

**Epic 2 Documentation**:
- [Epic 2 Tech Spec](../sprint-artifacts/tech-spec-epic-2.md#story-23-cleansing-registry-framework) - Cleansing registry design
- [Epic 2 Performance AC](../epic-2-performance-acceptance-criteria.md) - MANDATORY thresholds
- [Epics.md: Story 2.3](../epics.md#story-23-cleansing-registry-framework) - Acceptance criteria source

**Architecture Documentation**:
- [Architecture Boundaries](../architecture-boundaries.md) - Clean Architecture enforcement
- [Architecture.md](../architecture.md) - Domain layer patterns

**Epic 1 Foundation**:
- [Story 1.11: CI/CD](../sprint-artifacts/stories/1-11-enhanced-cicd-with-integration-tests.md) - Performance baseline pattern

**PRD References**:
- [PRD §817-824: FR-3.2: Registry-Driven Cleansing](../PRD.md#fr-32-registry-driven-cleansing)

## Dev Agent Record

### Context Reference

- [Story 2.3 Context](2-3-cleansing-registry-framework.context.xml)

### Agent Model Used

<!-- Agent model will be recorded here during story execution -->

### Debug Log References

- 2025-11-17T15:06 Implementation Plan:
  1. Build CleansingRegistry core (apply_rule/apply_rules, domain config loader, singleton helper) and ensure YAML-backed rule discovery.
  2. Implement canonical string/numeric cleansing rules plus config file, then wire registry + loaders into annuity models.
  3. Backfill comprehensive unit/performance tests, update baselines, and refresh story artifacts (file list, change log, status).
- 2025-11-17T15:46 Execution Notes:
  - Implemented registry enhancements, YAML-driven domain rules, new string/numeric rule modules, and Pydantic integration with domain-aware validators plus Pandera helpers.
  - Authored new unit suites (`tests/unit/cleansing`, `tests/unit/domain/annuity_performance/test_story_2_3_cleansing.py`) and performance harness (`tests/performance/test_story_2_3_performance.py`), refreshed `tests/.performance_baseline.json`, and validated via `PYTHONPATH=src pytest ...`.

### Completion Notes List

- 2025-11-17T15:46 Completed Story 2.3 implementation:
  - CleansingRegistry now supports apply_rule/apply_rules, YAML-backed domain chains, and exposes `get_cleansing_registry`.
  - Added canonical string/numeric rules, YAML config, Input/Output model integration, schema helpers, and sprint-status moved to `review`.
  - Tests: `PYTHONPATH=src pytest tests/unit/cleansing tests/unit/domain/annuity_performance/test_story_2_3_cleansing.py tests/domain/annuity_performance/test_story_2_1_ac.py` plus `PYTHONPATH=src pytest tests/performance/test_story_2_3_performance.py -k "string_rule_throughput or numeric_rule_overhead_below_threshold"`.

### File List

- `src/work_data_hub/cleansing/registry.py`
- `src/work_data_hub/cleansing/config/cleansing_rules.yml`
- `src/work_data_hub/cleansing/rules/string_rules.py`
- `src/work_data_hub/cleansing/rules/numeric_rules.py`
- `src/work_data_hub/cleansing/__init__.py`
- `src/work_data_hub/domain/annuity_performance/__init__.py`
- `src/work_data_hub/domain/annuity_performance/models.py`
- `src/work_data_hub/domain/annuity_performance/schemas.py`
- `tests/unit/cleansing/test_registry.py`
- `tests/unit/cleansing/test_rules.py`
- `tests/unit/domain/annuity_performance/test_story_2_3_cleansing.py`
- `tests/domain/annuity_performance/test_story_2_1_ac.py`
- `tests/performance/test_story_2_3_performance.py`
- `tests/.performance_baseline.json`
- `docs/sprint-artifacts/stories/2-3-cleansing-registry-framework.md`

---

## Change Log

**2025-11-17** - Story drafted by SM agent (create-story workflow)
- Status: drafted (ready for context generation via story-context workflow)
- Next steps: Run story-context workflow, then mark ready-for-dev
- Based on Epic 2 Tech Spec and learnings from Stories 2.1 and 2.2
- Technical debt resolution: Replaces inline placeholders from Story 2.1

**2025-11-17** - Dev implementation (Story 2.3)
- Built CleansingRegistry execution APIs, YAML domain loader, and exposed singleton via package root.
- Added string/numeric rule modules, YAML config, Input/Output/Pandera integrations, and sprint-status updated to review.
- Authored unit + integration + performance tests with refreshed `tests/.performance_baseline.json`.

---
