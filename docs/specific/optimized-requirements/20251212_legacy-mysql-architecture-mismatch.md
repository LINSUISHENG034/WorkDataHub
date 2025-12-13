# Critical Architecture Mismatch: Legacy MySQL Connector vs PostgreSQL Infrastructure

**Date:** 2025-12-12
**Status:** Open
**Component:** `LegacyMySQLConnector` & Reference Data Sync
**Priority:** Blocker (Must fix before Epic 6.5)

## 1. Issue Summary
The current codebase contains a fundamental architecture mismatch that will prevent Story 6.2 and Reference Data Sync from functioning.

- **Assumption (Code):** Legacy data resides in a running **MySQL** database.
- **Reality (Infrastructure):** Legacy data has been migrated to a **PostgreSQL** database named `legacy`, with original MySQL databases converted to PostgreSQL schemas (`enterprise`, `business`, `mapping`).
- **Consequence:** All code using `LegacyMySQLConnector` (based on `pymysql`) will fail to connect or execute queries against the PostgreSQL infrastructure.

## 2. Infrastructure Verification
Direct verification of the `legacy` PostgreSQL database confirms:
- **Connection:** Successful connection to `legacy` DB on localhost:5432.
- **Schemas:** All required legacy schemas exist as PostgreSQL schemas:
  - `enterprise` (was MySQL DB `enterprise`)
  - `business` (was MySQL DB `business`)
  - `mapping` (was MySQL DB `mapping`)

## 3. Impact Analysis
The following components are broken by design and require immediate refactoring:

1.  **`src/work_data_hub/io/connectors/legacy_mysql_connector.py`**
    - Uses `pymysql` driver (incompatible with Postgres).
    - Expects MySQL protocol.
    - **Status:** Needs complete replacement.

2.  **`src/work_data_hub/io/loader/company_mapping_loader.py`**
    - Attempts to use `MySqlDBManager` or `LegacyMySQLConnector`.
    - Hardcoded SQL likely uses MySQL syntax (e.g., backticks `` ` ``).
    - **Status:** Needs SQL syntax update and connector replacement.

3.  **`src/work_data_hub/domain/reference_backfill/sync_service.py`**
    - Configured with `source_type="legacy_mysql"`.
    - **Status:** Needs configuration update.

4.  **`config/data_sources.yml`**
    - Defines sources as `legacy_mysql`.
    - **Status:** Needs update to reflect Postgres source.

## 4. Key Risks to Address

When implementing the remediation, developers must specifically address these high-risk areas:

### A. SQL Syntax & Quoting (High Risk)
*   **Risk:** MySQL uses backticks (`` ` ``) for identifiers, while PostgreSQL uses double quotes (`"`). Hardcoded SQL strings in Loaders will throw syntax errors in Postgres.
*   **Mitigation:** 
    *   Strictly scan all SQL strings in `company_mapping_loader.py` and `legacy` modules.
    *   Replace all backticks with double quotes or remove them.
    *   Use **fully qualified names** (e.g., `enterprise.company_mapping`) instead of relying on `USE db` or context switching, as `enterprise` is now a schema, not a database.

### B. Cross-Schema vs Cross-Database
*   **Risk:** Legacy code treats `enterprise` and `business` as separate databases (requiring connection switching or `USE` statements). In Postgres, they are schemas within the single `legacy` database.
*   **Mitigation:** 
    *   The `LegacyPostgresConnector` should maintain a **single connection** to the `legacy` database.
    *   Remove any logic that attempts to "switch databases". Access all tables via `schema.table` syntax.

### C. Data Type Mismatches
*   **Risk:** MySQL `TINYINT(1)` (boolean), date `0000-00-00`, and lax group-by behavior may cause runtime errors or data corruption in Python types.
*   **Mitigation:** 
    *   Implement explicit casting in SQL (e.g., `CAST(is_active AS BOOLEAN)`) or validation in the Pydantic models.
    *   Ensure all `GROUP BY` clauses are standard-compliant (contain all non-aggregated columns).

## 5. Remediation Plan: "Postgres-to-Postgres" Adapter

We will implement **Scheme A (Dual Connection)** as it is the most robust code-level fix without requiring complex DB infra changes (FDW).

### Step 1: Create `LegacyPostgresConnector`
Create a new connector `src/work_data_hub/io/connectors/legacy_postgres_connector.py` that:
- Uses `psycopg2` (or SQLAlchemy with `postgresql` dialect).
- Connects specifically to the `legacy` database.
- Implements the same interface as the old MySQL connector (fetch_data, execute).

### Step 2: Refactor Loaders
Update `company_mapping_loader.py`:
- Replace `MySqlDBManager` / `LegacyMySQLConnector` imports with `LegacyPostgresConnector`.
- **SQL Sanitization:** Replace all backticks `` ` `` with double quotes `"` or remove them.
- Update query logic to access tables via schema qualification (e.g., `SELECT * FROM enterprise.company_mapping` instead of `USE enterprise; SELECT ...`).

### Step 3: Update Configuration
- **`config/data_sources.yml`**: Change `source_type` from `legacy_mysql` to `legacy_postgres`.
- **`src/work_data_hub/config/settings.py`**: Add `WDH_LEGACY_DB_*` settings (mirroring `WDH_DATABASE_*` but for the legacy DB name).

### Step 4: Cleanup
- Delete `legacy_mysql_connector.py`.
- Remove `PyMySQL` from `pyproject.toml`.
- Remove `WDH_LEGACY_MYSQL_*` variables from `.env` / `.wdh_env`.

## 6. Actionable Tasks
1.  [ ] **Spike**: Create `LegacyPostgresConnector` and verify connection to `legacy` DB.
2.  [ ] **Refactor**: Update `company_mapping_loader.py` to use new connector and fix SQL syntax (schema qualification, quoting).
3.  [ ] **Config**: Update `data_sources.yml` and `settings.py`.
4.  [ ] **Verify**: Run `tests/integration` to ensure data extraction works correctly with the new adapter.