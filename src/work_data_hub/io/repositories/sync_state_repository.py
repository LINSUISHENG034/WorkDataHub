"""
Sync State Repository for incremental sync state persistence.

Story 6.2-p4: Reference Sync Incremental State Persistence
Provides persistence and retrieval of sync state (last_synced_at timestamps)
for incremental reference data synchronization.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

SCHEMA_NAME = "system"
TABLE_NAME = "sync_state"


class SyncStateRepository:
    """
    Repository for managing sync state persistence.

    Stores and retrieves the last_synced_at timestamp for each job/table
    combination, enabling incremental synchronization.

    Usage:
        repo = SyncStateRepository(conn)

        # Get state for a specific table
        state = repo.get_state("reference_sync", "年金计划")
        if state:
            last_synced = state["last_synced_at"]

        # Get all states for a job
        states = repo.get_all_states("reference_sync")

        # Update state after successful sync
        repo.update_state("reference_sync", "年金计划", sync_time)
    """

    def __init__(self, conn: Connection):
        """
        Initialize the repository with a database connection.

        Args:
            conn: SQLAlchemy connection object
        """
        self.conn = conn
        self._table_verified = False

    def _ensure_table_exists(self) -> bool:
        """
        Verify the sync_state table exists.

        Returns:
            True if table exists, False otherwise
        """
        if self._table_verified:
            return True

        result = self.conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = :schema AND table_name = :table
                )
                """
            ),
            {"schema": SCHEMA_NAME, "table": TABLE_NAME},
        )
        exists = result.scalar()
        if exists:
            self._table_verified = True
        return exists

    def get_state(self, job_name: str, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the sync state for a specific job/table combination.

        Args:
            job_name: Name of the sync job (e.g., "reference_sync")
            table_name: Name of the table being synced

        Returns:
            Dictionary with state data or None if not found:
            {
                "job_name": str,
                "table_name": str,
                "last_synced_at": datetime,
                "updated_at": datetime
            }
        """
        if not self._ensure_table_exists():
            logger.warning(
                "sync_state table does not exist, returning None",
                extra={"job_name": job_name, "table_name": table_name},
            )
            return None

        result = self.conn.execute(
            sa.text(
                f"""
                SELECT job_name, table_name, last_synced_at, updated_at
                FROM {SCHEMA_NAME}.{TABLE_NAME}
                WHERE job_name = :job_name AND table_name = :table_name
                """
            ),
            {"job_name": job_name, "table_name": table_name},
        )
        row = result.fetchone()

        if row is None:
            return None

        return {
            "job_name": row[0],
            "table_name": row[1],
            "last_synced_at": row[2],
            "updated_at": row[3],
        }

    def get_all_states(self, job_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all sync states for a job, keyed by table name.

        Args:
            job_name: Name of the sync job (e.g., "reference_sync")

        Returns:
            Dictionary mapping table names to their state:
            {
                "年金计划": {"last_synced_at": datetime, ...},
                "组织架构": {"last_synced_at": datetime, ...},
            }
        """
        if not self._ensure_table_exists():
            logger.warning(
                "sync_state table does not exist, returning empty dict",
                extra={"job_name": job_name},
            )
            return {}

        result = self.conn.execute(
            sa.text(
                f"""
                SELECT job_name, table_name, last_synced_at, updated_at
                FROM {SCHEMA_NAME}.{TABLE_NAME}
                WHERE job_name = :job_name
                """
            ),
            {"job_name": job_name},
        )
        rows = result.fetchall()

        states = {}
        for row in rows:
            states[row[1]] = {
                "job_name": row[0],
                "table_name": row[1],
                "last_synced_at": row[2],
                "updated_at": row[3],
            }

        return states

    def update_state(
        self,
        job_name: str,
        table_name: str,
        last_synced_at: datetime,
    ) -> bool:
        """
        Update or insert the sync state for a job/table combination.

        Uses UPSERT (INSERT ... ON CONFLICT DO UPDATE) for atomic operation.

        Args:
            job_name: Name of the sync job
            table_name: Name of the table being synced
            last_synced_at: Timestamp of the sync operation

        Returns:
            True if operation succeeded, False otherwise
        """
        if not self._ensure_table_exists():
            logger.error(
                "sync_state table does not exist, cannot update state",
                extra={"job_name": job_name, "table_name": table_name},
            )
            return False

        # Ensure timezone-aware timestamp
        if last_synced_at.tzinfo is None:
            last_synced_at = last_synced_at.replace(tzinfo=timezone.utc)

        try:
            self.conn.execute(
                sa.text(
                    f"""
                    INSERT INTO {SCHEMA_NAME}.{TABLE_NAME}
                        (job_name, table_name, last_synced_at, updated_at)
                    VALUES
                        (:job_name, :table_name, :last_synced_at, CURRENT_TIMESTAMP)
                    ON CONFLICT (job_name, table_name)
                    DO UPDATE SET
                        last_synced_at = EXCLUDED.last_synced_at,
                        updated_at = CURRENT_TIMESTAMP
                    """
                ),
                {
                    "job_name": job_name,
                    "table_name": table_name,
                    "last_synced_at": last_synced_at,
                },
            )
            self.conn.commit()

            logger.info(
                "Sync state updated",
                extra={
                    "job_name": job_name,
                    "table_name": table_name,
                    "last_synced_at": last_synced_at.isoformat(),
                },
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to update sync state",
                extra={
                    "job_name": job_name,
                    "table_name": table_name,
                    "error": str(e),
                },
            )
            return False

    def delete_state(self, job_name: str, table_name: str) -> bool:
        """
        Delete the sync state for a job/table combination.

        Args:
            job_name: Name of the sync job
            table_name: Name of the table

        Returns:
            True if a row was deleted, False otherwise
        """
        if not self._ensure_table_exists():
            return False

        try:
            result = self.conn.execute(
                sa.text(
                    f"""
                    DELETE FROM {SCHEMA_NAME}.{TABLE_NAME}
                    WHERE job_name = :job_name AND table_name = :table_name
                    """
                ),
                {"job_name": job_name, "table_name": table_name},
            )
            self.conn.commit()
            return result.rowcount > 0

        except Exception as e:
            logger.error(
                "Failed to delete sync state",
                extra={
                    "job_name": job_name,
                    "table_name": table_name,
                    "error": str(e),
                },
            )
            return False

    def clear_all_states(self, job_name: str) -> int:
        """
        Clear all sync states for a job.

        Args:
            job_name: Name of the sync job

        Returns:
            Number of rows deleted
        """
        if not self._ensure_table_exists():
            return 0

        try:
            result = self.conn.execute(
                sa.text(
                    f"""
                    DELETE FROM {SCHEMA_NAME}.{TABLE_NAME}
                    WHERE job_name = :job_name
                    """
                ),
                {"job_name": job_name},
            )
            self.conn.commit()
            return result.rowcount

        except Exception as e:
            logger.error(
                "Failed to clear sync states",
                extra={"job_name": job_name, "error": str(e)},
            )
            return 0
