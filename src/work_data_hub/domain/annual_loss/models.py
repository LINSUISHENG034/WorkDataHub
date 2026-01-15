"""Annual Loss (当年流失) domain - Models.

This domain unifies TrusteeLossCleaner (企年受托流失) and
InvesteeLossCleaner (企年投资流失) from legacy system into a single domain.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from work_data_hub.infrastructure.cleansing import (
    DEFAULT_NUMERIC_RULES,
    apply_domain_rules,
    clean_code_field,
    clean_customer_name,
    get_cleansing_registry,
    normalize_company_id,
    normalize_plan_code,
)
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

logger = logging.getLogger(__name__)
CLEANSING_DOMAIN = "annual_loss"
CLEANSING_REGISTRY = get_cleansing_registry()


class AnnualLossIn(BaseModel):
    """Bronze layer input model - lenient validation.

    Handles both 企年受托流失 and 企年投资流失 sheets with unified schema.
    """

    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_default=True,
    )

    # Core identification fields
    年金计划号: Optional[str] = Field(None, description="Plan code")
    company_id: Optional[str] = Field(None, description="Company identifier")

    # Fields to be renamed/transformed
    客户全称: Optional[str] = Field(
        None, description="Original customer name (to be renamed to 上报客户名称)"
    )

    # Standard fields
    上报月份: Optional[Union[date, str, int]] = Field(None, description="Report month")
    流失日期: Optional[Union[date, str]] = Field(None, description="Loss date")
    业务类型: Optional[str] = Field(None, description="Business type (受托/投资)")
    产品线代码: Optional[str] = Field(None, description="Product line code (QN01/QN02)")
    机构: Optional[str] = Field(
        None, description="Institution name (to be renamed to 机构名称)"
    )
    机构名称: Optional[str] = Field(None, description="Institution name")
    机构代码: Optional[str] = Field(None, description="Institution code")

    # Common optional fields
    客户类型: Optional[str] = Field(None, description="Customer type")
    原受托人: Optional[str] = Field(
        None, description="Original trustee name (原受托人)"
    )
    计划规模: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Plan scale (亿元)"
    )
    年缴规模: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Annual payment scale (亿元)"
    )
    计划类型: Optional[str] = Field(None, description="Plan type (单一/集合)")
    证明材料: Optional[str] = Field(None, description="Evidence materials")
    考核有效: Optional[Union[int, str]] = Field(
        None, description="Assessment validity (0/1)"
    )
    备注: Optional[str] = Field(None, description="Remarks")

    @model_validator(mode="before")
    @classmethod
    def convert_nan_to_none(cls, data: Any) -> Dict[str, Any]:
        """Convert NaN values to None for proper handling."""
        import math

        if not isinstance(data, dict):
            return cast(Dict[str, Any], data)
        return {
            k: None if isinstance(v, float) and math.isnan(v) else v
            for k, v in data.items()
        }

    @field_validator("计划规模", "年缴规模", mode="before")
    @classmethod
    def clean_numeric_fields(cls, v: Any, info: ValidationInfo) -> Optional[float]:
        """Clean numeric fields with domain rules."""
        if v is None:
            return v
        field_name = info.field_name or "numeric_field"
        try:
            cleaned = apply_domain_rules(
                v, field_name, CLEANSING_DOMAIN, fallback_rules=DEFAULT_NUMERIC_RULES
            )
        except ValueError:
            return None  # Lenient - allow invalid values in bronze layer
        if cleaned is None:
            return None
        if isinstance(cleaned, (Decimal, int, float)):
            return float(cleaned)
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return None

    @field_validator("年金计划号", "机构代码", "company_id", mode="before")
    @classmethod
    def clean_code_fields(cls, v: Any) -> Optional[str]:
        """Clean code fields."""
        return clean_code_field(v)


class AnnualLossOut(BaseModel):
    """Gold layer output model - strict validation.

    Unified output schema for both trustee and investee loss records.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
        use_enum_values=True,
        from_attributes=True,
    )

    # Required identification fields
    上报月份: date = Field(..., description="Report month")
    业务类型: str = Field(..., min_length=1, description="Business type (受托/投资)")

    # Customer name fields (transformed)
    上报客户名称: str = Field(
        ..., min_length=1, description="Original reported customer name"
    )
    客户名称: Optional[str] = Field(
        None, description="Cleaned customer name via customer_name_normalize"
    )

    # Plan and company fields (conditional update logic applied)
    年金计划号: Optional[str] = Field(None, description="Plan code")
    company_id: Optional[str] = Field(None, description="Company identifier")

    # Standard fields
    机构名称: Optional[str] = Field(None, description="Institution name")
    机构代码: str = Field(..., description="Institution code")
    产品线代码: Optional[str] = Field(None, description="Product line code (QN01/QN02)")
    流失日期: Optional[date] = Field(None, description="Loss date")

    # Common optional fields
    客户类型: Optional[str] = Field(None, description="Customer type")
    原受托人: Optional[str] = Field(None, description="Original trustee name")
    计划规模: Optional[Decimal] = Field(None, description="Plan scale (亿元)")
    年缴规模: Optional[Decimal] = Field(None, description="Annual payment scale (亿元)")
    计划类型: Optional[str] = Field(None, description="Plan type")
    证明材料: Optional[str] = Field(None, description="Evidence materials")
    考核有效: Optional[int] = Field(None, description="Assessment validity")
    备注: Optional[str] = Field(None, description="Remarks")

    # Auto-generated
    id: Optional[int] = Field(None, description="Auto-generated ID (handled by DB)")

    @field_validator("上报月份", mode="before")
    @classmethod
    def parse_report_month(cls, v: Any) -> date:
        """Parse report month to date."""
        try:
            return parse_yyyymm_or_chinese(v)
        except ValueError as e:
            raise ValueError(f"Field '上报月份': {str(e)}")

    @field_validator("流失日期", mode="before")
    @classmethod
    def parse_loss_date(cls, v: Any) -> Optional[date]:
        """Parse loss date to date."""
        if v is None or v == "":
            return None
        try:
            return parse_yyyymm_or_chinese(v)
        except ValueError:
            return None  # Return None for invalid dates

    @field_validator("客户名称", mode="before")
    @classmethod
    def clean_customer_name_field(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        """Clean customer name using customer_name_normalize module."""
        field_name = info.field_name or "客户名称"
        return clean_customer_name(v, field_name, CLEANSING_DOMAIN)

    @field_validator("年金计划号", mode="after")
    @classmethod
    def normalize_plan_code_field(cls, v: Optional[str]) -> Optional[str]:
        """Normalize plan code."""
        if v is None:
            return None
        return normalize_plan_code(v, allow_null=True)

    @field_validator("company_id", mode="after")
    @classmethod
    def normalize_company_id_field(cls, v: Optional[str]) -> Optional[str]:
        """Normalize company ID."""
        return normalize_company_id(v)

    @field_validator("计划规模", "年缴规模", mode="before")
    @classmethod
    def clean_decimal_fields(cls, v: Any, info: ValidationInfo) -> Optional[Decimal]:
        """Clean decimal fields for output."""
        if v is None:
            return None
        field_name = info.field_name or "numeric_field"
        try:
            cleaned = apply_domain_rules(
                v, field_name, CLEANSING_DOMAIN, fallback_rules=DEFAULT_NUMERIC_RULES
            )
            if cleaned is None:
                return None
            return Decimal(str(cleaned))
        except (ValueError, TypeError):
            return None

    @field_validator("考核有效", mode="before")
    @classmethod
    def clean_int_fields(cls, v: Any) -> Optional[int]:
        """Clean integer flag fields."""
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class AnnualLossProcessingResult(BaseModel):
    """Result container for annual loss processing."""

    model_config = ConfigDict(validate_default=True, extra="forbid")

    records: List[AnnualLossOut] = Field(
        ..., description="Processed annual loss records"
    )
    source_type: str = Field(..., description="Source type: trustee, investee, or both")
    total_count: int = Field(0, description="Total records processed")
    success_count: int = Field(0, description="Successfully processed records")
    failed_count: int = Field(0, description="Failed records count")
    processing_time_ms: int = Field(0, description="Total processing time in ms")
    data_source: str = Field("unknown", description="Source file or identifier")
