"""
Pydantic v2 data models for annuity performance domain.

This module defines the input and output data contracts for annuity performance
data processing, providing robust validation and type safety using Pydantic v2.
Handles Chinese column names from "规模明细" Excel sheets.

Story 2.1 Enhancements:
- AC1: Loose validation with Optional[Union[...]] for messy Excel data
- AC2: Strict validation with required fields and business rules
- AC3: Custom validators with inline placeholders for Story 2.3/2.4
- AC4: Clear error messages with field context
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional, Union

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

from src.work_data_hub.cleansing import get_cleansing_registry
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


def apply_domain_rules(
    value: Any,
    field_name: str,
    fallback_rules: Optional[List[Any]] = None,
) -> Any:
    """Helper to resolve per-domain rule chains with fallback logic."""
    rules = CLEANSING_REGISTRY.get_domain_rules(CLEANSING_DOMAIN, field_name)
    if not rules:
        rules = fallback_rules or []

    if not rules:
        return value

    return CLEANSING_REGISTRY.apply_rules(
        value,
        rules,
        field_name=field_name,
    )



class AnnuityPerformanceIn(BaseModel):
    """
    Input model for raw annuity performance data from Excel files.

    This model accepts flexible input from Excel parsing with minimal validation,
    allowing for various column naming conventions and data formats commonly
    found in "规模明细" sheets.
    """

    model_config = ConfigDict(
        # Allow extra fields to handle varying Excel column structures
        extra="allow",
        # Automatically strip whitespace from string fields
        str_strip_whitespace=True,
        # Use original field names as-is from Excel
        populate_by_name=True,
        # Validate default values
        validate_default=True,
    )

    # Core identification fields (Chinese column names from DDL)
    年: Optional[str] = Field(None, description="Year field from Excel (年)")
    月: Optional[str] = Field(None, description="Month field from Excel (月)")
    月度: Optional[Union[date, str, int]] = Field(
        None, description="Report date (月度)"
    )
    计划代码: Optional[str] = Field(None, description="Plan code (计划代码)")
    公司代码: Optional[str] = Field(None, description="Company code - for mapping")

    # All DDL columns from "规模明细" table
    # Metadata and identification
    id: Optional[int] = Field(None, description="Auto-generated ID")
    业务类型: Optional[str] = Field(None, description="Business type (业务类型)")
    计划类型: Optional[str] = Field(None, description="Plan type (计划类型)")
    计划名称: Optional[str] = Field(None, description="Plan name (计划名称)")
    组合类型: Optional[str] = Field(None, description="Portfolio type (组合类型)")
    组合代码: Optional[str] = Field(None, description="Portfolio code (组合代码)")
    组合名称: Optional[str] = Field(None, description="Portfolio name (组合名称)")
    客户名称: Optional[str] = Field(None, description="Customer name (客户名称)")

    # Financial metrics (double precision in DDL)
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
        # Support both standardized and original column names
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
        None, description="Current period return rate (当期收益率)"
    )

    # Organizational fields
    机构代码: Optional[str] = Field(None, description="Institution code (机构代码)")
    机构名称: Optional[str] = Field(
        None,
        description="Institution name (机构名称)",
        # Support both '机构' and '机构名称' column names from Excel
        alias="机构",
    )
    产品线代码: Optional[str] = Field(
        None, description="Product line code (产品线代码)"
    )

    # Pension account fields
    年金账户号: Optional[str] = Field(
        None, description="Pension account number (年金账户号)"
    )
    年金账户名: Optional[str] = Field(
        None, description="Pension account name (年金账户名)"
    )

    # Enterprise group fields (from production data)
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

    # English fields for compatibility
    company_id: Optional[str] = Field(None, description="Company identifier")

    # Metadata fields
    report_period: Optional[str] = Field(None, description="Report period string")
    data_source: Optional[str] = Field(None, description="Source file or system")

    @field_validator("年", "月", mode="before")
    @classmethod
    def clean_date_component_fields(cls, v):
        """Clean year/month fields that may contain non-numeric characters."""
        if v is None:
            return v

        # Convert to string and strip whitespace
        v_str = str(v).strip()

        # Remove common non-numeric characters
        v_str = (
            v_str.replace("年", "").replace("月", "").replace("/", "").replace("-", "")
        )

        # Return cleaned string (will be validated later in transformation)
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
    def clean_numeric_fields(cls, v, info: ValidationInfo):
        """
        Clean numeric fields from Excel with comma-separated numbers.

        AC1: Handle messy Excel data like "1,234.56", "¥1,234", "5.5%", placeholders
        """
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
                f"Field '{field_name}': Cannot convert '{v}' to number. Expected numeric format."
            ) from exc

    @field_validator("月度", mode="before")
    @classmethod
    def preprocess_report_date(cls, v):
        """
        Preprocess 月度 field to handle integer dates from Excel.

        Excel often returns date fields as integers like 202411.
        This validator converts them to strings so they can be processed
        by the unified date parser in the service layer.
        """
        if v is None:
            return None

        # If it's an integer that looks like YYYYMM, convert to string
        if isinstance(v, int):
            if 200000 <= v <= 999999:  # Valid YYYYMM range
                return str(v)

        # Return other types as-is (date, str)
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
    def clean_code_fields(cls, v):
        """Convert code fields to strings to handle integer values from Excel."""
        if v is None:
            return v
        # Convert any numeric or other type to string
        return str(v).strip() if str(v).strip() else None


class AnnuityPerformanceOut(BaseModel):
    """
    Output model for validated and normalized annuity performance data.

    This model enforces strict validation rules and provides clean, typed data
    suitable for loading into the "规模明细" PostgreSQL table with consistent
    field names and formats matching the DDL schema.

    Story 2.1 AC2 Enhancements:
    - Strict required types for critical fields
    - Non-negative constraints on asset values
    - Business rule validation via @model_validator
    """

    model_config = ConfigDict(
        # Strict validation - no extra fields allowed in output
        extra="forbid",
        # Strip whitespace from strings
        str_strip_whitespace=True,
        # Validate all fields including defaults
        validate_default=True,
        # Use enum values for serialization
        use_enum_values=True,
        # Allow validation from ORM objects
        from_attributes=True,
    )

    # Core required fields matching composite PK from data_sources.yml
    计划代码: str = Field(
        ..., min_length=1, max_length=255, description="Plan code identifier"
    )
    # company_id将在后续数据清洗步骤中生成（Epic 5 - Company Enrichment）
    company_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Company identifier - generated during data cleansing",
    )

    # All fields from DDL schema - exact column name mapping
    id: Optional[int] = Field(None, description="Auto-generated ID (handled by DB)")
    月度: Optional[date] = Field(None, description="Report date (月度)")
    业务类型: Optional[str] = Field(None, max_length=255, description="Business type")
    计划类型: Optional[str] = Field(None, max_length=255, description="Plan type")
    计划名称: Optional[str] = Field(None, max_length=255, description="Plan name")
    组合类型: Optional[str] = Field(None, max_length=255, description="Portfolio type")
    组合代码: Optional[str] = Field(None, max_length=255, description="Portfolio code")
    组合名称: Optional[str] = Field(None, max_length=255, description="Portfolio name")
    客户名称: Optional[str] = Field(None, max_length=255, description="Customer name")

    # Financial metrics with proper precision and constraints (AC2: non-negative)
    期初资产规模: Optional[Decimal] = Field(
        None, decimal_places=4, ge=0, description="Initial asset scale (non-negative)"
    )
    期末资产规模: Optional[Decimal] = Field(
        None, decimal_places=4, ge=0, description="Final asset scale (non-negative, AC2 requirement)"
    )
    供款: Optional[Decimal] = Field(
        None, decimal_places=4, ge=0, description="Contribution (non-negative)"
    )
    # Preserve original alias throughout serialization so downstream SQL can reuse it
    流失_含待遇支付: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Loss including benefit payment",
        alias="流失(含待遇支付)",
        validation_alias="流失(含待遇支付)",
        serialization_alias="流失(含待遇支付)",
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
        description="Current period return rate (当期收益率, sanity check range)"
    )

    # Organizational fields
    机构代码: Optional[str] = Field(
        None, max_length=255, description="Institution code"
    )
    机构名称: Optional[str] = Field(
        None, max_length=255, description="Institution name"
    )
    产品线代码: Optional[str] = Field(
        None, max_length=255, description="Product line code"
    )

    # Pension account fields
    年金账户号: Optional[str] = Field(
        None, max_length=50, description="Pension account number"
    )
    年金账户名: Optional[str] = Field(
        None, max_length=255, description="Pension account name"
    )

    # Enterprise group fields (from production data)
    子企业号: Optional[str] = Field(
        None, max_length=50, description="Sub-enterprise number (子企业号)"
    )
    子企业名称: Optional[str] = Field(
        None, max_length=255, description="Sub-enterprise name (子企业名称)"
    )
    集团企业客户号: Optional[str] = Field(
        None, max_length=50, description="Group enterprise customer number (集团企业客户号)"
    )
    集团企业客户名称: Optional[str] = Field(
        None, max_length=255, description="Group enterprise customer name (集团企业客户名称)"
    )

    @field_validator('月度', mode='before')
    @classmethod
    def parse_date_field(cls, v):
        """
        AC3: Parse dates using the shared date parser utility.

        Examples:
            202501 → date(2025, 1, 1)
            "2025年1月" → date(2025, 1, 1)
            "2025-01" → date(2025, 1, 1)

        Raises:
            ValueError: If date cannot be parsed or is outside 2000-2030 range
        """
        if v is None:
            return v
        try:
            return parse_yyyymm_or_chinese(v)
        except ValueError as e:
            raise ValueError(
                f"Field '月度': {str(e)}"
            )

    @field_validator('客户名称', mode='before')
    @classmethod
    def clean_customer_name(cls, v, info: ValidationInfo):
        """
        AC3: Clean company names using CleansingRegistry rules.

        Raises:
            ValueError: If cleaning fails
        """
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
            raise ValueError(
                f"Field '客户名称': Cannot clean company name '{v}'. Error: {e}"
            )

    @field_validator("计划代码", mode="after")
    @classmethod
    def normalize_codes(cls, v: str) -> str:
        """Normalize identifier codes to uppercase and remove special chars."""
        if v is None:
            return v

        # Convert to uppercase and remove common separators
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")

        # Validate final format (allow Chinese characters and alphanumeric)
        if not normalized.replace(".", "").replace("（", "").replace("）", "").strip():
            raise ValueError(f"Code cannot be empty after normalization: {v}")

        return normalized

    @field_validator("company_id", mode="after")
    @classmethod
    def normalize_company_id(cls, v: Optional[str]) -> Optional[str]:
        """Normalize company_id if present (Optional field)."""
        if v is None:
            return v

        # Convert to uppercase and remove common separators
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")

        # Validate final format
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
    def clean_decimal_fields_output(cls, v, info: ValidationInfo):
        """
        AC2: Clean decimal fields for strict output validation.

        Uses the CleansingRegistry to standardize numeric inputs before conversion.
        """
        if v is None:
            return v
        field_name = info.field_name or "numeric_field"
        try:
            normalized = apply_domain_rules(
                v,
                field_name,
                fallback_rules=DEFAULT_NUMERIC_RULES,
            )
            return CLEANSING_REGISTRY.apply_rule(
                normalized,
                "comprehensive_decimal_cleaning",
                field_name=field_name,
            )
        except ValueError as exc:
            raise ValueError(
                f"Field '{field_name}': Cannot clean numeric value '{v}'. Error: {exc}"
            ) from exc

    @model_validator(mode="after")
    def validate_business_rules(self) -> "AnnuityPerformanceOut":
        """
        AC2: Cross-field business rules validation

        Business Rules:
        1. Report date must not be in the future
        2. Report date should not be older than 10 years (warning only)

        Raises:
            ValueError: If business rules are violated
        """
        # Rule 1: Check report date is not in the future
        report_date = self.月度
        if report_date:
            current_date = date.today()

            if report_date > current_date:
                raise ValueError(
                    f"Field '月度': Report date {report_date} cannot be in the future "
                    f"(today: {current_date})"
                )

            # Rule 2: Warn if date is too old (more than 10 years) - just log, don't fail
            if (current_date - report_date).days > 3650:
                logger.warning(
                    f"Report date {report_date} is older than 10 years (today: {current_date})"
                )

        return self


# ===== Company Enrichment Integration Models =====
# These models support optional company enrichment functionality


class EnrichmentStats(BaseModel):
    """Statistics collection for company enrichment operations."""

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

    def record(self, status: "ResolutionStatus", source: Optional[str] = None):
        """Record a resolution result for statistics tracking."""
        # Import here to avoid circular import
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
    """Extended processing result including enrichment statistics and exports."""

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
