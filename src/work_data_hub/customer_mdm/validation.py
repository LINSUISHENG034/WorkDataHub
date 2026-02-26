"""Data quality validation for customer status fields.

Story 7.6-11: Customer Status Field Enhancement
AC-5: Validate updated data distributions

Validation thresholds:
- is_strategic: 5-10% of records
- is_existing: > 70% of records
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import psycopg
from dotenv import load_dotenv
from structlog import get_logger

logger = get_logger(__name__)

# Validation thresholds
STRATEGIC_MIN_PCT = 5.0
STRATEGIC_MAX_PCT = 10.0
EXISTING_MIN_PCT = 70.0


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    actual_value: float
    expected_range: str
    message: str


@dataclass
class ValidationReport:
    """Complete validation report for a status year."""

    status_year: int
    total_records: int
    results: list[ValidationResult]

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def warnings(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.passed]


def validate_status_distribution(
    status_year: Optional[int] = None,
) -> ValidationReport:
    """Validate status field distributions for a given year.

    Args:
        status_year: Year to validate. If None, uses the latest year.

    Returns:
        ValidationReport with all check results.
    """
    load_dotenv(dotenv_path=".wdh_env", override=True)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment")

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            # Get reference year (for reporting only - we validate ALL contracts)
            if status_year is None:
                cur.execute('SELECT MAX(status_year) FROM customer."客户年金计划"')
                status_year = cur.fetchone()[0]

            # Get distribution stats for ALL contracts
            # (is_strategic/is_existing updated for all, not per status_year)
            cur.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN is_strategic THEN 1 ELSE 0 END) as strategic,
                    SUM(CASE WHEN is_existing THEN 1 ELSE 0 END) as existing,
                    SUM(CASE WHEN contract_status = '正常' THEN 1 ELSE 0 END) as normal
                FROM customer."客户年金计划"
                """
            )
            row = cur.fetchone()
            total, strategic, existing, normal = row

            results = []

            # Validate is_strategic (5-10%)
            strategic_pct = (strategic / total * 100) if total > 0 else 0
            results.append(_check_strategic(strategic_pct, strategic, total))

            # Validate is_existing (> 70%)
            existing_pct = (existing / total * 100) if total > 0 else 0
            results.append(_check_existing(existing_pct, existing, total))

            # Log results
            for r in results:
                if r.passed:
                    logger.info("Validation passed", check=r.name, value=r.actual_value)
                else:
                    logger.warning("Validation failed", check=r.name, **vars(r))

            return ValidationReport(
                status_year=status_year,
                total_records=total,
                results=results,
            )


def _check_strategic(pct: float, count: int, total: int) -> ValidationResult:
    """Check is_strategic distribution."""
    passed = STRATEGIC_MIN_PCT <= pct <= STRATEGIC_MAX_PCT
    return ValidationResult(
        name="is_strategic",
        passed=passed,
        actual_value=pct,
        expected_range=f"{STRATEGIC_MIN_PCT}-{STRATEGIC_MAX_PCT}%",
        message=f"{count}/{total} ({pct:.1f}%) records are strategic",
    )


def _check_existing(pct: float, count: int, total: int) -> ValidationResult:
    """Check is_existing distribution."""
    passed = pct >= EXISTING_MIN_PCT
    return ValidationResult(
        name="is_existing",
        passed=passed,
        actual_value=pct,
        expected_range=f">= {EXISTING_MIN_PCT}%",
        message=f"{count}/{total} ({pct:.1f}%) records are existing customers",
    )
