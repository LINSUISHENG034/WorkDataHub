"""
Pydantic v2 data models for trustee performance domain.

This module defines the input and output data contracts for trustee performance
data processing, providing robust validation and type safety using Pydantic v2.
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


class TrusteePerformanceIn(BaseModel):
    """
    Input model for raw trustee performance data from Excel files.

    This model accepts flexible input from Excel parsing with minimal validation,
    allowing for various column naming conventions and data formats commonly
    found in source files.
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

    # Core identification fields (Chinese column names as commonly used)
    年: Optional[str] = Field(None, description="Year field from Excel (年)")
    月: Optional[str] = Field(None, description="Month field from Excel (月)")
    计划代码: Optional[str] = Field(None, description="Plan code (计划代码)")
    公司代码: Optional[str] = Field(None, description="Company code (公司代码)")

    # Alternative field names for flexibility
    year: Optional[int] = Field(None, description="Year in integer format")
    month: Optional[int] = Field(None, description="Month in integer format")
    plan_code: Optional[str] = Field(None, description="Plan code in English")
    company_code: Optional[str] = Field(None, description="Company code in English")

    # Common performance metrics (flexible types to handle various formats)
    收益率: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Return rate (收益率)"
    )
    净值: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Net asset value (净值)"
    )
    规模: Optional[Union[Decimal, float, int, str]] = Field(
        None, description="Scale/size (规模)"
    )

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
        v_str = (
            v_str.replace("年", "").replace("月", "").replace("/", "").replace("-", "")
        )

        # Return cleaned string (will be validated later in transformation)
        return v_str if v_str else None


class TrusteePerformanceOut(BaseModel):
    """
    Output model for validated and normalized trustee performance data.

    This model enforces strict validation rules and provides clean, typed data
    suitable for loading into the data warehouse with consistent field names
    and formats.
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

    # Required core fields
    report_date: date = Field(..., description="Report date (YYYY-MM-DD)")
    plan_code: str = Field(
        ..., min_length=1, max_length=50, description="Plan identifier code"
    )
    company_code: str = Field(
        ..., min_length=1, max_length=20, description="Company identifier code"
    )

    # Performance metrics with proper typing and validation
    return_rate: Optional[Decimal] = Field(
        None,
        decimal_places=6,
        ge=-1.0,
        le=10.0,
        description="Return rate as decimal (e.g., 0.05 = 5%)",
    )

    net_asset_value: Optional[Decimal] = Field(
        None, decimal_places=4, gt=0, description="Net asset value per unit"
    )

    fund_scale: Optional[Decimal] = Field(
        None, decimal_places=2, ge=0, description="Total fund scale/size"
    )

    # Metadata and tracking fields
    data_source: str = Field(..., description="Source system or file")
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Timestamp when record was processed",
    )

    # Data quality indicators
    has_performance_data: bool = Field(
        default=False, description="Whether this record contains performance metrics"
    )

    validation_warnings: List[str] = Field(
        default_factory=list,
        description="List of validation warnings (non-fatal issues)",
    )

    @field_validator("plan_code", "company_code", mode="after")
    @classmethod
    def normalize_codes(cls, v: str) -> str:
        """Normalize identifier codes to uppercase and remove special chars."""
        if v is None:
            return v

        # Convert to uppercase and remove common separators
        normalized = v.upper().replace("-", "").replace("_", "").replace(" ", "")

        # Validate final format (alphanumeric only)
        if not normalized.replace(".", "").isalnum():
            raise ValueError(f"Code contains invalid characters: {v}")

        return normalized

    @field_validator("return_rate", "net_asset_value", "fund_scale", mode="before")
    @classmethod
    def _decimal_cleaner_proxy(cls, v, info: Any):
        """Proxy validator to allow runtime patching in tests."""
        return cls.clean_decimal_fields(v, info)

    @classmethod
    def clean_decimal_fields(cls, v, info: Any):
        """Clean decimal fields using the unified cleansing framework."""
        from work_data_hub.cleansing.rules.numeric_rules import (
            comprehensive_decimal_cleaning,
        )

        # Field-specific precision configuration
        precision_config = {
            "return_rate": 6,  # NUMERIC(8,6)
            "net_asset_value": 4,  # NUMERIC(18,4)
            "fund_scale": 2,  # NUMERIC(18,2)
        }

        return comprehensive_decimal_cleaning(
            value=v, field_name=info.field_name, precision_config=precision_config
        )

    @model_validator(mode="after")
    def validate_report_date(self) -> "TrusteePerformanceOut":
        """Validate report date is reasonable and consistent."""
        if self.report_date:
            current_date = date.today()

            # Check date is not in the future
            if self.report_date > current_date:
                raise ValueError(f"Report date cannot be in future: {self.report_date}")

            # Check date is not too old (more than 10 years)
            if (current_date - self.report_date).days > 3650:
                self.validation_warnings.append(
                    f"Report date is very old: {self.report_date}"
                )

        return self

    @model_validator(mode="after")
    def set_performance_data_flag(self) -> "TrusteePerformanceOut":
        """Set flag indicating whether performance metrics are present."""
        self.has_performance_data = any(
            [
                self.return_rate is not None,
                self.net_asset_value is not None,
                self.fund_scale is not None,
            ]
        )

        return self

    @model_validator(mode="after")
    def validate_consistency(self) -> "TrusteePerformanceOut":
        """Perform cross-field validation checks."""
        warnings = []

        # Check for suspicious return rates
        if self.return_rate is not None:
            if abs(self.return_rate) > 0.5:  # >50% return rate
                warnings.append(f"Unusually high return rate: {self.return_rate:.2%}")

        # Check for suspicious fund scales vs NAV
        if self.fund_scale is not None and self.net_asset_value is not None:
            if self.fund_scale < self.net_asset_value:
                warnings.append("Fund scale is less than NAV - may indicate data error")

        # Add any new warnings to existing list
        self.validation_warnings.extend(warnings)

        return self
