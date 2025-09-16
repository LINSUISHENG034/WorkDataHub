"""
Pydantic v2 data models for annuity performance domain.

This module defines the input and output data contracts for annuity performance
data processing, providing robust validation and type safety using Pydantic v2.
Handles Chinese column names from "规模明细" Excel sheets.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional, Union

if TYPE_CHECKING:
    from work_data_hub.domain.company_enrichment.models import ResolutionStatus

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)


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
    月度: Optional[Union[date, str, int]] = Field(None, description="Report date (月度)")
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
    供款: Optional[Union[Decimal, float, int, str]] = Field(None, description="Contribution (供款)")
    流失_含待遇支付: Optional[Union[Decimal, float, int, str]] = Field(
        None,
        description="Loss including benefit payment (流失_含待遇支付)",
        # Support both standardized and original column names
        alias="流失(含待遇支付)",
        serialization_alias="流失(含待遇支付)",
    )
    流失: Optional[Union[Decimal, float, int, str]] = Field(None, description="Loss (流失)")
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
        alias="机构"
    )
    产品线代码: Optional[str] = Field(None, description="Product line code (产品线代码)")

    # Pension account fields
    年金账户号: Optional[str] = Field(None, description="Pension account number (年金账户号)")
    年金账户名: Optional[str] = Field(None, description="Pension account name (年金账户名)")

    # English fields for compatibility
    company_id: Optional[str] = Field(None, description="Company identifier")

    # Metadata fields
    report_period: Optional[str] = Field(None, description="Report period string")
    data_source: Optional[str] = Field(None, description="Source file or system")

    @field_validator("年", "月", mode="before")
    @classmethod
    def clean_date_fields(cls, v):
        """Clean year/month fields that may contain non-numeric characters."""
        if v is None:
            return v

        # Convert to string and strip whitespace
        v_str = str(v).strip()

        # Remove common non-numeric characters
        v_str = v_str.replace("年", "").replace("月", "").replace("/", "").replace("-", "")

        # Return cleaned string (will be validated later in transformation)
        return v_str if v_str else None

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
    计划代码: str = Field(..., min_length=1, max_length=255, description="Plan code identifier")
    company_id: str = Field(
        ..., min_length=1, max_length=50, description="Company identifier - matches DB column"
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

    # Financial metrics with proper precision (double precision in PostgreSQL)
    期初资产规模: Optional[Decimal] = Field(
        None, decimal_places=4, description="Initial asset scale"
    )
    期末资产规模: Optional[Decimal] = Field(None, decimal_places=4, description="Final asset scale")
    供款: Optional[Decimal] = Field(None, decimal_places=4, description="Contribution")
    # 使用数据库标准化列名进行输出序列化，输入兼容别名（括号形式）
    流失_含待遇支付: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Loss including benefit payment",
        alias="流失(含待遇支付)",
        validation_alias="流失(含待遇支付)",
        serialization_alias="流失_含待遇支付",  # 输出遵循 DDL 列名
    )
    流失: Optional[Decimal] = Field(None, decimal_places=4, description="Loss")
    待遇支付: Optional[Decimal] = Field(None, decimal_places=4, description="Benefit payment")
    投资收益: Optional[Decimal] = Field(None, decimal_places=4, description="Investment return")
    当期收益率: Optional[Decimal] = Field(
        None, decimal_places=6, ge=-1.0, le=10.0, description="Current period return rate"
    )

    # Organizational fields
    机构代码: Optional[str] = Field(None, max_length=255, description="Institution code")
    机构名称: Optional[str] = Field(None, max_length=255, description="Institution name")
    产品线代码: Optional[str] = Field(None, max_length=255, description="Product line code")

    # Pension account fields
    年金账户号: Optional[str] = Field(None, max_length=50, description="Pension account number")
    年金账户名: Optional[str] = Field(None, max_length=255, description="Pension account name")

    @field_validator("计划代码", "company_id", mode="after")
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
    def clean_decimal_fields(cls, v, info: Any):
        """Clean decimal fields using the unified cleansing framework."""
        from work_data_hub.cleansing.rules.numeric_rules import comprehensive_decimal_cleaning

        # Field-specific precision configuration
        precision_config = {
            "当期收益率": 6,  # Return rate needs higher precision
            "期初资产规模": 4,
            "期末资产规模": 4,
            "供款": 4,
            "流失_含待遇支付": 4,
            "流失": 4,
            "待遇支付": 4,
            "投资收益": 4,
        }

        return comprehensive_decimal_cleaning(
            value=v, field_name=info.field_name, precision_config=precision_config
        )

    @model_validator(mode="after")
    def validate_report_date(self) -> "AnnuityPerformanceOut":
        """Validate report date is reasonable and consistent."""
        report_date = self.月度
        if report_date:
            current_date = date.today()

            # Check date is not in the future
            if report_date > current_date:
                raise ValueError(f"Report date cannot be in future: {report_date}")

            # Check date is not too old (more than 10 years) - just warn, don't fail
            if (current_date - report_date).days > 3650:
                # Just log warning, don't store in model since field doesn't exist
                pass

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
    success_internal: int = 0      # Resolved via internal mappings
    success_external: int = 0      # Resolved via EQC lookup + cached
    pending_lookup: int = 0        # Queued for async processing
    temp_assigned: int = 0         # Assigned temporary ID
    failed: int = 0               # Resolution failed completely
    sync_budget_used: int = 0     # EQC lookups consumed from budget
    processing_time_ms: int = 0   # Total enrichment processing time

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
    unknown_names_csv: Optional[str] = Field(None, description="Path to exported unknown names CSV")
    data_source: str = Field("unknown", description="Source file or identifier")
    processing_time_ms: int = Field(0, description="Total processing time")
