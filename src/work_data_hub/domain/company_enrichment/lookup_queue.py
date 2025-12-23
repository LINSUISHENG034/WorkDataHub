"""
Lookup queue DAO for asynchronous EQC company lookup processing.

This module provides atomic queue operations for managing EQC lookup requests
with proper concurrency control using PostgreSQL FOR UPDATE SKIP LOCKED patterns.
Supports both plan_only and execute modes for validation and execution.

Story 6.7: Added exponential backoff support for retry logic with next_retry_at
column filtering and configurable backoff schedule.

Story 6-2-P1: Refactored get_next_temp_id() to use HMAC-SHA1 for deterministic
temporary ID generation instead of database sequence.
"""

import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from work_data_hub.infrastructure.enrichment.normalizer import (
    generate_temp_company_id,
    normalize_for_temp_id,
)

from .models import LookupRequest

logger = logging.getLogger(__name__)

# Exponential backoff schedule in minutes for retry attempts 1, 2, 3
# AC2: Failed requests use exponential backoff: 1min, 5min, 15min delays
BACKOFF_SCHEDULE_MINUTES: Tuple[int, ...] = (1, 5, 15)

# AC3: Maximum retry attempts before permanent failure
MAX_RETRY_ATTEMPTS: int = 3


class LookupQueueError(Exception):
    """Base exception for lookup queue operations."""

    pass


def calculate_next_retry_at(attempts: int) -> datetime:
    """
    Calculate next retry time with bounded exponential backoff.

    AC2: Delays for attempts 1/2/3 → 1min, 5min, 15min (capped at 15min).

    Args:
        attempts: Current attempt count (1-based after failure)

    Returns:
        UTC datetime for next retry attempt
    """
    # Clamp index to valid range (0 to len-1)
    idx = min(max(attempts - 1, 0), len(BACKOFF_SCHEDULE_MINUTES) - 1)
    delay_minutes = BACKOFF_SCHEDULE_MINUTES[idx]
    return datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)


def normalize_name(name: str) -> str:
    """
    Normalize company name for consistent lookup and duplicate detection.

    This function provides basic normalization to ensure consistent
    company name matching and prevent duplicate queue entries.

    Args:
        name: Original company name

    Returns:
        Normalized company name

    Examples:
        >>> normalize_name("  中国平安保险股份有限公司  ")
        "中国平安保险股份有限公司"
        >>> normalize_name("China Ping An Insurance")
        "china ping an insurance"
    """
    if not name:
        return ""

    # Unicode normalization
    normalized = unicodedata.normalize("NFKC", name)

    # Basic cleaning
    normalized = normalized.strip()

    # Convert ASCII to lowercase for consistency
    normalized = "".join(
        char.lower() if char.isascii() and char.isalpha() else char
        for char in normalized
    )

    # Remove excessive whitespace
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized


class LookupQueue:
    """
    Queue DAO for managing asynchronous EQC company lookup requests.

    Provides atomic operations for enqueueing, dequeueing, and processing
    lookup requests with proper concurrency control and error handling.
    Supports both plan_only mode for validation and execute mode for actual operations.

    Examples:
        >>> queue = LookupQueue(connection, plan_only=False)
        >>> request = queue.enqueue("中国平安", "中国平安保险")
        >>> requests = queue.dequeue(batch_size=10)
        >>> queue.mark_done(requests[0].id)
    """

    def __init__(self, connection, *, plan_only: bool = False):
        """
        Initialize lookup queue DAO.

        Args:
            connection: psycopg2 database connection
            plan_only: If True, only generate SQL plans without executing
        """
        self.connection = connection
        self.plan_only = plan_only

        logger.debug(
            "LookupQueue initialized",
            extra={"plan_only": plan_only, "has_connection": bool(connection)},
        )

    def enqueue(
        self, name: str, normalized_name: Optional[str] = None
    ) -> LookupRequest:
        """
        Enqueue a new lookup request for async processing.

        Args:
            name: Original company name to lookup
            normalized_name: Pre-normalized name (will auto-normalize if None)

        Returns:
            LookupRequest object representing the queued request

        Raises:
            LookupQueueError: If enqueue operation fails
            ValueError: If name is empty or invalid
        """
        if not name or not name.strip():
            raise ValueError("Name cannot be empty")

        cleaned_name = name.strip()
        norm_name = normalized_name or normalize_name(cleaned_name)

        if self.plan_only:
            # Return a mock request for plan-only mode
            mock_request = LookupRequest(
                id=1,
                name=cleaned_name,
                normalized_name=norm_name,
                status="pending",
                attempts=0,
                last_error=None,
            )
            logger.info(
                "PLAN ONLY: Would enqueue lookup request",
                extra={"company_name": cleaned_name, "normalized_name": norm_name},
            )
            return mock_request

        sql = """
            INSERT INTO enterprise.enrichment_requests (
                raw_name,
                normalized_name,
                status,
                attempts,
                next_retry_at
            )
            VALUES (%s, %s, 'pending', 0, NOW())
            RETURNING id,
                      raw_name AS name,
                      normalized_name,
                      status,
                      attempts,
                      last_error,
                      created_at,
                      updated_at
        """

        try:
            # Use default cursor to work well with mocked connections in tests
            with self.connection.cursor() as cursor:
                logger.debug(
                    "Enqueueing lookup request",
                    extra={"company_name": cleaned_name, "normalized_name": norm_name},
                )

                cursor.execute(sql, (cleaned_name, norm_name))
                row = cursor.fetchone()

                if not row:
                    raise LookupQueueError(
                        "Failed to enqueue lookup request - no row returned"
                    )

                # Support both tuple- and dict-like rows from cursor
                if isinstance(row, dict):
                    request = LookupRequest(**row)
                else:
                    # Fallback: attempt to map columns positionally if provided by DB
                    # Columns: id, name, normalized_name, status, attempts,
                    #          last_error, created_at, updated_at
                    try:
                        request = LookupRequest(
                            id=row[0],
                            name=row[1],
                            normalized_name=row[2],
                            status=row[3],
                            attempts=row[4],
                            last_error=row[5],
                            created_at=row[6],
                            updated_at=row[7],
                        )
                    except Exception as map_err:
                        raise LookupQueueError(
                            f"Failed to parse enqueued row: {map_err}"
                        )

                logger.info(
                    "Lookup request enqueued successfully",
                    extra={
                        "request_id": request.id,
                        "company_name": request.name,
                        "normalized_name": request.normalized_name,
                    },
                )

                return request

        except Exception as e:
            logger.error(
                "Database error during enqueue operation",
                extra={"company_name": cleaned_name, "error": str(e)},
            )
            raise LookupQueueError(f"Failed to enqueue lookup request: {e}")

    def dequeue(self, batch_size: int = 50) -> List[LookupRequest]:
        """
        Atomically dequeue pending requests for processing.

        Uses FOR UPDATE SKIP LOCKED to prevent race conditions between
        multiple workers. Sets status to 'processing' for dequeued items.

        Args:
            batch_size: Maximum number of requests to dequeue

        Returns:
            List of LookupRequest objects ready for processing

        Raises:
            LookupQueueError: If dequeue operation fails
            ValueError: If batch_size is invalid
        """
        if batch_size <= 0:
            raise ValueError("Batch size must be positive")

        if self.plan_only:
            # Return mock requests for plan-only mode
            mock_requests = [
                LookupRequest(
                    id=i + 1,
                    name=f"Test Company {i + 1}",
                    normalized_name=f"test company {i + 1}",
                    status="processing",
                    attempts=0,
                    last_error=None,
                )
                for i in range(min(batch_size, 3))  # Return up to 3 mock requests
            ]
            logger.info(
                "PLAN ONLY: Would dequeue requests",
                extra={"batch_size": batch_size, "mock_count": len(mock_requests)},
            )
            return mock_requests

        # Atomic dequeue with status update using CTE pattern to avoid
        # FOR UPDATE in subquery
        # AC2: Filter by next_retry_at <= NOW() for exponential backoff
        sql = """
            WITH pending AS (
                SELECT id FROM enterprise.enrichment_requests
                WHERE status = 'pending'
                  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                ORDER BY created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE enterprise.enrichment_requests
            SET status = 'processing', updated_at = now()
            FROM pending
            WHERE enterprise.enrichment_requests.id = pending.id
            RETURNING enterprise.enrichment_requests.id,
                      raw_name AS name,
                      normalized_name,
                      status,
                      attempts,
                      last_error,
                      created_at,
                      updated_at
        """

        try:
            # Use default cursor to work well with mocked connections in tests
            with self.connection.cursor() as cursor:
                logger.debug(
                    "Dequeueing requests for processing",
                    extra={"batch_size": batch_size},
                )

                cursor.execute(sql, (batch_size,))
                rows = cursor.fetchall()

                requests: List[LookupRequest] = []
                for row in rows:
                    if isinstance(row, dict):
                        requests.append(LookupRequest(**row))
                    else:
                        try:
                            requests.append(
                                LookupRequest(
                                    id=row[0],
                                    name=row[1],
                                    normalized_name=row[2],
                                    status=row[3],
                                    attempts=row[4],
                                    last_error=row[5],
                                    created_at=row[6],
                                    updated_at=row[7],
                                )
                            )
                        except Exception as map_err:
                            raise LookupQueueError(
                                f"Failed to parse dequeued row: {map_err}"
                            )

                logger.info(
                    "Requests dequeued successfully",
                    extra={
                        "dequeued_count": len(requests),
                        "requested_batch_size": batch_size,
                    },
                )

                return requests

        except Exception as e:
            logger.error(
                "Database error during dequeue operation",
                extra={"batch_size": batch_size, "error": str(e)},
            )
            raise LookupQueueError(f"Failed to dequeue requests: {e}")

    def mark_done(self, request_id: int) -> None:
        """
        Mark a request as successfully processed.

        Args:
            request_id: ID of the request to mark as done

        Raises:
            LookupQueueError: If mark operation fails
            ValueError: If request_id is invalid
        """
        if not request_id or request_id <= 0:
            raise ValueError("Request ID must be positive")

        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would mark request as done",
                extra={"request_id": request_id},
            )
            return

        sql = """
            UPDATE enterprise.enrichment_requests
            SET status = 'done', updated_at = now()
            WHERE id = %s AND status = 'processing'
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (request_id,))

                if cursor.rowcount == 0:
                    logger.warning(
                        "No request updated - may not exist or not in processing state",
                        extra={"request_id": request_id},
                    )
                    raise LookupQueueError(
                        f"Request {request_id} not found or not in processing state"
                    )

                logger.info("Request marked as done", extra={"request_id": request_id})

        except Exception as e:
            logger.error(
                "Database error during mark_done operation",
                extra={"request_id": request_id, "error": str(e)},
            )
            raise LookupQueueError(f"Failed to mark request as done: {e}")

    def mark_failed(self, request_id: int, error_message: str, attempts: int) -> None:
        """
        Mark a request as failed with error details.

        Args:
            request_id: ID of the request to mark as failed
            error_message: Error message describing the failure
            attempts: Updated attempt count

        Raises:
            LookupQueueError: If mark operation fails
            ValueError: If parameters are invalid
        """
        if not request_id or request_id <= 0:
            raise ValueError("Request ID must be positive")

        if attempts < 0:
            raise ValueError("Attempts must be non-negative")

        if not error_message:
            error_message = "Unknown error"

        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would mark request as failed",
                extra={"request_id": request_id, "attempts": attempts},
            )
            return

        # AC2/AC3: Determine if this is a permanent failure or retry with backoff
        if attempts >= MAX_RETRY_ATTEMPTS:
            # AC3: Permanently failed - no more retries
            sql = """
                UPDATE enterprise.enrichment_requests
                SET status = 'failed',
                    last_error = %s,
                    attempts = %s,
                    next_retry_at = NULL,
                    updated_at = now()
                WHERE id = %s AND status = 'processing'
            """
            params = (error_message, attempts, request_id)
            final_status = "failed"
        else:
            # AC2: Schedule retry with exponential backoff (keep as pending)
            next_retry = calculate_next_retry_at(attempts)
            sql = """
                UPDATE enterprise.enrichment_requests
                SET status = 'pending',
                    last_error = %s,
                    attempts = %s,
                    next_retry_at = %s,
                    updated_at = now()
                WHERE id = %s AND status = 'processing'
            """
            params = (error_message, attempts, next_retry, request_id)
            final_status = "pending"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)

                if cursor.rowcount == 0:
                    logger.warning(
                        "No request updated - may not exist or not in processing state",
                        extra={"request_id": request_id},
                    )
                    raise LookupQueueError(
                        f"Request {request_id} not found or not in processing state"
                    )

                logger.info(
                    "Request marked as %s",
                    final_status,
                    extra={
                        "request_id": request_id,
                        "attempts": attempts,
                        "max_attempts": MAX_RETRY_ATTEMPTS,
                        "error": error_message,
                        "will_retry": final_status == "pending",
                    },
                )

        except Exception as e:
            logger.error(
                "Database error during mark_failed operation",
                extra={"request_id": request_id, "error": str(e)},
            )
            raise LookupQueueError(f"Failed to mark request as failed: {e}")

    def get_next_temp_id(self, company_name: str) -> str:
        """
        Generate stable temporary ID using HMAC-SHA1.

        Same company name always produces same ID (deterministic).
        This enables idempotent pipeline runs and consistent IDs across environments.

        Story 6-2-P1: Refactored from database sequence to HMAC-SHA1 for determinism.

        Args:
            company_name: Company name to generate ID for

        Returns:
            Temporary ID in IN<16-char-Base32> format (e.g., INABCD1234EFGH5678)

        Raises:
            LookupQueueError: If temp ID generation fails
        """
        if self.plan_only:
            # Return deterministic mock for plan-only mode using shared normalization
            normalized = normalize_for_temp_id(company_name or "")
            if not normalized:
                normalized = "__empty__"
            mock_hash = hashlib.sha1(normalized.encode()).hexdigest()[:8]
            mock_temp_id = f"IN_{mock_hash.upper()}"
            logger.info(
                "PLAN ONLY: Would generate temp ID",
                extra={"mock_temp_id": mock_temp_id, "company_name": company_name},
            )
            return mock_temp_id

        try:
            # Get salt from environment
            salt = os.getenv("WDH_ALIAS_SALT")
            if not salt:
                logger.warning(
                    "WDH_ALIAS_SALT not set, using default development salt. "
                    "This should be configured in production for security."
                )
                salt = "default_dev_salt"

            temp_id = generate_temp_company_id(company_name or "", salt)

            logger.debug(
                "Generated temporary ID",
                extra={"company_name": company_name, "temp_id": temp_id},
            )

            return temp_id

        except Exception as e:
            logger.error(
                "Error during temp ID generation",
                extra={"company_name": company_name, "error": str(e)},
            )
            raise LookupQueueError(f"Failed to generate temp ID: {e}")

    def get_queue_stats(self) -> dict:
        """
        Get queue statistics for monitoring and debugging.

        Returns:
            Dictionary with queue statistics (pending, processing, done, failed counts)

        Raises:
            LookupQueueError: If stats query fails
        """
        if self.plan_only:
            # Return mock stats for plan-only mode
            mock_stats = {"pending": 5, "processing": 2, "done": 100, "failed": 3}
            logger.info(
                "PLAN ONLY: Would get queue stats", extra={"mock_stats": mock_stats}
            )
            return mock_stats

        sql = """
            SELECT
                status,
                COUNT(*) as count
            FROM enterprise.enrichment_requests
            GROUP BY status
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()

                stats = {row[0]: row[1] for row in rows}

                # Ensure all status types are represented
                for status in ["pending", "processing", "done", "failed"]:
                    if status not in stats:
                        stats[status] = 0

                logger.debug("Queue stats retrieved", extra={"stats": stats})

                return stats

        except Exception as e:
            logger.error("Database error during stats query", extra={"error": str(e)})
            raise LookupQueueError(f"Failed to get queue stats: {e}")

    def get_queue_depth(self, status: str = "pending", ready_only: bool = False) -> int:
        """
        Get count of requests with specified status for monitoring.

        AC4/AC5: Used for queue depth monitoring and sensor triggering.

        Args:
            status: Queue status to count (default: 'pending')
            ready_only: When True and status='pending', only count rows whose
                backoff window has elapsed (next_retry_at IS NULL OR <= NOW())

        Returns:
            Integer count of requests with specified status

        Raises:
            LookupQueueError: If query fails
        """
        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would get queue depth",
                extra={"status": status, "ready_only": ready_only, "mock_depth": 5},
            )
            return 5  # Mock value for plan-only mode

        # Apply backoff filter only to pending queue depth when requested
        backoff_clause = ""
        params = (status,)
        if status == "pending" and ready_only:
            backoff_clause = " AND (next_retry_at IS NULL OR next_retry_at <= NOW())"

        sql = (
            """
            SELECT COUNT(*) FROM enterprise.enrichment_requests
            WHERE status = %s
            """
            + backoff_clause
        )

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                row = cursor.fetchone()

                count = row[0] if row else 0

                logger.debug(
                    "Queue depth retrieved",
                    extra={"status": status, "count": count, "ready_only": ready_only},
                )

                return count

        except Exception as e:
            logger.error(
                "Database error during queue depth query",
                extra={"status": status, "error": str(e)},
            )
            raise LookupQueueError(f"Failed to get queue depth: {e}")

    def reset_stale_processing(self, stale_minutes: int = 15) -> int:
        """
        Reset stale 'processing' rows back to 'pending' for recovery.

        AC6: Startup recovery hook to resume interrupted batches.
        Rows older than stale_minutes in 'processing' status are reset
        to 'pending' with incremented attempts and backoff delay.

        Args:
            stale_minutes: Minutes after which processing rows are considered stale

        Returns:
            Number of rows reset

        Raises:
            LookupQueueError: If reset operation fails
        """
        if self.plan_only:
            logger.info(
                "PLAN ONLY: Would reset stale processing rows",
                extra={"stale_minutes": stale_minutes},
            )
            return 0

        # Reset stale processing rows back to pending with backoff that matches AC2
        sql = """
            UPDATE enterprise.enrichment_requests
            SET status = 'pending',
                attempts = attempts + 1,
                next_retry_at = CASE
                    WHEN attempts + 1 >= 3 THEN NOW() + INTERVAL '15 minutes'
                    WHEN attempts + 1 = 2 THEN NOW() + INTERVAL '5 minutes'
                    ELSE NOW() + INTERVAL '1 minute'
                END,
                updated_at = NOW()
            WHERE status = 'processing'
              AND updated_at < NOW() - INTERVAL '%s minutes'
            RETURNING id
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (stale_minutes,))
                reset_count = cursor.rowcount

                if reset_count > 0:
                    logger.warning(
                        "Reset stale processing rows to pending",
                        extra={
                            "reset_count": reset_count,
                            "stale_minutes": stale_minutes,
                        },
                    )
                else:
                    logger.debug(
                        "No stale processing rows found",
                        extra={"stale_minutes": stale_minutes},
                    )

                return reset_count

        except Exception as e:
            logger.error(
                "Database error during stale processing reset",
                extra={"stale_minutes": stale_minutes, "error": str(e)},
            )
            raise LookupQueueError(f"Failed to reset stale processing rows: {e}")
