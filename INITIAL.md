# Data Cleansing Framework Optimization (INITIAL.md)

## FEATURE

Optimize the existing data cleansing framework architecture to eliminate over-engineering components while preserving core functionality needed to support migration of 21 legacy domains, ensuring the framework adheres to KISS and YAGNI principles.

## PROBLEM BACKGROUND

**Current Issue**: During implementation of the annuity_performance domain, developers discovered duplicate data cleansing logic between domains and created a comprehensive cleansing framework (`src/work_data_hub/cleansing`). This framework needs evaluation and optimization to ensure it follows KISS/YAGNI principles while supporting the confirmed migration requirements.

**Specific Duplication**: 
- `src/work_data_hub/domain/annuity_performance/models.py:257-336` (80 lines)
- `src/work_data_hub/domain/trustee_performance/models.py:167-237` (71 lines)
- Both contain nearly identical `clean_decimal_fields` methods with same logic for currency symbols, percentage conversion, null handling, and precision quantization

**Architecture Context**: This is a complete system rewrite replacing legacy `annuity_hub` with 21 confirmed domain cleaners requiring migration. According to `docs/overview/R-015_LEGACY_INVENTORY.md`, these domains have varying complexity (HIGH: 4, MEDIUM: 8, LOW: 9) and require unified cleansing capabilities.

## SCOPE

### In-scope:
- Simplify complex indexing system in `src/work_data_hub/cleansing/registry.py`
- Preserve and optimize core cleansing functions in `numeric_rules.py`
- Streamline `pydantic_adapter.py` integration logic
- Ensure both existing domain models can utilize the optimized framework
- Create concise cleansing rule registration and lookup mechanism
- Eliminate the 151 lines of duplicate `clean_decimal_fields` code

### Non-goals:
- Complete framework rewrite (preserve sound architectural design)
- Immediate migration of all 21 legacy domains (phased implementation)
- Removal of all advanced features (retain genuinely needed capabilities)
- Changes to core business logic or cleansing algorithms

## CONTEXT SNAPSHOT

```bash
src/work_data_hub/
  cleansing/                    # Current framework (893 lines total)
    __init__.py                 # 137 lines - Framework entry point
    registry.py                 # 254 lines - Registry and indexing system [SIMPLIFY]
    rules/
      numeric_rules.py          # 286 lines - Core cleansing rules [PRESERVE/OPTIMIZE]
    integrations/
      pydantic_adapter.py       # 216 lines - Pydantic integration [SIMPLIFY]
  domain/
    annuity_performance/models.py    # Contains duplicate clean_decimal_fields
    trustee_performance/models.py    # Contains duplicate clean_decimal_fields

# Legacy reference for context
docs/overview/R-015_LEGACY_INVENTORY.md  # 21 domain migration requirements
ROADMAP.md                               # M2 milestone domain migration plan
```

## EXAMPLES

**Preserve Pattern - Core Cleansing Functions**:
- Path: `src/work_data_hub/cleansing/rules/numeric_rules.py` — This contains the actual solution to duplication, architecture is sound

**Simplify Pattern - Registry System**:
- Path: `src/work_data_hub/cleansing/registry.py` — Remove complex indexing, retain basic registration

**Integration Pattern - Domain Usage**:
- Path: `src/work_data_hub/domain/trustee_performance/models.py:167-237` — Reference existing clean_decimal_fields pattern

**Current Duplication Example**:
```python
# DUPLICATE CODE (to be eliminated)
# Both domains have this nearly identical 70-line method:
@field_validator("期初资产规模", "期末资产规模", "供款", mode="before")
@classmethod
def clean_decimal_fields(cls, v, info: Any):
    """Clean and convert financial fields with precision quantization."""
    # 70 lines of identical logic for:
    # - Currency symbol removal (¥, $, ￥)
    # - Percentage conversion (50% -> 0.50)
    # - Null value handling ("", "-", "N/A", "无", "暂无")
    # - Decimal precision quantization
```

**Optimized Registry Design**:
```python
# Simplified registry (remove complex indexing)
class CleansingRegistry:
    _rules: Dict[str, CleansingRule] = {}
    
    def register(self, rule: CleansingRule) -> None:
        """Register a cleansing rule by name."""
        self._rules[rule.name] = rule
    
    def get_rule(self, name: str) -> Optional[CleansingRule]:
        """Get rule by name for direct lookup."""
        return self._rules.get(name)
    
    def find_numeric_rules(self) -> List[CleansingRule]:
        """Find rules for numeric data types."""
        return [r for r in self._rules.values() if r.category == RuleCategory.NUMERIC]
```

## DOCUMENTATION

- File: `CLAUDE.md` — Project coding standards and architectural principles
- File: `docs/overview/R-015_LEGACY_INVENTORY.md` — Complete inventory of 21 domain cleansing requirements
- File: `docs/overview/MIGRATION_REFERENCE.md` — Migration approach and architecture requirements
- File: `ROADMAP.md` — M2 milestone domain migration timeline
- URL: https://docs.pydantic.dev/2.0/ — Pydantic v2 integration patterns

## INTEGRATION POINTS

**Data Models**:
- Preserve existing `CleansingRule` dataclass, simplify metadata fields
- Retain `RuleCategory` enum, focus primarily on NUMERIC category for current needs
- Update domain models to use simplified cleansing interface

**Configuration**:
- Remove complex configuration file-driven approach (`domain_rules.yml` etc.)
- Maintain code-level cleansing rule definitions for simplicity

**Integration Interfaces**:
- Simplify `decimal_fields_cleaner` decorator implementation
- Preserve Pydantic v2 integration for new architecture requirements

## DATA CONTRACTS

```python
# Simplified cleansing rule definition
@dataclass
class CleansingRule:
    name: str
    category: RuleCategory
    func: Callable
    description: str
    # REMOVED: applicable_types, field_patterns, version, author (over-engineering)

# Preserved core cleansing function interface
def comprehensive_decimal_cleaning(
    value: Any, 
    field_name: str = "", 
    precision: int = 4
) -> Optional[Decimal]:
    """
    Unified decimal field cleansing function to eliminate duplication.
    
    Handles:
    - Currency symbol removal (¥, $, ￥)
    - Percentage conversion (50% -> 0.50)
    - Null value standardization ("", "-", "N/A", "无", "暂无")
    - Decimal precision quantization with ROUND_HALF_UP
    """
```

## GOTCHAS & LIBRARY QUIRKS

- Maintain Pydantic v2 compatibility, avoid v1 `orm_mode`
- Handle Chinese field names properly (`期初资产规模`, `期末资产规模` etc.)
- Decimal precision quantization must use `ROUND_HALF_UP` for consistency
- Percentage conversion logic must distinguish between string "50%" and numeric 50
- Use `rg` (ripgrep) for searches, not `grep/find` per project standards

## IMPLEMENTATION NOTES

**Refactoring Strategy**:
1. **Preserve effective components**: `numeric_rules.py` cleansing functions solve real duplication
2. **Simplify registration mechanism**: Remove multi-layer indexing, keep basic registration/lookup
3. **Progressive adoption**: Start with existing 2 domains, validate effectiveness, then expand
4. **Avoid breaking changes**: Maintain public API stability during optimization

**Architectural Principles**:
- Follow CLAUDE.md KISS principle: choose simple solutions over complex ones
- Keep functions under 50 lines, classes under 100 lines per project standards
- Prefer composition over inheritance
- Maintain clean separation between Config → IO → Domain → Orchestration → Utils layers

## VALIDATION GATES

```bash
# Basic validation
uv run ruff check src/ --fix
uv run mypy src/
uv run pytest -v

# Ensure existing functionality works
uv run pytest tests/test_cleansing_framework.py -v

# Ensure domain model integration works
uv run pytest tests/domain/ -k "decimal" -v

# Verify no regressions in existing domains
uv run pytest tests/domain/test_trustee_performance.py -v
uv run pytest tests/domain/test_annuity_performance.py -v
```

## ACCEPTANCE CRITERIA

- [ ] Both existing domain models successfully use optimized cleansing framework
- [ ] `clean_decimal_fields` duplicate code (151 lines) is eliminated
- [ ] Registry system complexity reduced while maintaining basic functionality
- [ ] Core cleansing rule functionality completely preserved
- [ ] Framework total code lines reduced by 20-30%
- [ ] All existing tests continue to pass
- [ ] New simplified API is clearly documented and easy to understand
- [ ] Integration with Pydantic v2 field validators works seamlessly
- [ ] Chinese field names and data continue to process correctly

## ROLLOUT & RISK

**Implementation Phases**:
1. **Phase 1**: Simplify registry, remove unnecessary indexing systems
2. **Phase 2**: Update existing domain models to use optimized framework
3. **Phase 3**: Provide clean interface for next domain migration

**Risk Controls**:
- Maintain backward compatibility to ensure existing code remains unaffected
- Step-by-step refactoring with test validation at each step
- Preserve rollback option: can quickly revert to current implementation
- No changes to core business logic or data processing algorithms

## IMPLEMENTATION PRIORITY

**High Priority (Execute Immediately)**:
1. Simplify `CleansingRegistry` class, remove complex indexing
2. Update both domain models to use framework, eliminating duplication

**Medium Priority (Subsequent Optimization)**:
1. Streamline `pydantic_adapter.py` decorator logic
2. Improve test coverage and documentation

**Low Priority (Optional)**:
1. Prepare additional cleansing rule types for future domain migrations

**Success Outcome**: A cleansing framework that adheres to KISS/YAGNI principles while supporting enterprise-scale domain migration requirements, with 151 lines of duplicate code eliminated and architecture simplified for maintainability.