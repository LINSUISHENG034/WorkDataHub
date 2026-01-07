"""
YAML override resolution strategy.

This module handles Step 1 of the resolution priority: YAML overrides
with 3 priority levels (plan → hardcode → name).

Note: account and account_name priorities removed in Story 6.1.1 to align
with DB layer simplification (merged with customer_name or deemed unreliable).

Story 7.3: Infrastructure Layer Decomposition
"""

from typing import Dict, Tuple

import pandas as pd

from work_data_hub.infrastructure.enrichment.types import ResolutionStrategy

# YAML priority levels in resolution order
# Note: account/account_name removed - aligned with DB layer (Story 6.1.1)
YAML_PRIORITY_ORDER = ["plan", "hardcode", "name"]

# Special placeholder for "empty" company_id (excluded names)
# Usage in YAML: "保留账户管理": "__EMPTY__"
EMPTY_PLACEHOLDER = "__EMPTY__"


def resolve_via_yaml_overrides(
    df: pd.DataFrame,
    strategy: ResolutionStrategy,
    yaml_overrides: Dict[str, Dict[str, str]],
) -> Tuple[pd.Series, Dict[str, int]]:
    """
    Resolve company_id via YAML overrides (3 priority levels).

    Priority order: plan (1) → hardcode (2) → name (3)

    Special value "__EMPTY__" in YAML will resolve to empty string,
    treating the name as explicitly excluded from resolution.

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
    # Note: account/account_name removed - aligned with DB layer (Story 6.1.1)
    priority_columns = {
        "plan": strategy.plan_code_column,
        "hardcode": strategy.plan_code_column,  # Same as plan for hardcode
        "name": strategy.customer_name_column,
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

        # Convert __EMPTY__ placeholder to empty string
        lookup_values = lookup_values.replace(EMPTY_PLACEHOLDER, "")

        # Count hits: both non-NA values and empty strings (explicit exclusions)
        new_hits = lookup_values.notna()

        # Update resolved series with new values (avoid deprecated fillna downcasting)
        # Only update where lookup_values is not NA
        resolved_subset = resolved.loc[mask_unresolved].copy()
        update_mask = lookup_values.notna()
        resolved_subset.loc[update_mask] = lookup_values.loc[update_mask]
        resolved.loc[mask_unresolved] = resolved_subset
        hits_by_priority[priority] = int(new_hits.sum())

    return resolved, hits_by_priority
