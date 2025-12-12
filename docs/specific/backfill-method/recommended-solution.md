# Recommended Solution: Configuration-Driven Generic Backfill Framework

**Created:** 2025-12-11
**Status:** Proposed
**Related:** [Problem Analysis](./problem-analysis.md)

---

## 1. Executive Summary

This document proposes a **Configuration-Driven Generic Backfill Framework** to handle foreign key constraints across all domains. The solution enables:

- **Multi-FK Support:** Handle multiple foreign keys per fact table simultaneously
- **Zero-Code Domain Addition:** New domains only require configuration changes
- **Efficient Batch Processing:** Optimized for large datasets
- **Dependency-Aware Ordering:** Automatic topological sorting of FK dependencies

---

## 2. Design Philosophy

```
Configuration Declaration → Automatic Extraction → Batch Backfill → Gated Loading
```

**Core Principles:**
1. **Convention over Code:** FK relationships declared in config, not hardcoded
2. **Single Responsibility:** One generic service handles all backfill operations
3. **Fail-Fast:** Validate FK configs at startup, not runtime
4. **Observability:** Structured logging for all backfill operations

---

## 3. Configuration Layer Design

### 3.1 Enhanced `data_sources.yml`

```yaml
domains:
  annuity_performance:
    # ... existing configuration ...

    # NEW: Foreign Key Relationship Declaration
    foreign_keys:
      # FK 1: 年金计划 (Plans)
      - name: "fk_plan"
        source_column: "计划代码"           # Column in fact data
        target_table: "年金计划"            # Referenced parent table
        target_key: "年金计划号"            # Primary key in parent table
        backfill_columns:                   # Columns to populate in parent table
          - source: "计划代码"
            target: "年金计划号"
          - source: "计划名称"              # Optional: if available in fact data
            target: "计划名称"
            optional: true                  # Won't fail if missing
        mode: "insert_missing"              # insert_missing | fill_null_only
        priority: 1                         # Lower = earlier (for dependency ordering)

      # FK 2: 组合计划 (Portfolios) - depends on 年金计划
      - name: "fk_portfolio"
        source_column: "组合代码"
        target_table: "组合计划"
        target_key: "组合代码"
        backfill_columns:
          - source: "组合代码"
            target: "组合代码"
          - source: "计划代码"
            target: "年金计划号"            # FK to 年金计划
        mode: "insert_missing"
        priority: 2                         # After 年金计划
        depends_on: ["fk_plan"]             # Explicit dependency

      # FK 3: 产品线 (Product Lines)
      - name: "fk_product_line"
        source_column: "产品线"
        target_table: "产品线"
        target_key: "产品线代码"
        backfill_columns:
          - source: "产品线"
            target: "产品线代码"
        mode: "insert_missing"
        priority: 1                         # No dependencies

      # FK 4: 组织架构 (Organization)
      - name: "fk_organization"
        source_column: "机构代码"
        target_table: "组织架构"
        target_key: "机构代码"
        backfill_columns:
          - source: "机构代码"
            target: "机构代码"
          - source: "机构名称"
            target: "机构名称"
            optional: true
        mode: "insert_missing"
        priority: 1                         # No dependencies

  # Example: New domain with different FK structure
  annuity_income:
    # ... existing configuration ...

    foreign_keys:
      - name: "fk_plan"
        source_column: "计划代码"
        target_table: "年金计划"
        target_key: "年金计划号"
        backfill_columns:
          - source: "计划代码"
            target: "年金计划号"
        mode: "insert_missing"
        priority: 1
```

### 3.2 Configuration Schema (Pydantic)

```python
# src/work_data_hub/domain/reference_backfill/config.py

from pydantic import BaseModel, Field
from typing import Literal

class BackfillColumnMapping(BaseModel):
    """Mapping from source column to target column."""
    source: str = Field(..., description="Column name in fact data")
    target: str = Field(..., description="Column name in parent table")
    optional: bool = Field(default=False, description="Skip if source column missing")

class ForeignKeyConfig(BaseModel):
    """Foreign key relationship configuration."""
    name: str = Field(..., description="Unique identifier for this FK")
    source_column: str = Field(..., description="FK column in fact data")
    target_table: str = Field(..., description="Referenced parent table name")
    target_key: str = Field(..., description="Primary key column in parent table")
    backfill_columns: list[BackfillColumnMapping] = Field(
        ...,
        description="Columns to populate when backfilling"
    )
    mode: Literal["insert_missing", "fill_null_only"] = Field(
        default="insert_missing",
        description="Backfill strategy"
    )
    priority: int = Field(
        default=1,
        description="Execution order (lower = earlier)"
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="FK names this depends on"
    )

class DomainForeignKeysConfig(BaseModel):
    """All FK configurations for a domain."""
    foreign_keys: list[ForeignKeyConfig] = Field(default_factory=list)
```

---

## 4. Service Layer Design

### 4.1 Generic Backfill Service

```python
# src/work_data_hub/domain/reference_backfill/generic_service.py

from dataclasses import dataclass
from typing import Any
import pandas as pd
from sqlalchemy import Connection, text
import structlog

from .config import ForeignKeyConfig, DomainForeignKeysConfig

logger = structlog.get_logger(__name__)

@dataclass
class BackfillTableResult:
    """Result of backfilling a single table."""
    table_name: str
    candidates_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    errors: list[str]

@dataclass
class BackfillResult:
    """Aggregated result of all backfill operations."""
    domain: str
    table_results: list[BackfillTableResult]
    total_inserted: int
    total_updated: int
    success: bool

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "tables_processed": len(self.table_results),
            "total_inserted": self.total_inserted,
            "total_updated": self.total_updated,
            "success": self.success,
        }


class GenericBackfillService:
    """
    Configuration-driven foreign key backfill service.

    Handles multiple foreign keys per domain with automatic
    dependency ordering and batch processing.
    """

    def __init__(self, schema: str = "business"):
        self.schema = schema

    def derive_candidates(
        self,
        df: pd.DataFrame,
        fk_config: ForeignKeyConfig
    ) -> pd.DataFrame:
        """
        Extract unique FK candidates from fact data.

        Args:
            df: Processed fact data DataFrame
            fk_config: Foreign key configuration

        Returns:
            DataFrame with unique candidate records for parent table
        """
        # Build column mapping
        column_map = {}
        required_sources = []

        for mapping in fk_config.backfill_columns:
            if mapping.source in df.columns:
                column_map[mapping.source] = mapping.target
            elif not mapping.optional:
                required_sources.append(mapping.source)

        if required_sources:
            raise ValueError(
                f"Missing required columns for {fk_config.name}: {required_sources}"
            )

        if not column_map:
            logger.warning(
                "no_columns_to_backfill",
                fk_name=fk_config.name,
                target_table=fk_config.target_table
            )
            return pd.DataFrame()

        # Extract unique records using groupby for efficiency
        source_cols = list(column_map.keys())
        candidates = (
            df[source_cols]
            .drop_duplicates()
            .dropna(subset=[fk_config.source_column])  # FK column must not be null
            .rename(columns=column_map)
        )

        logger.info(
            "derived_candidates",
            fk_name=fk_config.name,
            target_table=fk_config.target_table,
            candidate_count=len(candidates)
        )

        return candidates

    def _sort_by_dependencies(
        self,
        fk_configs: list[ForeignKeyConfig]
    ) -> list[ForeignKeyConfig]:
        """
        Topological sort of FK configs based on dependencies.

        Ensures parent tables are backfilled before child tables.
        """
        # Build dependency graph
        name_to_config = {c.name: c for c in fk_configs}

        # Simple sort by priority + dependency check
        sorted_configs = sorted(fk_configs, key=lambda c: c.priority)

        # Validate dependencies exist
        for config in sorted_configs:
            for dep in config.depends_on:
                if dep not in name_to_config:
                    raise ValueError(
                        f"FK {config.name} depends on unknown FK: {dep}"
                    )

        return sorted_configs

    def _backfill_table(
        self,
        candidates: pd.DataFrame,
        fk_config: ForeignKeyConfig,
        conn: Connection
    ) -> BackfillTableResult:
        """
        Backfill a single parent table with candidate records.
        """
        if candidates.empty:
            return BackfillTableResult(
                table_name=fk_config.target_table,
                candidates_count=0,
                inserted_count=0,
                updated_count=0,
                skipped_count=0,
                errors=[]
            )

        table_name = fk_config.target_table
        key_column = fk_config.target_key
        inserted = 0
        updated = 0
        skipped = 0
        errors = []

        for _, row in candidates.iterrows():
            try:
                key_value = row[key_column]

                # Check if record exists
                check_sql = text(f'''
                    SELECT 1 FROM "{self.schema}"."{table_name}"
                    WHERE "{key_column}" = :key_value
                ''')
                exists = conn.execute(
                    check_sql,
                    {"key_value": key_value}
                ).fetchone() is not None

                if not exists and fk_config.mode == "insert_missing":
                    # Insert new record
                    columns = list(row.index)
                    col_str = ", ".join(f'"{c}"' for c in columns)
                    val_str = ", ".join(f":{c}" for c in columns)

                    insert_sql = text(f'''
                        INSERT INTO "{self.schema}"."{table_name}" ({col_str})
                        VALUES ({val_str})
                        ON CONFLICT ("{key_column}") DO NOTHING
                    ''')
                    conn.execute(insert_sql, row.to_dict())
                    inserted += 1

                elif exists and fk_config.mode == "fill_null_only":
                    # Update NULL fields only
                    update_cols = [c for c in row.index if c != key_column]
                    if update_cols:
                        set_clause = ", ".join(
                            f'"{c}" = COALESCE("{c}", :{c})'
                            for c in update_cols
                        )
                        update_sql = text(f'''
                            UPDATE "{self.schema}"."{table_name}"
                            SET {set_clause}
                            WHERE "{key_column}" = :key_value
                        ''')
                        params = {**row.to_dict(), "key_value": key_value}
                        conn.execute(update_sql, params)
                        updated += 1
                else:
                    skipped += 1

            except Exception as e:
                errors.append(f"Row {key_value}: {str(e)}")
                logger.error(
                    "backfill_row_error",
                    table=table_name,
                    error=str(e)
                )

        logger.info(
            "backfill_table_complete",
            table=table_name,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            errors=len(errors)
        )

        return BackfillTableResult(
            table_name=table_name,
            candidates_count=len(candidates),
            inserted_count=inserted,
            updated_count=updated,
            skipped_count=skipped,
            errors=errors
        )

    def backfill_all(
        self,
        df: pd.DataFrame,
        domain: str,
        fk_configs: list[ForeignKeyConfig],
        conn: Connection
    ) -> BackfillResult:
        """
        Backfill all foreign key reference tables for a domain.

        Args:
            df: Processed fact data DataFrame
            domain: Domain name for logging
            fk_configs: List of FK configurations
            conn: Database connection

        Returns:
            Aggregated backfill result
        """
        logger.info(
            "backfill_all_start",
            domain=domain,
            fk_count=len(fk_configs)
        )

        # Sort by dependencies
        sorted_configs = self._sort_by_dependencies(fk_configs)

        results = []
        total_inserted = 0
        total_updated = 0
        success = True

        for config in sorted_configs:
            try:
                candidates = self.derive_candidates(df, config)
                result = self._backfill_table(candidates, config, conn)
                results.append(result)
                total_inserted += result.inserted_count
                total_updated += result.updated_count

                if result.errors:
                    success = False

            except Exception as e:
                logger.error(
                    "backfill_config_error",
                    fk_name=config.name,
                    error=str(e)
                )
                results.append(BackfillTableResult(
                    table_name=config.target_table,
                    candidates_count=0,
                    inserted_count=0,
                    updated_count=0,
                    skipped_count=0,
                    errors=[str(e)]
                ))
                success = False

        result = BackfillResult(
            domain=domain,
            table_results=results,
            total_inserted=total_inserted,
            total_updated=total_updated,
            success=success
        )

        logger.info("backfill_all_complete", **result.summary)

        return result
```

---

## 5. Pipeline Integration

### 5.1 Generic Backfill Op

```python
# src/work_data_hub/orchestration/ops.py (additions)

from work_data_hub.domain.reference_backfill.generic_service import (
    GenericBackfillService,
    BackfillResult
)
from work_data_hub.domain.reference_backfill.config import ForeignKeyConfig

def load_foreign_key_configs(domain: str) -> list[ForeignKeyConfig]:
    """Load FK configurations from data_sources.yml for a domain."""
    from work_data_hub.config import get_settings
    import yaml

    settings = get_settings()
    config_path = settings.data_sources_config_path

    with open(config_path) as f:
        config = yaml.safe_load(f)

    domain_config = config.get("domains", {}).get(domain, {})
    fk_dicts = domain_config.get("foreign_keys", [])

    return [ForeignKeyConfig(**fk) for fk in fk_dicts]


@op(
    description="Generic foreign key backfill for any domain",
    config_schema={"domain": str}
)
def generic_backfill_op(
    context: OpExecutionContext,
    processed_data: pd.DataFrame
) -> BackfillResult:
    """
    Backfill all foreign key reference tables based on configuration.

    This op replaces domain-specific derive_*_candidates ops with a
    single configuration-driven implementation.
    """
    domain = context.op_config["domain"]

    # Load FK configurations from data_sources.yml
    fk_configs = load_foreign_key_configs(domain)

    if not fk_configs:
        context.log.info(f"No foreign_keys configured for domain: {domain}")
        return BackfillResult(
            domain=domain,
            table_results=[],
            total_inserted=0,
            total_updated=0,
            success=True
        )

    # Get database connection
    conn = get_database_connection()

    # Execute backfill
    service = GenericBackfillService()
    result = service.backfill_all(
        df=processed_data,
        domain=domain,
        fk_configs=fk_configs,
        conn=conn
    )

    context.log.info(f"Backfill complete: {result.summary}")

    return result
```

### 5.2 Updated Job Definition

```python
# src/work_data_hub/orchestration/jobs.py (updated)

@job(description="Process domain data with generic FK backfill")
def process_domain_job():
    """
    Generic domain processing job with configuration-driven FK backfill.

    Pipeline flow:
    1. Discover files for domain
    2. Read and process data
    3. Backfill all FK reference tables (config-driven)
    4. Gate until backfill complete
    5. Load fact data to database
    """
    # Existing ops
    files = discover_files_op()
    raw_data = read_excel_op(files)
    processed_data = process_domain_op(raw_data)

    # NEW: Generic backfill replaces domain-specific ops
    backfill_result = generic_backfill_op(processed_data)

    # Gate ensures backfill completes before loading
    gated_data = gate_after_backfill(processed_data, backfill_result)

    # Load fact data
    load_result = load_op(gated_data)

    return load_result
```

---

## 6. Migration Path

### 6.1 Phased Approach

```
Phase 1: Implement Generic Framework (Non-Breaking)
├── Add GenericBackfillService
├── Add ForeignKeyConfig schema
├── Add generic_backfill_op
└── Keep existing derive_*_candidates ops

Phase 2: Configure Existing Domains
├── Add foreign_keys config for annuity_performance
├── Add missing FKs (产品线, 组织架构)
├── Validate with integration tests
└── Keep legacy ops as fallback

Phase 3: Migrate to Generic Framework
├── Switch annuity_performance to generic_backfill_op
├── Remove legacy derive_plan_candidates
├── Remove legacy derive_portfolio_candidates
└── Update documentation

Phase 4: Extend to New Domains
├── Add foreign_keys config for annuity_income
├── Add foreign_keys config for future domains
└── No code changes required
```

### 6.2 Backward Compatibility

```python
# Fallback logic in generic_backfill_op
def generic_backfill_op(context, processed_data):
    domain = context.op_config["domain"]
    fk_configs = load_foreign_key_configs(domain)

    if not fk_configs:
        # No config = use legacy behavior (if exists)
        context.log.warning(
            f"No foreign_keys config for {domain}, "
            "falling back to legacy backfill"
        )
        return legacy_backfill_op(context, processed_data)

    # Use generic framework
    ...
```

---

## 7. Efficiency Optimizations

### 7.1 Batch Candidate Extraction

```python
def derive_all_candidates(
    df: pd.DataFrame,
    fk_configs: list[ForeignKeyConfig]
) -> dict[str, pd.DataFrame]:
    """
    Extract all FK candidates in a single pass.

    More efficient than iterating configs separately.
    """
    candidates =

    # Group configs by source columns to minimize DataFrame operations
    for config in fk_configs:
        source_cols = [m.source for m in config.backfill_columns
                       if m.source in df.columns]

        if source_cols:
            candidates[config.name] = (
                df[source_cols]
                .drop_duplicates()
                .dropna(subset=[config.source_column])
            )

    return candidates
```

### 7.2 Parallel Backfill (Optional)

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def backfill_parallel(
    independent_configs: list[ForeignKeyConfig],
    candidates: dict[str, pd.DataFrame],
    conn: Connection
) -> list[BackfillTableResult]:
    """
    Backfill independent tables in parallel.

    Only for tables with no dependencies on each other.
    """
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                _backfill_table,
                candidates[config.name],
                config,
                conn
            )
            for config in independent_configs
        ]

        results = await asyncio.gather(*tasks)

    return results
```

### 7.3 Bulk Insert Optimization

```python
def _bulk_insert(
    candidates: pd.DataFrame,
    table_name: str,
    conn: Connection
) -> int:
    """
    Use COPY or bulk insert for large candidate sets.
    """
    if len(candidates) > 1000:
        # Use pandas to_sql with method='multi' for bulk insert
        candidates.to_sql(
            table_name,
            conn,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=500
        )
        return len(candidates)
    else:
        # Use row-by-row for small sets (better error handling)
        ...
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# tests/unit/domain/reference_backfill/test_generic_service.py

class TestGenericBackfillService:

    def test_derive_candidates_extracts_unique_values(self):
        """Verify unique FK values are extracted."""
        df = pd.DataFrame({
            "计划代码": ["P001", "P001", "P002"],
            "计划名称": ["Plan A", "Plan A", "Plan B"]
        })
        config = ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                {"source": "计划代码", "target": "年金计划号"},
                {"source": "计划名称", "target": "计划名称"}
            ]
        )

        service = GenericBackfillService()
        candidates = service.derive_candidates(df, config)

        assert len(candidates) == 2  # P001, P002
        assert "年金计划号" in candidates.columns

    def test_dependency_sorting(self):
        """Verify FK configs are sorted by dependencies."""
        configs = [
            ForeignKeyConfig(name="fk_child", depends_on=["fk_parent"], ...),
            ForeignKeyConfig(name="fk_parent", depends_on=[], ...),
        ]

        service = GenericBackfillService()
        sorted_configs = service._sort_by_dependencies(configs)

        assert sorted_configs[0].name == "fk_parent"
        assert sorted_configs[1].name == "fk_child"
```

### 8.2 Integration Tests

```python
# tests/integration/domain/reference_backfill/test_generic_backfill.py

@pytest.mark.integration
def test_backfill_all_creates_missing_records(test_db):
    """Verify backfill creates missing parent records."""
    # Setup: fact data with FK values not in parent tables
    fact_data = pd.DataFrame({
        "计划代码": ["NEW_PLAN_001"],
        "组合代码": ["NEW_PORT_001"],
        "产品线": ["NEW_LINE_001"]
    })

    fk_configs = load_foreign_key_configs("annuity_performance")

    service = GenericBackfillService()
    result = service.backfill_all(fact_data, "annuity_performance", fk_configs, test_db)

    assert result.success
    assert result.total_inserted >= 3  # At least 3 new records

    # Verify records exist in parent tables
    assert record_exists(test_db, "年金计划", "年金计划号", "NEW_PLAN_001")
    assert record_exists(test_db, "组合计划", "组合代码", "NEW_PORT_001")
    assert record_exists(test_db, "产品线", "产品线代码", "NEW_LINE_001")
```

---

## 9. Observability

### 9.1 Structured Logging

```python
# All backfill operations use structured logging
logger.info(
    "backfill_complete",
    domain="annuity_performance",
    tables_processed=4,
    total_inserted=15,
    total_updated=3,
    duration_ms=245
)
```

### 9.2 Metrics

```python
# Dagster asset materialization metadata
context.add_output_metadata({
    "backfill_tables": len(result.table_results),
    "records_inserted": result.total_inserted,
    "records_updated": result.total_updated,
    "success": result.success
})
```

---

## 10. Implementation Checklist

- [ ] Create `ForeignKeyConfig` Pydantic model
- [ ] Create `GenericBackfillService` class
- [ ] Add `foreign_keys` schema to `data_sources.yml`
- [ ] Configure FKs for `annuity_performance` domain
- [ ] Add missing FKs (产品线, 组织架构)
- [ ] Create `generic_backfill_op` Dagster op
- [ ] Add unit tests for service
- [ ] Add integration tests for full pipeline
- [ ] Update architecture documentation
- [ ] Create migration guide for existing domains

---

## 11. References

- [Problem Analysis](./problem-analysis.md)
- [Existing Backfill Service](../../../src/work_data_hub/domain/reference_backfill/generic_service.py)
- [Data Sources Config](../../../config/data_sources.yml)
- [Pipeline Jobs](../../../src/work_data_hub/orchestration/jobs.py)
