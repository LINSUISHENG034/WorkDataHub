"""
Pydantic v2 data models for company enrichment domain.

This module defines the data contracts for:
1. Company ID mapping and resolution (internal system)
2. EQC API integration for external company data enrichment
3. Company enrichment service with caching and queue processing

Provides robust validation and type safety for both legacy mapping migration
and modern EQC client integration with comprehensive service architecture.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

logger = logging.getLogger(__name__)

# Temp ID validation constants (Story 7.1-16)
TEMP_ID_PREFIX = "TEMP_"
TEMP_ID_EXPECTED_LENGTH = 11  # TEMP_ (5) + 6 digit sequence


class CompanyMappingRecord(BaseModel):
    """
    Input/output model for company ID mapping records.

    Used for enrichment_index table (Story 6.1.1) and EQC API result caching.

    Note: enterprise.company_mapping table was removed in Story 7.1-4 (Zero Legacy).
    This model now exclusively serves enrichment_index operations.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        from_attributes=True,
        extra="forbid",
    )

    alias_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Source identifier (plan code, account, name, etc.)",
    )
    canonical_id: str = Field(
        ..., min_length=1, max_length=50, description="Target company_id to resolve to"
    )
    source: Literal["internal"] = Field(
        default="internal", description="Data source identifier"
    )
    match_type: Literal["plan", "account", "hardcode", "name", "account_name"] = Field(
        ..., description="Mapping type determining priority order"
    )
    priority: int = Field(
        ...,
        ge=1,
        le=5,
        description="Search priority (1=highest, matches legacy layer numbering)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record update timestamp",
    )

    @field_validator("alias_name", "canonical_id", mode="before")
    @classmethod
    def clean_identifiers(cls, v: Any) -> Optional[str]:
        """Clean and normalize identifier fields."""
        if v is None:
            return v

        # Convert to string and strip whitespace
        cleaned = str(v).strip()

        # Empty string validation will be handled by min_length constraint
        return cleaned if cleaned else None

    @field_validator("match_type", mode="after")
    @classmethod
    def validate_match_type_priority(cls, v: str, info: ValidationInfo) -> str:
        """Validate match_type aligns with expected priority mappings."""
        # Priority mapping per legacy logic:
        # plan=1, account=2, hardcode=3, name=4, account_name=5
        expected_priority_map = {
            "plan": 1,
            "account": 2,
            "hardcode": 3,
            "name": 4,
            "account_name": 5,
        }

        # Check if priority field exists in values
        if hasattr(info, "data") and info.data and "priority" in info.data:
            priority = info.data["priority"]
            expected_priority = expected_priority_map.get(v)

            if expected_priority and priority != expected_priority:
                logger.warning(
                    "Priority mismatch: match_type=%s expects priority=%s, "
                    "got priority=%s",
                    v,
                    expected_priority,
                    priority,
                )

        return v


class CompanyMappingQuery(BaseModel):
    """Input model for company ID resolution queries."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="allow",  # Allow extra fields for flexibility
    )

    plan_code: Optional[str] = Field(
        None, description="Plan code for priority 1 lookup (计划代码)"
    )
    account_number: Optional[str] = Field(
        None, description="Account number for priority 2 lookup (集团企业客户号)"
    )
    customer_name: Optional[str] = Field(
        None, description="Customer name for priority 4 lookup (客户名称)"
    )
    account_name: Optional[str] = Field(
        None, description="Account name for priority 5 lookup (年金账户名)"
    )

    @field_validator(
        "plan_code", "account_number", "customer_name", "account_name", mode="before"
    )
    @classmethod
    def normalize_query_fields(cls, v: Any) -> Optional[str]:
        """Normalize query field values for consistent lookup."""
        if v is None:
            return None

        # Convert to string and strip whitespace
        normalized = str(v).strip()

        # Return None for empty strings to ensure proper null handling
        return normalized if normalized else None


class CompanyResolutionResult(BaseModel):
    """Result model for company ID resolution operations."""

    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )

    company_id: Optional[str] = Field(
        None, description="Resolved company_id or None if no match found"
    )
    match_type: Optional[str] = Field(
        None, description="Which mapping type provided the result (plan, account, etc.)"
    )
    source_value: Optional[str] = Field(
        None, description="The alias_name that matched in the lookup"
    )
    priority: Optional[int] = Field(
        None, ge=1, le=5, description="Priority level of the successful match"
    )

    @field_validator("company_id", mode="after")
    @classmethod
    def validate_company_id_format(cls, v: Optional[str]) -> Optional[str]:
        """Basic validation for company_id format."""
        if v is None:
            return v

        # Company IDs should be numeric strings based on legacy data
        if not v.isdigit():
            logger.warning(f"Non-numeric company_id detected: {v}")

        return v


# ===== EQC API Models =====
# These models define the data contracts for EQC (Enterprise Query Center)
# API integration


class CompanySearchResult(BaseModel):
    """
    Result from EQC company search API.

    Maps to the response structure from EQC's searchAll endpoint,
    providing validated company search results with scoring.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        extra="forbid",
    )

    company_id: str = Field(..., min_length=1, description="EQC company ID as string")
    official_name: str = Field(
        ..., min_length=1, max_length=500, description="Official company name from EQC"
    )
    unite_code: Optional[str] = Field(
        None,
        max_length=100,
        description="Unified social credit code (统一社会信用代码)",
    )
    match_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Search relevance score (0.0-1.0)"
    )

    @field_validator("company_id", mode="before")
    @classmethod
    def normalize_company_id(cls, v: Any) -> str:
        """Normalize company ID to string format."""
        if v is None:
            return v
        return str(v).strip()

    @field_validator("unite_code", mode="before")
    @classmethod
    def normalize_unite_code(cls, v: Any) -> Optional[str]:
        """Normalize and validate unite code format."""
        if v is None or str(v).strip() == "":
            return None

        # Clean whitespace and return
        cleaned = str(v).strip()
        return cleaned if cleaned else None


class CompanyDetail(BaseModel):
    """
    Detailed company information from EQC findDepart API.

    Maps to the businessInfodto response structure providing
    comprehensive company details for enrichment purposes.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        extra="forbid",
    )

    company_id: str = Field(..., min_length=1, description="EQC company ID as string")
    official_name: str = Field(
        ..., min_length=1, max_length=500, description="Official company name from EQC"
    )
    unite_code: Optional[str] = Field(
        None,
        max_length=100,
        description="Unified social credit code (统一社会信用代码)",
    )
    aliases: List[str] = Field(
        default_factory=list, description="Alternative company names and aliases"
    )
    business_status: Optional[str] = Field(
        None, max_length=100, description="Current business operating status"
    )

    @field_validator("company_id", mode="before")
    @classmethod
    def normalize_company_id(cls, v: Any) -> str:
        """Normalize company ID to string format."""
        if v is None:
            return v
        return str(v).strip()

    @field_validator("unite_code", mode="before")
    @classmethod
    def normalize_unite_code(cls, v: Any) -> Optional[str]:
        """Normalize and validate unite code format."""
        if v is None or str(v).strip() == "":
            return None

        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("aliases", mode="before")
    @classmethod
    def normalize_aliases(cls, v: Any) -> List[str]:
        """Normalize aliases list, filtering out empty values."""
        if v is None:
            return []

        if isinstance(v, str):
            # Single string - convert to list
            cleaned = v.strip()
            return [cleaned] if cleaned else []

        if isinstance(v, list):
            # Filter out None and empty strings
            return [str(alias).strip() for alias in v if alias and str(alias).strip()]

        return []


# ===== EQC API Extended Models for Full Data Acquisition =====
# These models support findDepart and findLabels API endpoints


class BusinessInfoResult(BaseModel):
    """
    Result from EQC findDepart API (businessInfodto structure).

    Maps to the businessInfodto response from findDepart endpoint,
    providing comprehensive business registration information.
    Raw string values are stored; data cleansing is handled in Story 6.2-P9.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        extra="forbid",
    )

    company_id: str = Field(..., min_length=1, description="EQC company ID")
    company_name: Optional[str] = Field(
        None, max_length=500, description="Company name"
    )

    # Raw values here are strings; normalization/typing happens in Story 6.2-P9.
    registered_date: Optional[str] = Field(
        None, description="Registration date (raw string)"
    )
    registered_capital_raw: Optional[str] = Field(
        None, description="Registered capital (raw string, e.g., '80000.00万元')"
    )
    registered_status: Optional[str] = Field(
        None, max_length=100, description="Registration status"
    )
    legal_person_name: Optional[str] = Field(
        None, max_length=255, description="Legal representative name"
    )
    address: Optional[str] = Field(None, description="Company address")
    codename: Optional[str] = Field(
        None, max_length=100, description="Company code name"
    )
    company_en_name: Optional[str] = Field(None, description="English company name")
    currency: Optional[str] = Field(None, max_length=50, description="Currency")
    credit_code: Optional[str] = Field(
        None, max_length=50, description="Unified social credit code"
    )
    register_code: Optional[str] = Field(
        None, max_length=50, description="Registration code"
    )
    organization_code: Optional[str] = Field(
        None, max_length=50, description="Organization code"
    )
    company_type: Optional[str] = Field(
        None, max_length=100, description="Company type"
    )
    industry_name: Optional[str] = Field(
        None, max_length=255, description="Industry classification"
    )
    registration_organ_name: Optional[str] = Field(
        None, max_length=255, description="Registration authority name"
    )
    start_date: Optional[str] = Field(
        None, description="Business period start date (raw string)"
    )
    end_date: Optional[str] = Field(
        None, description="Business period end date (raw string)"
    )
    start_end: Optional[str] = Field(
        None, max_length=100, description="Business period display string"
    )
    business_scope: Optional[str] = Field(None, description="Business scope")
    telephone: Optional[str] = Field(None, max_length=100, description="Telephone")
    email_address: Optional[str] = Field(
        None, max_length=255, description="Email address"
    )
    website: Optional[str] = Field(None, max_length=500, description="Website")
    colleagues_num: Optional[str] = Field(
        None, description="Employees count (raw string)"
    )
    company_former_name: Optional[str] = Field(None, description="Former company names")
    control_id: Optional[str] = Field(None, max_length=100, description="Controller ID")
    control_name: Optional[str] = Field(
        None, max_length=255, description="Controller name"
    )
    bene_id: Optional[str] = Field(None, max_length=100, description="Beneficiary ID")
    bene_name: Optional[str] = Field(
        None, max_length=255, description="Beneficiary name"
    )
    legal_person_id: Optional[str] = Field(
        None, max_length=100, description="Legal person ID"
    )
    province: Optional[str] = Field(None, max_length=100, description="Province")
    logo_url: Optional[str] = Field(None, description="Logo URL")
    type_code: Optional[str] = Field(
        None, max_length=50, description="Company type code"
    )
    department: Optional[str] = Field(None, max_length=255, description="Department")
    update_time: Optional[str] = Field(None, description="EQC update time (raw string)")
    actual_capital_raw: Optional[str] = Field(
        None, description="Paid-in capital (raw string)"
    )
    registered_capital_currency: Optional[str] = Field(
        None, max_length=50, description="Registered capital currency"
    )
    full_register_type_desc: Optional[str] = Field(
        None, max_length=255, description="Full register type description"
    )
    industry_code: Optional[str] = Field(
        None, max_length=50, description="Industry code"
    )

    @field_validator("company_id", mode="before")
    @classmethod
    def normalize_company_id(cls, v: Any) -> str:
        """Normalize company ID to string format."""
        if v is None:
            return v
        return str(v).strip()


class LabelInfo(BaseModel):
    """
    Result from EQC findLabels API.

    Maps to individual label entries from the labels response structure.
    Handles null companyId fallback logic per Legacy crawler pattern.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        populate_by_name=True,
        extra="forbid",
    )

    company_id: str = Field(..., description="Company ID (may need sibling fallback)")
    type: str = Field(..., description="Label category (e.g., '行业分类')")
    lv1_name: Optional[str] = Field(
        None, alias="lv1Name", description="Level 1 label name"
    )
    lv2_name: Optional[str] = Field(
        None, alias="lv2Name", description="Level 2 label name"
    )
    lv3_name: Optional[str] = Field(
        None, alias="lv3Name", description="Level 3 label name"
    )
    lv4_name: Optional[str] = Field(
        None, alias="lv4Name", description="Level 4 label name"
    )

    @field_validator("company_id", mode="before")
    @classmethod
    def normalize_company_id(cls, v: Any) -> str:
        """Normalize company ID to string format."""
        if v is None:
            return v
        return str(v).strip()


# ===== Company Enrichment Service Models =====
# These models define the data contracts for the CompanyEnrichmentService
# with caching, queue processing, and unified resolution capabilities


class ResolutionStatus(str, Enum):
    """Status enumeration for company ID resolution operations."""

    SUCCESS_INTERNAL = "success_internal"  # Found in internal mappings
    SUCCESS_EXTERNAL = "success_external"  # Found via EQC lookup + cached
    PENDING_LOOKUP = "pending_lookup"  # Queued for async lookup
    TEMP_ASSIGNED = "temp_assigned"  # Assigned temporary ID


class CompanyIdResult(BaseModel):
    """
    Result model for company ID resolution operations.

    Provides comprehensive result information from CompanyEnrichmentService
    with status tracking, source attribution, and temporary ID handling.
    """

    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )

    company_id: Optional[str] = Field(
        None, description="Resolved company_id or temp ID"
    )
    status: ResolutionStatus = Field(
        ..., description="Resolution status indicating the resolution path taken"
    )
    source: Optional[str] = Field(
        None, description="Source of resolution (internal/EQC/temp/queued)"
    )
    temp_id: Optional[str] = Field(
        None, description="Generated temporary ID if applicable"
    )

    @field_validator("temp_id", mode="after")
    @classmethod
    def validate_temp_id_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate temporary ID format if provided."""
        if v is None:
            return v

        # Temp IDs should follow TEMP_NNNNNN format
        if not v.startswith(TEMP_ID_PREFIX) or len(v) != TEMP_ID_EXPECTED_LENGTH:
            logger.warning(f"Invalid temp ID format: {v}")

        return v


class LookupRequest(BaseModel):
    """
    Model for queued lookup requests in the async processing system.

    Maps directly to enterprise.lookup_requests table structure,
    providing validation and transformation for queue processing operations.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        from_attributes=True,
        extra="forbid",
    )

    id: Optional[int] = None
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original company name to lookup via EQC API",
    )
    normalized_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Normalized version of name for duplicate detection",
    )
    status: str = Field(default="pending", description="Queue processing status")
    attempts: int = Field(
        default=0, ge=0, description="Number of processing attempts for retry logic"
    )
    last_error: Optional[str] = Field(
        None, description="Last error message from failed processing attempt"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Request creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last status update timestamp",
    )

    @field_validator("status", mode="after")
    @classmethod
    def validate_status_enum(cls, v: str) -> str:
        """Validate status is one of the allowed queue states."""
        allowed_statuses = {"pending", "processing", "done", "failed"}
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of {allowed_statuses}, got: {v}")
        return v

    @field_validator("name", "normalized_name", mode="before")
    @classmethod
    def clean_name_fields(cls, v: Any) -> Optional[str]:
        """Clean and normalize name fields."""
        if v is None:
            return v

        # Convert to string and strip whitespace
        cleaned = str(v).strip()

        # Empty string validation will be handled by min_length constraint
        return cleaned if cleaned else None


# ===== EQC Data Cleansing Models (Story 6.2-P9) =====
# These models represent the normalized DB table structures,
# distinct from the API response models above (BusinessInfoResult, LabelInfo).


class BusinessInfoRecord(BaseModel):
    """
    DB record model for enterprise.business_info table.

    Maps to the normalized business_info table structure from Story 6.2-P7.
    This is distinct from BusinessInfoResult which represents raw API responses.

    Fields are normalized types (DATE, NUMERIC) after cleansing from raw strings.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        from_attributes=True,
        extra="forbid",
    )

    company_id: str = Field(
        ..., min_length=1, max_length=255, description="Company ID (FK to base_info)"
    )

    # Normalized fields (cleansed from raw strings)
    registered_date: Optional[datetime] = Field(
        None, description="Registration date (DATE type)"
    )
    registered_capital: Optional[float] = Field(
        None, description="Registered capital in yuan (NUMERIC)"
    )
    start_date: Optional[datetime] = Field(
        None, description="Business period start date (DATE)"
    )
    end_date: Optional[datetime] = Field(
        None, description="Business period end date (DATE)"
    )
    colleagues_num: Optional[int] = Field(None, description="Employee count (INTEGER)")
    actual_capital: Optional[float] = Field(
        None, description="Paid-in capital in yuan (NUMERIC)"
    )

    # Retained string fields
    registered_status: Optional[str] = Field(
        None, max_length=100, description="Registration status"
    )
    legal_person_name: Optional[str] = Field(
        None, max_length=255, description="Legal representative name"
    )
    address: Optional[str] = Field(None, description="Company address")
    codename: Optional[str] = Field(
        None, max_length=100, description="Company code name"
    )
    company_name: Optional[str] = Field(
        None, max_length=255, description="Company name"
    )
    company_en_name: Optional[str] = Field(None, description="English company name")
    currency: Optional[str] = Field(None, max_length=50, description="Currency")
    credit_code: Optional[str] = Field(
        None, max_length=50, description="Unified social credit code"
    )
    register_code: Optional[str] = Field(
        None, max_length=50, description="Registration code"
    )
    organization_code: Optional[str] = Field(
        None, max_length=50, description="Organization code"
    )
    company_type: Optional[str] = Field(
        None, max_length=100, description="Company type"
    )
    industry_name: Optional[str] = Field(
        None, max_length=255, description="Industry classification"
    )
    registration_organ_name: Optional[str] = Field(
        None, max_length=255, description="Registration authority"
    )
    start_end: Optional[str] = Field(
        None, max_length=100, description="Business period display string"
    )
    business_scope: Optional[str] = Field(None, description="Business scope")
    telephone: Optional[str] = Field(None, max_length=100, description="Telephone")
    email_address: Optional[str] = Field(
        None, max_length=255, description="Email address"
    )
    website: Optional[str] = Field(None, max_length=500, description="Website")
    company_former_name: Optional[str] = Field(None, description="Former company names")
    control_id: Optional[str] = Field(None, max_length=100, description="Controller ID")
    control_name: Optional[str] = Field(
        None, max_length=255, description="Controller name"
    )
    bene_id: Optional[str] = Field(None, max_length=100, description="Beneficiary ID")
    bene_name: Optional[str] = Field(
        None, max_length=255, description="Beneficiary name"
    )
    province: Optional[str] = Field(None, max_length=100, description="Province")
    department: Optional[str] = Field(None, max_length=255, description="Department")

    # snake_case converted from camelCase
    legal_person_id: Optional[str] = Field(
        None, max_length=100, description="Legal person ID"
    )
    logo_url: Optional[str] = Field(None, description="Logo URL")
    type_code: Optional[str] = Field(
        None, max_length=50, description="Company type code"
    )
    update_time: Optional[datetime] = Field(None, description="EQC data update time")
    registered_capital_currency: Optional[str] = Field(
        None, max_length=50, description="Registered capital currency"
    )
    full_register_type_desc: Optional[str] = Field(
        None, max_length=255, description="Full register type description"
    )
    industry_code: Optional[str] = Field(
        None, max_length=50, description="Industry code"
    )

    # Cleansing metadata
    cleansing_status: Optional[dict] = Field(
        None, description="Per-field cleansing status tracking"
    )

    @field_validator("company_id", mode="before")
    @classmethod
    def normalize_company_id(cls, v: Any) -> str:
        """Normalize company ID to string format."""
        if v is None:
            return v
        return str(v).strip()


class BizLabelRecord(BaseModel):
    """
    DB record model for enterprise.biz_label table.

    Maps to the normalized biz_label table structure from Story 6.2-P7.
    This is distinct from LabelInfo which represents raw API response entries.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
        from_attributes=True,
        extra="forbid",
    )

    company_id: str = Field(
        ..., min_length=1, max_length=255, description="Company ID (FK to base_info)"
    )
    type: Optional[str] = Field(None, max_length=100, description="Label category type")
    lv1_name: Optional[str] = Field(
        None, max_length=255, description="Level 1 label name"
    )
    lv2_name: Optional[str] = Field(
        None, max_length=255, description="Level 2 label name"
    )
    lv3_name: Optional[str] = Field(
        None, max_length=255, description="Level 3 label name"
    )
    lv4_name: Optional[str] = Field(
        None, max_length=255, description="Level 4 label name"
    )

    @field_validator("company_id", mode="before")
    @classmethod
    def normalize_company_id(cls, v: Any) -> str:
        """Normalize company ID to string format."""
        if v is None:
            return v
        return str(v).strip()
