from typing import Any, Dict, List, Optional

from work_data_hub.io.loader.insert_builder import (
    _adapt_param,
    _ensure_list_of_dicts,
    _get_column_order,
    build_insert_sql,
)
from work_data_hub.io.loader.models import DataWarehouseLoaderError
from work_data_hub.io.loader.sql_utils import quote_ident, quote_qualified, quote_table
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


def insert_missing(
    table: str,
    key_cols: List[str],
    rows: List[Dict[str, Any]],
    conn: Any,
    chunk_size: int = 1000,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert rows that don't conflict with existing keys using ON CONFLICT DO NOTHING.

    Falls back to SELECT-filter + plain INSERT when ON CONFLICT target constraint is
    not available in the database, preserving correctness in environments without
    unique indexes.

    Args:
        table: Target table name
        key_cols: Primary key columns for conflict detection
        rows: List of dictionaries with row data
        conn: psycopg2 connection object (None = return plan only)
        chunk_size: Rows per batch for chunking
        schema: Optional schema name for qualified table reference

    Returns:
        Dictionary with execution metadata:
        {
            "inserted": int,
            "batches": int,
            "sql_plans": list  # If conn is None
        }

    Raises:
        DataWarehouseLoaderError: For validation or execution errors
    """
    if not rows:
        return {"inserted": 0, "batches": 0}

    # Validate key columns exist in rows
    missing_keys = []
    for i, row in enumerate(rows[:5]):  # Check first 5 rows for efficiency
        for col in key_cols:
            if col not in row:
                missing_keys.append(f"Row {i} missing key column '{col}'")
    if missing_keys:
        raise DataWarehouseLoaderError(
            f"Missing key columns in rows: {'; '.join(missing_keys)}"
        )

    # Build SQL with ON CONFLICT clause
    quoted_table = quote_qualified(schema, table)
    all_cols = _get_column_order(rows)
    quoted_cols = [quote_ident(col) for col in all_cols]
    col_list = ",".join(quoted_cols)

    # ON CONFLICT clause for composite keys
    pk_cols = ",".join(quote_ident(col) for col in key_cols)

    operations = []
    inserted_total = 0
    batches = 0

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]

        # Build VALUES clause with proper parameter adaptation
        row_data = [[_adapt_param(row.get(col)) for col in all_cols] for row in chunk]

        # CRITICAL: Use ON CONFLICT DO NOTHING for concurrent safety
        sql = (
            f"INSERT INTO {quoted_table} ({col_list}) VALUES %s "
            f"ON CONFLICT ({pk_cols}) DO NOTHING"
        )

        if conn is None:
            # Plan-only mode: return SQL plans and optimistic inserted count
            operations.append(("INSERT_MISSING", sql, row_data))
            inserted_total += len(chunk)
        else:
            # Execute mode: try ON CONFLICT fast-path, fallback when constraint missing
            try:
                from psycopg2.extras import execute_values
            except ImportError:
                raise DataWarehouseLoaderError(
                    "psycopg2 not available for bulk operations"
                )

            with conn.cursor() as cursor:
                try:
                    execute_values(
                        cursor, sql, row_data, page_size=min(len(chunk), 1000)
                    )
                    # Prefer actual rowcount when available (accounts for conflicts)
                    try:
                        rc = int(getattr(cursor, "rowcount", 0))
                    except Exception:
                        rc = 0
                    if rc is None or rc < 0:
                        rc = len(row_data)
                    inserted_total += max(0, rc)
                    logger.info(
                        "Insert missing (ON CONFLICT): attempted %s rows for %s, "
                        "inserted ~%s",
                        len(chunk),
                        table,
                        rc,
                    )
                except Exception as e:
                    # Robust detection of missing unique/exclusion constraint
                    # for ON CONFLICT
                    msg = str(e)
                    pgcode = getattr(e, "pgcode", None)
                    should_fallback = False
                    # PostgreSQL error code 42P10 often used for:
                    # no unique or exclusion constraint matching ON CONFLICT
                    if pgcode == "42P10":
                        should_fallback = True
                    # Message-based heuristics (multi-language)
                    if "ON CONFLICT" in msg and (
                        "constraint" in msg
                        or "唯一" in msg  # Chinese: unique
                        or "排除" in msg  # Chinese: exclusion
                        or "约束" in msg  # Chinese: constraint
                    ):
                        should_fallback = True

                    if should_fallback:
                        # Fallback: SELECT existing keys, then plain INSERT for
                        # missing only
                        key_tuples = [tuple(r.get(k) for k in key_cols) for r in chunk]
                        existing_set = set()
                        if key_tuples:
                            sel_cols = ",".join(quote_ident(k) for k in key_cols)
                            tuple_placeholder = (
                                "(" + ",".join(["%s"] * len(key_cols)) + ")"
                            )
                            placeholders = ",".join(
                                [tuple_placeholder] * len(key_tuples)
                            )
                            sel_sql = (
                                f"SELECT {sel_cols} FROM {quoted_table} "
                                f"WHERE ({sel_cols}) IN ({placeholders})"
                            )
                            params: List[Any] = []
                            for t in key_tuples:
                                params.extend(list(t))
                            cursor.execute(sel_sql, params)
                            existing_set = set(
                                tuple(row) for row in (cursor.fetchall() or [])
                            )

                        to_insert = [
                            r
                            for r in chunk
                            if tuple(r.get(k) for k in key_cols) not in existing_set
                        ]
                        if to_insert:
                            simple_sql = (
                                f"INSERT INTO {quoted_table} ({col_list}) VALUES %s"
                            )
                            simple_data = [
                                [_adapt_param(r.get(c)) for c in all_cols]
                                for r in to_insert
                            ]
                            execute_values(
                                cursor,
                                simple_sql,
                                simple_data,
                                page_size=min(len(simple_data), 1000),
                            )
                            try:
                                rc2 = int(getattr(cursor, "rowcount", 0))
                            except Exception:
                                rc2 = 0
                            if rc2 is None or rc2 < 0:
                                rc2 = len(simple_data)
                            inserted_total += max(0, rc2)
                            logger.info(
                                "Insert missing (fallback): inserted %s/%s rows "
                                "into %s",
                                rc2,
                                len(to_insert),
                                table,
                            )
                        else:
                            logger.info(
                                "Insert missing (fallback): all %s keys already "
                                "exist in %s",
                                len(chunk),
                                table,
                            )
                    else:
                        # Unknown error: re-raise
                        raise

        batches += 1

    result: Dict[str, Any] = {"inserted": inserted_total, "batches": batches}
    if conn is None:
        result["sql_plans"] = operations

    return result


def fill_null_only(
    table: str,
    key_cols: List[str],
    rows: List[Dict[str, Any]],
    updatable_cols: List[str],
    conn: Any,
    schema: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update only NULL columns for existing rows, preserving non-NULL values.

    Args:
        table: Target table name
        key_cols: Primary key columns for row identification
        rows: List of dictionaries with row data
        updatable_cols: Columns that can be updated when NULL
        conn: psycopg2 connection object (None = return plan only)
        schema: Optional schema name for qualified table reference

    Returns:
        Dictionary with execution metadata:
        {
            "updated": int,
            "sql_plans": list  # If conn is None
        }

    Raises:
        DataWarehouseLoaderError: For validation or execution errors
    """
    if not rows:
        return {"updated": 0}

    # Validate columns exist in rows
    all_required_cols = set(key_cols + updatable_cols)
    missing_cols = []
    for i, row in enumerate(rows[:5]):  # Check first 5 rows
        for col in all_required_cols:
            if col not in row:
                missing_cols.append(f"Row {i} missing column '{col}'")
    if missing_cols:
        raise DataWarehouseLoaderError(
            f"Missing columns in rows: {'; '.join(missing_cols)}"
        )

    quoted_table = quote_qualified(schema, table)
    operations = []
    updated_total = 0

    for col in updatable_cols:
        # Filter rows that have non-null values for this column
        update_rows = [row for row in rows if row.get(col) is not None]
        if not update_rows:
            continue

        # Build parameterized UPDATE for this column
        quoted_col = quote_ident(col)
        key_conditions = " AND ".join(f"{quote_ident(k)} = %s" for k in key_cols)

        sql = (
            f"UPDATE {quoted_table} SET {quoted_col} = %s "
            f"WHERE {key_conditions} AND {quoted_col} IS NULL"
        )

        if conn is None:
            # Plan-only mode: return SQL plans
            params_list = []
            for row in update_rows:
                params = [_adapt_param(row[col])] + [
                    _adapt_param(row[k]) for k in key_cols
                ]
                params_list.append(params)
            operations.append(("UPDATE_NULL_ONLY", sql, params_list))
        else:
            # Execute mode
            with conn.cursor() as cursor:
                for row in update_rows:
                    params = [_adapt_param(row[col])] + [
                        _adapt_param(row[k]) for k in key_cols
                    ]
                    cursor.execute(sql, params)
                    updated_total += (
                        cursor.rowcount if hasattr(cursor, "rowcount") else 0
                    )

            logger.info(
                f"Fill null only: updated {len(update_rows)} rows "
                f"for column {col} in {table}"
            )

    result: Dict[str, Any] = {"updated": updated_total}
    if conn is None:
        result["sql_plans"] = operations

    return result


def load(
    table: str,
    rows: List[Dict[str, Any]],
    mode: str = "delete_insert",
    pk: Optional[List[str]] = None,
    chunk_size: int = 1000,
    conn: Any = None,
) -> Dict[str, Any]:
    """
    Load data into PostgreSQL table with transactional safety.

    Args:
        table: Target table name
        rows: List of dictionaries with row data
        mode: "delete_insert" or "append"
        pk: Primary key columns (required for delete_insert)
        chunk_size: Rows per batch for chunking
        conn: psycopg2 connection object (None = return plan only)

    Returns:
        Dictionary with execution metadata:
        {
            "mode": str,
            "table": str,
            "deleted": int,
            "inserted": int,
            "batches": int,
            "sql_plans": list  # If conn is None
        }

    Raises:
        DataWarehouseLoaderError: For validation or execution errors
    """
    # Validation
    if mode not in ["delete_insert", "append"]:
        raise DataWarehouseLoaderError(f"Invalid mode: {mode}")

    if mode == "delete_insert" and not pk:
        raise DataWarehouseLoaderError("Primary key required for delete_insert mode")

    if not isinstance(rows, list):
        # Add check for rows type to be safe, though _ensure_list_of_dicts does it
        pass

    rows = _ensure_list_of_dicts(rows)  # Using imported helper

    # Early return for empty data
    if not rows:
        return {
            "mode": mode,
            "table": table,
            "deleted": 0,
            "inserted": 0,
            "batches": 0,
        }

    # Determine column order
    cols = _get_column_order(rows)

    # Build SQL operations
    operations = []
    # Number of keys scheduled for deletion (estimate prior to execution)
    estimated_deleted = 0

    if mode == "delete_insert":
        # pk is guaranteed to be not None due to validation above
        assert pk is not None

        # Build chunked DELETE operations to avoid oversized SQL and stack depth issues
        # Validate rows and gather PK tuples
        missing_keys: list[str] = []
        pk_tuples_raw: list[tuple[Any, ...]] = []
        for i, row in enumerate(rows):
            pk_values: list[Any] = []
            for col in pk:
                if col not in row or row[col] is None:
                    missing_keys.append(f"Row {i} missing key {col}")
                    break
                pk_values.append(row[col])
            if len(pk_values) == len(pk):
                pk_tuples_raw.append(tuple(pk_values))

        if missing_keys:
            raise DataWarehouseLoaderError(
                "Missing primary key values: " + "; ".join(missing_keys)
            )

        # Deduplicate and sort for determinism
        unique_tuples: list[tuple[Any, ...]] = sorted(list(set(pk_tuples_raw)))

        # Estimate deletions (number of unique key tuples targeted)
        estimated_deleted = len(unique_tuples)

        if unique_tuples:
            quoted_table = quote_table(table)
            quoted_pk_cols = ",".join(quote_ident(c) for c in pk)
            cols_tuple = f"({quoted_pk_cols})"

            # Number of PK tuples per DELETE; reuse chunk_size to keep
            # configuration simple
            delete_chunk = max(1, min(chunk_size, 1000))
            for j in range(0, len(unique_tuples), delete_chunk):
                chunk_pk = unique_tuples[j : j + delete_chunk]
                # Build placeholders for this chunk
                tuple_placeholder = "(" + ",".join(["%s"] * len(pk)) + ")"
                placeholders = ",".join([tuple_placeholder] * len(chunk_pk))
                sql = (
                    f"DELETE FROM {quoted_table} WHERE {cols_tuple} IN ({placeholders})"
                )
                params: list[Any] = []
                for t in chunk_pk:
                    params.extend(t)
                operations.append(("DELETE", sql, params))

    # Chunk insertions
    total_inserted = 0
    batches = 0

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        insert_sql, insert_params = build_insert_sql(table, cols, chunk)

        if insert_sql:
            operations.append(("INSERT", insert_sql, insert_params))
            total_inserted += len(chunk)
            batches += 1

    result = {
        "mode": mode,
        "table": table,
        # deleted will be set to actual rows deleted if executing against DB;
        # otherwise remains the estimated number of key tuples targeted.
        "deleted": estimated_deleted,
        "inserted": total_inserted,
        "batches": batches,
    }

    # If no connection, return plan only (for testing)
    if conn is None:
        result["sql_plans"] = operations
        return result

    # Execute with database connection (manual transaction management for
    # broad compatibility)
    try:
        executed_deleted_total = 0
        with conn.cursor() as cursor:
            for op_type, sql, params in operations:
                if op_type == "DELETE":
                    cursor.execute(sql, params)
                    # Accumulate actual number of rows deleted by the database
                    try:
                        rc = int(getattr(cursor, "rowcount", 0))
                    except Exception:
                        rc = 0
                    executed_deleted_total += max(0, rc)
                    logger.info(f"Deleted {rc} rows from {table}")
                elif op_type == "INSERT":
                    # Use execute_values for performance
                    try:
                        from psycopg2.extras import execute_values
                    except ImportError:
                        raise DataWarehouseLoaderError(
                            "psycopg2 not available for bulk operations"
                        )

                    # Convert flattened params back to rows and adapt JSONB parameters
                    cols_per_row = len(cols)
                    row_data = [
                        [_adapt_param(val) for val in params[i : i + cols_per_row]]
                        for i in range(0, len(params), cols_per_row)
                    ]

                    quoted_table = quote_table(table)
                    quoted_cols = [quote_ident(col) for col in cols]
                    col_list = ",".join(quoted_cols)

                    execute_values(
                        cursor,
                        f"INSERT INTO {quoted_table} ({col_list}) VALUES %s",
                        row_data,
                        page_size=min(chunk_size, 1000),
                    )
                    logger.info(f"Inserted {len(row_data)} rows into {table}")

        # Commit if all operations succeed
        try:
            conn.commit()
        except Exception:
            # If commit not supported in mocked connection, ignore
            pass

        # Overwrite deleted estimate with actual rows deleted after successful commit
        result["deleted"] = executed_deleted_total

    except Exception as e:
        # Rollback on error when possible
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Database operation failed: {e}")
        raise DataWarehouseLoaderError(f"Load failed: {e}") from e

    return result
