"""
Response parsing logic for EQC connector.
"""

from typing import List, Optional, Dict, Any

from work_data_hub.domain.company_enrichment.models import (
    BusinessInfoResult,
    LabelInfo,
    CompanySearchResult,
)


def first_non_empty_str(payload: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """Return the first non-empty string value from a list of keys."""
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        cleaned = str(value).strip()
        if cleaned:
            return cleaned
    return None


def extract_aliases(business_info: Dict[str, Any]) -> List[str]:
    """
    Extract company aliases from business info response.

    Args:
        business_info: Business information dictionary from EQC API

    Returns:
        List of company aliases/alternative names
    """
    aliases = []

    # Common fields that might contain alternative names
    alias_fields = [
        "alias_name",
        "short_name",
        "english_name",
        "former_name",
        "other_names",
    ]

    for field in alias_fields:
        value = business_info.get(field)
        if value and str(value).strip():
            cleaned_alias = str(value).strip()
            if cleaned_alias not in aliases:
                aliases.append(cleaned_alias)

    # Check if aliases is a list/array in the response
    if "aliases" in business_info:
        alias_data = business_info["aliases"]
        if isinstance(alias_data, list):
            for alias in alias_data:
                if alias and str(alias).strip():
                    cleaned_alias = str(alias).strip()
                    if cleaned_alias not in aliases:
                        aliases.append(cleaned_alias)
        elif isinstance(alias_data, str) and alias_data.strip():
            cleaned_alias = alias_data.strip()
            if cleaned_alias not in aliases:
                aliases.append(cleaned_alias)

    return aliases


def parse_business_info(
    business_info: Dict[str, Any],
    fallback_company_id: str,
) -> BusinessInfoResult:
    """
    Parse business_infodto dict into BusinessInfoResult model.

    Maps EQC API fields to our domain model with proper validation.

    Args:
        business_info: businessInfodto dictionary from EQC API response
        fallback_company_id: Company ID to use if not found in response

    Returns:
        BusinessInfoResult with mapped fields
    """
    company_id = (
        first_non_empty_str(business_info, ["company_id", "companyId", "id"])
        or fallback_company_id
    )

    company_name = first_non_empty_str(
        business_info,
        ["companyFullName", "company_name", "companyName", "name", "coname"],
    )

    registered_date = first_non_empty_str(
        business_info, ["registered_date", "registeredDate", "est_date", "estDate"]
    )

    registered_capital_raw = first_non_empty_str(
        business_info, ["registerCaptial", "reg_cap", "registered_capital"]
    )

    registered_status = first_non_empty_str(
        business_info, ["registered_status", "registeredStatus", "registered_status"]
    )

    legal_person_name = first_non_empty_str(
        business_info, ["legal_person_name", "legalPersonName", "le_rep"]
    )

    address = first_non_empty_str(business_info, ["address"])

    credit_code = first_non_empty_str(
        business_info, ["unite_code", "uniteCode", "credit_code", "creditCode"]
    )

    company_type = first_non_empty_str(
        business_info, ["company_type", "companyType", "type"]
    )

    industry_name = first_non_empty_str(
        business_info, ["industry_name", "industryName"]
    )

    business_scope = first_non_empty_str(
        business_info, ["business_scope", "businessScope"]
    )

    codename = first_non_empty_str(business_info, ["codename"])
    company_en_name = first_non_empty_str(business_info, ["company_en_name"])
    currency = first_non_empty_str(business_info, ["currency"])
    register_code = first_non_empty_str(business_info, ["register_code"])
    organization_code = first_non_empty_str(
        business_info, ["organization_code", "organizationCode"]
    )
    registration_organ_name = first_non_empty_str(
        business_info, ["registration_organ_name"]
    )
    start_date = first_non_empty_str(business_info, ["start_date", "startDate"])
    end_date = first_non_empty_str(business_info, ["end_date", "endDate"])
    start_end = first_non_empty_str(business_info, ["start_end"])
    telephone = first_non_empty_str(business_info, ["telephone"])
    email_address = first_non_empty_str(business_info, ["email_address"])
    website = first_non_empty_str(business_info, ["website"])
    colleagues_num = first_non_empty_str(
        business_info, ["colleagues_num", "collegues_num"]
    )
    company_former_name = first_non_empty_str(business_info, ["company_former_name"])
    control_id = first_non_empty_str(business_info, ["control_id"])
    control_name = first_non_empty_str(business_info, ["control_name"])
    bene_id = first_non_empty_str(business_info, ["bene_id"])
    bene_name = first_non_empty_str(business_info, ["bene_name"])
    legal_person_id = first_non_empty_str(business_info, ["legalPersonId", "legal_person_id"])
    province = first_non_empty_str(business_info, ["province"])
    logo_url = first_non_empty_str(business_info, ["logoUrl", "logo_url"])
    type_code = first_non_empty_str(business_info, ["typeCode", "type_code"])
    department = first_non_empty_str(business_info, ["department"])
    update_time = first_non_empty_str(business_info, ["updateTime", "update_time"])
    actual_capital_raw = first_non_empty_str(business_info, ["actualCapi", "actual_capital"])
    registered_capital_currency = first_non_empty_str(
        business_info, ["registeredCapitalCurrency", "registered_capital_currency"]
    )
    full_register_type_desc = first_non_empty_str(
        business_info, ["fullRegisterTypeDesc", "full_register_type_desc"]
    )
    industry_code = first_non_empty_str(business_info, ["industryCode", "industry_code"])

    return BusinessInfoResult(
        company_id=company_id,
        company_name=company_name,
        registered_date=registered_date,
        registered_capital_raw=registered_capital_raw,
        registered_status=registered_status,
        legal_person_name=legal_person_name,
        address=address,
        credit_code=credit_code,
        company_type=company_type,
        industry_name=industry_name,
        business_scope=business_scope,
        codename=codename,
        company_en_name=company_en_name,
        currency=currency,
        register_code=register_code,
        organization_code=organization_code,
        registration_organ_name=registration_organ_name,
        start_date=start_date,
        end_date=end_date,
        start_end=start_end,
        telephone=telephone,
        email_address=email_address,
        website=website,
        colleagues_num=colleagues_num,
        company_former_name=company_former_name,
        control_id=control_id,
        control_name=control_name,
        bene_id=bene_id,
        bene_name=bene_name,
        legal_person_id=legal_person_id,
        province=province,
        logo_url=logo_url,
        type_code=type_code,
        department=department,
        update_time=update_time,
        actual_capital_raw=actual_capital_raw,
        registered_capital_currency=registered_capital_currency,
        full_register_type_desc=full_register_type_desc,
        industry_code=industry_code,
    )


def parse_labels_with_fallback(
    labels_response: Dict[str, Any], target_company_id: str
) -> List[LabelInfo]:
    """
    Parse labels response with null companyId fallback logic.

    When companyId is None, search siblings for a non-null value.
    From legacy crawler pattern.

    Args:
        labels_response: Response from findLabels API
        target_company_id: Company ID to use as final fallback

    Returns:
        List of LabelInfo objects
    """
    results = []
    for category in labels_response.get("labels", []):
        label_type = category.get("type", "")
        for lab in category.get("labels", []):
            company_id = lab.get("companyId")
            # Fallback: if companyId is None, try siblings
            if company_id is None:
                for sibling in category.get("labels", []):
                    if sibling.get("companyId"):
                        company_id = sibling["companyId"]
                        break
            # Final fallback: use the target_company_id from search
            if company_id is None:
                company_id = target_company_id

            lv1 = lab.get("lv1Name")
            lv2 = lab.get("lv2Name")
            lv3 = lab.get("lv3Name")
            lv4 = lab.get("lv4Name")

            # Legacy quirk: some responses encode region labels as:
            # lv1Name="地区分类", lv2Name=<province>, lv3Name=<city>.
            # Normalize to make the hierarchy usable without special handling downstream.
            if lv1 == "地区分类" and lv2:
                lv1, lv2, lv3, lv4 = lv2, lv3, lv4, None

            results.append(
                LabelInfo(
                    company_id=company_id,
                    type=label_type,
                    lv1_name=lv1,
                    lv2_name=lv2,
                    lv3_name=lv3,
                    lv4_name=lv4,
                )
            )
    return results


def parse_company_search_item(item: Dict[str, Any]) -> CompanySearchResult:
    """Parse a single company search result item."""
    return CompanySearchResult(
        company_id=str(item.get("companyId", "")),
        official_name=item.get("companyFullName", ""),
        unite_code=item.get("unite_code"),
        match_score=0.9,  # EQC doesn't provide scores, use high default
    )
