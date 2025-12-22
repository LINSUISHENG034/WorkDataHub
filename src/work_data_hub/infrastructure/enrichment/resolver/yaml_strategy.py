"""
YAML override resolution strategy.

This module handles Step 1 of the resolution priority: YAML overrides
with 5 priority levels (plan → account → hardcode → name → account_name).

Story 7.3: Infrastructure Layer Decomposition
"""

from typing import Dict, Tuple

import pandas as pd

from ..types import ResolutionStrategy

# YAML priority levels in resolution order
YAML_PRIORITY_ORDER = ["plan", "account", "hardcode", "name", "account_name"]


def resolve_via_yaml_overrides(
    df: pd.DataFrame,
    strategy: ResolutionStrategy,
    yaml_overrides: Dict[str, Dict[str, str]],
) -> Tuple[pd.Series, Dict[str, int]]:
    """
    Resolve company_id via YAML overrides (5 priority levels).

    Priority order: plan (1) → account (2) → hardcode (3) →
    name (4) → account_name (5)

    Args:
        df: Input DataFrame.
        strategy: Resolution strategy configuration.
        yaml_overrides: Dict of priority level -> {alias: company_id} mappings.

    Returns:
        Tuple of (resolved_series, hits_by_priority)
    """
    resolved = pd.Series(pd.NA, index=df.index, dtype=object)
    hits_by_priority: Dict[str, int] = {}

    # Map priority levels to columns
    priority_columns = {
        "plan": strategy.plan_code_column,
        "account": strategy.account_number_column,
        "hardcode": strategy.plan_code_column,  # Same as plan for hardcode
        "name": strategy.customer_name_column,
        "account_name": strategy.account_name_column,
    }

    for priority in YAML_PRIORITY_ORDER:
        column = priority_columns.get(priority)
        if not column or column not in df.columns:
            hits_by_priority[priority] = 0
            continue

        mappings = yaml_overrides.get(priority, {})
        if not mappings:
            hits_by_priority[priority] = 0
            continue

        # Vectorized lookup for unresolved rows
        mask_unresolved = resolved.isna()
        if not mask_unresolved.any():
            hits_by_priority[priority] = 0
            break

        # Map values to company IDs
        lookup_values = df.loc[mask_unresolved, column].map(mappings)
        new_hits = lookup_values.notna()

        # Update resolved series
        resolved.loc[mask_unresolved] = resolved.loc[mask_unresolved].fillna(
            lookup_values
        )
        hits_by_priority[priority] = int(new_hits.sum())

    return resolved, hits_by_priority
