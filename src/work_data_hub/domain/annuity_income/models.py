import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

if TYPE_CHECKING:
    pass
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
    MAX_DATE_RANGE_DAYS,
    MAX_YYYYMM_VALUE,
    MIN_YYYYMM_VALUE,
    apply_domain_rules,
    clean_code_field,
    clean_customer_name,
    get_cleansing_registry,
    normalize_company_id,
    normalize_plan_code,
)

# Story 6.2-P13: Import shared EnrichmentStats from infrastructure layer
from work_data_hub.infrastructure.models.shared import EnrichmentStats
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

logger = logging.getLogger(__name__)
CLEANSING_DOMAIN = "annuity_income"
CLEANSING_REGISTRY = get_cleansing_registry()


class AnnuityIncomeIn(BaseModel):
    """Permissive input model for AnnuityIncome bronze layer data."""

    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_default=True,
    )

    月度: Optional[Union[date, str, int]] = Field(
        None, description="Report date (月度)"
    )
    机构: Optional[str] = Field(
        None, description="Institution (机构) - renamed to 机构代码"
    )
    机构名称: Optional[str] = Field(None, description="Institution name (机构名称)")
    机构代码: Optional[str] = Field(None, description="Institution code (机构代码)")
    计划代码: Optional[str] = Field(None, description="Plan code (计划代码)")
    客户名称: Optional[str] = Field(None, description="Customer name (客户名称)")
    业务类型: Optional[str] = Field(None, description="Business type (业务类型)")
    计划类型: Optional[str] = Field(None, description="Plan type (计划类型)")
    组合代码: Optional[str] = Field(None, description="Portfolio code (组合代码)")
    # Story 5.5.5: Four income fields instead of 收入金额
    固费: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Fixed fee income (固费)"
    )
    浮费: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Variable fee income (浮费)"
    )
    回补: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Rebate income (回补)"
    )
    税: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Tax amount (税)"
    )
    年金账户名: Optional[str] = Field(
        None, description="Pension account name (年金账户名)"
    )
    产品线代码: Optional[str] = Field(
        None, description="Product line code (产品线代码)"
    )
    company_id: Optional[str] = Field(None, description="Company identifier")
    id: Optional[int] = Field(None, description="Auto-generated ID")
    data_source: Optional[str] = Field(None, description="Source file or system")

    @model_validator(mode="before")
    @classmethod
    def convert_nan_to_none(cls, data: Any) -> Dict[str, Any]:
        import math

        if not isinstance(data, dict):
            return cast(Dict[str, Any], data)
        result: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, float) and math.isnan(value):
                result[key] = None
            else:
                result[key] = value
        return result

    # Story 5.5.5: Validator for four income fields instead of 收入金额
    @field_validator("固费", "浮费", "回补", "税", mode="before")
    @classmethod
    def clean_numeric_fields(cls, v: Any, info: ValidationInfo) -> Optional[float]:
        if v is None:
            return v
        field_name = info.field_name or "numeric_field"
        try:
            # Story 7.3-2: Use shared apply_domain_rules with domain parameter
            cleaned = apply_domain_rules(
                v,
                field_name,
                CLEANSING_DOMAIN,
                fallback_rules=DEFAULT_NUMERIC_RULES,
            )
        except ValueError as exc:
            raise ValueError(
                f"Field '{field_name}': Cannot clean numeric value '{v}'. Error: {exc}"
            ) from exc
        if cleaned is None:
            return None
        if isinstance(cleaned, Decimal):
            return float(cleaned)
        if isinstance(cleaned, (int, float)):
            return float(cleaned)
        try:
            return float(cleaned)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Field '{field_name}': Cannot convert '{v}' to number."
            ) from exc

    @field_validator("月度", mode="before")
    @classmethod
    def preprocess_report_date(cls, v: Any) -> Optional[Union[str, int]]:
        if v is None:
            return None
        if isinstance(v, int):
            if MIN_YYYYMM_VALUE <= v <= MAX_YYYYMM_VALUE:  # Valid YYYYMM range
                return str(v)
        return v

    @field_validator(
        "组合代码",
        "计划代码",
        "机构代码",
        "产品线代码",
        "company_id",
        mode="before",
    )
    @classmethod
    def clean_code_fields(cls, v: Any) -> Optional[str]:
        # Story 7.3-2: Use shared clean_code_field function
        return clean_code_field(v)


class AnnuityIncomeOut(BaseModel):
    """Strict output model for AnnuityIncome gold layer data."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
        use_enum_values=True,
        from_attributes=True,
    )

    # Required fields (composite PK: 月度, 计划代码, company_id)
    月度: date = Field(..., description="Report date (月度)")
    计划代码: str = Field(
        ..., min_length=1, max_length=255, description="Plan code identifier"
    )
    company_id: Optional[str] = Field(
        None,  # Nullable - Story 7.3-1
        min_length=1,
        max_length=50,
        description="Company identifier - generated during data cleansing",
    )

    # Required output fields
    客户名称: Optional[str] = Field(
        None, max_length=255, description="Customer name (normalized)"
    )
    产品线代码: str = Field(..., max_length=255, description="Product line code")
    机构代码: str = Field(..., max_length=255, description="Institution code")
    # Story 5.5.5: Four income fields instead of 收入金额
    固费: Decimal | float = Field(
        ..., decimal_places=4, description="Fixed fee income (固费)"
    )
    浮费: Decimal | float = Field(
        ..., decimal_places=4, description="Variable fee income (浮费)"
    )
    回补: Decimal | float = Field(
        ..., decimal_places=4, description="Rebate income (回补)"
    )
    税: Decimal | float = Field(..., decimal_places=4, description="Tax amount (税)")

    # Optional fields
    id: Optional[int] = Field(None, description="Auto-generated ID (handled by DB)")
    业务类型: Optional[str] = Field(None, max_length=255, description="Business type")
    计划类型: Optional[str] = Field(None, max_length=255, description="Plan type")
    组合代码: Optional[str] = Field(None, max_length=255, description="Portfolio code")
    年金账户名: Optional[str] = Field(
        None, max_length=255, description="Pension account name (original 客户名称)"
    )

    @field_validator("月度", mode="before")
    @classmethod
    def parse_date_field(cls, v: Any) -> date:
        try:
            return parse_yyyymm_or_chinese(v)
        except ValueError as e:
            raise ValueError(f"Field '月度': {str(e)}")

    @field_validator("客户名称", mode="before")
    @classmethod
    def clean_customer_name(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        # Story 7.3-2: Use shared clean_customer_name function
        # Story 7.3-1: Allow null values - handled by shared function
        field_name = info.field_name or "客户名称"
        return clean_customer_name(v, field_name, CLEANSING_DOMAIN)

    @field_validator("计划代码", mode="after")
    @classmethod
    def normalize_plan_code(cls, v: str) -> str:
        # Story 7.3-2: Use shared normalize_plan_code function
        # Note: annuity_income requires 计划代码 (non-null), so allow_null=False
        return normalize_plan_code(v, allow_null=False)

    @field_validator("company_id", mode="after")
    @classmethod
    def normalize_company_id(cls, v: Optional[str]) -> Optional[str]:
        # Story 7.3-2: Use shared normalize_company_id function
        # Story 7.3-1: Allow null values - handled by shared function
        return normalize_company_id(v)

    # Story 5.5.5: Validator for four income fields instead of 收入金额
    @field_validator("固费", "浮费", "回补", "税", mode="before")
    @classmethod
    def clean_decimal_fields_output(
        cls, v: Any, info: ValidationInfo
    ) -> Decimal | float:
        field_name = info.field_name or "numeric_field"
        try:
            # Story 7.3-2: Use shared apply_domain_rules with domain parameter
            normalized = apply_domain_rules(
                v, field_name, CLEANSING_DOMAIN, fallback_rules=DEFAULT_NUMERIC_RULES
            )
            cleaned = CLEANSING_REGISTRY.apply_rule(
                normalized, "comprehensive_decimal_cleaning", field_name=field_name
            )
            return cast(Decimal | float, cleaned)
        except ValueError as exc:
            raise ValueError(
                f"Field '{field_name}': Cannot clean numeric value '{v}'. Error: {exc}"
            ) from exc

    @model_validator(mode="after")
    def validate_business_rules(self) -> "AnnuityIncomeOut":
        report_date = self.月度
        if report_date:
            current_date = date.today()
            if report_date > current_date:
                raise ValueError(
                    f"Field '月度': Report date {report_date} cannot be in the future "
                    f"(today: {current_date})"
                )
            if (current_date - report_date).days > MAX_DATE_RANGE_DAYS:
                logger.warning(f"Report date {report_date} is older than 10 years")
        return self


# Story 6.2-P13: EnrichmentStats is now imported from
# work_data_hub.infrastructure.models.shared and re-exported for backward compatibility
# See: src/work_data_hub/infrastructure/models/shared.py


class ProcessingResultWithEnrichment(BaseModel):
    """Result container for AnnuityIncome processing with enrichment stats."""

    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )
    records: List[AnnuityIncomeOut] = Field(
        ..., description="Processed annuity income records"
    )
    enrichment_stats: EnrichmentStats = Field(default_factory=EnrichmentStats)
    unknown_names_csv: Optional[str] = Field(
        None, description="Path to exported unknown names CSV"
    )
    data_source: str = Field("unknown", description="Source file or identifier")
    processing_time_ms: int = Field(0, description="Total processing time")
