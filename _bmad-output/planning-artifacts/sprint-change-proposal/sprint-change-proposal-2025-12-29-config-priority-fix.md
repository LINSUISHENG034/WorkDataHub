# Sprint Change Proposal: Configuration Priority Fix

> **Date:** 2025-12-29  
> **Status:** 📋 Proposed  
> **Author:** Correct-Course Workflow  
> **Priority:** P1 (High)  
> **Epic:** 7.3 (Multi-Domain Consistency Fixes) - Story 7.3-5

---

## 1. Issue Summary

### Problem Statement

During multi-domain testing, Alembic migrations connected to the wrong database (`wdh_migration_test`) instead of the `.wdh_env` configured database (`postgres`).

### Root Cause

PowerShell session contained `$env:WDH_DATABASE__URI = wdh_migration_test`. Per **pydantic-settings default priority**:

1. **System environment variables** ← Highest priority (overrides .wdh_env)
2. `.env` file (`.wdh_env`)
3. Code defaults

### Design Expectation

`.wdh_env` should be the **single source of truth** for configuration, preventing accidental overrides from lingering environment variables.

### Discovery Context

- **Triggering Activity:** Epic 7.3 Story 7.3-4 field gap validation
- **Discovery Method:** `alembic upgrade head` wrote to wrong database
- **Evidence:** Tables created in `wdh_migration_test` instead of `postgres`

---

## 2. Impact Analysis

### Epic Impact

| Epic     | Status       | Impact                                                            |
| -------- | ------------ | ----------------------------------------------------------------- |
| Epic 7.3 | **REOPENED** | Add Story 7.3-5 - issue discovered during post-completion testing |
| Epic 8   | Backlog      | No impact - depends on clean configuration                        |

### Story Impact

No existing stories require modification. New story will be created.

### Artifact Conflicts

| Document     | Conflict        | Resolution                                      |
| ------------ | --------------- | ----------------------------------------------- |
| PRD          | None            | No scope change                                 |
| Architecture | Minor           | Document configuration priority design decision |
| Settings.py  | **Code Change** | Modify `get_database_connection_string()`       |

### Technical Impact

| Component            | Impact Level | Description                             |
| -------------------- | ------------ | --------------------------------------- |
| `config/settings.py` | **MODIFY**   | Add .wdh_env-only mode for database URI |
| Alembic migrations   | Indirect     | Will use correct database after fix     |
| ETL CLI              | Indirect     | Will use correct database after fix     |
| Unit tests           | Low          | May need fixture adjustments            |

---

## 3. Recommended Approach

### Selected Option: **Option 1 - Direct Adjustment (方案 A)**

Modify `get_database_connection_string()` to **ignore system environment variables** and read exclusively from `.wdh_env` file.

### Rationale

1. **Single Source of Truth:** Eliminates configuration ambiguity
2. **Developer Safety:** Prevents accidental production issues from lingering env vars
3. **Minimal Risk:** Change is isolated to one method
4. **Backward Compatible:** `.wdh_env` users see no difference

### Effort Estimate: **Low** (1-2 hours)

### Risk Level: **Low**

- Change is localized to one method
- All existing tests should pass
- No database schema changes

---

## 4. Detailed Change Proposals

### 4.1 Modify `get_database_connection_string()` Method

**File:** `src/work_data_hub/config/settings.py`  
**Section:** Lines 352-379

#### OLD (Current Implementation):

```python
def get_database_connection_string(self) -> str:
    """Get PostgreSQL connection string from .env file only.

    Configuration is read exclusively from .env file to ensure single source
    of truth.
    Priority order:
    1) WDH_DATABASE__URI (canonical, from .env)
    2) WDH_DATABASE_URI (alternate, from .env)
    3) Construct from individual WDH_DATABASE_* components (from .env)

    Automatically corrects 'postgres://' scheme to 'postgresql://' for
    SQLAlchemy compatibility.
    """
    env_uri = os.getenv("WDH_DATABASE__URI") or os.getenv("WDH_DATABASE_URI")

    final_uri = None
    if env_uri:
        final_uri = env_uri
    elif self.database_uri:
        final_uri = self.database_uri
    else:
        final_uri = self.database.get_connection_string()

    # Fix for SQLAlchemy compatibility (postgres:// is deprecated/unsupported in newer versions)
    if final_uri and final_uri.startswith("postgres://"):
        final_uri = final_uri.replace("postgres://", "postgresql://", 1)

    return final_uri
```

#### NEW (Proposed Implementation):

```python
def get_database_connection_string(self) -> str:
    """Get PostgreSQL connection string from .wdh_env file ONLY.

    Configuration is read EXCLUSIVELY from the .wdh_env file to ensure
    single source of truth. System environment variables are IGNORED
    to prevent accidental overrides from lingering shell variables.

    Priority order (from .wdh_env file only):
    1) WDH_DATABASE__URI (canonical)
    2) WDH_DATABASE_URI (alternate)
    3) Construct from individual WDH_DATABASE_* components

    Automatically corrects 'postgres://' scheme to 'postgresql://' for
    SQLAlchemy compatibility.

    Returns:
        PostgreSQL connection string (DSN)

    Raises:
        ValueError: If no database configuration found in .wdh_env
    """
    final_uri: str | None = None

    # Step 1: Read ONLY from .wdh_env file (ignore system environment variables)
    if isinstance(SETTINGS_ENV_FILE, Path) and SETTINGS_ENV_FILE.exists():
        for line in SETTINGS_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("WDH_DATABASE__URI="):
                final_uri = line.split("=", 1)[1].strip()
                break
            if line.startswith("WDH_DATABASE_URI="):
                final_uri = line.split("=", 1)[1].strip()
                # Continue looking for WDH_DATABASE__URI (higher priority)

    # Step 2: Fallback to constructed URI from components (also from .wdh_env via pydantic)
    if not final_uri:
        if self.database_uri:
            final_uri = self.database_uri
        else:
            final_uri = self.database.get_connection_string()

    # Step 3: Validate we have a URI
    if not final_uri:
        raise ValueError(
            f"No database configuration found. "
            f"Please set WDH_DATABASE__URI in {SETTINGS_ENV_FILE}"
        )

    # Step 4: Fix for SQLAlchemy compatibility
    if final_uri.startswith("postgres://"):
        final_uri = final_uri.replace("postgres://", "postgresql://", 1)

    return final_uri
```

#### Rationale

1. **Explicit file-only reading:** Uses `SETTINGS_ENV_FILE.read_text()` instead of `os.getenv()`
2. **Priority preserved:** `WDH_DATABASE__URI` still takes precedence over `WDH_DATABASE_URI`
3. **Clear error message:** Tells user exactly where to configure if missing
4. **No side effects:** Does not modify any global state

---

### 4.2 Add Documentation Warning

**File:** `.wdh_env.example` (or project documentation)

#### Add Warning:

```bash
# IMPORTANT: Database configuration is read ONLY from this file.
# System environment variables (e.g., $env:WDH_DATABASE__URI) are IGNORED
# to prevent accidental overrides. This ensures single source of truth.
WDH_DATABASE__URI=postgresql://user:password@localhost:5432/postgres
```

---

## 5. Implementation Handoff

### Change Scope: **Minor**

Direct implementation by development team. No backlog reorganization required.

### Handoff Recipients

| Role          | Responsibility                                |
| ------------- | --------------------------------------------- |
| **Dev Team**  | Implement code change, run unit tests         |
| **QA (Self)** | Verify migration connects to correct database |

### Success Criteria

1. [ ] `get_database_connection_string()` reads ONLY from `.wdh_env` file
2. [ ] System environment variable `$env:WDH_DATABASE__URI` is ignored
3. [ ] All existing unit tests pass
4. [ ] `alembic upgrade head` connects to `.wdh_env` configured database
5. [ ] `etl --domains annuity_income` writes to correct database

### Verification Steps

```bash
# Step 1: Set conflicting environment variable
$env:WDH_DATABASE__URI = "wdh_wrong_database"

# Step 2: Verify .wdh_env has correct configuration
cat .wdh_env | Select-String "WDH_DATABASE__URI"
# Expected: WDH_DATABASE__URI=postgresql://...@localhost:5432/postgres

# Step 3: Run migration and verify correct database
uv run --env-file .wdh_env alembic upgrade head
# Expected: Connects to postgres (from .wdh_env), NOT wdh_wrong_database

# Step 4: Cleanup
Remove-Item Env:WDH_DATABASE__URI
```

---

## 6. Story Definition

### Epic 7.3: Multi-Domain Consistency Fixes (Extended)

### Story 7.3-5: Fix Database URI Configuration Priority

**Status:** Ready for Development  
**Priority:** P1 (High)  
**Effort:** 2 Story Points  
**Rationale:** Issue discovered during multi-domain testing (Story 7.3-4 validation phase)

#### Acceptance Criteria

- [ ] **AC1:** `get_database_connection_string()` ignores system environment variables
- [ ] **AC2:** Configuration is read exclusively from `.wdh_env` file
- [ ] **AC3:** Clear error message when no database URI found in `.wdh_env`
- [ ] **AC4:** All existing unit tests pass
- [ ] **AC5:** Integration verification: Alembic connects to correct database

#### Tasks

1. [ ] Modify `get_database_connection_string()` to read only from file
2. [ ] Update docstring to reflect new behavior
3. [ ] Add unit test for environment variable override protection
4. [ ] Update `.wdh_env.example` with warning comment
5. [ ] Verify with multi-domain ETL test

---

## Appendix: Related Documents

- **Issue Analysis:** [config-priority-issue.md](file:///e:/Projects/WorkDataHub/docs/specific/multi-domain/config-priority-issue.md)
- **Settings Module:** [settings.py](file:///e:/Projects/WorkDataHub/src/work_data_hub/config/settings.py)
- **pydantic-settings Docs:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/
