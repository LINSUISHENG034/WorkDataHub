"""
Specialized data loader for company mapping migration.

This module provides data extraction from legacy 5-layer COMPANY_ID mapping
sources and loading to PostgreSQL enterprise.company_mapping table, with
retry logic for unstable MySQL connections and comprehensive error handling.
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add legacy path for MySqlDBManager import
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent / "legacy"))

try:
    from legacy.annuity_hub.database_operations.mysql_ops import MySqlDBManager
except ImportError:
    # Fallback for development/testing
    MySqlDBManager = None  # type: ignore
    logging.warning("MySqlDBManager not available - legacy extraction will be disabled")


from work_data_hub.domain.company_enrichment.models import CompanyMappingRecord
from work_data_hub.io.loader.warehouse_loader import (
    DataWarehouseLoaderError,
    _get_column_order,
    build_delete_sql,
    build_insert_sql,
    build_insert_sql_with_conflict,
    quote_qualified,
)

logger = logging.getLogger(__name__)


class CompanyMappingLoaderError(Exception):
    """Raised when company mapping loader encounters an error."""

    pass


def extract_legacy_mappings() -> List[CompanyMappingRecord]:
    """
    Extract company mappings from all 5 legacy sources with retry logic.

    Replicates the exact mapping structure from
    legacy/annuity_hub/data_handler/mappings.py with proper error handling
    and retry logic for unstable MySQL connections.

    Returns:
        List of CompanyMappingRecord instances ready for database loading

    Raises:
        CompanyMappingLoaderError: If critical extraction failures occur
    """
    if MySqlDBManager is None:
        raise CompanyMappingLoaderError(
            "MySqlDBManager not available - cannot extract legacy mappings"
        )

    logger.info("Starting legacy mapping extraction from 5 sources")
    mappings: List[CompanyMappingRecord] = []
    extraction_stats = {
        "plan": 0,
        "account": 0,
        "hardcode": 0,
        "name": 0,
        "account_name": 0,
    }

    # COMPANY_ID1_MAPPING: Plan codes (priority=1)
    try:
        plan_mappings = _extract_with_retry(
            _extract_company_id1_mapping, "COMPANY_ID1_MAPPING (plan codes)"
        )
        for alias, company_id in plan_mappings.items():
            if alias and company_id:
                mappings.append(
                    CompanyMappingRecord(
                        alias_name=str(alias).strip(),
                        canonical_id=str(company_id).strip(),
                        match_type="plan",
                        priority=1,
                        source="internal",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                extraction_stats["plan"] += 1
    except Exception as e:
        logger.error(f"Failed to extract COMPANY_ID1_MAPPING: {e}")
        raise CompanyMappingLoaderError(f"Plan code extraction failed: {e}")

    # COMPANY_ID2_MAPPING: Account numbers (priority=2)
    try:
        account_mappings = _extract_with_retry(
            _extract_company_id2_mapping, "COMPANY_ID2_MAPPING (account numbers)"
        )
        for alias, company_id in account_mappings.items():
            if alias and company_id:
                mappings.append(
                    CompanyMappingRecord(
                        alias_name=str(alias).strip(),
                        canonical_id=str(company_id).strip(),
                        match_type="account",
                        priority=2,
                        source="internal",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                extraction_stats["account"] += 1
    except Exception as e:
        logger.error(f"Failed to extract COMPANY_ID2_MAPPING: {e}")
        raise CompanyMappingLoaderError(f"Account number extraction failed: {e}")

    # COMPANY_ID3_MAPPING: Hardcoded mappings (priority=3)
    # This is the hardcoded dictionary from mappings.py lines 148-158
    hardcoded_mappings = {
        "FP0001": "614810477",
        "FP0002": "614810477",
        "FP0003": "610081428",
        "P0809": "608349737",
        "SC002": "604809109",
        "SC007": "602790403",
        "XNP466": "603968573",
        "XNP467": "603968573",
        "XNP596": "601038164",
    }

    for alias, company_id in hardcoded_mappings.items():
        mappings.append(
            CompanyMappingRecord(
                alias_name=alias,
                canonical_id=company_id,
                match_type="hardcode",
                priority=3,
                source="internal",
                updated_at=datetime.now(timezone.utc),
            )
        )
        extraction_stats["hardcode"] += 1

    # COMPANY_ID4_MAPPING: Customer names (priority=4)
    try:
        name_mappings = _extract_with_retry(
            _extract_company_id4_mapping, "COMPANY_ID4_MAPPING (customer names)"
        )
        for alias, company_id in name_mappings.items():
            if alias and company_id:
                mappings.append(
                    CompanyMappingRecord(
                        alias_name=str(alias).strip(),
                        canonical_id=str(company_id).strip(),
                        match_type="name",
                        priority=4,
                        source="internal",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                extraction_stats["name"] += 1
    except Exception as e:
        logger.error(f"Failed to extract COMPANY_ID4_MAPPING: {e}")
        raise CompanyMappingLoaderError(f"Customer name extraction failed: {e}")

    # COMPANY_ID5_MAPPING: Account names (priority=5)
    try:
        account_name_mappings = _extract_with_retry(
            _extract_company_id5_mapping, "COMPANY_ID5_MAPPING (account names)"
        )
        for alias, company_id in account_name_mappings.items():
            if alias and company_id:
                mappings.append(
                    CompanyMappingRecord(
                        alias_name=str(alias).strip(),
                        canonical_id=str(company_id).strip(),
                        match_type="account_name",
                        priority=5,
                        source="internal",
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                extraction_stats["account_name"] += 1
    except Exception as e:
        logger.error(f"Failed to extract COMPANY_ID5_MAPPING: {e}")
        raise CompanyMappingLoaderError(f"Account name extraction failed: {e}")

    logger.info(
        "Legacy mapping extraction completed",
        extra={
            "total_mappings": len(mappings),
            "plan_mappings": extraction_stats["plan"],
            "account_mappings": extraction_stats["account"],
            "hardcode_mappings": extraction_stats["hardcode"],
            "name_mappings": extraction_stats["name"],
            "account_name_mappings": extraction_stats["account_name"],
        },
    )

    return mappings


def _extract_with_retry(
    extraction_func,
    description: str,
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
) -> Dict[str, str]:
    """
    Execute extraction function with exponential backoff retry logic.

    Args:
        extraction_func: Function to execute (should return dict)
        description: Human-readable description for logging
        max_attempts: Maximum retry attempts
        backoff_factor: Backoff multiplier for retry delays

    Returns:
        Dictionary mapping from extraction function

    Raises:
        Exception: Re-raises the last exception if all retries fail
    """
    last_exception: Exception = Exception("No attempts made")

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Extracting {description} (attempt {attempt}/{max_attempts})")
            result = extraction_func()
            logger.debug(
                f"Successfully extracted {description}, got {len(result)} mappings"
            )
            return result

        except Exception as e:
            last_exception = e
            logger.warning(
                f"Extraction attempt {attempt} failed for {description}: {e}",
                extra={"attempt": attempt, "max_attempts": max_attempts},
            )

            if attempt < max_attempts:
                sleep_time = backoff_factor ** (attempt - 1)
                logger.debug(f"Retrying after {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                logger.error(f"All {max_attempts} attempts failed for {description}")

    # Re-raise the last exception
    raise last_exception


def _extract_company_id1_mapping() -> Dict[str, str]:
    """Extract COMPANY_ID1_MAPPING from MySQL (plan codes)."""
    with MySqlDBManager(database="mapping") as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("""
                SELECT `年金计划号`, `company_id`
                FROM mapping.`年金计划`
                WHERE `计划类型`= '单一计划' AND `年金计划号` != 'AN002';
            """)
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return {row[0]: row[1] for row in rows if row[0] and row[1]}


def _extract_company_id2_mapping() -> Dict[str, str]:
    """Extract COMPANY_ID2_MAPPING from MySQL (account numbers)."""
    with MySqlDBManager(database="enterprise") as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("""
                SELECT DISTINCT `年金账户号`, `company_id`
                FROM `annuity_account_mapping`
                WHERE `年金账户号` NOT LIKE 'GM%';
            """)
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return {row[0]: row[1] for row in rows if row[0] and row[1]}


def _extract_company_id4_mapping() -> Dict[str, str]:
    """Extract COMPANY_ID4_MAPPING from MySQL (customer names)."""
    with MySqlDBManager(database="enterprise") as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("""
                SELECT DISTINCT `company_name`, `company_id`
                FROM `company_id_mapping`;
            """)
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return {row[0]: row[1] for row in rows if row[0] and row[1]}


def _extract_company_id5_mapping() -> Dict[str, str]:
    """Extract COMPANY_ID5_MAPPING from MySQL (account names)."""
    with MySqlDBManager(database="business") as mysqldb:
        cursor = mysqldb.cursor
        try:
            cursor.execute("""
                SELECT DISTINCT `年金账户名`, `company_id`
                FROM `规模明细`
                WHERE `company_id` IS NOT NULL;
            """)
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return {row[0]: row[1] for row in rows if row[0] and row[1]}


def load_company_mappings(
    mappings: List[CompanyMappingRecord],
    conn: Any,  # psycopg2 connection
    schema: str = "enterprise",
    table: str = "company_mapping",
    mode: str = "delete_insert",
    chunk_size: int = 1000,
) -> Dict[str, Any]:
    """
    Load company mappings to PostgreSQL with transactional safety.

    Args:
        mappings: List of CompanyMappingRecord instances to load
        conn: psycopg2 database connection
        schema: Target schema name (default: enterprise)
        table: Target table name (default: company_mapping)
        mode: Load mode - 'delete_insert' (upsert) or 'append'
        chunk_size: Batch size for INSERT operations

    Returns:
        Dictionary with operation statistics

    Raises:
        DataWarehouseLoaderError: If loading operation fails
    """
    if not mappings:
        logger.warning("No company mappings provided for loading")
        return {"inserted": 0, "deleted": 0, "batches": 0}

    logger.info(
        "Starting company mapping load",
        extra={
            "mappings_count": len(mappings),
            "schema": schema,
            "table": table,
            "mode": mode,
            "chunk_size": chunk_size,
        },
    )

    # Convert Pydantic models to dictionaries
    mapping_dicts = [mapping.model_dump() for mapping in mappings]

    # Get column order (excluding auto-generated columns)
    cols = _get_column_order(mapping_dicts)

    # Primary key columns for delete operation
    pk_cols = ["alias_name", "match_type"]

    qualified_table = quote_qualified(schema, table)
    stats = {"inserted": 0, "deleted": 0, "batches": 0}

    try:
        with conn:  # Start transaction
            if mode == "delete_insert":
                # Delete existing records for the keys we're about to insert
                delete_sql, delete_params = build_delete_sql(
                    qualified_table, pk_cols, mapping_dicts
                )

                if delete_sql:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(delete_sql, delete_params)
                        stats["deleted"] = cursor.rowcount
                        logger.debug(f"Deleted {stats['deleted']} existing records")
                    finally:
                        cursor.close()

            elif mode == "append":
                # For append mode, we'll use conflict handling in the insert logic below
                logger.debug("Using append mode with conflict handling")

            # Insert new records in chunks
            total_inserted = 0
            batch_count = 0

            for i in range(0, len(mapping_dicts), chunk_size):
                chunk = mapping_dicts[i : i + chunk_size]

                if mode == "append":
                    # Use conflict-aware SQL for append mode
                    insert_sql, insert_params = build_insert_sql_with_conflict(
                        qualified_table,
                        cols,
                        chunk,
                        conflict_cols=pk_cols,
                        conflict_action="DO NOTHING",
                    )
                else:
                    # Use regular SQL for delete_insert mode
                    insert_sql, insert_params = build_insert_sql(
                        qualified_table, cols, chunk
                    )

                if insert_sql:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(insert_sql, insert_params)
                        chunk_inserted = cursor.rowcount
                        total_inserted += chunk_inserted
                        batch_count += 1

                        logger.debug(
                            f"Inserted batch {batch_count}: {chunk_inserted} records"
                        )
                    finally:
                        cursor.close()

            stats["inserted"] = total_inserted
            stats["batches"] = batch_count

        logger.info("Company mapping load completed successfully", extra=stats)

    except Exception as e:
        logger.error(f"Company mapping load failed: {e}")
        raise DataWarehouseLoaderError(f"Loading failed: {e}")

    return stats


def generate_load_plan(
    mappings: List[CompanyMappingRecord],
    schema: str = "enterprise",
    table: str = "company_mapping",
) -> Dict[str, Any]:
    """
    Generate execution plan for company mapping load without executing.

    Args:
        mappings: List of CompanyMappingRecord instances
        schema: Target schema name
        table: Target table name

    Returns:
        Dictionary with execution plan details
    """
    if not mappings:
        return {
            "operation": "company_mapping_load",
            "table": f"{schema}.{table}",
            "total_mappings": 0,
            "mapping_breakdown": {},
            "sql_plans": [],
        }

    # Analyze mapping breakdown by type
    breakdown: Dict[str, int] = {}
    for mapping in mappings:
        match_type = mapping.match_type
        breakdown[match_type] = breakdown.get(match_type, 0) + 1

    # Generate sample SQL
    sample_mappings = mappings[:3]  # First 3 for demo
    mapping_dicts = [mapping.model_dump() for mapping in sample_mappings]
    cols = _get_column_order(mapping_dicts)
    pk_cols = ["alias_name", "match_type"]

    qualified_table = quote_qualified(schema, table)

    sample_delete_sql, _ = build_delete_sql(qualified_table, pk_cols, mapping_dicts)
    sample_insert_sql, _ = build_insert_sql(qualified_table, cols, mapping_dicts)

    return {
        "operation": "company_mapping_load",
        "table": f"{schema}.{table}",
        "total_mappings": len(mappings),
        "mapping_breakdown": breakdown,
        "primary_key": pk_cols,
        "column_order": cols,
        "sql_plans": [
            {
                "operation": "DELETE (upsert mode)",
                "sql_template": sample_delete_sql,
                "estimated_affected": len(mapping_dicts),
            },
            {
                "operation": "INSERT",
                "sql_template": sample_insert_sql,
                "estimated_affected": len(mapping_dicts),
            },
        ],
    }
