"""
CSV export functionality for enrichment observability.

This module provides infrastructure-layer file I/O for exporting unknown
company records to CSV files for manual backfill review.

Story 6.8: Enrichment Observability and Export (AC2, AC3, AC8)
"""

import csv
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from work_data_hub.domain.company_enrichment.observability import (
    EnrichmentObserver,
    UnknownCompanyRecord,
)

logger = logging.getLogger(__name__)


def write_unknown_companies_csv(
    rows: List[List[str]],
    output_dir: str = "logs/",
) -> Optional[Path]:
    """
    Write unknown companies to CSV file.

    Infrastructure-layer function that handles file I/O for CSV export.
    Creates output directory if it doesn't exist.

    Args:
        rows: List of CSV row values (from observer.get_unknown_company_rows())
        output_dir: Directory for CSV output (default: "logs/")

    Returns:
        Path to created CSV file, or None if no rows to export

    Raises:
        OSError: If directory creation or file writing fails
    """
    if not rows:
        logger.info("No unknown companies to export")
        return None

    output_path = Path(output_dir)

    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(
            "Failed to create output directory",
            extra={"output_dir": str(output_path), "error": str(e)},
        )
        raise

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    filepath = output_path / f"unknown_companies_{timestamp}_{suffix}.csv"

    try:
        with filepath.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(UnknownCompanyRecord.csv_headers())
            writer.writerows(rows)

        logger.info(
            "Exported unknown companies to CSV",
            extra={"filepath": str(filepath), "count": len(rows)},
        )
        return filepath

    except OSError as e:
        logger.error(
            "Failed to write CSV file",
            extra={"filepath": str(filepath), "error": str(e)},
        )
        raise


def export_unknown_companies(
    observer: EnrichmentObserver,
    output_dir: str = "logs/",
) -> Optional[Path]:
    """
    Export unknown companies from observer to CSV file.

    Convenience function that combines domain data extraction with
    infrastructure file I/O.

    Args:
        observer: EnrichmentObserver instance with recorded unknown companies
        output_dir: Directory for CSV output (default: "logs/")

    Returns:
        Path to created CSV file, or None if no unknown companies
    """
    if not observer.has_unknown_companies():
        logger.debug("No unknown companies recorded in observer")
        return None

    rows = observer.get_unknown_company_rows()
    return write_unknown_companies_csv(rows, output_dir)
