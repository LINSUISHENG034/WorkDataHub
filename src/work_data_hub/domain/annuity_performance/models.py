import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.models import ResolutionStatus
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from work_data_hub.infrastructure.cleansing import get_cleansing_registry
from work_data_hub.utils.date_parser import parse_yyyymm_or_chinese

logger = logging.getLogger(__name__)
CLEANSING_DOMAIN = "annuity_performance"
CLEANSING_REGISTRY = get_cleansing_registry()
DEFAULT_COMPANY_RULES = ["trim_whitespace", "normalize_company_name"]
DEFAULT_NUMERIC_RULES: List[Any] = [
    "standardize_null_values",
    "remove_currency_symbols",
    "clean_comma_separated_number",
    {"name": "handle_percentage_conversion"},
]


def apply_domain_rules(value: Any, field_name: str, fallback_rules: Optional[List[Any]] = None) -> Any:
    rules = CLEANSING_REGISTRY.get_domain_rules(CLEANSING_DOMAIN, field_name)
    if not rules:
        rules = fallback_rules or []
    if not rules:
        return value
    return CLEANSING_REGISTRY.apply_rules(value, rules, field_name=field_name)


class AnnuityPerformanceIn(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_default=True,
    )
    年: Optional[str] = Field(None, description="Year field from Excel (年)")
    月: Optional[str] = Field(None, description="Month field from Excel (月)")
    月度: Optional[Union[date, str, int]] = Field(None, description="Report date (月度)")
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
    期初资产规模: Optional[Union[Decimal, float, int, str]] = Field(None, description="Initial asset scale (期初资产规模)")
    期末资产规模: Optional[Union[Decimal, float, int, str]] = Field(None, description="Final asset scale (期末资产规模)")
    供款: Optional[Union[Decimal, float, int, str]] = Field(None, description="Contribution (供款)")
    流失_含待遇支付: Optional[Union[Decimal, float, int, str]] = Field(
        None,
        description="Loss including benefit payment (流失_含待遇支付)",
        alias="流失(含待遇支付)",
        serialization_alias="流失(含待遇支付)",
    )
    流失: Optional[Union[Decimal, float, int, str]] = Field(None, description="Loss (流失)")
    待遇支付: Optional[Union[Decimal, float, int, str]] = Field(None, description="Benefit payment (待遇支付)")
    投资收益: Optional[Union[Decimal, float, int, str]] = Field(None, description="Investment return (投资收益)")
    当期收益率: Optional[Union[Decimal, float, int, str]] = Field(
        None,
        description="Current period return rate (当期收益率)",
        validation_alias=AliasChoices("当期收益率", "年化收益率"),
    )
    机构代码: Optional[str] = Field(None, description="Institution code (机构代码)")
    机构名称: Optional[str] = Field(None, description="Institution name (机构名称)", alias="机构")
    产品线代码: Optional[str] = Field(None, description="Product line code (产品线代码)")
    年金账户号: Optional[str] = Field(None, description="Pension account number (年金账户号)")
    年金账户名: Optional[str] = Field(None, description="Pension account name (年金账户名)")
    子企业号: Optional[str] = Field(None, description="Sub-enterprise number (子企业号)")
    子企业名称: Optional[str] = Field(None, description="Sub-enterprise name (子企业名称)")
    集团企业客户号: Optional[str] = Field(None, description="Group enterprise customer number (集团企业客户号)")
    集团企业客户名称: Optional[str] = Field(None, description="Group enterprise customer name (集团企业客户名称)")
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
        v_str = v_str.replace("年", "").replace("月", "").replace("/", "").replace("-", "")
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
            cleaned = apply_domain_rules(
                v,
                field_name,
                fallback_rules=DEFAULT_NUMERIC_RULES,
            )
        except ValueError as exc:
            raise ValueError(f"Field '{field_name}': Cannot clean numeric value '{v}'. Error: {exc}") from exc
        if cleaned is None:
            return None
        if isinstance(cleaned, Decimal):
            return float(cleaned)
        if isinstance(cleaned, (int, float)):
            return float(cleaned)
        try:
            return float(cleaned)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Field '{field_name}': Cannot convert '{v}' to number.") from exc

    @field_validator("月度", mode="before")
    @classmethod
    def preprocess_report_date(cls, v: Any) -> Optional[Union[str, int]]:
        if v is None:
            return None
        if isinstance(v, int):
            if 200000 <= v <= 999999:  # Valid YYYYMM range
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
    def clean_code_fields(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s_val = str(v).strip()
        return s_val if s_val else None

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
    )
    计划代码: str = Field(..., min_length=1, max_length=255, description="Plan code identifier")
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
    期初资产规模: Optional[Decimal] = Field(None, decimal_places=4, ge=0, description="Initial asset scale (non-negative)")
    期末资产规模: Optional[Decimal] = Field(None, decimal_places=4, ge=0, description="Final asset scale")
    供款: Optional[Decimal] = Field(None, decimal_places=4, ge=0, description="Contribution (non-negative)")
    流失_含待遇支付: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Loss including benefit payment",
        validation_alias="流失(含待遇支付)",
    )
    流失: Optional[Decimal] = Field(None, decimal_places=4, description="Loss")
    待遇支付: Optional[Decimal] = Field(None, decimal_places=4, description="Benefit payment")
    投资收益: Optional[Decimal] = Field(None, decimal_places=4, description="Investment return (can be negative)")
    当期收益率: Optional[Decimal] = Field(
        None,
        decimal_places=6,
        ge=-1.0,
        le=10.0,
        description="Current period return rate (当期收益率, sanity check range)",
        validation_alias=AliasChoices("当期收益率", "年化收益率"),
    )
    机构代码: Optional[str] = Field(None, max_length=255, description="Institution code")
    机构名称: Optional[str] = Field(None, max_length=255, description="Institution name")
    产品线代码: Optional[str] = Field(None, max_length=255, description="Product line code")
    年金账户号: Optional[str] = Field(None, max_length=50, description="Pension account number")
    年金账户名: Optional[str] = Field(None, max_length=255, description="Pension account name")
    子企业号: Optional[str] = Field(None, max_length=50, description="Sub-enterprise number (子企业号)")
    子企业名称: Optional[str] = Field(None, max_length=255, description="Sub-enterprise name (子企业名称)")
    集团企业客户号: Optional[str] = Field(None, max_length=50, description="Group enterprise customer number")
    集团企业客户名称: Optional[str] = Field(None, max_length=255, description="Group enterprise customer name")

    @field_validator("月度", mode="before")
    @classmethod
    def parse_date_field(cls, v: Any) -> Optional[date]:
        if v is None:
            return v
        try:
            return parse_yyyymm_or_chinese(v)
        except ValueError as e:
            raise ValueError(f"Field '月度': {str(e)}")

    @field_validator("客户名称", mode="before")
    @classmethod
    def clean_customer_name(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        if v is None:
            return v
        try:
            field_name = info.field_name or "客户名称"
            return apply_domain_rules(
                v,
                field_name,
                fallback_rules=DEFAULT_COMPANY_RULES,
            )
        except Exception as e:
            raise ValueError(f"Field '客户名称': Cannot clean company name '{v}'. Error: {e}")

    @field_validator("计划代码", mode="after")
    @classmethod
    def normalize_codes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
        if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
            raise ValueError(f"Code cannot be empty after normalization: {v}")
        return normalized

    @field_validator("company_id", mode="after")
    @classmethod
    def normalize_company_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
        if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
            raise ValueError(f"company_id cannot be empty after normalization: {v}")
        return normalized

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
    def clean_decimal_fields_output(cls, v: Any, info: ValidationInfo) -> Optional[Decimal]:
        if v is None:
            return None
        field_name = info.field_name or "numeric_field"
        try:
            normalized = apply_domain_rules(v, field_name, fallback_rules=DEFAULT_NUMERIC_RULES)
            cleaned = CLEANSING_REGISTRY.apply_rule(normalized, "comprehensive_decimal_cleaning", field_name=field_name)
            return cast(Optional[Decimal], cleaned)
        except ValueError as exc:
            raise ValueError(f"Field '{field_name}': Cannot clean numeric value '{v}'. Error: {exc}") from exc

    @model_validator(mode="after")
    def validate_business_rules(self) -> "AnnuityPerformanceOut":
        report_date = self.月度
        if report_date:
            current_date = date.today()
            if report_date > current_date:
                raise ValueError(f"Field '月度': Report date {report_date} cannot be in the future (today: {current_date})")
            if (current_date - report_date).days > 3650:
                logger.warning(f"Report date {report_date} is older than 10 years")
        return self

    @property
    def 年化收益率(self) -> Optional[Decimal]:
        return getattr(self, "当期收益率")

    @年化收益率.setter
    def 年化收益率(self, value: Optional[Decimal]) -> None:
        setattr(self, "当期收益率", value)


class EnrichmentStats(BaseModel):
    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )
    total_records: int = 0
    success_internal: int = 0  # Resolved via internal mappings
    success_external: int = 0  # Resolved via EQC lookup + cached
    pending_lookup: int = 0  # Queued for async processing
    temp_assigned: int = 0  # Assigned temporary ID
    failed: int = 0  # Resolution failed completely
    sync_budget_used: int = 0  # EQC lookups consumed from budget
    processing_time_ms: int = 0  # Total enrichment processing time

    def record(self, status: "ResolutionStatus", source: Optional[str] = None) -> None:
        from work_data_hub.domain.company_enrichment.models import ResolutionStatus

        self.total_records += 1
        if status == ResolutionStatus.SUCCESS_INTERNAL:
            self.success_internal += 1
        elif status == ResolutionStatus.SUCCESS_EXTERNAL:
            self.success_external += 1
            self.sync_budget_used += 1
        elif status == ResolutionStatus.PENDING_LOOKUP:
            self.pending_lookup += 1
        elif status == ResolutionStatus.TEMP_ASSIGNED:
            self.temp_assigned += 1
        else:
            self.failed += 1


class ProcessingResultWithEnrichment(BaseModel):
    model_config = ConfigDict(
        validate_default=True,
        extra="forbid",
    )
    records: List[AnnuityPerformanceOut] = Field(..., description="Processed annuity performance records")
    enrichment_stats: EnrichmentStats = Field(default_factory=EnrichmentStats)
    unknown_names_csv: Optional[str] = Field(None, description="Path to exported unknown names CSV")
    data_source: str = Field("unknown", description="Source file or identifier")
    processing_time_ms: int = Field(0, description="Total processing time")
