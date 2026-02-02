"""Annual Award (当年中标) domain.

This domain unifies TrusteeAwardCleaner (企年受托中标) and
InvesteeAwardCleaner (企年投资中标) from the legacy system into a single domain.

Implements requirements:
1. Drop columns: 区域, 年金中心, 上报人
2. Conditional update: Keep original 年金计划号 and company_id if non-empty
3. Customer name transformation: 客户全称 → 上报客户名称, cleaned to 客户名称
4. Plan code update: Based on customer_plan_contract table (Phase 2)
"""

from .models import AnnualAwardIn, AnnualAwardOut, AnnualAwardProcessingResult
from .schemas import (
    BronzeAnnualAwardSchema,
    GoldAnnualAwardSchema,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from .service import process_annual_award

__all__ = [
    # Models
    "AnnualAwardIn",
    "AnnualAwardOut",
    "AnnualAwardProcessingResult",
    # Schemas
    "BronzeAnnualAwardSchema",
    "GoldAnnualAwardSchema",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    # Service
    "process_annual_award",
]
