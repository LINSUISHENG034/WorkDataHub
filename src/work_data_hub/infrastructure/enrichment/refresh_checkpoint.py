"""
Refresh Checkpoint Model for resumable full refresh operations.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 5.2: Checkpoint model and persistence for resumable refresh

This module provides checkpoint functionality for long-running refresh operations,
allowing them to be paused and resumed without losing progress.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RefreshCheckpoint:
    """
    Checkpoint for tracking refresh operation progress.

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint.
        operation_type: Type of operation (e.g., "full_refresh", "stale_refresh").
        total_companies: Total number of companies to refresh.
        processed_companies: Number of companies processed so far.
        successful_companies: Number of successfully refreshed companies.
        failed_companies: Number of failed companies.
        failed_company_ids: List of company IDs that failed.
        company_ids: Stable ordered list of company IDs for resumable operations.
        next_index: Next index into company_ids to process on resume.
        current_batch: Current batch number.
        started_at: Timestamp when operation started.
        last_updated_at: Timestamp of last checkpoint update.
        completed_at: Timestamp when operation completed (None if in progress).
        checkpoint_file: Path to checkpoint file.
        verification: Optional post-refresh verification results (best-effort).
    """

    checkpoint_id: str
    operation_type: str
    total_companies: int
    processed_companies: int = 0
    successful_companies: int = 0
    failed_companies: int = 0
    failed_company_ids: List[str] = field(default_factory=list)
    company_ids: List[str] = field(default_factory=list)
    next_index: int = 0
    current_batch: int = 0
    started_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    checkpoint_file: Optional[str] = None
    verification: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.started_at is None:
            self.started_at = datetime.now().isoformat()
        if self.last_updated_at is None:
            self.last_updated_at = self.started_at

    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_companies == 0:
            return 0.0
        return (self.processed_companies / self.total_companies) * 100

    @property
    def is_completed(self) -> bool:
        """Check if operation is completed."""
        return self.completed_at is not None

    @property
    def remaining_companies(self) -> int:
        """Calculate remaining companies to process."""
        return self.total_companies - self.processed_companies

    def update_progress(
        self,
        processed: int,
        successful: int,
        failed: int,
        failed_ids: List[str],
        batch: int,
        *,
        next_index: Optional[int] = None,
    ) -> None:
        """
        Update checkpoint with progress information.

        Args:
            processed: Number of companies processed in this batch.
            successful: Number of successful refreshes in this batch.
            failed: Number of failed refreshes in this batch.
            failed_ids: List of company IDs that failed in this batch.
            batch: Current batch number.
        """
        self.processed_companies += processed
        self.successful_companies += successful
        self.failed_companies += failed
        if failed_ids:
            existing = set(self.failed_company_ids)
            for failed_id in failed_ids:
                if failed_id and failed_id not in existing:
                    self.failed_company_ids.append(failed_id)
                    existing.add(failed_id)
        self.current_batch = batch
        if next_index is not None:
            self.next_index = max(0, int(next_index))
        self.last_updated_at = datetime.now().isoformat()

    def mark_completed(self) -> None:
        """Mark operation as completed."""
        self.completed_at = datetime.now().isoformat()
        self.last_updated_at = self.completed_at

    def to_dict(self) -> dict:
        """Convert checkpoint to dictionary for serialization."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "operation_type": self.operation_type,
            "total_companies": self.total_companies,
            "processed_companies": self.processed_companies,
            "successful_companies": self.successful_companies,
            "failed_companies": self.failed_companies,
            "failed_company_ids": self.failed_company_ids,
            "company_ids": self.company_ids,
            "next_index": self.next_index,
            "current_batch": self.current_batch,
            "started_at": self.started_at,
            "last_updated_at": self.last_updated_at,
            "completed_at": self.completed_at,
            "checkpoint_file": self.checkpoint_file,
            "verification": self.verification,
            "progress_percentage": self.progress_percentage,
            "remaining_companies": self.remaining_companies,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RefreshCheckpoint":
        """Create checkpoint from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            operation_type=data["operation_type"],
            total_companies=data["total_companies"],
            processed_companies=data.get("processed_companies", 0),
            successful_companies=data.get("successful_companies", 0),
            failed_companies=data.get("failed_companies", 0),
            failed_company_ids=data.get("failed_company_ids", []),
            company_ids=data.get("company_ids", []),
            next_index=data.get("next_index", 0),
            current_batch=data.get("current_batch", 0),
            started_at=data.get("started_at"),
            last_updated_at=data.get("last_updated_at"),
            completed_at=data.get("completed_at"),
            checkpoint_file=data.get("checkpoint_file"),
            verification=data.get("verification", {}) or {},
        )

    def save(self, checkpoint_dir: Path) -> Path:
        """
        Save checkpoint to file.

        Args:
            checkpoint_dir: Directory to save checkpoint file.

        Returns:
            Path to saved checkpoint file.
        """
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_file = checkpoint_dir / f"{self.checkpoint_id}.json"
        self.checkpoint_file = str(checkpoint_file)

        with checkpoint_file.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

        logger.debug(
            "refresh_checkpoint.saved",
            checkpoint_id=self.checkpoint_id,
            file=str(checkpoint_file),
        )

        return checkpoint_file

    @classmethod
    def load(cls, checkpoint_file: Path) -> "RefreshCheckpoint":
        """
        Load checkpoint from file.

        Args:
            checkpoint_file: Path to checkpoint file.

        Returns:
            RefreshCheckpoint instance.

        Raises:
            FileNotFoundError: If checkpoint file doesn't exist.
            ValueError: If checkpoint file is invalid.
        """
        if not checkpoint_file.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_file}")

        try:
            with checkpoint_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            checkpoint = cls.from_dict(data)

            logger.info(
                "refresh_checkpoint.loaded",
                checkpoint_id=checkpoint.checkpoint_id,
                progress=f"{checkpoint.progress_percentage:.1f}%",
            )

            return checkpoint

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid checkpoint file: {e}")

    @classmethod
    def find_latest(cls, checkpoint_dir: Path, operation_type: str) -> Optional["RefreshCheckpoint"]:
        """
        Find the latest incomplete checkpoint for given operation type.

        Args:
            checkpoint_dir: Directory containing checkpoint files.
            operation_type: Type of operation to search for.

        Returns:
            Latest incomplete checkpoint, or None if not found.
        """
        if not checkpoint_dir.exists():
            return None

        checkpoints = []
        for checkpoint_file in checkpoint_dir.glob("*.json"):
            try:
                checkpoint = cls.load(checkpoint_file)
                if checkpoint.operation_type == operation_type and not checkpoint.is_completed:
                    checkpoints.append(checkpoint)
            except (FileNotFoundError, ValueError):
                continue

        if not checkpoints:
            return None

        # Return the most recently updated checkpoint
        return max(checkpoints, key=lambda c: c.last_updated_at or "")
