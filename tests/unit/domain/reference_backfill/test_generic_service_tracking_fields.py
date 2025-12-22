"""Smoke tests for GenericBackfillService tracking fields (Story 6.2.2).

Runs without a database to provide local coverage even when integration
tests are skipped (e.g., no PostgreSQL available). Verifies tracking
fields are added correctly in plan-only scenarios.
"""

from __future__ import annotations

import pandas as pd

from work_data_hub.domain.reference_backfill.generic_service import (
    GenericBackfillService,
)


def test_add_tracking_fields_plan_only_smoke():
    """Ensure tracking fields are populated when no DB is used (plan_only path)."""
    service = GenericBackfillService(domain="annuity_performance")
    df = pd.DataFrame([{"年金计划号": "PLN-001"}])

    enriched = service._add_tracking_fields(df)  # noqa: SLF001 (smoke-level access)

    assert set(
        ["_source", "_needs_review", "_derived_from_domain", "_derived_at"]
    ).issubset(set(enriched.columns))
    assert enriched.loc[0, "_source"] == "auto_derived"
    assert bool(enriched.loc[0, "_needs_review"]) is True
    assert enriched.loc[0, "_derived_from_domain"] == "annuity_performance"
    assert isinstance(enriched.loc[0, "_derived_at"], str)
