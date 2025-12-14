# Reference Sync Incremental State Persistence Gap

**Status:** Resolved
**Related Story:** Story 6.2-4 (Pre-load Reference Sync Service)
**Date:** 2025-12-14

## Resolution

**Fixed in Story 6.2-p4 (2025-12-14):**
1.  **Schema:** Added `system.sync_state` table via migration `20251214_000001`.
2.  **Repository:** Implemented `SyncStateRepository` to manage state persistence.
3.  **Orchestration:** Updated `reference_sync_op` to:
    -   Load previous state from DB before sync.
    -   Persist new state (high-water mark) after successful sync.
    -   Support `force_full_sync` and `persist_state` flags.
4.  **Verification:** Validated with unit tests (`test_sync_state_repository.py`) and integration tests (`test_reference_sync_integration.py`).

## Context

In Story 6.2-4, the `ReferenceSyncService` and `LegacyMySQLConnector` were implemented to support incremental synchronization using a `last_synced_at` timestamp. The connector logic correctly constructs SQL queries using this parameter if provided:

```python
# src/work_data_hub/io/connectors/legacy_mysql_connector.py

if source_config.incremental:
    last_synced_at = None
    if state:
        last_synced_at = state.get("last_synced_at")
    
    if last_synced_at is None:
        # Fallback to full load
    else:
        # Use incremental WHERE clause
```

## The Problem

While the *consumption* logic exists, the **persistence and retrieval** mechanism for this state is missing in the orchestration layer.

1.  **No State Storage:** There is no dedicated database table or file storage to record the `last_synced_at` timestamp after a successful sync.
2.  **Dagster Op Limitation:** The `reference_sync_op` currently accepts an optional `state` from config, but does not automatically fetch the previous run's high-water mark.
3.  **Result:** The system defaults to full synchronization on every run, failing to utilize the incremental capabilities designed in the connector.

## Technical Gap Analysis

### Missing Components

1.  **State Repository:** A distinct component responsible for:
    *   `get_last_sync_time(job_name: str, table_name: str) -> Optional[datetime]`
    *   `update_last_sync_time(job_name: str, table_name: str, sync_time: datetime)`

2.  **Database Schema:** A `system.sync_state` table is required.
    *   Columns: `job_name` (PK), `table_name` (PK), `last_synced_at`, `updated_at`.

3.  **Orchestration Integration:** `reference_sync_op` needs to:
    *   Instantiate the repository.
    *   Fetch the state *before* calling `sync_service.sync_all`.
    *   Update the state *after* successful execution (or per table).

## Proposed Solution

### 1. Database Schema
Create a new migration for the state table:

```sql
CREATE TABLE system.sync_state (
    job_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    last_synced_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (job_name, table_name)
);
```

### 2. Repository Implementation
Implement `SyncStateRepository` in `src/work_data_hub/io/repositories/sync_state_repository.py`.

### 3. Service/Op Update
Modify `reference_sync_op` to wire these together:

```python
# Pseudo-code for updated Op
state_repo = SyncStateRepository(conn)
current_states = state_repo.get_all_states(job_name="reference_sync")

results = sync_service.sync_all(..., state=current_states)

for result in results:
    if result.success:
        state_repo.update_state(
            job_name="reference_sync", 
            table=result.table, 
            timestamp=sync_start_time
        )
```

## Impact Assessment

-   **Performance:** Without this fix, tables like `organization` or large plan tables will always be fully reloaded, putting unnecessary load on the legacy database and the network.
-   **Data Quality:** Incremental syncs are generally safer as they touch fewer records, though full reloads ensure eventual consistency. The hybrid strategy relies on efficient pre-loading.

## Next Steps

1.  Create a fix task/story (e.g., `Story 6.2-p4`).
2.  Implement the `system.sync_state` table.
3.  Implement the repository and integrate into the Dagster Op.
