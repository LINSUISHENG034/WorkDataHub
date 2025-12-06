import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.models import ResolutionStatus
from pydantic import (
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
CLEANSING_DOMAIN = "annuity_income"
CLEANSING_REGISTRY = get_cleansing_registry()
DEFAULT_COMPANY_RULES = ["trim_whitespace", "normalize_company_name"]
DEFAULT_NUMERIC_RULES: List[Any] = [
    "standardize_null_values",
    "remove_currency_symbols",
    "clean_comma_separated_number",
]


def apply_domain_rules(
    value: Any, field_name: str, fallback_rules: Optional[List[Any]] = None
) -> Any:
    """Apply cleansing rules from registry for the annuity_income domain."""
    rules = CLEANSING_REGISTRY.get_domain_rules(CLEANSING_DOMAIN, field_name)
    if not rules:
        rules = fallback_rules or []
    if not rules:
        return value
    return CLEANSING_REGISTRY.apply_rules(value, rules, field_name=field_name)


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
    计划号: Optional[str] = Field(None, description="Plan code (计划号)")
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
            cleaned = apply_domain_rules(
                v,
                field_name,
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
            if 200000 <= v <= 999999:  # Valid YYYYMM range
                return str(v)
        return v

    @field_validator(
        "组合代码",
        "计划号",
        "机构代码",
        "产品线代码",
        "company_id",
        mode="before",
    )
    @classmethod
    def clean_code_fields(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s_val = str(v).strip()
        return s_val if s_val else None


class AnnuityIncomeOut(BaseModel):
    """Strict output model for AnnuityIncome gold layer data."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_default=True,
        use_enum_values=True,
        from_attributes=True,
    )

    # Required fields (composite PK: 月度, 计划号, company_id)
    月度: date = Field(..., description="Report date (月度)")
    计划号: str = Field(
        ..., min_length=1, max_length=255, description="Plan code identifier"
    )
    company_id: str = Field(
        ...,  # Required for gold output parity and composite PK
        min_length=1,
        max_length=50,
        description="Company identifier - generated during data cleansing",
    )

    # Required output fields
    客户名称: str = Field(..., max_length=255, description="Customer name (normalized)")
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
    def clean_customer_name(cls, v: Any, info: ValidationInfo) -> str:
        try:
            field_name = info.field_name or "客户名称"
            return apply_domain_rules(
                v,
                field_name,
                fallback_rules=DEFAULT_COMPANY_RULES,
            )
        except Exception as e:
            raise ValueError(
                f"Field '客户名称': Cannot clean company name '{v}'. Error: {e}"
            )

    @field_validator("计划号", mode="after")
    @classmethod
    def normalize_plan_code(cls, v: str) -> str:
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
        if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
            raise ValueError(f"Plan code cannot be empty after normalization: {v}")
        return normalized

    @field_validator("company_id", mode="after")
    @classmethod
    def normalize_company_id(cls, v: str) -> str:
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")
        if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
            raise ValueError(f"company_id cannot be empty after normalization: {v}")
        return normalized

    # Story 5.5.5: Validator for four income fields instead of 收入金额
    @field_validator("固费", "浮费", "回补", "税", mode="before")
    @classmethod
    def clean_decimal_fields_output(
        cls, v: Any, info: ValidationInfo
    ) -> Decimal | float:
        field_name = info.field_name or "numeric_field"
        try:
            normalized = apply_domain_rules(
                v, field_name, fallback_rules=DEFAULT_NUMERIC_RULES
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
            if (current_date - report_date).days > 3650:
                logger.warning(f"Report date {report_date} is older than 10 years")
        return self


# NOTE(5.5.4-deferred): Extraction deferred to Epic 6
# Reason: Low risk, but bundled with other model extractions for consistency
# See: docs/sprint-artifacts/epic-5.5-optimization-recommendations.md "Reuse Candidates"
# table
# Duplicated from: annuity_performance/models.py
# Reuse potential: HIGH - Epic 6 will extract to infrastructure/models/shared.py
class EnrichmentStats(BaseModel):
    """Statistics for company ID enrichment process."""

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
