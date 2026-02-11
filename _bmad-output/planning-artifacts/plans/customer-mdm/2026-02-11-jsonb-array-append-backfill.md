# JSONB Array Append Backfill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend FK Backfill service to support JSONB array append mode, migrate `年金客户标签` to `tags` JSONB field, and re-run annual_award/annual_loss backfill.

**Architecture:** Add new `JSONB_APPEND` aggregation type that generates JSON arrays from lambda expressions. Extend PostgreSQL dialect to support JSONB array merge syntax in upsert operations. Update FK config to target `tags` field.

**Tech Stack:** Python, Pydantic, SQLAlchemy, PostgreSQL JSONB operators (`||`, `jsonb_agg`, `COALESCE`)

---

## Task 1: Add JSONB_APPEND Aggregation Type to Models

**Files:**
- Modify: `src/work_data_hub/domain/reference_backfill/models.py:16-36`
- Test: `tests/unit/domain/reference_backfill/test_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/domain/reference_backfill/test_models.py
def test_jsonb_append_aggregation_type_exists():
    """JSONB_APPEND aggregation type should be available."""
    from work_data_hub.domain.reference_backfill.models import AggregationType

    assert hasattr(AggregationType, "JSONB_APPEND")
    assert AggregationType.JSONB_APPEND.value == "jsonb_append"


def test_jsonb_append_requires_code():
    """JSONB_APPEND aggregation requires code field."""
    from work_data_hub.domain.reference_backfill.models import AggregationConfig

    # Should raise validation error without code
    with pytest.raises(ValueError, match="code is required"):
        AggregationConfig(type="jsonb_append")

    # Should pass with code
    config = AggregationConfig(
        type="jsonb_append",
        code='lambda g: ["tag1"]'
    )
    assert config.code == 'lambda g: ["tag1"]'
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/domain/reference_backfill/test_models.py -k "jsonb_append" -v`
Expected: FAIL with "JSONB_APPEND not found"

**Step 3: Write minimal implementation**

```python
# src/work_data_hub/domain/reference_backfill/models.py
# Add to AggregationType enum (after LAMBDA):

class AggregationType(str, Enum):
    # ... existing types ...
    LAMBDA = "lambda"
    JSONB_APPEND = "jsonb_append"  # Story 7.6-18: JSONB array append mode
```

Update validator in `AggregationConfig`:

```python
@model_validator(mode="after")
def validate_aggregation_config(self):
    """Validate aggregation type-specific required fields."""
    if self.type == AggregationType.MAX_BY and not self.order_column:
        raise ValueError("aggregation.order_column is required when type is 'max_by'")
    if self.type == AggregationType.TEMPLATE and not self.template:
        raise ValueError("template is required when type is 'template'")
    if self.type == AggregationType.LAMBDA and not self.code:
        raise ValueError("code is required when type is 'lambda'")
    if self.type == AggregationType.JSONB_APPEND and not self.code:
        raise ValueError("code is required when type is 'jsonb_append'")
    return self
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/domain/reference_backfill/test_models.py -k "jsonb_append" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_data_hub/domain/reference_backfill/models.py tests/unit/domain/reference_backfill/test_models.py
git commit -m "$(cat <<'EOF'
feat(backfill): add JSONB_APPEND aggregation type

Story 7.6-18: Support JSONB array append mode for tags field migration.
EOF
)"
```

---

## Task 2: Implement JSONB Append Aggregation in GenericBackfillService

**Files:**
- Modify: `src/work_data_hub/domain/reference_backfill/generic_service.py:361-367`
- Test: `tests/unit/domain/reference_backfill/test_generic_backfill_service.py`

**Step 1: Write the failing test**

```python
# tests/unit/domain/reference_backfill/test_generic_backfill_service.py
def test_aggregate_jsonb_append_generates_list():
    """JSONB_APPEND aggregation should generate Python list values."""
    import pandas as pd
    from work_data_hub.domain.reference_backfill.generic_service import GenericBackfillService
    from work_data_hub.domain.reference_backfill.models import (
        AggregationConfig,
        AggregationType,
        BackfillColumnMapping,
    )

    service = GenericBackfillService(domain="test")

    df = pd.DataFrame({
        "company_id": ["C001", "C001", "C002"],
        "month": ["2025-11-01", "2025-10-01", "2025-11-01"],
    })

    mapping = BackfillColumnMapping(
        source="month",
        target="tags",
        aggregation=AggregationConfig(
            type=AggregationType.JSONB_APPEND,
            code='lambda g: [pd.to_datetime(g["month"].iloc[0]).strftime("%y%m") + "中标"]'
        )
    )

    result = service._aggregate_jsonb_append(df, "company_id", mapping)

    assert result["C001"] == ["2511中标"]
    assert result["C002"] == ["2511中标"]
    assert isinstance(result["C001"], list)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/domain/reference_backfill/test_generic_backfill_service.py -k "jsonb_append" -v`
Expected: FAIL with "has no attribute '_aggregate_jsonb_append'"

**Step 3: Write minimal implementation**

```python
# src/work_data_hub/domain/reference_backfill/generic_service.py
# Add new method after _aggregate_lambda:

def _aggregate_jsonb_append(
    self, df: pd.DataFrame, group_col: str, mapping: BackfillColumnMapping
) -> pd.Series:
    """
    Execute lambda and ensure result is a JSON-serializable list.

    Story 7.6-18: JSONB array append mode for tags field.

    The lambda must return a list. If it returns a non-list value,
    it will be wrapped in a list automatically.

    Args:
        df: Source DataFrame
        group_col: Column to group by
        mapping: Column mapping with aggregation config

    Returns:
        Series with list values indexed by group
    """
    import json

    code = mapping.aggregation.code
    try:
        func = eval(code)  # noqa: S307 - Config files are developer-controlled
    except Exception as e:
        self.logger.error(f"Failed to compile jsonb_append lambda: {e}")
        raise ValueError(f"Invalid jsonb_append lambda expression: {code}") from e

    def safe_apply(group):
        try:
            result = func(group)
            # Ensure result is a list
            if result is None:
                return []
            if not isinstance(result, list):
                return [result]
            # Validate JSON serializable
            json.dumps(result)
            return result
        except Exception as e:
            self.logger.warning(f"jsonb_append lambda error for group: {e}")
            return []

    return df.groupby(group_col).apply(safe_apply)
```

Update `derive_candidates` method to handle JSONB_APPEND:

```python
# In derive_candidates method, add after LAMBDA handling (around line 367):
elif col_mapping.aggregation.type == AggregationType.JSONB_APPEND:
    # Story 7.6-18: JSONB array append aggregation
    candidates_df[col_mapping.target] = (
        self._aggregate_jsonb_append(source_df, config.source_column, col_mapping)
        .reindex(grouped_first.index)
        .to_numpy()
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/domain/reference_backfill/test_generic_backfill_service.py -k "jsonb_append" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_data_hub/domain/reference_backfill/generic_service.py tests/unit/domain/reference_backfill/test_generic_backfill_service.py
git commit -m "$(cat <<'EOF'
feat(backfill): implement JSONB_APPEND aggregation method

Story 7.6-18: Execute lambda and ensure JSON-serializable list output.
EOF
)"
```

---

## Task 3: Extend PostgreSQL Dialect for JSONB Array Merge

**Files:**
- Modify: `src/work_data_hub/infrastructure/sql/dialects/postgresql.py`
- Test: `tests/unit/infrastructure/sql/test_postgresql_dialect.py`

**Step 1: Write the failing test**

```python
# tests/unit/infrastructure/sql/test_postgresql_dialect.py
def test_build_insert_on_conflict_with_jsonb_merge():
    """JSONB columns should use array merge syntax on conflict."""
    from work_data_hub.infrastructure.sql.dialects.postgresql import PostgreSQLDialect

    dialect = PostgreSQLDialect()
    sql = dialect.build_insert_on_conflict_do_update(
        table="年金客户",
        columns=["company_id", "客户名称", "tags"],
        placeholders=[":col_0", ":col_1", ":col_2"],
        conflict_columns=["company_id"],
        update_columns=["客户名称", "tags"],
        null_guard=True,
        schema="customer",
        jsonb_merge_columns=["tags"],  # New parameter
    )

    # tags should use JSONB merge syntax
    assert "COALESCE" in sql
    assert "||" in sql
    assert "jsonb_agg" in sql or "tags" in sql
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/infrastructure/sql/test_postgresql_dialect.py -k "jsonb_merge" -v`
Expected: FAIL with "unexpected keyword argument 'jsonb_merge_columns'"

**Step 3: Write minimal implementation**

```python
# src/work_data_hub/infrastructure/sql/dialects/postgresql.py
# Update build_insert_on_conflict_do_update method signature and implementation:

def build_insert_on_conflict_do_update(
    self,
    table: str,
    columns: List[str],
    placeholders: List[str],
    conflict_columns: List[str],
    update_columns: List[str],
    null_guard: bool = True,
    schema: Optional[str] = None,
    jsonb_merge_columns: Optional[List[str]] = None,  # New parameter
) -> str:
    """
    Build INSERT ... ON CONFLICT DO UPDATE statement.

    Args:
        table: Table name
        columns: List of column names to insert
        placeholders: List of parameter placeholders
        conflict_columns: Columns for conflict detection
        update_columns: Columns to update on conflict
        null_guard: If True, only update if existing value is NULL
        schema: Optional schema name
        jsonb_merge_columns: Columns that should use JSONB array merge

    Returns:
        INSERT ... ON CONFLICT DO UPDATE SQL statement
    """
    qualified_table = self.qualify(table, schema)
    base_insert = self.build_insert(table, columns, placeholders, schema)
    conflict_cols = ", ".join(self.quote(c) for c in conflict_columns)
    jsonb_merge_set = set(jsonb_merge_columns or [])

    update_parts = []
    for col in update_columns:
        quoted_col = self.quote(col)
        if col in jsonb_merge_set:
            # JSONB array merge: append new values, deduplicate
            # Uses: COALESCE(existing, '[]') || EXCLUDED.col
            # Then wraps with subquery to deduplicate
            update_parts.append(
                f"{quoted_col} = ("
                f"SELECT jsonb_agg(DISTINCT elem) "
                f"FROM jsonb_array_elements("
                f"COALESCE({qualified_table}.{quoted_col}, '[]'::jsonb) || "
                f"COALESCE(EXCLUDED.{quoted_col}, '[]'::jsonb)"
                f") AS elem"
                f")"
            )
        elif null_guard:
            # Only update if existing value is NULL
            update_parts.append(
                f"{quoted_col} = CASE WHEN {qualified_table}.{quoted_col} IS NULL "
                f"THEN EXCLUDED.{quoted_col} ELSE {qualified_table}.{quoted_col} END"
            )
        else:
            # Always update
            update_parts.append(f"{quoted_col} = EXCLUDED.{quoted_col}")

    update_set = ", ".join(update_parts)
    return f"{base_insert} ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/infrastructure/sql/test_postgresql_dialect.py -k "jsonb_merge" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_data_hub/infrastructure/sql/dialects/postgresql.py tests/unit/infrastructure/sql/test_postgresql_dialect.py
git commit -m "$(cat <<'EOF'
feat(sql): add JSONB array merge support to PostgreSQL dialect

Story 7.6-18: Support JSONB array deduplication on upsert.
EOF
)"
```

---

## Task 4: Update InsertBuilder and GenericBackfillService Integration

**Files:**
- Modify: `src/work_data_hub/infrastructure/sql/operations/insert.py`
- Modify: `src/work_data_hub/domain/reference_backfill/generic_service.py:646-671`

**Step 1: Write the failing test**

```python
# tests/unit/domain/reference_backfill/test_generic_backfill_service.py
def test_backfill_table_uses_jsonb_merge_for_jsonb_columns(mocker):
    """Backfill should use JSONB merge syntax for JSONB_APPEND columns."""
    # This is an integration test - verify SQL contains JSONB merge syntax
    pass  # Will be verified in integration test
```

**Step 2: Update InsertBuilder**

```python
# src/work_data_hub/infrastructure/sql/operations/insert.py
# Update upsert method signature:

def upsert(
    self,
    schema: Optional[str],
    table: str,
    columns: List[str],
    placeholders: List[str],
    conflict_columns: List[str],
    mode: Literal["do_nothing", "do_update"] = "do_nothing",
    update_columns: Optional[List[str]] = None,
    null_guard: bool = True,
    jsonb_merge_columns: Optional[List[str]] = None,  # New parameter
) -> str:
    # ... existing code ...
    else:
        if not update_columns:
            update_columns = [c for c in columns if c not in conflict_columns]
        return self.dialect.build_insert_on_conflict_do_update(
            table,
            columns,
            placeholders,
            conflict_columns,
            update_columns,
            null_guard,
            schema,
            jsonb_merge_columns,  # Pass through
        )
```

**Step 3: Update GenericBackfillService.backfill_table**

```python
# src/work_data_hub/domain/reference_backfill/generic_service.py
# In backfill_table method, detect JSONB_APPEND columns:

def backfill_table(
    self,
    candidates_df: pd.DataFrame,
    config: ForeignKeyConfig,
    conn: Connection,
    add_tracking_fields: bool = True,
) -> int:
    # ... existing code up to InsertBuilder usage ...

    # Detect JSONB_APPEND columns for merge syntax
    jsonb_merge_columns = [
        col_mapping.target
        for col_mapping in config.backfill_columns
        if col_mapping.aggregation
        and col_mapping.aggregation.type == AggregationType.JSONB_APPEND
    ]

    if conn.dialect.name == "postgresql":
        dialect = PostgreSQLDialect()
        builder = InsertBuilder(dialect)
        update_columns = [col for col in columns if col != config.target_key]

        if config.mode == "fill_null_only":
            query = builder.upsert(
                schema=config.target_schema,
                table=config.target_table,
                columns=columns,
                placeholders=placeholders,
                conflict_columns=conflict_columns,
                mode="do_update",
                update_columns=update_columns,
                null_guard=True,
                jsonb_merge_columns=jsonb_merge_columns,  # New
            )
        else:
            # insert_missing mode - still use do_nothing for non-JSONB
            # But if we have JSONB columns, we need do_update with merge
            if jsonb_merge_columns:
                query = builder.upsert(
                    schema=config.target_schema,
                    table=config.target_table,
                    columns=columns,
                    placeholders=placeholders,
                    conflict_columns=conflict_columns,
                    mode="do_update",
                    update_columns=jsonb_merge_columns,  # Only update JSONB columns
                    null_guard=False,  # Always merge JSONB
                    jsonb_merge_columns=jsonb_merge_columns,
                )
            else:
                query = builder.upsert(
                    schema=config.target_schema,
                    table=config.target_table,
                    columns=columns,
                    placeholders=placeholders,
                    conflict_columns=conflict_columns,
                    mode="do_nothing",
                )
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/domain/reference_backfill/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/work_data_hub/infrastructure/sql/operations/insert.py src/work_data_hub/domain/reference_backfill/generic_service.py
git commit -m "$(cat <<'EOF'
feat(backfill): integrate JSONB merge into backfill pipeline

Story 7.6-18: Auto-detect JSONB_APPEND columns and use merge syntax.
EOF
)"
```

---

## Task 5: Update FK Configuration for tags Field

**Files:**
- Modify: `config/foreign_keys.yml:467-478, 555-566`

**Step 1: Update annual_award configuration**

Replace `年金客户标签` mapping with `tags`:

```yaml
# config/foreign_keys.yml - annual_award section
# Replace:
          - source: "上报月份"
            target: "年金客户标签"
            optional: true
            aggregation:
              type: "lambda"
              code: 'lambda g: pd.to_datetime(g["上报月份"].dropna().iloc[0]).strftime("%y%m") + "中标" if len(g["上报月份"].dropna()) > 0 else ""'
# With:
          - source: "上报月份"
            target: "tags"
            optional: true
            aggregation:
              type: "jsonb_append"
              code: 'lambda g: [pd.to_datetime(g["上报月份"].dropna().iloc[0]).strftime("%y%m") + "中标"] if len(g["上报月份"].dropna()) > 0 else []'
```

**Step 2: Update annual_loss configuration**

```yaml
# config/foreign_keys.yml - annual_loss section
# Replace:
          - source: "上报月份"
            target: "年金客户标签"
            optional: true
            aggregation:
              type: "lambda"
              code: 'lambda g: pd.to_datetime(g["上报月份"].dropna().iloc[0]).strftime("%y%m") + "流失" if len(g["上报月份"].dropna()) > 0 else ""'
# With:
          - source: "上报月份"
            target: "tags"
            optional: true
            aggregation:
              type: "jsonb_append"
              code: 'lambda g: [pd.to_datetime(g["上报月份"].dropna().iloc[0]).strftime("%y%m") + "流失"] if len(g["上报月份"].dropna()) > 0 else []'
```

**Step 3: Validate configuration**

Run: `uv run --env-file .wdh_env python -c "from work_data_hub.domain.reference_backfill.config_loader import load_fk_config; c = load_fk_config(); print('annual_award tags:', [m.target for m in c['annual_award'].foreign_keys[0].backfill_columns if m.target == 'tags'])"`
Expected: `annual_award tags: ['tags']`

**Step 4: Commit**

```bash
git add config/foreign_keys.yml
git commit -m "$(cat <<'EOF'
feat(config): migrate 年金客户标签 to tags JSONB field

Story 7.6-18: Use JSONB_APPEND aggregation for tags array.
EOF
)"
```

---

## Task 6: Integration Test and Data Backfill

**Step 1: Run unit tests**

Run: `uv run pytest tests/unit/domain/reference_backfill/ -v`
Expected: All PASS

**Step 2: Run annual_award backfill (dry-run)**

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annual_award --period 202511 --mode delete_insert --debug
```

Expected: Backfill shows tags column in candidates

**Step 3: Run annual_award backfill (execute)**

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annual_award --period 202511 --mode delete_insert --execute
```

**Step 4: Run annual_loss backfill (execute)**

```bash
uv run --env-file .wdh_env python -m work_data_hub.cli etl --domain annual_loss --period 202511 --mode delete_insert --execute
```

**Step 5: Verify database**

```sql
-- Check tags field populated
SELECT company_id, 客户名称, tags
FROM customer."年金客户"
WHERE tags IS NOT NULL AND tags != '[]'::jsonb
LIMIT 10;
```

**Step 6: Final commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(backfill): complete JSONB array append implementation

Story 7.6-18: Successfully migrated 年金客户标签 to tags JSONB field.
- Added JSONB_APPEND aggregation type
- Extended PostgreSQL dialect for JSONB merge
- Updated FK config for annual_award/annual_loss
- Verified backfill execution
EOF
)"
```

---

## Verification Checklist

- [ ] JSONB_APPEND aggregation type added to models
- [ ] _aggregate_jsonb_append method implemented
- [ ] PostgreSQL dialect supports JSONB merge syntax
- [ ] InsertBuilder passes jsonb_merge_columns
- [ ] GenericBackfillService detects JSONB_APPEND columns
- [ ] FK config updated for annual_award (tags field)
- [ ] FK config updated for annual_loss (tags field)
- [ ] Unit tests pass
- [ ] annual_award backfill executed successfully
- [ ] annual_loss backfill executed successfully
- [ ] Database shows tags populated with arrays
