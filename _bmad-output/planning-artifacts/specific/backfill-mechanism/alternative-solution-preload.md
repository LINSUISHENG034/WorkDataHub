# Alternative Solution: Reference Table Pre-Loading

**Created:** 2025-12-11
**Status:** Alternative Option (Option D)
**Related:** [Problem Analysis](./problem-analysis.md) | [Recommended Solution](./recommended-solution.md)

---

## 1. Executive Summary

This document describes the **Reference Table Pre-Loading** approach as an alternative solution to handle foreign key constraints. Instead of dynamically backfilling reference tables during fact data processing, this approach ensures all reference data exists **before** the pipeline runs.

**Core Concept:**
```
Reference Data Sync (Independent Job)
    ↓
Reference Tables Populated
    ↓
Fact Data Processing (No Backfill Needed)
    ↓
FK Constraints Satisfied
```

---

## 2. Design Philosophy

### 2.1 Separation of Concerns

| Responsibility | Owner |
|---------------|-------|
| Reference Data Management | Dedicated sync job |
| Reference Data Quality | Validation pipeline |
| Fact Data Processing | Domain pipeline |
| FK Constraint Satisfaction | Pre-condition (not runtime) |

### 2.2 Data Flow Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    Reference Data Sources                        │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  Legacy MySQL   │  Config Files   │  External APIs / MDM        │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
         ▼                 ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              Reference Data Sync Job (Scheduled)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │年金计划   │  │组合计划   │  │产品线    │  │组织架构   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Reference Tables                   │
│  (Pre-populated with all known reference values)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Fact Data Processing Pipeline                       │
│  (No backfill needed - FK values already exist)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Reference Data Sources

### 3.1 Source Types

| Source Type | Description | Use Case |
|-------------|-------------|----------|
| Legacy MySQL | Existing reference tables in legacy system | 年金计划, 组合计划, 组织架构 |
| Config Files | YAML/JSON files with static reference data | 产品线, 业务类型 |
| External APIs | Master Data Management (MDM) systems | Company master, Industry codes |
| Manual Entry | Admin UI for ad-hoc additions | Exception handling |

### 3.2 Source Configuration

```yaml
# config/reference_sources.yml

reference_tables:
  年金计划:
    source_type: "legacy_mysql"
    source_config:
      database: "annuity_hub"
      table: "年金计划"
      key_column: "年金计划号"
    sync_strategy: "full_replace"  # full_replace | incremental | merge
    schedule: "0 2 * * *"  # Daily at 2 AM

  组合计划:
    source_type: "legacy_mysql"
    source_config:
      database: "annuity_hub"
      table: "组合计划"
      key_column: "组合代码"
    sync_strategy: "incremental"
    schedule: "0 2 * * *"
    depends_on: ["年金计划"]  # Sync after 年金计划

  产品线:
    source_type: "config_file"
    source_config:
      file_path: "config/reference_data/product_lines.yml"
      format: "yaml"
    sync_strategy: "full_replace"
    schedule: "on_change"  # Sync when file changes

  组织架构:
    source_type: "legacy_mysql"
    source_config:
      database: "enterprise"
      table: "组织架构"
      key_column: "机构代码"
    sync_strategy: "incremental"
    schedule: "0 3 * * *"  # Daily at 3 AM
```

### 3.3 Static Reference Data Example

```yaml
# config/reference_data/product_lines.yml

product_lines:
  - code: "PL001"
    name: "传统年金"
    category: "annuity"
    active: true

  - code: "PL002"
    name: "万能险"
    category: "universal"
    active: true

  - code: "PL003"
    name: "投连险"
    category: "unit_linked"
    active: true
```

---

## 4. Sync Service Design

### 4.1 Core Components

```python
# src/work_data_hub/infrastructure/reference_sync/service.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal
import pandas as pd
from sqlalchemy import Connection

@dataclass
class SyncResult:
    """Result of a reference table sync operation."""
    table_name: str
    source_type: str
    records_synced: int
    records_inserted: int
    records_updated: int
    records_deleted: int
    duration_ms: int
    success: bool
    errors: list[str]


class ReferenceDataSource(ABC):
    """Abstract base class for reference data sources."""

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """Fetch reference data from source."""
        pass

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> list[str]:
        """Validate fetched data, return list of errors."""
        pass


class LegacyMySQLSource(ReferenceDataSource):
    """Fetch reference data from legacy MySQL database."""

    def __init__(self, database: str, table: str, key_column: str):
        self.database = database
        self.table = table
        self.key_column = key_column

    def fetch(self) -> pd.DataFrame:
        """Fetch all records from legacy table."""
        from work_data_hub.io.connectors.mysql_connector import get_mysql_connection

        conn = get_mysql_connection(self.database)
        query = f"SELECT * FROM `{self.table}`"
        return pd.read_sql(query, conn)

    def validate(self, df: pd.DataFrame) -> list[str]:
        errors = []
        if self.key_column not in df.columns:
            errors.append(f"Key column '{self.key_column}' not found")
        if df[self.key_column].isna().any():
            errors.append(f"NULL values in key column '{self.key_column}'")
        if df[self.key_column].duplicated().any():
            errors.append(f"Duplicate values in key column '{self.key_column}'")
        return errors


class ConfigFileSource(ReferenceDataSource):
    """Fetch reference data from config file."""

    def __init__(self, file_path: str, format: str = "yaml"):
        self.file_path = file_path
        self.format = format

    def fetch(self) -> pd.DataFrame:
        import yaml
        import json

        with open(self.file_path) as f:
            if self.format == "yaml":
                data = yaml.safe_load(f)
            else:
                data = json.load(f)

        # Assume data is a dict with a single key containing list of records
        key = list(data.keys())[0]
        return pd.DataFrame(data[key])

    def validate(self, df: pd.DataFrame) -> list[str]:
        errors = []
        if df.empty:
            errors.append("Config file contains no records")
        return errors


class ReferenceSyncService:
    """
    Service for synchronizing reference tables from various sources.
    """

    def __init__(self, target_schema: str = "business"):
        self.target_schema = target_schema
        self.sources: dict[str, ReferenceDataSource] = {}

    def register_source(
        self,
        table_name: str,
        source: ReferenceDataSource
    ) -> None:
        """Register a data source for a reference table."""
        self.sources[table_name] = source

    def sync_table(
        self,
        table_name: str,
        strategy: Literal["full_replace", "incremental", "merge"],
        conn: Connection
    ) -> SyncResult:
        """
        Sync a single reference table from its source.
        """
        import time
        start_time = time.time()

        source = self.sources.get(table_name)
        if not source:
            return SyncResult(
                table_name=table_name,
                source_type="unknown",
                records_synced=0,
                records_inserted=0,
                records_updated=0,
                records_deleted=0,
                duration_ms=0,
                success=False,
                errors=[f"No source registered for table: {table_name}"]
            )

        try:
            # Fetch data from source
            df = source.fetch()

            # Validate data
            errors = source.validate(df)
            if errors:
                return SyncResult(
                    table_name=table_name,
                    source_type=type(source).__name__,
                    records_synced=0,
                    records_inserted=0,
                    records_updated=0,
                    records_deleted=0,
                    duration_ms=int((time.time() - start_time) * 1000),
                    success=False,
                    errors=errors
                )

            # Apply sync strategy
            if strategy == "full_replace":
                result = self._full_replace(table_name, df, conn)
            elif strategy == "incremental":
                result = self._incremental_sync(table_name, df, conn)
            else:  # merge
                result = self._merge_sync(table_name, df, conn)

            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        except Exception as e:
            return SyncResult(
                table_name=table_name,
                source_type=type(source).__name__,
                records_synced=0,
                records_inserted=0,
                records_updated=0,
                records_deleted=0,
                duration_ms=int((time.time() - start_time) * 1000),
                success=False,
                errors=[str(e)]
            )

    def _full_replace(
        self,
        table_name: str,
        df: pd.DataFrame,
        conn: Connection
    ) -> SyncResult:
        """Replace all records in target table."""
        from sqlalchemy import text

        # Truncate existing data
        conn.execute(text(f'TRUNCATE TABLE "{self.target_schema}"."{table_name}" CASCADE'))

        # Insert new data
        df.to_sql(
            table_name,
            conn,
            schema=self.target_schema,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )

        return SyncResult(
            table_name=table_name,
            source_type="",
            records_synced=len(df),
            records_inserted=len(df),
            records_updated=0,
            records_deleted=0,  # Unknown due to truncate
            duration_ms=0,
            success=True,
            errors=[]
        )

    def _incremental_sync(
        self,
        table_name: str,
        df: pd.DataFrame,
        conn: Connection
    ) -> SyncResult:
        """Add new records only, don't update existing."""
        # Implementation: INSERT ... ON CONFLICT DO NOTHING
        ...

    def _merge_sync(
        self,
        table_name: str,
        df: pd.DataFrame,
        conn: Connection
    ) -> SyncResult:
        """Upsert: insert new, update existing."""
        # Implementation: INSERT ... ON CONFLICT DO UPDATE
        ...
```

### 4.2 Dagster Job for Reference Sync

```python
# src/work_data_hub/orchestration/reference_sync_job.py

from dagster import job, op, schedule, OpExecutionContext
import yaml

from work_data_hub.infrastructure.reference_sync.service import (
    ReferenceSyncService,
    LegacyMySQLSource,
    ConfigFileSource,
    SyncResult
)

def load_reference_config() -> dict:
    """Load reference sources configuration."""
    with open("config/reference_sources.yml") as f:
        return yaml.safe_load(f)


@op(description="Sync a single reference table")
def sync_reference_table_op(
    context: OpExecutionContext,
    table_name: str
) -> SyncResult:
    """Sync a reference table from its configured source."""
    config = load_reference_config()
    table_config = config["reference_tables"].get(table_name)

    if not table_config:
        raise ValueError(f"No configuration for table: {table_name}")

    # Create appropriate source
    source_type = table_config["source_type"]
    source_config = table_config["source_config"]

    if source_type == "legacy_mysql":
        source = LegacyMySQLSource(**source_config)
    elif source_type == "config_file":
        source = ConfigFileSource(**source_config)
    else:
        raise ValueError(f"Unknown source type: {source_type}")

    # Create service and sync
    service = ReferenceSyncService()
    service.register_source(table_name, source)

    conn = get_database_connection()
    result = service.sync_table(
        table_name,
        table_config["sync_strategy"],
        conn
    )

    context.log.info(f"Sync result for {table_name}: {result}")
    return result


@op(description="Sync all reference tables in dependency order")
def sync_all_references_op(context: OpExecutionContext) -> list[SyncResult]:
    """Sync all configured reference tables."""
    config = load_reference_config()
    tables = config["reference_tables"]

    # Topological sort by depends_on
    sorted_tables = topological_sort_tables(tables)

    results = []
    for table_name in sorted_tables:
        result = sync_reference_table_op(context, table_name)
        results.append(result)

        if not result.success:
            context.log.error(f"Failed to sync {table_name}: {result.errors}")
            # Continue or abort based on configuration

    return results


@job(description="Sync all reference tables from sources")
def reference_sync_job():
    """
    Job to synchronize all reference tables.

    Run this job before fact data processing to ensure
    all FK reference values exist.
    """
    sync_all_references_op()


@schedule(
    job=reference_sync_job,
    cron_schedule="0 1 * * *",  # Daily at 1 AM
    execution_timezone="Asia/Shanghai"
)
def daily_reference_sync_schedule(context):
    """Daily schedule for reference data sync."""
    return {}
```

---

## 5. Pre-Condition Validation

### 5.1 FK Validation Before Processing

```python
# src/work_data_hub/orchestration/ops.py

@op(description="Validate FK values exist in reference tables")
def validate_fk_preconditions_op(
    context: OpExecutionContext,
    processed_data: pd.DataFrame,
    domain: str
) -> pd.DataFrame:
    """
    Validate that all FK values in fact data exist in reference tables.

    This is a PRE-CONDITION check, not a backfill operation.
    If validation fails, the pipeline should abort with clear error messages.
    """
    fk_configs = load_foreign_key_configs(domain)
    conn = get_database_connection()

    missing_refs = []

    for config in fk_configs:
        # Get unique FK values from fact data
        fk_values = processed_data[config.source_column].dropna().unique()

        # Check which values exist in reference table
        existing = get_existing_keys(
            conn,
            config.target_table,
            config.target_key,
            fk_values
        )

        missing = set(fk_values) - set(existing)

        if missing:
            missing_refs.append({
                "fk_name": config.name,
                "target_table": config.target_table,
                "missing_count": len(missing),
                "missing_sample": list(missing)[:10]  # First 10 for logging
            })

    if missing_refs:
        # Log detailed error
        context.log.error(
            "FK precondition validation failed",
            missing_references=missing_refs
        )

        # Option 1: Raise exception to abort pipeline
        raise FKPreconditionError(
            f"Missing FK references in {len(missing_refs)} tables. "
            f"Run reference_sync_job first or add missing records manually."
        )

        # Option 2: Return filtered data (exclude rows with missing FKs)
        # return filter_rows_with_missing_fks(processed_data, missing_refs)

    context.log.info("FK precondition validation passed")
    return processed_data
```

### 5.2 Pipeline with Pre-Condition Check

```python
@job(description="Process domain data with FK pre-condition validation")
def process_domain_with_precheck_job():
    """
    Domain processing job that validates FK preconditions.

    Pipeline flow:
    1. Discover and read files
    2. Process data
    3. Validate FK preconditions (FAIL if missing refs)
    4. Load fact data
    """
    files = discover_files_op()
    raw_data = read_excel_op(files)
    processed_data = process_domain_op(raw_data)

    # Pre-condition check (no backfill)
    validated_data = validate_fk_preconditions_op(processed_data)

    # Load only if validation passes
    load_result = load_op(validated_data)

    return load_result
```

---

## 6. Handling New/Unknown FK Values

### 6.1 The Core Challenge

Pre-loading cannot handle FK values that:
- Don't exist in any source system
- Are newly created in the current data batch
- Result from data entry errors

### 6.2 Mitigation Strategies

#### Strategy A: Quarantine Unknown Values

```python
@op
def quarantine_unknown_fks_op(
    context: OpExecutionContext,
    processed_data: pd.DataFrame,
    domain: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Separate rows with unknown FK values into quarantine.

    Returns:
        - valid_data: Rows with all FKs resolved
        - quarantine_data: Rows with unknown FKs (for manual review)
    """
    fk_configs = load_foreign_key_configs(domain)

    # Identify rows with missing FKs
    mask = pd.Series(True, index=processed_data.index)

    for config in fk_configs:
        existing_keys = get_existing_keys(config.target_table, config.target_key)
        mask &= processed_data[config.source_column].isin(existing_keys)

    valid_data = processed_data[mask]
    quarantine_data = processed_data[~mask]

    if len(quarantine_data) > 0:
        # Export quarantine data for review
        export_quarantine(quarantine_data, domain)
        context.log.warning(
            f"Quarantined {len(quarantine_data)} rows with unknown FK values"
        )

    return valid_data, quarantine_data
```

#### Strategy B: Auto-Register Unknown Values

```python
@op
def auto_register_unknown_fks_op(
    context: OpExecutionContext,
    processed_data: pd.DataFrame,
    domain: str
) -> pd.DataFrame:
    """
    Automatically register unknown FK values as new reference records.

    This is essentially a hybrid approach combining pre-load with
    on-demand backfill for truly new values.
    """
    fk_configs = load_foreign_key_configs(domain)

    for config in fk_configs:
        if not config.allow_auto_register:
            continue

        # Find unknown values
        fk_values = processed_data[config.source_column].dropna().unique()
        existing = get_existing_keys(config.target_table, config.target_key)
        unknown = set(fk_values) - set(existing)

        if unknown:
            # Create minimal reference records
            new_records = pd.DataFrame({
                config.target_key: list(unknown),
                "auto_registered": True,
                "registered_at": datetime.now(),
                "source_domain": domain
            })

            insert_reference_records(config.target_table, new_records)

            context.log.info(
                f"Auto-registered {len(unknown)} new {config.target_table} records"
            )

    return processed_data
```

#### Strategy C: Notification and Manual Intervention

```python
@op
def notify_unknown_fks_op(
    context: OpExecutionContext,
    unknown_fks: dict[str, list]
) -> None:
    """
    Send notification about unknown FK values for manual resolution.
    """
    if not unknown_fks:
        return

    # Send email/Slack notification
    send_notification(
        channel="data-quality-alerts",
        message=f"Unknown FK values detected in pipeline run",
        details=unknown_fks,
        action_required="Add missing reference records before re-running"
    )

    # Create JIRA ticket (optional)
    create_data_quality_ticket(
        title="Missing Reference Data",
        description=format_unknown_fks_report(unknown_fks)
    )
```

---

## 7. Scheduling and Orchestration

### 7.1 Execution Order

```
┌─────────────────────────────────────────────────────────────────┐
│  1:00 AM - Reference Sync Job                                   │
│  ├── Sync 年金计划 from Legacy MySQL                            │
│  ├── Sync 组合计划 from Legacy MySQL (after 年金计划)           │
│  ├── Sync 产品线 from Config File                               │
│  └── Sync 组织架构 from Legacy MySQL                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2:00 AM - Reference Validation Job                             │
│  ├── Validate all reference tables populated                    │
│  ├── Check FK relationships between reference tables            │
│  └── Generate reference data quality report                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3:00 AM - Fact Data Processing Jobs                            │
│  ├── annuity_performance pipeline                               │
│  ├── annuity_income pipeline                                    │
│  └── other domain pipelines                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Dagster Sensor for Dependency

```python
@sensor(
    job=process_domain_job,
    minimum_interval_seconds=300
)
def reference_sync_complete_sensor(context):
    """
    Trigger fact processing only after reference sync completes.
    """
    # Check if reference sync job completed successfully today
    last_sync = get_last_successful_run("reference_sync_job")

    if last_sync and last_sync.date() == date.today():
        # Reference data is fresh, trigger fact processing
        return RunRequest(run_key=f"fact_processing_{date.today()}")

    return SkipReason("Waiting for reference_sync_job to complete")
```

---

## 8. Comparison with Recommended Solution

| Aspect | Pre-Load (Option D) | Generic Backfill (Option B) |
|--------|--------------------|-----------------------------|
| **New FK Values** | ❌ Fails or quarantines | ✅ Auto-creates |
| **Data Freshness** | ⚠️ Depends on sync schedule | ✅ Real-time |
| **Complexity** | Medium (separate job) | Medium (integrated) |
| **Reference Data Quality** | ✅ Can validate before use | ⚠️ Minimal records only |
| **Audit Trail** | ✅ Clear sync history | ⚠️ Mixed with fact processing |
| **Separation of Concerns** | ✅ Clear boundaries | ⚠️ Coupled with fact processing |
| **Recovery from Failure** | ✅ Re-run sync job | ⚠️ Re-run entire pipeline |

### 8.1 When to Choose Pre-Load

- Reference data comes from authoritative source (MDM, legacy system)
- Reference data changes infrequently
- Data quality validation is important before use
- Clear audit trail for reference data changes is required
- Organization has established data governance processes

### 8.2 When to Choose Generic Backfill

- Reference data is derived from fact data
- New FK values are common and expected
- Real-time processing is required
- Simpler operational model preferred
- No authoritative source for reference data

---

## 9. Hybrid Approach

For maximum flexibility, consider combining both approaches:

```python
@job
def hybrid_reference_management_job():
    """
    Hybrid approach:
    1. Pre-load known reference data from authoritative sources
    2. Validate FK preconditions
    3. Auto-register truly new values (with flag)
    4. Process fact data
    """
    # Step 1: Sync from authoritative sources
    sync_results = sync_all_references_op()

    # Step 2: Read and process fact data
    processed_data = process_domain_op(read_excel_op(discover_files_op()))

    # Step 3: Validate and identify unknown FKs
    validated_data, unknown_fks = validate_and_identify_unknown_op(processed_data)

    # Step 4: Auto-register unknown values (if allowed)
    if unknown_fks:
        auto_register_unknown_fks_op(unknown_fks)

    # Step 5: Load fact data
    load_op(validated_data)
```

---

## 10. Implementation Checklist

- [ ] Create `reference_sources.yml` configuration schema
- [ ] Implement `ReferenceDataSource` abstract class
- [ ] Implement `LegacyMySQLSource` for MySQL sync
- [ ] Implement `ConfigFileSource` for static data
- [ ] Create `ReferenceSyncService` with sync strategies
- [ ] Create `reference_sync_job` Dagster job
- [ ] Create daily schedule for reference sync
- [ ] Implement FK precondition validation op
- [ ] Implement quarantine mechanism for unknown FKs
- [ ] Add monitoring and alerting for sync failures
- [ ] Document operational procedures

---

## 11. References

- [Problem Analysis](./problem-analysis.md)
- [Recommended Solution (Option B)](./recommended-solution.md)
- [Legacy MySQL Operations](../../../legacy/annuity_hub/database_operations/mysql_ops.py)
- [Data Sources Config](../../../config/data_sources.yml)
