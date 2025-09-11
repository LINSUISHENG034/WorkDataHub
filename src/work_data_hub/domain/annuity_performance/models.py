"""
Pydantic v2 data models for annuity performance domain.

This module defines the input and output data contracts for annuity performance
data processing, providing robust validation and type safety using Pydantic v2.
Handles Chinese column names from "规模明细" Excel sheets.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional, Union

if TYPE_CHECKING:
    pass

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
    供款: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Contribution (供款)"
    )
    流失_含待遇支付: Optional[Union[Decimal, float, int, str]] = Field(
        None,
        description="Loss including benefit payment (流失(含待遇支付))",
        alias="流失(含待遇支付)"
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
    机构名称: Optional[str] = Field(None, description="Institution name (机构名称)")
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
    报告日期: Optional[date] = Field(
        None, description="Report date derived from 年/月", alias="月度"
    )
    计划代码: str = Field(..., min_length=1, max_length=255, description="Plan code identifier")
    公司代码: str = Field(..., min_length=1, max_length=50, description="Company code identifier")

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
    期末资产规模: Optional[Decimal] = Field(
        None, decimal_places=4, description="Final asset scale"
    )
    供款: Optional[Decimal] = Field(
        None, decimal_places=4, description="Contribution"
    )
    流失_含待遇支付: Optional[Decimal] = Field(
        None,
        decimal_places=4,
        description="Loss including benefit payment",
        alias="流失(含待遇支付)"
    )
    流失: Optional[Decimal] = Field(
        None, decimal_places=4, description="Loss"
    )
    待遇支付: Optional[Decimal] = Field(
        None, decimal_places=4, description="Benefit payment"
    )
    投资收益: Optional[Decimal] = Field(
        None, decimal_places=4, description="Investment return"
    )
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
    company_id: Optional[str] = Field(None, max_length=50, description="Company identifier")

    # Metadata and tracking fields
    data_source: str = Field(..., description="Source system or file")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(), description="Timestamp when record was processed"
    )

    # Data quality indicators
    has_financial_data: bool = Field(
        default=False, description="Whether this record contains financial metrics"
    )

    validation_warnings: List[str] = Field(
        default_factory=list, description="List of validation warnings (non-fatal issues)"
    )

    @field_validator("计划代码", "公司代码", mode="after")
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
        "期初资产规模", "期末资产规模", "供款", "流失_含待遇支付",
        "流失", "待遇支付", "投资收益", "当期收益率", mode="before"
    )
    @classmethod
    def clean_decimal_fields(cls, v, info: Any):
        """Clean and convert financial fields with precision quantization."""
        if v is None or v == "":
            return None

        # Handle various input types
        if isinstance(v, (int, Decimal)):
            # For integers and Decimals, check for percentage interpretation
            if info.field_name == "当期收益率" and isinstance(v, (int, float)):
                if 1 < v <= 100:  # Interpret as percentage
                    v = v / 100.0
            # Process for quantization
            pass
        elif isinstance(v, float):
            # Check for percentage interpretation before string conversion
            if info.field_name == "当期收益率" and 1 < v <= 100:
                v = v / 100.0
            # Convert float to string first to avoid precision issues
            v = str(v)
        elif isinstance(v, str):
            # Clean string values
            v_clean = v.strip().replace(",", "").replace(" ", "")
            v_clean = v_clean.replace("¥", "").replace("$", "").replace("￥", "")

            # Handle percentage format (convert to decimal)
            if "%" in v_clean:
                v_clean = v_clean.replace("%", "")
                try:
                    v = float(v_clean) / 100.0
                    v = str(v)  # Convert to string for Decimal conversion
                except ValueError:
                    raise ValueError(f"Invalid percentage format: {v}")
            else:
                v = v_clean

            # Handle empty or placeholder values
            if v in ("", "-", "N/A", "无", "暂无"):
                return None

            # Try to convert to float for validation, then back to string
            try:
                float_val = float(v)
                v = str(float_val)
            except ValueError:
                raise ValueError(f"Cannot convert to decimal: {v}")

        # Convert to Decimal using string to avoid float precision issues
        try:
            if isinstance(v, Decimal):
                d = v
            else:
                d = Decimal(str(v))
        except (ValueError, TypeError):
            raise ValueError(f"Cannot convert to decimal: {v}")

        # Field-specific quantization based on schema precision requirements
        field_precision_map = {
            "当期收益率": 6,  # Return rate needs higher precision
            # Most financial fields use 4 decimal places for currency precision
            "期初资产规模": 4,
            "期末资产规模": 4,
            "供款": 4,
            "流失_含待遇支付": 4,
            "流失": 4,
            "待遇支付": 4,
            "投资收益": 4,
        }

        if info.field_name and info.field_name in field_precision_map:
            from decimal import ROUND_HALF_UP
            places = field_precision_map[info.field_name]
            quantizer = Decimal(1).scaleb(-places)
            d = d.quantize(quantizer, rounding=ROUND_HALF_UP)

        return d

    @model_validator(mode="after")
    def validate_report_date(self) -> "AnnuityPerformanceOut":
        """Validate report date is reasonable and consistent."""
        report_date = self.月度 or self.报告日期
        if report_date:
            current_date = date.today()

            # Check date is not in the future
            if report_date > current_date:
                raise ValueError(f"Report date cannot be in future: {report_date}")

            # Check date is not too old (more than 10 years)
            if (current_date - report_date).days > 3650:
                self.validation_warnings.append(f"Report date is very old: {report_date}")

            # Ensure both date fields are consistent
            if not self.月度:
                self.月度 = report_date

        return self

    @model_validator(mode="after")
    def set_financial_data_flag(self) -> "AnnuityPerformanceOut":
        """Set flag indicating whether financial metrics are present."""
        self.has_financial_data = any([
            self.期初资产规模 is not None,
            self.期末资产规模 is not None,
            self.供款 is not None,
            self.投资收益 is not None,
            self.当期收益率 is not None,
        ])

        return self

    @model_validator(mode="after")
    def validate_consistency(self) -> "AnnuityPerformanceOut":
        """Perform cross-field validation checks."""
        warnings = []

        # Check for suspicious return rates
        if self.当期收益率 is not None:
            if abs(self.当期收益率) > 0.5:  # >50% return rate
                warnings.append(f"Unusually high return rate: {self.当期收益率:.2%}")

        # Check for negative asset scales
        if self.期初资产规模 is not None and self.期初资产规模 < 0:
            warnings.append("Initial asset scale is negative")
        if self.期末资产规模 is not None and self.期末资产规模 < 0:
            warnings.append("Final asset scale is negative")

        # Check for logical relationship between initial, final, and flows
        if (self.期初资产规模 is not None and self.期末资产规模 is not None and
            self.供款 is not None and self.投资收益 is not None):

            expected_final = self.期初资产规模 + self.供款 + self.投资收益
            流失总额 = (self.流失 or Decimal(0)) + (self.待遇支付 or Decimal(0))
            expected_final -= 流失总额

            # Allow 1000 unit tolerance
            if abs(expected_final - self.期末资产规模) > Decimal("1000"):
                warnings.append("Asset flow calculation doesn't balance - may indicate data error")

        # Add any new warnings to existing list
        self.validation_warnings.extend(warnings)

        return self
