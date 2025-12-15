"""
BusinessInfo Repository for UPSERT operations on enterprise.business_info.

Story 6.2-P9: Raw Data Cleansing & Transformation
Task 3.1: Implement BusinessInfoRepository
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from work_data_hub.domain.company_enrichment.models import BusinessInfoRecord
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


class BusinessInfoRepository:
    """
    Repository for UPSERT operations on enterprise.business_info table.

    Uses ON CONFLICT (company_id) DO UPDATE pattern for idempotent writes.
    """

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def upsert(self, record: BusinessInfoRecord) -> None:
        """
        UPSERT a BusinessInfoRecord to enterprise.business_info.

        Uses ON CONFLICT (company_id) DO UPDATE pattern.

        Args:
            record: BusinessInfoRecord to persist
        """
        # Note: business_info has company_id as regular column with FK,
        # so we need to check if row exists and handle accordingly
        upsert_sql = text("""
            INSERT INTO enterprise.business_info (
                company_id,
                registered_date,
                registered_capital,
                start_date,
                end_date,
                colleagues_num,
                actual_capital,
                registered_status,
                legal_person_name,
                address,
                codename,
                company_name,
                company_en_name,
                currency,
                credit_code,
                register_code,
                organization_code,
                company_type,
                industry_name,
                registration_organ_name,
                start_end,
                business_scope,
                telephone,
                email_address,
                website,
                company_former_name,
                control_id,
                control_name,
                bene_id,
                bene_name,
                province,
                department,
                legal_person_id,
                logo_url,
                type_code,
                update_time,
                registered_capital_currency,
                full_register_type_desc,
                industry_code,
                _cleansing_status,
                updated_at
            ) VALUES (
                :company_id,
                :registered_date,
                :registered_capital,
                :start_date,
                :end_date,
                :colleagues_num,
                :actual_capital,
                :registered_status,
                :legal_person_name,
                :address,
                :codename,
                :company_name,
                :company_en_name,
                :currency,
                :credit_code,
                :register_code,
                :organization_code,
                :company_type,
                :industry_name,
                :registration_organ_name,
                :start_end,
                :business_scope,
                :telephone,
                :email_address,
                :website,
                :company_former_name,
                :control_id,
                :control_name,
                :bene_id,
                :bene_name,
                :province,
                :department,
                :legal_person_id,
                :logo_url,
                :type_code,
                :update_time,
                :registered_capital_currency,
                :full_register_type_desc,
                :industry_code,
                CAST(:cleansing_status AS jsonb),
                NOW()
            )
            ON CONFLICT (company_id) DO UPDATE SET
                registered_date = EXCLUDED.registered_date,
                registered_capital = EXCLUDED.registered_capital,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                colleagues_num = EXCLUDED.colleagues_num,
                actual_capital = EXCLUDED.actual_capital,
                registered_status = EXCLUDED.registered_status,
                legal_person_name = EXCLUDED.legal_person_name,
                address = EXCLUDED.address,
                codename = EXCLUDED.codename,
                company_name = EXCLUDED.company_name,
                company_en_name = EXCLUDED.company_en_name,
                currency = EXCLUDED.currency,
                credit_code = EXCLUDED.credit_code,
                register_code = EXCLUDED.register_code,
                organization_code = EXCLUDED.organization_code,
                company_type = EXCLUDED.company_type,
                industry_name = EXCLUDED.industry_name,
                registration_organ_name = EXCLUDED.registration_organ_name,
                start_end = EXCLUDED.start_end,
                business_scope = EXCLUDED.business_scope,
                telephone = EXCLUDED.telephone,
                email_address = EXCLUDED.email_address,
                website = EXCLUDED.website,
                company_former_name = EXCLUDED.company_former_name,
                control_id = EXCLUDED.control_id,
                control_name = EXCLUDED.control_name,
                bene_id = EXCLUDED.bene_id,
                bene_name = EXCLUDED.bene_name,
                province = EXCLUDED.province,
                department = EXCLUDED.department,
                legal_person_id = EXCLUDED.legal_person_id,
                logo_url = EXCLUDED.logo_url,
                type_code = EXCLUDED.type_code,
                update_time = EXCLUDED.update_time,
                registered_capital_currency = EXCLUDED.registered_capital_currency,
                full_register_type_desc = EXCLUDED.full_register_type_desc,
                industry_code = EXCLUDED.industry_code,
                _cleansing_status = EXCLUDED._cleansing_status,
                updated_at = NOW()
        """)

        params = {
            "company_id": record.company_id,
            "registered_date": record.registered_date,
            "registered_capital": record.registered_capital,
            "start_date": record.start_date,
            "end_date": record.end_date,
            "colleagues_num": record.colleagues_num,
            "actual_capital": record.actual_capital,
            "registered_status": record.registered_status,
            "legal_person_name": record.legal_person_name,
            "address": record.address,
            "codename": record.codename,
            "company_name": record.company_name,
            "company_en_name": record.company_en_name,
            "currency": record.currency,
            "credit_code": record.credit_code,
            "register_code": record.register_code,
            "organization_code": record.organization_code,
            "company_type": record.company_type,
            "industry_name": record.industry_name,
            "registration_organ_name": record.registration_organ_name,
            "start_end": record.start_end,
            "business_scope": record.business_scope,
            "telephone": record.telephone,
            "email_address": record.email_address,
            "website": record.website,
            "company_former_name": record.company_former_name,
            "control_id": record.control_id,
            "control_name": record.control_name,
            "bene_id": record.bene_id,
            "bene_name": record.bene_name,
            "province": record.province,
            "department": record.department,
            "legal_person_id": record.legal_person_id,
            "logo_url": record.logo_url,
            "type_code": record.type_code,
            "update_time": record.update_time,
            "registered_capital_currency": record.registered_capital_currency,
            "full_register_type_desc": record.full_register_type_desc,
            "industry_code": record.industry_code,
            "cleansing_status": json.dumps(record.cleansing_status, ensure_ascii=False) if record.cleansing_status else None,
        }

        try:
            self.connection.execute(upsert_sql, params)
            logger.debug(
                "business_info_repository.upsert_success",
                company_id=record.company_id,
            )
        except Exception as e:
            logger.error(
                "business_info_repository.upsert_failed",
                company_id=record.company_id,
                error=str(e),
            )
            raise
