# Critical Issue 001: Production Database Downgrade Incident

**Date**: 2026-01-09
**Severity**: CRITICAL
**Status**: FIXED (Multi-layer defense implemented)
**Impact**: Production database (postgres) schema `business` deleted, other schemas potentially reverted to base state.

## Incident Description
During the execution of automated tests (`test_migrations.py`), the production database was incorrectly targeted by the rollback (downgrade) operation, causing the deletion of all schema objects managed by migration scripts (including `business` and `mapping` schemas).

## Root Cause Analysis

The incident was caused by a combination of a flaw in `env.py` and a "Split Brain" configuration state during test teardown.

### 1. The `env.py` Flaw (Primary Cause)
The Alembic environment configuration file (`io/schema/migrations/env.py`) was implemented to **unconditionally override** the database URL provided by the runner with the URL from the application settings (`get_settings()`).

```python
# io/schema/migrations/env.py (Lines 33-36)
settings = get_settings()
database_url = settings.get_database_connection_string()
# CRITICAL FLAW: Overwrites whatever URL was passed programmatically
config.set_main_option("sqlalchemy.url", database_url)
```

This means that even if `migration_runner.downgrade(temp_dsn)` is called explicitly with a safe temporary database URL, `env.py` ignores it and uses whatever `get_settings()` returns.

### 2. Test Fixture Environment Desynchronization
The test fixture `postgres_db_with_migrations` in `tests/conftest.py` relies on modifying `os.environ` to hijack `get_settings()`.

```python
# tests/conftest.py
@pytest.fixture
def postgres_db_with_migrations():
    # ... setup temp_dsn ...
    os.environ["DATABASE_URL"] = temp_dsn  # Point settings to temp DB
    
    try:
        yield temp_dsn
    finally:
        # TEARDOWN PHASE
        # Issue: downgrade() is called here
        migration_runner.downgrade(temp_dsn, "base") 
```

During the cleanup phase of the failing test, the environment context was either lost, restored prematurely, or `get_settings()` returned cached values pointing to the original `DATABASE_URL` (Production/Postgres).

### 3. The Catastrophic Chain
1. Test `test_migrations.py` fails.
2. Fixture enters `finally` block for cleanup.
3. `migration_runner.downgrade(temp_dsn, "base")` is called with the *correct* temp URL.
4. Alembic starts and loads `env.py`.
5. `env.py` executes `settings = get_settings()`.
6. Due to environment desynchronization, `settings` resolves to the **Production Database URL**.
7. `env.py` forces Alembic to use the Production URL, ignoring the `temp_dsn` passed in step 3.
8. Alembic executes `downgrade base` on Production, deleting all tables.

## Impact Checklist
- [x] `business` schema deleted (confirmed)
- [x] `mapping` schema deleted (confirmed)
- [x] `enterprise` schema potentially affected
- [x] `alembic_version` table cleared

## Required Fixes

1. **Fix `env.py`**: Stop overwriting `sqlalchemy.url` if it's already set in the config object. Only use `get_settings()` as a fallback or for CLI usage.
2. **Harden `conftest.py`**: Do not rely on `os.environ` manipulation for critical safety. Pass explicit database URLs to runner functions.
3. **Safety Guard**: Implement a "Production Guard" in `migration_runner` that explicitly forbids `downgrade` operations if the resolved URL matches production patterns, regardless of inputs.

## Fix Implementation (2026-01-09)

A multi-layer defense strategy was implemented to prevent similar incidents:

### Layer 1: env.py URL Override Fix
**File**: `io/schema/migrations/env.py`

- Only use `get_settings()` as fallback when no explicit URL is provided
- Respect URLs passed via `config.attributes["explicit_database_url"]`

### Layer 2: Explicit URL Passing
**File**: `src/work_data_hub/io/schema/migration_runner.py`

- Pass database URL via `config.attributes` to bypass potential overrides
- Ensures programmatic calls always use the intended database

### Layer 3: Production Database Protection (Core Defense)
**File**: `src/work_data_hub/io/schema/migration_runner.py`

- Added `_is_production_database()` detection function
- `downgrade()` now blocks operations on production databases
- Requires explicit override: `WDH_ALLOW_PRODUCTION_DOWNGRADE='I_KNOW_WHAT_I_AM_DOING'`
- Safe patterns: `test`, `tmp`, `dev`, `local`, `sandbox`, `wdh_test_`

### Layer 4: Test Isolation Enhancement
**File**: `tests/conftest.py`

- Added assertion to verify temp database uses `wdh_test_` prefix
- Explicit URL passing to migration_runner functions

### Verification
```bash
# Test production protection
python -c "from work_data_hub.io.schema import migration_runner; migration_runner.downgrade('postgresql://localhost/prod_db')"
# Result: RuntimeError: BLOCKED: Refusing to downgrade potential production database.
```