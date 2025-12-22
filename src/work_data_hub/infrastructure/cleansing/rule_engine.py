"""
Data Cleansing Rule Engine for EQC Business Info.

Story 6.2-P5: EQC Data Persistence & Legacy Table Integration
Task 4.2: Thin wrapper around cleansing registry for EQC business_info fields

This module provides a high-level interface for applying cleansing rules
to EQC business data, with support for:
- Pattern extraction (e.g., "万元/亿元")
- Type conversion
- Date parsing
- Null handling
- Cleansing status tracking
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from work_data_hub.infrastructure.cleansing.registry import CleansingRegistry
from work_data_hub.infrastructure.cleansing.rules import (  # noqa: F401
    date_rules,
    numeric_rules,
    string_rules,
)
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FieldCleansingResult:
    """
    Result of cleansing a single field.

    Attributes:
        field_name: Name of the field that was cleansed.
        original_value: Original value before cleansing.
        cleansed_value: Value after cleansing.
        rules_applied: List of rule names that were applied.
        success: Whether cleansing succeeded without errors.
        error: Error message if cleansing failed.
    """

    field_name: str
    original_value: Any
    cleansed_value: Any
    rules_applied: List[str]
    success: bool = True
    error: Optional[str] = None


@dataclass
class RecordCleansingResult:
    """
    Result of cleansing an entire record.

    Attributes:
        domain: Domain name (e.g., "eqc_business_info").
        fields_cleansed: Number of fields successfully cleansed.
        fields_failed: Number of fields that failed cleansing.
        field_results: Detailed results for each field.
        cleansing_status: JSONB-compatible status object.
    """

    domain: str
    fields_cleansed: int = 0
    fields_failed: int = 0
    field_results: List[FieldCleansingResult] = field(default_factory=list)

    @property
    def cleansing_status(self) -> Dict[str, Any]:
        """
        Generate JSONB-compatible cleansing status.

        Returns:
            Dict with cleansing metadata for persistence.
        """
        return {
            "domain": self.domain,
            "fields_cleansed": self.fields_cleansed,
            "fields_failed": self.fields_failed,
            "failed_fields": [
                {
                    "field": result.field_name,
                    "error": result.error,
                }
                for result in self.field_results
                if not result.success
            ],
        }


class CleansingRuleEngine:
    """
    High-level interface for applying cleansing rules to EQC business data.

    This is a thin wrapper around CleansingRegistry that provides:
    - Domain-aware field cleansing
    - Batch record processing
    - Cleansing status tracking
    - Error handling and logging

    Example:
        >>> engine = CleansingRuleEngine()
        >>> record = {"companyId": "123", "reg_cap": "1,000万元"}
        >>> result = engine.cleanse_record("eqc_business_info", record)
        >>> print(result.cleansing_status)
    """

    def __init__(self, registry: Optional[CleansingRegistry] = None) -> None:
        """
        Initialize CleansingRuleEngine.

        Args:
            registry: Optional CleansingRegistry instance. If None, uses singleton.
        """
        self.registry = registry or CleansingRegistry()

    def cleanse_field(
        self,
        domain: str,
        field_name: str,
        value: Any,
    ) -> FieldCleansingResult:
        """
        Cleanse a single field value using domain-specific rules.

        Args:
            domain: Domain name (e.g., "eqc_business_info").
            field_name: Field name (e.g., "reg_cap").
            value: Original field value.

        Returns:
            FieldCleansingResult with cleansing outcome.

        Example:
            >>> engine = CleansingRuleEngine()
            >>> result = engine.cleanse_field("eqc_business_info", "reg_cap", "1,000万元")
            >>> print(result.cleansed_value)  # 10000000.0
        """
        # Get rules for this domain + field
        rule_specs = self.registry.get_domain_rules(domain, field_name)

        if not rule_specs:
            # No rules configured - return original value
            return FieldCleansingResult(
                field_name=field_name,
                original_value=value,
                cleansed_value=value,
                rules_applied=[],
                success=True,
            )

        # Apply rules
        try:
            cleansed_value = self.registry.apply_rules(value, rule_specs)

            # Extract rule names for tracking
            rule_names = []
            for spec in rule_specs:
                if isinstance(spec, str):
                    rule_names.append(spec)
                elif isinstance(spec, dict):
                    rule_names.append(spec.get("name", "unknown"))

            return FieldCleansingResult(
                field_name=field_name,
                original_value=value,
                cleansed_value=cleansed_value,
                rules_applied=rule_names,
                success=True,
            )

        except Exception as e:
            logger.warning(
                "cleansing_rule_engine.field_cleansing_failed",
                domain=domain,
                field=field_name,
                error=str(e),
            )

            return FieldCleansingResult(
                field_name=field_name,
                original_value=value,
                cleansed_value=value,  # Return original on error
                rules_applied=[],
                success=False,
                error=str(e),
            )

    def cleanse_record(
        self,
        domain: str,
        record: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> RecordCleansingResult:
        """
        Cleanse all fields in a record using domain-specific rules.

        Args:
            domain: Domain name (e.g., "eqc_business_info").
            record: Record dict with field names as keys.
            fields: Optional list of fields to cleanse. If None, cleanses all fields.

        Returns:
            RecordCleansingResult with cleansing outcomes and status.

        Example:
            >>> engine = CleansingRuleEngine()
            >>> record = {
            ...     "companyId": "  123  ",
            ...     "reg_cap": "1,000万元",
            ...     "companyFullName": "  Test Company  ",
            ... }
            >>> result = engine.cleanse_record("eqc_business_info", record)
            >>> print(result.fields_cleansed)  # 3
        """
        result = RecordCleansingResult(domain=domain)

        # Determine which fields to cleanse
        fields_to_cleanse = fields if fields is not None else list(record.keys())

        for field_name in fields_to_cleanse:
            if field_name not in record:
                continue

            value = record[field_name]

            # Cleanse field
            field_result = self.cleanse_field(domain, field_name, value)
            result.field_results.append(field_result)

            # Update record with cleansed value
            record[field_name] = field_result.cleansed_value

            # Update counters
            if field_result.success:
                result.fields_cleansed += 1
            else:
                result.fields_failed += 1

        logger.debug(
            "cleansing_rule_engine.record_cleansed",
            domain=domain,
            fields_cleansed=result.fields_cleansed,
            fields_failed=result.fields_failed,
        )

        return result

    def cleanse_batch(
        self,
        domain: str,
        records: List[Dict[str, Any]],
        fields: Optional[List[str]] = None,
    ) -> List[RecordCleansingResult]:
        """
        Cleanse multiple records in batch.

        Args:
            domain: Domain name (e.g., "eqc_business_info").
            records: List of record dicts.
            fields: Optional list of fields to cleanse in each record.

        Returns:
            List of RecordCleansingResult, one per record.

        Example:
            >>> engine = CleansingRuleEngine()
            >>> records = [
            ...     {"companyId": "123", "reg_cap": "1,000万元"},
            ...     {"companyId": "456", "reg_cap": "500万元"},
            ... ]
            >>> results = engine.cleanse_batch("eqc_business_info", records)
            >>> print(len(results))  # 2
        """
        results = []

        for record in records:
            result = self.cleanse_record(domain, record, fields)
            results.append(result)

        total_cleansed = sum(r.fields_cleansed for r in results)
        total_failed = sum(r.fields_failed for r in results)

        logger.info(
            "cleansing_rule_engine.batch_cleansed",
            domain=domain,
            records_count=len(records),
            total_fields_cleansed=total_cleansed,
            total_fields_failed=total_failed,
        )

        return results
