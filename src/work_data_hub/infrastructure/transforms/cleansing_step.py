"""
Cleansing step for pipeline transformation.

Story 5.6: Implement Standard Pipeline Steps
Architecture Decision AD-010: Infrastructure Layer & Pipeline Composition

This module provides CleansingStep that integrates with infrastructure/cleansing/
to apply domain-specific cleansing rules to DataFrame columns.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import structlog

from work_data_hub.domain.pipelines.types import PipelineContext
from work_data_hub.infrastructure.cleansing import registry

from .base import TransformStep

logger = structlog.get_logger(__name__)


class CleansingStep(TransformStep):
    """
    Apply cleansing rules to specified columns using the cleansing registry.

    This step integrates with infrastructure/cleansing/ to apply domain-specific
    cleansing rules (trim_whitespace, normalize_company_name, etc.) to columns.

    Example:
        >>> # Simple usage - lookup rules by domain
        >>> step = CleansingStep(domain="annuity_performance")
        >>>
        >>> # With explicit rules override
        >>> step = CleansingStep(
        ...     domain="annuity_performance",
        ...     rules_override={"客户名称": ["trim_whitespace"]}
        ... )
        >>> df_out = step.apply(df_in, context)
    """

    def __init__(
        self,
        domain: str,
        columns: Optional[List[str]] = None,
        rules_override: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """
        Initialize cleansing step.

        Args:
            domain: Domain name for looking up cleansing rules from registry
            columns: Specific columns to cleanse (None = all configured columns)
            rules_override: Explicit rules map (overrides registry lookup if provided)
        """
        self._domain = domain
        self._columns = columns
        self._rules_override = rules_override

    @property
    def name(self) -> str:
        """Return human-friendly step name used for logging."""
        return "CleansingStep"

    def apply(self, df: pd.DataFrame, context: PipelineContext) -> pd.DataFrame:
        """Apply cleansing rules to specified columns."""
        log = logger.bind(
            step=self.name,
            domain=self._domain,
            pipeline=context.pipeline_name,
        )

        result = df.copy()
        columns_to_cleanse = self._columns or list(df.columns)
        cleansed_count = 0
        columns_processed = 0

        for column in columns_to_cleanse:
            if column not in result.columns:
                continue

            # Get rules from override or registry
            if self._rules_override and column in self._rules_override:
                rule_specs = self._rules_override[column]
            else:
                rule_specs = registry.get_domain_rules(self._domain, column)

            if not rule_specs:
                continue

            columns_processed += 1

            try:
                # Apply registry rules with support for rule kwargs via apply_rules
                result[column] = result[column].apply(
                    lambda value: registry.apply_rules(value, rule_specs)
                )
                cleansed_count += len(rule_specs)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "cleansing_rule_failed",
                    column=column,
                    rules=rule_specs,
                    error=str(exc),
                )

        log.info(
            "cleansing_applied",
            columns_processed=columns_processed,
            rules_applied=cleansed_count,
        )

        return result
