"""Annual Loss (流失客户明细) domain.

This domain unifies TrusteeLossCleaner (企年受托流失) and
InvesteeLossCleaner (企年投资流失) from the legacy system into a single domain.

Implements requirements:
1. Drop columns: 区域, 年金中心, 上报人, 考核标签
2. Ignore investment-specific redundant fields:
   战区前五大, 中心前十大, 机构前十大, 五亿以上
3. Rename: 受托人 → 原受托人
4. Conditional update: Keep original 年金计划号 and company_id if non-empty
5. Customer name transformation: 客户全称 → 上报客户名称
6. Plan code update: Based on 客户年金计划 table
"""

from .models import AnnualLossIn, AnnualLossOut, AnnualLossProcessingResult
from .schemas import (
    BronzeAnnualLossSchema,
    GoldAnnualLossSchema,
    validate_bronze_dataframe,
    validate_gold_dataframe,
)
from .service import process_annual_loss

__all__ = [
    # Models
    "AnnualLossIn",
    "AnnualLossOut",
    "AnnualLossProcessingResult",
    # Schemas
    "BronzeAnnualLossSchema",
    "GoldAnnualLossSchema",
    "validate_bronze_dataframe",
    "validate_gold_dataframe",
    # Service
    "process_annual_loss",
]
