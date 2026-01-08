import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

if TYPE_CHECKING:
    pass
from pydantic import (
    AliasChoices,
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

# Date validation constants (Story 7.1-16)
MIN_VALID_YEAR = 2000  # Earliest valid year for report dates
MAX_VALID_YEAR = 2030  # Latest valid year for report dates

logger = logging.getLogger(__name__)
CLEANSING_DOMAIN = "annuity_performance"
CLEANSING_REGISTRY = get_cleansing_registry()

# Note: DEFAULT_NUMERIC_RULES from shared module doesn't include
# "handle_percentage_conversion", so we add it here for annuity_performance
DEFAULT_NUMERIC_RULES_WITH_PERCENTAGE = [
    *DEFAULT_NUMERIC_RULES,
    {"name": "handle_percentage_conversion"},
]


class AnnuityPerformanceIn(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_default=True,
    )
    年: Optional[str] = Field(None, description="Year field from Excel (年)")
    月: Optional[str] = Field(None, description="Month field from Excel (月)")
    月度: Optional[Union[date, str, int]] = Field(
        None, description="Report date (月度)"
    )
    计划代码: Optional[str] = Field(None, description="Plan code (计划代码)")
    公司代码: Optional[str] = Field(None, description="Company code - for mapping")
    id: Optional[int] = Field(None, description="Auto-generated ID")
    业务类型: Optional[str] = Field(None, description="Business type (业务类型)")
    计划类型: Optional[str] = Field(None, description="Plan type (计划类型)")
    计划名称: Optional[str] = Field(None, description="Plan name (计划名称)")
    组合类型: Optional[str] = Field(None, description="Portfolio type (组合类型)")
    组合代码: Optional[str] = Field(None, description="Portfolio code (组合代码)")
    组合名称: Optional[str] = Field(None, description="Portfolio name (组合名称)")
    客户名称: Optional[str] = Field(None, description="Customer name (客户名称)")
    期初资产规模: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Initial asset scale (期初资产规模)"
    )
    期末资产规模: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Final asset scale (期末资产规模)"
    )
    供款: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Contribution (供款)"
    )
    流失_含待遇支付: Optional[Union[Decimal, float, int, str]] = Field(
        None,
        description="Loss including benefit payment (流失_含待遇支付)",
        alias="流失(含待遇支付)",
        serialization_alias="流失(含待遇支付)",
    )
    流失: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Loss (流失)"
    )
    待遇支付: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Benefit payment (待遇支付)"
    )
    投资收益: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Investment return (投资收益)"
    )
    当期收益率: Optional[Union[Decimal, float, int, str]] = Field(
        None,
        description="Current period return rate (当期收益率)",
        validation_alias=AliasChoices("当期收益率", "年化收益率"),
    )
    机构代码: Optional[str] = Field(None, description="Institution code (机构代码)")
    机构名称: Optional[str] = Field(
        None, description="Institution name (机构名称)", alias="机构"
    )
    产品线代码: Optional[str] = Field(
        None, description="Product line code (产品线代码)"
    )
    年金账户号: Optional[str] = Field(
        None, description="Pension account number (年金账户号)"
    )
    年金账户名: Optional[str] = Field(
        None, description="Pension account name (年金账户名)"
    )
    子企业号: Optional[str] = Field(
        None, description="Sub-enterprise number (子企业号)"
    )
    子企业名称: Optional[str] = Field(
        None, description="Sub-enterprise name (子企业名称)"
    )
    集团企业客户号: Optional[str] = Field(
        None, description="Group enterprise customer number (集团企业客户号)"
    )
    集团企业客户名称: Optional[str] = Field(
        None, description="Group enterprise customer name (集团企业客户名称)"
    )
    company_id: Optional[str] = Field(None, description="Company identifier")
    report_period: Optional[str] = Field(None, description="Report period string")
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

    @field_validator("年", "月", mode="before")
    @classmethod
    def clean_date_component_fields(cls, v: Any) -> Optional[str]:
        if v is None:
            return v
        v_str = str(v).strip()
        v_str = (
            v_str.replace("年", "").replace("月", "").replace("/", "").replace("-", "")
        )
        return v_str if v_str else None

    @field_validator(
        "期初资产规模",
        "期末资产规模",
        "供款",
        "流失_含待遇支付",
        "流失",
        "待遇支付",
        "投资收益",
        "当期收益率",
        mode="before",
    )
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
                fallback_rules=DEFAULT_NUMERIC_RULES_WITH_PERCENTAGE,
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
        "公司代码",
        "机构代码",
        "产品线代码",
        "年金账户号",
        "company_id",
        mode="before",
    )
    @classmethod
    def clean_code_field(cls, v: Any) -> Optional[str]:
        # Story 7.3-2: Use shared clean_code_field function
        # Story 7.3-3: Renamed from clean_code_fields (plural) for consistency
        return clean_code_field(v)

    @property
    def 年化收益率(self) -> Optional[Union[Decimal, float, int, str]]:
        return getattr(self, "当期收益率")

    @年化收益率.setter
    def 年化收益率(self, value: Optional[Union[Decimal, float, int, str]]) -> None:
        setattr(self, "当期收益率", value)


class AnnuityPerformanceOut(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
        use_enum_values=True,
        from_attributes=True,
        populate_by_name=True,
    )
    计划代码: str = Field(
        ..., min_length=1, max_length=255, description="Plan code identifier"
    )
    company_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Company identifier - generated during data cleansing",
    )
    id: Optional[int] = Field(None, description="Auto-generated ID (handled by DB)")
    月度: Optional[date] = Field(None, description="Report date (月度)")
    业务类型: Optional[str] = Field(None, max_length=255, description="Business type")
    计划类型: Optional[str] = Field(None, max_length=255, description="Plan type")
    计划名称: Optional[str] = Field(None, max_length=255, description="Plan name")
    组合类型: Optional[str] = Field(None, max_length=255, description="Portfolio type")
    组合代码: Optional[str] = Field(None, max_length=255, description="Portfolio code")
    组合名称: Optional[str] = Field(None, max_length=255, description="Portfolio name")
    客户名称: Optional[str] = Field(None, max_length=255, description="Customer name")
    期初资产规模: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Initial asset scale (can be negative for adjustments)",
    )
    期末资产规模: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Final asset scale (can be negative for adjustments)",
    )
    供款: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Contribution (can be negative for adjustments)",
    )
    流失_含待遇支付: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Loss including benefit payment",
        validation_alias="流失(含待遇支付)",
    )
    流失: Optional[Decimal] = Field(None, decimal_places=4, description="Loss")
    待遇支付: Optional[Decimal] = Field(
        None, decimal_places=4, description="Benefit payment"
    )
    投资收益: Optional[Decimal] = Field(
        None, decimal_places=4, description="Investment return (can be negative)"
    )
    当期收益率: Optional[Decimal] = Field(
        None,
        decimal_places=6,
        ge=-1.0,
        le=10.0,
        description="Current period return rate (当期收益率, sanity check range)",
        validation_alias=AliasChoices("当期收益率", "年化收益率"),
    )
    机构代码: Optional[str] = Field(
        None, max_length=255, description="Institution code"
    )
    机构名称: Optional[str] = Field(
        None, max_length=255, description="Institution name"
    )
    产品线代码: Optional[str] = Field(
        None, max_length=255, description="Product line code"
    )
    年金账户号: Optional[str] = Field(
        None, max_length=50, description="Pension account number"
    )
    年金账户名: Optional[str] = Field(
        None, max_length=255, description="Pension account name"
    )
    子企业号: Optional[str] = Field(
        None, max_length=50, description="Sub-enterprise number (子企业号)"
    )
    子企业名称: Optional[str] = Field(
        None, max_length=255, description="Sub-enterprise name (子企业名称)"
    )
    集团企业客户号: Optional[str] = Field(
        None, max_length=50, description="Group enterprise customer number"
    )
    集团企业客户名称: Optional[str] = Field(
        None, max_length=255, description="Group enterprise customer name"
    )

    @field_validator("月度", mode="before")
    @classmethod
    def parse_date_field(cls, v: Any) -> Optional[date]:
        if v is None:
            return v
        try:
            parsed = parse_yyyymm_or_chinese(v)
            if parsed.year < MIN_VALID_YEAR or parsed.year > MAX_VALID_YEAR:
                raise ValueError(
                    f"Cannot parse '{v}': outside valid range "
                    f"({MIN_VALID_YEAR}-{MAX_VALID_YEAR})"
                )
            return parsed
        except ValueError as e:
            raise ValueError(f"Field '月度': {str(e)}")

    @field_validator("客户名称", mode="before")
    @classmethod
    def clean_customer_name(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        # Story 7.3-2: Use shared clean_customer_name function
        field_name = info.field_name or "客户名称"
        return clean_customer_name(v, field_name, CLEANSING_DOMAIN)

    @field_validator("计划代码", mode="after")
    @classmethod
    def normalize_plan_code(cls, v: Optional[str]) -> Optional[str]:
        # Story 7.3-2: Use shared normalize_plan_code function
        # Story 7.3-3: Renamed from normalize_codes for consistency
        # Note: annuity_performance allows null for 计划代码
        return normalize_plan_code(v, allow_null=True)

    @field_validator("company_id", mode="after")
    @classmethod
    def normalize_company_id(cls, v: Optional[str]) -> Optional[str]:
        # Story 7.3-2: Use shared normalize_company_id function
        return normalize_company_id(v)

    @field_validator(
        "期初资产规模",
        "期末资产规模",
        "供款",
        "流失_含待遇支付",
        "流失",
        "待遇支付",
        "投资收益",
        "当期收益率",
        mode="before",
    )
    @classmethod
    def clean_decimal_fields_output(
        cls, v: Any, info: ValidationInfo
    ) -> Optional[Decimal]:
        if v is None:
            return None
        field_name = info.field_name or "numeric_field"
        try:
            # Story 7.3-2: Use shared apply_domain_rules with domain parameter
            normalized = apply_domain_rules(
                v,
                field_name,
                CLEANSING_DOMAIN,
                fallback_rules=DEFAULT_NUMERIC_RULES_WITH_PERCENTAGE,
            )
            cleaned = CLEANSING_REGISTRY.apply_rule(
                normalized, "comprehensive_decimal_cleaning", field_name=field_name
            )
            return cast(Optional[Decimal], cleaned)
        except ValueError as exc:
            raise ValueError(
                f"Field '{field_name}': Cannot clean numeric value '{v}'. Error: {exc}"
            ) from exc

    @model_validator(mode="after")
    def validate_business_rules(self) -> "AnnuityPerformanceOut":
        report_date = self.月度
        if report_date:
            current_date = date.today()
            if report_date > current_date:
                raise ValueError(
                    f"Field '月度': Report date {report_date} cannot be in the future (today: {current_date})"
                )
            if (current_date - report_date).days > MAX_DATE_RANGE_DAYS:
                logger.warning(f"Report date {report_date} is older than 10 years")
        return self

    @property
    def 年化收益率(self) -> Optional[Decimal]:
        return getattr(self, "当期收益率")

    @年化收益率.setter
    def 年化收益率(self, value: Optional[Decimal]) -> None:
        setattr(self, "当期收益率", value)


# Story 6.2-P13: EnrichmentStats is now imported from
# work_data_hub.infrastructure.models.shared and re-exported for backward compatibility
# See: src/work_data_hub/infrastructure/models/shared.py


class ProcessingResultWithEnrichment(BaseModel):
    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )
    records: List[AnnuityPerformanceOut] = Field(
        ..., description="Processed annuity performance records"
    )
    enrichment_stats: EnrichmentStats = Field(default_factory=EnrichmentStats)
    unknown_names_csv: Optional[str] = Field(
        None, description="Path to exported unknown names CSV"
    )
    data_source: str = Field("unknown", description="Source file or identifier")
    processing_time_ms: int = Field(0, description="Total processing time")
