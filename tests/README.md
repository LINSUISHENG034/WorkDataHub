# WorkDataHub Test Suite

> Python 3.10+ | pytest | uv

## Quick Start

```bash
# Run all unit tests
PYTHONPATH=src uv run pytest tests/unit -m "not postgres"

# Run with coverage
PYTHONPATH=src uv run pytest tests/unit --cov=src --cov-report=html

# Run integration tests (requires PostgreSQL)
PYTHONPATH=src uv run pytest tests/integration -m postgres

# Run specific domain tests
PYTHONPATH=src uv run pytest tests/unit/domain/annuity_performance
```

## Prerequisites

1. Copy `.wdh_env.example` to `.wdh_env` and fill in values
2. Install dev dependencies: `uv sync --group dev`
3. For PostgreSQL tests: ensure `DATABASE_URL` is set in `.wdh_env`

## Directory Structure

```
tests/
├── conftest.py              # Root conftest: DB fixtures, env loading, markers
├── unit/                    # Pure unit tests (no external dependencies)
│   ├── architecture/        # Architecture compliance tests
│   ├── cli/                 # CLI command tests
│   ├── cleansing/           # Cleansing rule tests
│   ├── config/              # Configuration tests
│   ├── customer_mdm/        # Customer MDM domain tests
│   ├── domain/              # Domain logic tests
│   ├── infrastructure/      # Infrastructure layer tests
│   ├── io/                  # IO layer tests
│   ├── orchestration/       # Orchestration layer tests
│   ├── scripts/             # Script tests
│   └── utils/               # Utility tests
├── integration/             # Tests requiring external resources (DB, filesystem)
├── e2e/                     # End-to-end pipeline tests
├── slice_tests/             # Data slice validation tests
├── performance/             # Performance benchmarks
├── smoke/                   # Smoke tests for monthly data
├── fixtures/                # Shared test data files
│   ├── sample_data/         # Excel/CSV sample inputs
│   ├── mappings/            # JSON mapping fixtures
│   ├── golden_dataset/      # Golden reference datasets
│   ├── performance/         # Performance test data
│   └── test_data_factory.py # DataFrame factory for integration tests
└── support/                 # Shared test utilities
    └── helpers/             # Reusable test helpers
```

## Test Markers

| Marker | Description | Command |
|---|---|---|
| `unit` | Fast tests, no external deps | `pytest -m unit` |
| `integration` | Requires DB or filesystem | `pytest -m integration` |
| `postgres` | Requires PostgreSQL | `pytest -m postgres` |
| `e2e` | Legacy parity scenarios | `pytest -m e2e` |
| `performance` | Slow benchmarks | `pytest -m performance` |
| `legacy_suite` | Opt-in: `RUN_LEGACY_TESTS=1` | `pytest --run-legacy-tests` |
| `e2e_suite` | Opt-in: `RUN_E2E_TESTS=1` | `pytest --run-e2e-tests` |
| `sandbox_domain` | Sandbox domain tests | `pytest -m sandbox_domain` |

## Best Practices

- All tests follow Arrange-Act-Assert pattern
- Use `@pytest.mark.unit` for tests with no external dependencies
- Use `@pytest.mark.postgres` for tests requiring database
- Use `AnnuityTestDataFactory` from `tests/fixtures/test_data_factory.py` for DataFrame generation
- Never hardcode credentials — use `.wdh_env` environment variables
- Ephemeral test databases use `wdh_test_*` prefix with auto-cleanup

## CI Integration

**PR Pipeline** (< 10 min):
```bash
PYTHONPATH=src uv run pytest tests/unit -m "not postgres" --cov=src --cov-fail-under=80
```

**Nightly Pipeline** (< 25 min):
```bash
PYTHONPATH=src uv run pytest tests/unit tests/integration -m "not e2e_suite"
```

## Migration Tools

The test suite is undergoing structural migration. Use these tools:

```bash
# Collect baseline before migration
PYTHONPATH=src uv run python scripts/verify_test_migration.py collect

# Verify no tests lost after migration
PYTHONPATH=src uv run python scripts/verify_test_migration.py verify

# Strict mode (fail if count decreased)
PYTHONPATH=src uv run python scripts/verify_test_migration.py verify --strict
```

See `_bmad-output/test-artifacts/framework-setup-progress.md` for the full migration plan.
