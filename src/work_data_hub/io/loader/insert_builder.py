from typing import Any, Dict, List, Optional, Set, Tuple

from .sql_utils import quote_ident, quote_table


def _ensure_list_of_dicts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and normalize row data."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list")

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Row {i} must be a dictionary")

    return rows


def _get_column_order(
    rows: List[Dict[str, Any]], provided_cols: Optional[List[str]] = None
) -> List[str]:
    """Determine deterministic column ordering, excluding auto-generated columns."""
    if provided_cols:
        return provided_cols

    # Get union of all keys, sorted for deterministic order
    all_keys: Set[str] = set()
    for row in rows:
        all_keys.update(row.keys())

    # Exclude auto-generated ID columns (GENERATED ALWAYS AS IDENTITY)
    # Common patterns: id, {entity}_id
    auto_generated_columns = {"id", "annuity_performance_id", "trustee_performance_id"}
    for col in auto_generated_columns:
        all_keys.discard(col)

    return sorted(all_keys)


def _adapt_param(v: Any) -> Any:
    """
    Adapt dict/list parameters for JSONB columns.

    Args:
        v: Parameter value

    Returns:
        psycopg2.extras.Json wrapped value for dict/list, otherwise unchanged
    """
    if isinstance(v, (dict, list)):
        from psycopg2.extras import Json

        return Json(v)
    return v


def build_insert_sql(
    table: str, cols: List[str], rows: List[Dict[str, Any]]
) -> Tuple[Optional[str], List[Any]]:
    """
    Build parameterized INSERT SQL for bulk operations.

    Args:
        table: Target table name
        cols: Column names in desired order
        rows: List of dictionaries with row data

    Returns:
        Tuple of (sql_string, flattened_parameters)

    Example:
        >>> sql, params = build_insert_sql(
        ...     "users",
        ...     ["id", "name"],
        ...     [{"id": 1, "name": "John"}],
        ... )
        >>> sql
        'INSERT INTO "users" ("id","name") VALUES (%s,%s)'
        >>> params
        [1, "John"]
    """
    if not table:
        raise ValueError("Table name is required")
    if not cols:
        raise ValueError("Column list cannot be empty")

    rows = _ensure_list_of_dicts(rows)
    if not rows:
        return None, []

    # Quote table and column identifiers
    quoted_table = quote_table(table)
    quoted_cols = [quote_ident(col) for col in cols]

    # Build SQL template
    col_list = ",".join(quoted_cols)
    value_template = "(" + ",".join(["%s"] * len(cols)) + ")"

    sql = f"INSERT INTO {quoted_table} ({col_list}) VALUES {value_template}"

    # Flatten parameters in row-major order
    params = []
    for row in rows:
        for col in cols:
            params.append(row.get(col))  # None if key missing

    return sql, params


def build_insert_sql_with_conflict(
    table: str,
    cols: List[str],
    rows: List[Dict[str, Any]],
    conflict_cols: Optional[List[str]] = None,
    conflict_action: str = "DO NOTHING",
) -> Tuple[Optional[str], List[Any]]:
    """
    Build parameterized INSERT SQL with conflict resolution for bulk operations.

    Args:
        table: Target table name
        cols: Column names in desired order
        rows: List of dictionaries with row data
        conflict_cols: Columns to check for conflicts (for ON CONFLICT clause)
        conflict_action: Action to take on conflict ("DO NOTHING" or
            "DO UPDATE SET ...")

    Returns:
        Tuple of (sql_string, flattened_parameters)

    Example:
        >>> sql, params = build_insert_sql_with_conflict(
        ...     "users",
        ...     ["id", "name"],
        ...     [{"id": 1, "name": "John"}],
        ...     conflict_cols=["id"],
        ...     conflict_action="DO NOTHING",
        ... )
        >>> sql
        'INSERT INTO "users" ("id","name") VALUES (%s,%s) ON CONFLICT ("id") DO NOTHING'
    """
    if not table:
        raise ValueError("Table name is required")
    if not cols:
        raise ValueError("Column list cannot be empty")
    if conflict_cols and not isinstance(conflict_cols, list):
        raise ValueError("conflict_cols must be a list")

    rows = _ensure_list_of_dicts(rows)
    if not rows:
        return None, []

    # Quote table and column identifiers
    quoted_table = quote_table(table)
    quoted_cols = [quote_ident(col) for col in cols]

    # Build SQL template
    col_list = ",".join(quoted_cols)
    value_template = "(" + ",".join(["%s"] * len(cols)) + ")"

    sql = f"INSERT INTO {quoted_table} ({col_list}) VALUES {value_template}"

    # Add conflict resolution if specified
    if conflict_cols:
        quoted_conflict_cols = [quote_ident(col) for col in conflict_cols]
        conflict_col_list = ",".join(quoted_conflict_cols)
        sql += f" ON CONFLICT ({conflict_col_list}) {conflict_action}"

    # Flatten parameters in row-major order
    params = []
    for row in rows:
        for col in cols:
            params.append(row.get(col))  # None if key missing

    return sql, params


def build_delete_sql(
    table: str, pk_cols: List[str], rows: List[Dict[str, Any]]
) -> Tuple[Optional[str], List[Any]]:
    """
    Build DELETE SQL using composite key tuple IN pattern.

    Args:
        table: Target table name
        pk_cols: Primary key column names
        rows: Rows containing PK values to delete

    Returns:
        Tuple of (sql_string, flattened_parameters)

    Example:
        >>> sql, params = build_delete_sql(
        ...     "users",
        ...     ["id", "type"],
        ...     [{"id": 1, "type": "A"}],
        ... )
        >>> sql
        'DELETE FROM "users" WHERE ("id","type") IN ((%s,%s))'
        >>> params
        [1, "A"]
    """
    if not table:
        raise ValueError("Table name is required")
    if not pk_cols:
        raise ValueError("Primary key columns are required")

    rows = _ensure_list_of_dicts(rows)
    if not rows:
        return None, []

    # Validate all rows have PK values
    missing_keys = []
    pk_tuples = []

    for i, row in enumerate(rows):
        pk_values = []
        for col in pk_cols:
            if col not in row or row[col] is None:
                missing_keys.append(f"Row {i} missing key {col}")
            else:
                pk_values.append(row[col])

        # Fix: Indentation of pk_tuples.append was inside else; moved it to match original if logic
        # Original:
        #         if len(pk_values) == len(pk_cols):
        #             pk_tuples.append(tuple(pk_values))
        if len(pk_values) == len(pk_cols):
            pk_tuples.append(tuple(pk_values))

    if missing_keys:
        raise ValueError("Missing primary key values: " + "; ".join(missing_keys))

    # Deduplicate PK tuples and sort for deterministic order
    unique_tuples = sorted(list(set(pk_tuples)))

    # Build SQL
    quoted_table = quote_table(table)
    quoted_cols = [quote_ident(col) for col in pk_cols]
    col_list = "(" + ",".join(quoted_cols) + ")"

    # Create tuple placeholders: ((%s,%s),(%s,%s))
    tuple_template = "(" + ",".join(["%s"] * len(pk_cols)) + ")"
    tuples_list = ",".join([tuple_template] * len(unique_tuples))

    sql = f"DELETE FROM {quoted_table} WHERE {col_list} IN ({tuples_list})"

    # Flatten parameters
    params: list[Any] = []
    for pk_tuple in unique_tuples:
        params.extend(pk_tuple)

    return sql, params


def _prepare_unique_pk_tuples(
    pk_cols: List[str], rows: List[Dict[str, Any]]
) -> List[Tuple[Any, ...]]:
    """
    Extract, validate and deduplicate PK tuples from rows.

    Raises ValueError if any required PK is missing.
    Returns a sorted list of unique PK tuples for deterministic behavior.
    """
    rows = _ensure_list_of_dicts(rows)
    if not rows:
        return []

    missing_keys = []
    pk_tuples: List[Tuple[Any, ...]] = []

    for i, row in enumerate(rows):
        pk_values = []
        for col in pk_cols:
            if col not in row or row[col] is None:
                missing_keys.append(f"Row {i} missing key {col}")
            else:
                pk_values.append(row[col])
        if len(pk_values) == len(pk_cols):
            pk_tuples.append(tuple(pk_values))

    if missing_keys:
        raise ValueError("Missing primary key values: " + "; ".join(missing_keys))

    unique_tuples = sorted(list(set(pk_tuples)))
    return unique_tuples
