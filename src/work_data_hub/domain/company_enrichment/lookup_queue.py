"""
Lookup queue DAO for asynchronous EQC company lookup processing.

This module provides atomic queue operations for managing EQC lookup requests
with proper concurrency control using PostgreSQL FOR UPDATE SKIP LOCKED patterns.
Supports both plan_only and execute modes for validation and execution.
"""

import logging
import re
import unicodedata
from typing import List, Optional

from .models import LookupRequest

logger = logging.getLogger(__name__)


class LookupQueueError(Exception):
    """Base exception for lookup queue operations."""
    pass


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
            extra={"plan_only": plan_only, "has_connection": bool(connection)}
        )

    def enqueue(self, name: str, normalized_name: Optional[str] = None) -> LookupRequest:
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
                last_error=None
            )
            logger.info(
                "PLAN ONLY: Would enqueue lookup request",
                extra={"company_name": cleaned_name, "normalized_name": norm_name}
            )
            return mock_request

        sql = """
            INSERT INTO enterprise.lookup_requests (name, normalized_name, status, attempts)
            VALUES (%s, %s, 'pending', 0)
            RETURNING id, name, normalized_name, status, attempts, last_error,
                      created_at, updated_at
        """

        try:
            # Use default cursor to work well with mocked connections in tests
            with self.connection.cursor() as cursor:
                logger.debug(
                    "Enqueueing lookup request",
                    extra={"company_name": cleaned_name, "normalized_name": norm_name}
                )

                cursor.execute(sql, (cleaned_name, norm_name))
                row = cursor.fetchone()

                if not row:
                    raise LookupQueueError("Failed to enqueue lookup request - no row returned")

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
                        "normalized_name": request.normalized_name
                    }
                )

                return request

        except Exception as e:
            logger.error(
                "Database error during enqueue operation",
                extra={"company_name": cleaned_name, "error": str(e)}
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
                    last_error=None
                )
                for i in range(min(batch_size, 3))  # Return up to 3 mock requests
            ]
            logger.info(
                "PLAN ONLY: Would dequeue requests",
                extra={"batch_size": batch_size, "mock_count": len(mock_requests)}
            )
            return mock_requests

        # Atomic dequeue with status update using CTE pattern to avoid FOR UPDATE in subquery
        sql = """
            WITH pending AS (
                SELECT id FROM enterprise.lookup_requests
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE enterprise.lookup_requests
            SET status = 'processing', updated_at = now()
            FROM pending
            WHERE enterprise.lookup_requests.id = pending.id
            RETURNING enterprise.lookup_requests.id, name, normalized_name, status,
                      attempts, last_error, created_at, updated_at
        """

        try:
            # Use default cursor to work well with mocked connections in tests
            with self.connection.cursor() as cursor:
                logger.debug(
                    "Dequeueing requests for processing",
                    extra={"batch_size": batch_size}
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
                        "requested_batch_size": batch_size
                    }
                )

                return requests

        except Exception as e:
            logger.error(
                "Database error during dequeue operation",
                extra={"batch_size": batch_size, "error": str(e)}
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
                extra={"request_id": request_id}
            )
            return

        sql = """
            UPDATE enterprise.lookup_requests
            SET status = 'done', updated_at = now()
            WHERE id = %s AND status = 'processing'
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (request_id,))

                if cursor.rowcount == 0:
                    logger.warning(
                        "No request updated - may not exist or not in processing state",
                        extra={"request_id": request_id}
                    )
                    raise LookupQueueError(
                        f"Request {request_id} not found or not in processing state"
                    )

                logger.info(
                    "Request marked as done",
                    extra={"request_id": request_id}
                )

        except Exception as e:
            logger.error(
                "Database error during mark_done operation",
                extra={"request_id": request_id, "error": str(e)}
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
                extra={"request_id": request_id, "attempts": attempts}
            )
            return

        sql = """
            UPDATE enterprise.lookup_requests
            SET status = 'failed', last_error = %s, attempts = %s, updated_at = now()
            WHERE id = %s AND status = 'processing'
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (error_message, attempts, request_id))

                if cursor.rowcount == 0:
                    logger.warning(
                        "No request updated - may not exist or not in processing state",
                        extra={"request_id": request_id}
                    )
                    raise LookupQueueError(
                        f"Request {request_id} not found or not in processing state"
                    )

                logger.info(
                    "Request marked as failed",
                    extra={
                        "request_id": request_id,
                        "attempts": attempts,
                        "error": error_message
                    }
                )

        except Exception as e:
            logger.error(
                "Database error during mark_failed operation",
                extra={"request_id": request_id, "error": str(e)}
            )
            raise LookupQueueError(f"Failed to mark request as failed: {e}")

    def get_next_temp_id(self) -> str:
        """
        Generate next temporary ID using atomic sequence increment.

        Uses UPDATE...RETURNING pattern for thread-safe ID generation
        across multiple workers and concurrent requests.

        Returns:
            Temporary ID in TEMP_NNNNNN format (e.g., TEMP_000001)

        Raises:
            LookupQueueError: If temp ID generation fails
        """
        if self.plan_only:
            # Return a mock temp ID for plan-only mode
            mock_temp_id = "TEMP_000001"
            logger.info(
                "PLAN ONLY: Would generate temp ID",
                extra={"mock_temp_id": mock_temp_id}
            )
            return mock_temp_id

        sql = """
            UPDATE enterprise.temp_id_sequence
            SET last_number = last_number + 1, updated_at = now()
            RETURNING last_number
        """

        try:
            with self.connection.cursor() as cursor:
                def _extract_sequence_value(result):
                    """Normalize cursor row into an integer sequence value."""
                    if result is None:
                        return None
                    if isinstance(result, dict):
                        value = result.get("last_number")
                        if value is not None:
                            return value
                        if len(result) == 1:
                            try:
                                return next(iter(result.values()))
                            except StopIteration:
                                return None
                        return None
                    try:
                        return result[0]
                    except (IndexError, TypeError):
                        return None

                cursor.execute(sql)
                row = cursor.fetchone()
                sequence_value = _extract_sequence_value(row)

                if sequence_value is None:
                    logger.debug(
                        "Temp ID sequence empty - seeding initial row",
                        extra={"bootstrap": True}
                    )
                    cursor.execute(
                        """
                        INSERT INTO enterprise.temp_id_sequence (last_number, updated_at)
                        SELECT 0, now()
                        WHERE NOT EXISTS (SELECT 1 FROM enterprise.temp_id_sequence)
                        """
                    )
                    cursor.execute(sql)
                    row = cursor.fetchone()
                    sequence_value = _extract_sequence_value(row)

                if sequence_value is None:
                    raise LookupQueueError(
                        "Failed to generate temp ID - no sequence value returned"
                    )

                temp_id = f"TEMP_{sequence_value:06d}"

                logger.debug(
                    "Generated temporary ID",
                    extra={"temp_id": temp_id, "sequence_value": sequence_value}
                )
                return temp_id

        except Exception as e:
            logger.error(
                "Database error during temp ID generation",
                extra={"error": str(e)}
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
                "PLAN ONLY: Would get queue stats",
                extra={"mock_stats": mock_stats}
            )
            return mock_stats

        sql = """
            SELECT
                status,
                COUNT(*) as count
            FROM enterprise.lookup_requests
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
            logger.error(
                "Database error during stats query",
                extra={"error": str(e)}
            )
            raise LookupQueueError(f"Failed to get queue stats: {e}")
