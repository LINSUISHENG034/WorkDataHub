"""Config-driven status evaluation engine.

Story 7.6-18: Config-Driven Status Evaluation Framework

This module provides a StatusEvaluator class that generates SQL fragments
from configuration, replacing hardcoded SQL in snapshot_refresh.py.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from structlog import get_logger

from work_data_hub.infrastructure.settings.customer_status_schema import (
    DEFAULT_CONFIG_PATH,
    ConditionConfig,
    EvaluationRule,
    load_customer_status_config,
)

# Pattern for valid SQL identifiers (alphanumeric, underscore, Chinese characters)
_SAFE_IDENTIFIER_PATTERN = re.compile(
    r"^[a-zA-Z_\u4e00-\u9fff][a-zA-Z0-9_\u4e00-\u9fff]*$"
)

logger = get_logger(__name__)


class StatusEvaluator:
    """Config-driven status evaluation engine.

    Generates SQL fragments for status evaluation based on YAML configuration.
    This allows business rules to be modified without code changes.

    Example:
        evaluator = StatusEvaluator()
        sql = evaluator.generate_sql_fragment(
            "is_winning_this_year",
            table_alias="c",
            params={"snapshot_year": 2026}
        )
    """

    def __init__(
        self,
        config_path: str = DEFAULT_CONFIG_PATH,
    ) -> None:
        """Initialize StatusEvaluator with configuration.

        Args:
            config_path: Path to the configuration file
        """
        self.config = load_customer_status_config(config_path)
        self._sql_generators = {
            "exists_in_year": self._generate_exists_in_year,
            "field_equals": self._generate_field_equals,
            "status_reference": self._generate_status_reference,
            "negation": self._generate_negation,
            "aggregated_field": self._generate_aggregated_field,
            "disappeared": self._generate_disappeared,
            "first_appearance": self._generate_first_appearance,
        }
        logger.debug(
            "status_evaluator.initialized",
            config_path=config_path,
            rules_count=len(self.config.evaluation_rules),
        )

    def _validate_identifier(self, name: str, context: str) -> str:
        """Validate SQL identifier to prevent injection.

        Args:
            name: The identifier to validate
            context: Description of where this identifier is used (for error messages)

        Returns:
            The validated identifier (unchanged if valid)

        Raises:
            ValueError: If the identifier contains invalid characters
        """
        if not _SAFE_IDENTIFIER_PATTERN.match(name):
            raise ValueError(f"Invalid SQL identifier in {context}: {name}")
        return name

    def generate_sql_fragment(
        self,
        status_name: str,
        table_alias: str,
        params: Dict[str, Any],
    ) -> str:
        """Generate SQL fragment for a status evaluation.

        Args:
            status_name: Name of the status to evaluate
            table_alias: Alias of the main table in the query
            params: Query parameters (e.g., snapshot_year)

        Returns:
            SQL fragment string for the status evaluation

        Raises:
            KeyError: If status_name not found in config
        """
        if status_name not in self.config.evaluation_rules:
            raise KeyError(f"Unknown status: {status_name}")

        rule = self.config.evaluation_rules[status_name]

        logger.debug(
            "status_evaluator.generating_sql",
            status=status_name,
            conditions_count=len(rule.conditions),
            operator=rule.operator,
        )

        condition_sqls = []
        for condition in rule.conditions:
            generator = self._sql_generators.get(condition.type)
            if generator is None:
                raise ValueError(f"Unknown condition type: {condition.type}")

            sql = generator(condition, table_alias, params, rule)
            condition_sqls.append(sql)

        # Combine conditions with operator
        if len(condition_sqls) == 1:
            return condition_sqls[0]

        joiner = " OR " if rule.operator == "OR" else " AND "
        combined = joiner.join(f"({sql})" for sql in condition_sqls)
        return f"({combined})"

    def _generate_exists_in_year(
        self,
        condition: ConditionConfig,
        table_alias: str,
        params: Dict[str, object],
        rule: EvaluationRule,
    ) -> str:
        """Generate EXISTS subquery for year-based check."""
        source_name = condition.source
        source_config = self.config.sources[source_name]

        schema = source_config.schema_name
        table = source_config.table
        year_field = self._validate_identifier(
            condition.year_field, "exists_in_year.year_field"
        )

        # Build match conditions with validated field names
        match_conditions = []
        for match in condition.match_fields:
            src_field = self._validate_identifier(
                match.source_field, "exists_in_year.source_field"
            )
            tgt_field = self._validate_identifier(
                match.target_field, "exists_in_year.target_field"
            )
            match_conditions.append(f"sub.{tgt_field} = {table_alias}.{src_field}")

        match_sql = " AND ".join(match_conditions)

        return f"""EXISTS (
            SELECT 1 FROM {schema}."{table}" sub
            WHERE {match_sql}
              AND EXTRACT(YEAR FROM sub.{year_field}) = %(snapshot_year)s
        )"""

    def _generate_field_equals(
        self,
        condition: ConditionConfig,
        table_alias: str,
        params: Dict[str, object],
        rule: EvaluationRule,
    ) -> str:
        """Generate field equality check.

        Uses parameterized queries to prevent SQL injection.
        """
        field = self._validate_identifier(condition.field, "field_equals.field")
        value = condition.value

        # Generate unique parameter name to avoid collisions
        param_name = f"field_eq_{field}_{id(condition)}"
        params[param_name] = value
        return f"{table_alias}.{field} = %({param_name})s"

    def _generate_status_reference(
        self,
        condition: ConditionConfig,
        table_alias: str,
        params: Dict[str, object],
        rule: EvaluationRule,
    ) -> str:
        """Generate reference to another status evaluation."""
        referenced_status = condition.status
        return self.generate_sql_fragment(referenced_status, table_alias, params)

    def _generate_negation(
        self,
        condition: ConditionConfig,
        table_alias: str,
        params: Dict[str, object],
        rule: EvaluationRule,
    ) -> str:
        """Generate NOT wrapper for nested condition."""
        nested = condition.condition
        nested_type = nested.get("type")

        if nested_type == "aggregated_field":
            field = self._validate_identifier(
                nested.get("field"), "negation.nested.field"
            )
            agg = nested.get("aggregation", "BOOL_OR")
            # Validate aggregation function (whitelist approach)
            allowed_aggs = {"BOOL_OR", "BOOL_AND", "SUM", "COUNT", "MAX", "MIN", "AVG"}
            if agg not in allowed_aggs:
                raise ValueError(f"Invalid aggregation function: {agg}")
            return f"NOT {agg}({table_alias}.{field})"

        raise ValueError(
            f"Unsupported nested condition type in negation: {nested_type}"
        )

    def _generate_aggregated_field(
        self,
        condition: ConditionConfig,
        table_alias: str,
        params: Dict[str, object],
        rule: EvaluationRule,
    ) -> str:
        """Generate aggregated field reference."""
        field = self._validate_identifier(condition.field, "aggregated_field.field")
        agg = condition.aggregation or "BOOL_OR"
        # Validate aggregation function (whitelist approach)
        allowed_aggs = {"BOOL_OR", "BOOL_AND", "SUM", "COUNT", "MAX", "MIN", "AVG"}
        if agg not in allowed_aggs:
            raise ValueError(f"Invalid aggregation function: {agg}")
        return f"{agg}({table_alias}.{field})"

    def _generate_disappeared(
        self,
        condition: ConditionConfig,
        table_alias: str,
        params: Dict[str, object],
        rule: EvaluationRule,
    ) -> str:
        """Generate condition for records that disappeared.

        Records existed in previous period but not in current period.

        Config fields:
            source: Source table reference
            period_field: Field containing the period (e.g., snapshot_month)
            match_fields: Fields to match between periods
            scope_field: Optional scope field (e.g., product_line_code)
        """
        source_name = condition.source
        source_config = self.config.sources[source_name]

        schema = source_config.schema_name
        table = source_config.table
        period_field = self._validate_identifier(
            condition.period_field, "disappeared.period_field"
        )

        # Build match conditions
        match_conditions = []
        for match in condition.match_fields:
            src_field = self._validate_identifier(
                match.source_field, "disappeared.source_field"
            )
            tgt_field = self._validate_identifier(
                match.target_field, "disappeared.target_field"
            )
            match_conditions.append(f"prev.{tgt_field} = {table_alias}.{src_field}")

        match_sql = " AND ".join(match_conditions)

        # Optional scope field for additional filtering
        scope_sql = ""
        if condition.scope_field:
            scope_field = self._validate_identifier(
                condition.scope_field, "disappeared.scope_field"
            )
            scope_sql = f" AND prev.{scope_field} = {table_alias}.{scope_field}"

        # Build replacement strings for curr alias
        curr_match = match_sql.replace("prev.", "curr.")
        curr_scope = scope_sql.replace("prev.", "curr.")

        # Existed in previous period but not in current
        # Uses interval arithmetic to find previous month
        prev_period = (
            f"prev.{period_field} = {table_alias}.{period_field} - INTERVAL '1 month'"
        )
        curr_period = f"curr.{period_field} = {table_alias}.{period_field}"

        return f"""(
            EXISTS (
                SELECT 1 FROM {schema}."{table}" prev
                WHERE {match_sql}{scope_sql}
                  AND {prev_period}
            )
            AND NOT EXISTS (
                SELECT 1 FROM {schema}."{table}" curr
                WHERE {curr_match}{curr_scope}
                  AND {curr_period}
            )
        )"""

    def _generate_first_appearance(
        self,
        condition: ConditionConfig,
        table_alias: str,
        params: Dict[str, object],
        rule: EvaluationRule,
    ) -> str:
        """Generate condition for first-time appearance in source.

        This checks if the current record is the first time this entity
        appears in the source table (no prior records exist).

        Config fields:
            source: Source table reference
            period_field: Field containing the period (e.g., snapshot_month)
            match_fields: Fields to match for identity
            scope_field: Optional field to scope the comparison
        """
        source_name = condition.source
        source_config = self.config.sources[source_name]

        schema = source_config.schema_name
        table = source_config.table
        period_field = self._validate_identifier(
            condition.period_field, "first_appearance.period_field"
        )

        # Build match conditions
        match_conditions = []
        for match in condition.match_fields:
            src_field = self._validate_identifier(
                match.source_field, "first_appearance.source_field"
            )
            tgt_field = self._validate_identifier(
                match.target_field, "first_appearance.target_field"
            )
            match_conditions.append(f"hist.{tgt_field} = {table_alias}.{src_field}")

        match_sql = " AND ".join(match_conditions)

        # Optional scope field
        scope_sql = ""
        if condition.scope_field:
            scope_field = self._validate_identifier(
                condition.scope_field, "first_appearance.scope_field"
            )
            scope_sql = f" AND hist.{scope_field} = {table_alias}.{scope_field}"

        # No records exist before current period
        return f"""NOT EXISTS (
            SELECT 1 FROM {schema}."{table}" hist
            WHERE {match_sql}{scope_sql}
              AND hist.{period_field} < {table_alias}.{period_field}
        )"""

    def get_status_names(self) -> List[str]:
        """Get list of all configured status names."""
        return list(self.config.evaluation_rules.keys())

    def get_status_description(self, status_name: str) -> str:
        """Get human-readable description for a status."""
        if status_name not in self.config.status_definitions:
            return ""
        return self.config.status_definitions[status_name].description
