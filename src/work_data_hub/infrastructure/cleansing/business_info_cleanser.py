"""
BusinessInfo Cleanser Service for transforming raw JSONB to normalized records.

Story 6.2-P9: Raw Data Cleansing & Transformation
Task 2.1: Implement BusinessInfoCleanser service
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from work_data_hub.domain.company_enrichment.models import BusinessInfoRecord
from work_data_hub.infrastructure.cleansing.registry import get_cleansing_registry

logger = logging.getLogger(__name__)


class BusinessInfoCleanser:
    """
    Transform raw_business_info JSONB to normalized BusinessInfoRecord.

    Uses the eqc_business_info domain rules from cleansing_rules.yml
    to cleanse and type-convert raw API response data.
    """

    def __init__(self) -> None:
        self.registry = get_cleansing_registry()
        self.domain = "eqc_business_info"

    def transform(self, raw: Dict[str, Any], company_id: str) -> BusinessInfoRecord:
        """
        Apply cleansing rules and return normalized BusinessInfoRecord.

        Args:
            raw: Raw JSONB from base_info.raw_business_info
            company_id: Company ID from base_info.company_id

        Returns:
            BusinessInfoRecord with cleansed values and cleansing_status tracking
        """
        status: Dict[str, str] = {}

        # Story 6.2-P9: Extract businessInfodto sub-object if present
        # The findDepart API returns data nested under businessInfodto key
        data = raw.get("businessInfodto", raw)

        # registered_capital: "80000.00万元" → float
        # Uses rule chain: remove_currency_symbols → clean_comma_separated_number → convert_chinese_amount_units
        raw_capital = data.get("registerCaptial") or data.get("registered_capital")
        capital, capital_status = self._cleanse_numeric_field("registerCaptial", raw_capital)
        status["registered_capital"] = capital_status

        # registered_date: "2015-01-15" or "2015年01月15日" → date
        raw_date = data.get("registered_date") or raw.get("est_date")
        reg_date, date_status = self._cleanse_date_field("registered_date", raw_date)
        status["registered_date"] = date_status

        # start_date: Business period start
        raw_start_date = data.get("start_date") or raw.get("startDate")
        start_date, start_date_status = self._cleanse_date_field("registered_date", raw_start_date)
        status["start_date"] = start_date_status

        # end_date: Business period end
        raw_end_date = data.get("end_date") or raw.get("endDate")
        end_date, end_date_status = self._cleanse_date_field("registered_date", raw_end_date)
        status["end_date"] = end_date_status

        # actual_capital: Paid-in capital
        raw_actual = data.get("actualCapi") or raw.get("actual_capital")
        actual_capital, actual_status = self._cleanse_numeric_field("registerCaptial", raw_actual)
        status["actual_capital"] = actual_status

        # colleagues_num: Employee count
        raw_colleagues = data.get("collegues_num") or raw.get("colleagues_num")
        colleagues_num = self._parse_int(raw_colleagues)
        status["colleagues_num"] = "cleansed" if colleagues_num is not None else (
            "null_input" if raw_colleagues is None else "parse_failed"
        )

        # update_time: EQC data update time
        raw_update_time = data.get("updateTime") or raw.get("update_time")
        update_time, update_time_status = self._cleanse_date_field("registered_date", raw_update_time)
        status["update_time"] = update_time_status

        # String fields with simple trim_whitespace
        registered_status = self._cleanse_string_field(data.get("registered_status"))
        legal_person_name = self._cleanse_string_field(data.get("legal_person_name") or data.get("le_rep"))
        address = self._cleanse_string_field(data.get("address"))
        codename = self._cleanse_string_field(data.get("codename"))
        company_name = self._cleanse_string_field(data.get("company_name"))
        company_en_name = self._cleanse_string_field(data.get("company_en_name"))
        currency = self._cleanse_string_field(data.get("currency"))
        credit_code = self._cleanse_string_field(data.get("credit_code") or data.get("unite_code"))
        register_code = self._cleanse_string_field(data.get("register_code"))
        organization_code = self._cleanse_string_field(data.get("organization_code"))
        company_type = self._cleanse_string_field(data.get("company_type"))
        industry_name = self._cleanse_string_field(data.get("industry_name"))
        registration_organ_name = self._cleanse_string_field(data.get("registration_organ_name"))
        start_end = self._cleanse_string_field(data.get("start_end"))
        business_scope = self._cleanse_string_field(data.get("business_scope"))
        telephone = self._cleanse_string_field(data.get("telephone"))
        email_address = self._cleanse_string_field(data.get("email_address"))
        website = self._cleanse_string_field(data.get("website"))
        company_former_name = self._cleanse_string_field(data.get("company_former_name") or raw.get("company_former_name"))
        control_id = self._cleanse_string_field(data.get("control_id"))
        control_name = self._cleanse_string_field(data.get("control_name"))
        bene_id = self._cleanse_string_field(data.get("bene_id"))
        bene_name = self._cleanse_string_field(data.get("bene_name"))
        province = self._cleanse_string_field(data.get("province") or raw.get("province"))
        department = self._cleanse_string_field(data.get("department"))

        # snake_case converted from camelCase
        legal_person_id = self._cleanse_string_field(data.get("legalPersonId") or data.get("legal_person_id"))
        logo_url = self._cleanse_string_field(data.get("logoUrl") or data.get("logo_url"))
        type_code = self._cleanse_string_field(data.get("typeCode") or data.get("type_code"))
        registered_capital_currency = self._cleanse_string_field(
            data.get("registeredCapitalCurrency") or data.get("registered_capital_currency")
        )
        full_register_type_desc = self._cleanse_string_field(
            data.get("fullRegisterTypeDesc") or data.get("full_register_type_desc")
        )
        industry_code = self._cleanse_string_field(data.get("industryCode") or data.get("industry_code"))

        return BusinessInfoRecord(
            company_id=company_id,
            registered_date=reg_date,
            registered_capital=capital,
            start_date=start_date,
            end_date=end_date,
            colleagues_num=colleagues_num,
            actual_capital=actual_capital,
            registered_status=registered_status,
            legal_person_name=legal_person_name,
            address=address,
            codename=codename,
            company_name=company_name,
            company_en_name=company_en_name,
            currency=currency,
            credit_code=credit_code,
            register_code=register_code,
            organization_code=organization_code,
            company_type=company_type,
            industry_name=industry_name,
            registration_organ_name=registration_organ_name,
            start_end=start_end,
            business_scope=business_scope,
            telephone=telephone,
            email_address=email_address,
            website=website,
            company_former_name=company_former_name,
            control_id=control_id,
            control_name=control_name,
            bene_id=bene_id,
            bene_name=bene_name,
            province=province,
            department=department,
            legal_person_id=legal_person_id,
            logo_url=logo_url,
            type_code=type_code,
            update_time=update_time,
            registered_capital_currency=registered_capital_currency,
            full_register_type_desc=full_register_type_desc,
            industry_code=industry_code,
            cleansing_status=status,
        )

    def _cleanse_numeric_field(self, field: str, value: Any) -> Tuple[Optional[float], str]:
        """
        Apply domain rules for numeric field and return (result, status).

        Uses the registerCaptial rule chain which includes convert_chinese_amount_units.
        """
        if value is None:
            return None, "null_input"
        try:
            rules = self.registry.get_domain_rules(self.domain, field)
            if not rules:
                return self._parse_float(value), "no_rules"
            result = self.registry.apply_rules(value, rules)
            if result is None:
                return None, "parse_failed"
            # Convert to float for DB storage
            if isinstance(result, (int, float, Decimal)):
                return float(result), "cleansed"
            # Try to parse if still string
            try:
                return float(result), "cleansed"
            except (ValueError, TypeError):
                return None, "parse_failed"
        except Exception as e:
            logger.warning(
                "business_info_cleanser.numeric_cleanse_error field=%s error=%s",
                field,
                type(e).__name__,
            )
            return None, f"error:{type(e).__name__}"

    def _cleanse_date_field(self, field: str, value: Any) -> Tuple[Optional[datetime], str]:
        """
        Apply domain rules for date field and return (result, status).

        Uses the registered_date rule chain which includes parse_chinese_date_value.
        """
        if value is None:
            return None, "null_input"

        # If already a date/datetime, just return it
        if isinstance(value, datetime):
            return value, "cleansed"
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()), "cleansed"

        try:
            rules = self.registry.get_domain_rules(self.domain, field)
            if not rules:
                return None, "no_rules"
            result = self.registry.apply_rules(value, rules)
            if result is None:
                return None, "parse_failed"
            # Convert to datetime for DB storage
            if isinstance(result, datetime):
                return result, "cleansed"
            if isinstance(result, date):
                return datetime.combine(result, datetime.min.time()), "cleansed"
            # If still a string (parsing failed), return None
            if isinstance(result, str):
                return None, "parse_failed"
            return None, "parse_failed"
        except Exception as e:
            logger.warning(
                "business_info_cleanser.date_cleanse_error field=%s error=%s",
                field,
                type(e).__name__,
            )
            return None, f"error:{type(e).__name__}"

    def _cleanse_string_field(self, value: Any) -> Optional[str]:
        """Apply basic trim_whitespace to string field."""
        if value is None:
            return None
        result = str(value).strip()
        return result if result else None

    def _parse_float(self, value: Any) -> Optional[float]:
        """Try to parse value as float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value: Any) -> Optional[int]:
        """Try to parse value as int (for employee count)."""
        if value is None:
            return None
        try:
            # Handle string values like "100人" or "100"
            if isinstance(value, str):
                cleaned = value.replace("人", "").replace(",", "").strip()
                if not cleaned:
                    return None
                return int(float(cleaned))  # Handle "100.0" -> 100
            return int(value)
        except (ValueError, TypeError):
            return None
