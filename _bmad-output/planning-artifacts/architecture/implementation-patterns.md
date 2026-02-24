# Implementation Patterns

These patterns ensure AI agent consistency across 100+ stories.

### Pattern 1: Epic Story Implementation Flow

**For All Domain Migration Epics (Epic 4, 9):**

```
Story X.1: Pydantic Models (Chinese fields, validators)
  ↓
Story X.2: Bronze Schema (pandera, structural validation)
  ↓
Story X.3: Transformation Pipeline (DataFrame + Row steps)
  ↓
Story X.4: Gold Schema (pandera, business rules)
  ↓
Story X.5: Database Loading (warehouse_loader.py)
  ↓
Story X.6: Parity Tests (vs legacy, CI-enforced)
```

**Apply to:** Epic 4 (Annuity), Epic 9 (Growth Domains)

---

### Pattern 2: Error Handling Standard

**For All Transformation Steps:**

```python
def transform_step(row: Row, context: Dict) -> StepResult:
    """Standard error handling pattern."""
    warnings = []
    errors = []

    try:
        # 1. Validate inputs
        if not row.get('required_field'):
            raise ValueError("Missing required field")

        # 2. Perform transformation
        result = complex_transformation(row)

        # 3. Validate outputs
        if result < 0:
            warnings.append("Negative value detected, clamping to 0")
            result = 0

        return StepResult(
            row={**row, 'new_field': result},
            warnings=warnings,
            errors=errors
        )

    except Exception as e:
        # 4. Create structured error context
        context = ErrorContext(
            error_type="TransformationError",
            operation="transform_step",
            domain=context.get('domain'),
            row_number=context.get('row_number'),
            field='new_field',
            input_data={'row': sanitize(row)},
            original_error=str(e)
        )

        errors.append(create_error_message(str(e), context))

        return StepResult(
            row=row,  # Return original on error
            warnings=warnings,
            errors=errors
        )
```

---

### Pattern 3: Configuration-Driven Discovery

**For All Domains (Epic 3 Integration):**

```yaml
# config/data_sources.yml
domains:
  annuity_performance:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns:
      - "*年金*.xlsx"
    version_strategy: "highest_number"  # Decision #1
    sheet_selection: "auto"  # First sheet with data

  business_collection:
    base_path: "reference/monthly/{YYYYMM}/收集数据/业务收集"
    file_patterns:
      - "*业务*.xlsx"
    version_strategy: "highest_number"
```

**Python Integration:**
```python
from config.mapping_loader import load_data_source_config

# Epic 3 Story 3.5
config = load_data_source_config("annuity_performance")
file_path = discover_file(
    base_path=config.base_path.format(YYYYMM="202501"),
    patterns=config.file_patterns,
    version_strategy=config.version_strategy  # Uses Decision #1
)
```

---

### Pattern 4: Testing Strategy

**Test Pyramid (Epic 6):**

```
                    /\
                   /  \
                  / E2E \    ← test_pipeline_vs_legacy.py (parity)
                 /______\
                /        \
               / Integration \   ← test_domain_pipeline.py
              /______________\
             /                \
            /   Unit Tests     \  ← test_date_parser.py, test_normalizer.py
           /____________________\
```

**Unit Tests (Epic 6 Story 6.1):**
- Test pure functions: date parser, company normalizer, validators
- Mock external dependencies: database, EQC API
- Fast (<1s total execution)

**Integration Tests (Epic 6 Story 6.2):**
- Test pipeline orchestration: step execution order, error propagation
- Use test fixtures: sample Excel files, stub providers
- Medium speed (<10s)

**E2E/Parity Tests (Epic 6 Story 6.3):**
- Compare new vs legacy outputs (100% match requirement)
- Use real data: `reference/monthly/` samples
- Slow (<60s), run on CI only

**Pytest Markers:**
```python
@pytest.mark.unit
def test_date_parser():
    """Fast unit test."""
    ...

@pytest.mark.integration
def test_annuity_pipeline():
    """Integration test with fixtures."""
    ...

@pytest.mark.parity
@pytest.mark.legacy_data
def test_annuity_vs_legacy():
    """E2E parity test (slow, CI only)."""
    ...
```

**Run Strategies:**
```bash
# Development (fast feedback)
uv run pytest -v -m "unit"

# Pre-commit (medium)
uv run pytest -v -m "unit or integration"

# CI (comprehensive)
uv run pytest -v --cov=src --cov-report=term-missing
```

---

### Pattern 5: Pipeline Context Contract (Epic 5.8)

- `PipelineContext` MUST include: `pipeline_name`, `execution_id`, `run_id`, `domain`, `timestamp`, `config`, `metadata`, optional `logger` and `extra`.
- Context propagates through every TransformStep; steps may read/write `metadata` for metrics (e.g., `db_queries` counters).
- Service entrypoints are responsible for constructing a fully populated `PipelineContext` and passing it into pipeline execution to satisfy AC10/AC11.

---

### Pattern 6: Package Modularization (Epic 7)

> **Added 2025-12-22:** Enforces 800-line file limit via pre-commit hooks.

**When to Apply:**
- Any file exceeding 800 lines MUST be decomposed
- Files approaching 600+ lines SHOULD be proactively modularized

**Decomposition Strategy:**

```
Before (monolithic):                 After (package):
src/module/                          src/module/
├── large_file.py (1200+ lines)      ├── __init__.py     # Public API exports
                                     ├── package/
                                     │   ├── __init__.py
                                     │   ├── core.py     # Main class
                                     │   ├── models.py   # Data classes
                                     │   ├── utils.py    # Helper functions
                                     │   └── ...
                                     └── large_file.py   # Facade (re-exports)
```

**Key Principles:**

1. **Facade Pattern:** Original file becomes a thin re-export layer for backward compatibility
2. **Single Responsibility:** Each sub-module handles one concern
3. **Public API via `__init__.py`:** All exports explicitly listed
4. **Zero Breaking Changes:** External imports continue to work

**File Size Guidelines (from `project-context.md`):**

| Limit | Threshold | Action |
|-------|-----------|--------|
| **MAX 800 lines** | File size | Split into sub-modules immediately |
| **MAX 50 lines** | Function size | Extract helper functions |
| **MAX 100 lines** | Class size | Use composition, split class |

**Epic 7 Examples:**

| Original File | Package | Story |
|---------------|---------|-------|
| `ops.py` (1700 lines) | `orchestration/ops/` | 7-1 |
| `warehouse_loader.py` (1400 lines) | `io/loader/` | 7-2 |
| `eqc_client.py` (1100 lines) | `io/connectors/eqc/` | 7-2 |
| `etl.py` (1200 lines) | `cli/etl/` | 7-4 |
| `domain_registry.py` (900 lines) | `infrastructure/schema/` | 7-5 |

**Pre-commit Hook Enforcement:**

```bash
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: check-file-length
      name: Check file length (max 800 lines)
      entry: python scripts/quality/check_file_length.py
      language: system
      types: [python]
```

---
