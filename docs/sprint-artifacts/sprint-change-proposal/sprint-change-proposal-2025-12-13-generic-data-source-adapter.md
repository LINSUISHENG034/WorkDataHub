# Sprint Change Proposal: Generic Data Source Adapter Architecture

**Date:** 2025-12-13
**Status:** Draft
**Triggered By:** Story 6.2-4 (Pre-load Reference Sync Service)
**Change Scope:** Moderate
**Priority:** High (Blocker for Epic 6.2 completion)

---

## 1. Issue Summary

### Problem Statement

Epic 6.2 Story 6.2-4 (Pre-load Reference Sync Service) implementation assumes Legacy data resides in a MySQL database, but the actual infrastructure has migrated Legacy data to a PostgreSQL database. The existing `LegacyMySQLConnector` uses the `pymysql` driver and cannot connect to PostgreSQL.

### Discovery Context

- **When:** 2025-12-12, during architecture review
- **How:** Code analysis revealed `LegacyMySQLConnector` uses `pymysql`, while infrastructure verification confirmed Legacy data is in PostgreSQL `legacy` database
- **Evidence:**
  - `legacy_mysql_connector.py:15` - `import pymysql`
  - `company_mapping_loader.py:244,261,277` - Uses `MySqlDBManager(database="enterprise/business")`
  - `data_sources.yml:194,214,233` - Configures `source_type: "legacy_mysql"`
  - Infrastructure: PostgreSQL `legacy` database with schemas `enterprise`, `business`, `mapping`

### Strategic Consideration

Rather than a point fix for the current scenario, this change proposes a **Generic Data Source Adapter Architecture** that:
- Treats external databases as **data sources**, not project dependencies
- Supports multiple database types (PostgreSQL, MySQL, Oracle, etc.)
- Enables configuration-driven adapter selection
- Follows Open/Closed Principle for future extensibility

---

## 2. Impact Analysis

### Epic Impact

| Epic | Status | Impact |
|------|--------|--------|
| Epic 6.2 | in-progress | Story 6.2-4 marked `done` but non-functional |
| Epic 6.2-5 | done | Needs compatibility verification |
| Epic 6.2-6 | backlog | No direct impact |
| Epic 7 | backlog | No direct impact |

### Story Impact

| Story | Current Status | Required Action |
|-------|----------------|-----------------|
| 6.2-4 Pre-load Reference Sync Service | done (broken) | Add Patch Story to implement generic adapter |
| 6.2-5 Hybrid Reference Service | done | Verify compatibility with new adapters |

### Artifact Conflicts

| Artifact | Impact | Action Required |
|----------|--------|-----------------|
| `legacy_mysql_connector.py` | High | Refactor to `MySQLSourceAdapter` |
| `company_mapping_loader.py` | Medium | Update to use generic adapter |
| `data_sources.yml` | Medium | Update `source_type` configuration |
| `sync_service.py` | Low | Already adapter-agnostic (Protocol-based) |
| Architecture docs | Medium | Add AD for Generic Adapter Architecture |

### Technical Impact

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `io/connectors/` | New + Refactor | Create `PostgresSourceAdapter`, refactor `MySQLSourceAdapter` |
| `config/data_sources.yml` | Update | Change `source_type: "legacy_mysql"` → `"postgres"` |
| `config/settings.py` | Update | Add `WDH_LEGACY_*` environment variable support |
| Tests | New | Add adapter unit and integration tests |

---

## 3. Recommended Approach

### Selected Path: Route C - Generic Data Source Adapter Architecture

### Architecture Design

```
┌─────────────────────────────────────────────────────────┐
│                  ReferenceSyncService                    │
│              (Existing, adapter-agnostic)                │
└─────────────────────────┬───────────────────────────────┘
                          │ uses
                          ▼
┌─────────────────────────────────────────────────────────┐
│              DataSourceAdapter Protocol                  │
│  - fetch_data(table_config, state) -> DataFrame         │
│  - test_connection() -> bool (optional)                 │
└─────────────────────────┬───────────────────────────────┘
                          │ implements
          ┌───────────────┼───────────────┬───────────────┐
          ▼               ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
    │ Postgres │   │  MySQL   │   │  Config  │   │  Future  │
    │ Adapter  │   │ Adapter  │   │  File    │   │ Adapters │
    └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### Rationale

| Factor | Assessment |
|--------|------------|
| Open/Closed Principle | ✅ Open for extension (new adapters), closed for modification |
| Future Extensibility | ✅ Supports MySQL, PostgreSQL, Oracle, APIs, etc. |
| Configuration-Driven | ✅ No code changes needed to switch data sources |
| Preserves MySQL Capability | ✅ Retains ability to connect to MySQL if needed |
| Implementation Effort | Medium - Well-scoped changes |
| Risk Level | Low - Existing Protocol pattern already in place |

### Alternatives Considered

| Alternative | Reason Not Selected |
|-------------|---------------------|
| Route A: PostgresConnector only | Limited extensibility, doesn't preserve MySQL capability |
| Route B: Restore MySQL database | Adds infrastructure complexity, treats MySQL as dependency |

---

## 4. Detailed Change Proposals

### 4.1 Create PostgresSourceAdapter

**File:** `src/work_data_hub/io/connectors/postgres_source_adapter.py` (NEW)

**Description:** PostgreSQL adapter implementing `DataSourceAdapter` protocol for connecting to PostgreSQL databases as data sources.

**Key Features:**
- Uses `psycopg2` or SQLAlchemy with PostgreSQL dialect
- Supports schema-qualified table access (`schema.table`)
- Connection configuration via environment variables
- Implements same interface as existing adapters

### 4.2 Refactor MySQLSourceAdapter

**File:** `src/work_data_hub/io/connectors/legacy_mysql_connector.py` → `mysql_source_adapter.py`

**Changes:**
- Rename class to `MySQLSourceAdapter`
- Ensure consistent interface with `PostgresSourceAdapter`
- Retain all existing MySQL connection logic

**Rationale:** Preserve MySQL capability for environments that still use MySQL.

### 4.3 Create AdapterFactory

**File:** `src/work_data_hub/io/connectors/adapter_factory.py` (NEW)

**Description:** Factory class that creates appropriate adapter based on `source_type` configuration.

```python
class AdapterFactory:
    @staticmethod
    def create(source_type: str, **kwargs) -> DataSourceAdapter:
        if source_type == "postgres":
            return PostgresSourceAdapter(**kwargs)
        elif source_type == "mysql" or source_type == "legacy_mysql":
            return MySQLSourceAdapter(**kwargs)
        elif source_type == "config_file":
            return ConfigFileAdapter(**kwargs)
        else:
            raise ValueError(f"Unknown source_type: {source_type}")
```

### 4.4 Update Configuration

**File:** `config/data_sources.yml`

**OLD:**
```yaml
reference_sync:
  tables:
    - name: "年金计划"
      source_type: "legacy_mysql"
      source_config:
        table: "annuity_plan"
```

**NEW:**
```yaml
reference_sync:
  tables:
    - name: "年金计划"
      source_type: "postgres"
      source_config:
        connection_env_prefix: "WDH_LEGACY"  # → WDH_LEGACY_HOST, WDH_LEGACY_PORT, etc.
        schema: "enterprise"
        table: "annuity_plan"
```

**Rationale:** Configuration-driven adapter selection enables environment-specific data source configuration.

### 4.5 Update company_mapping_loader.py

**File:** `src/work_data_hub/io/loader/company_mapping_loader.py`

**Changes:**
- Replace `MySqlDBManager` with generic adapter
- Update SQL syntax (backticks → standard SQL or double quotes)
- Use schema-qualified table names (`enterprise.table_name`)

### 4.6 Environment Configuration

**File:** `.wdh_env` or environment variables

**New Variables:**
```bash
# Legacy PostgreSQL Database (for reference sync)
WDH_LEGACY_HOST=localhost
WDH_LEGACY_PORT=5432
WDH_LEGACY_DATABASE=legacy
WDH_LEGACY_USER=postgres
WDH_LEGACY_PASSWORD=***
```

---

## 5. Implementation Handoff

### Change Scope Classification: **Moderate**

This change requires:
- Code implementation (new adapters, factory, refactoring)
- Configuration updates
- Architecture documentation
- Testing

### Handoff Plan

| Role | Responsibility | Deliverables |
|------|----------------|--------------|
| SM (Scrum Master) | Create Patch Story, update sprint-status.yaml | Story file, status update |
| Developer | Implement generic adapter architecture | Code, tests |
| Architect | Review design, document AD | AD-0XX document |
| QA | Verify reference sync functionality | Test results |

### Proposed Patch Story

**Story ID:** 6.2-P1 (Patch for 6.2-4)
**Title:** Generic Data Source Adapter Architecture

**Acceptance Criteria:**
1. `PostgresSourceAdapter` connects to PostgreSQL `legacy` database
2. `MySQLSourceAdapter` retains MySQL connection capability
3. `AdapterFactory` creates adapters based on `source_type` configuration
4. `data_sources.yml` updated to use `source_type: "postgres"`
5. Reference sync successfully fetches data from PostgreSQL
6. All existing tests pass
7. New adapter tests added

### Success Criteria

1. Reference sync service successfully connects to PostgreSQL `legacy` database
2. Data fetched matches expected schema and content
3. Configuration change (postgres ↔ mysql) works without code changes
4. No regression in existing functionality

---

## 6. Approval

- [x] **User Approval:** Approved by Link on 2025-12-13
- [ ] **Architecture Review:** Pending
- [ ] **Implementation Started:** Pending

---

## Appendix: Reference Documents

- `docs/specific/optimized-requirements/20251212_legacy-mysql-architecture-mismatch.md`
- `docs/epics/epic-6-company-enrichment-service.md`
- `docs/sprint-artifacts/sprint-status.yaml`
- `src/work_data_hub/io/connectors/legacy_mysql_connector.py`
- `config/data_sources.yml`
