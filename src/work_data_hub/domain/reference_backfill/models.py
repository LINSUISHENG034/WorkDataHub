"""
Data models for reference backfill operations.

This module defines Pydantic models representing reference table candidates
that can be derived from processed fact data.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class AnnuityPlanCandidate(BaseModel):
    """
    Candidate model for 年金计划 (Annuity Plan) reference table.

    Derived from processed annuity performance fact data to create
    missing reference entries before fact loading.
    """

    年金计划号: str = Field(
        ..., min_length=1, max_length=255, description="Plan code identifier"
    )
    计划全称: Optional[str] = Field(None, max_length=255, description="Full plan name")
    计划类型: Optional[str] = Field(None, max_length=255, description="Plan type")
    客户名称: Optional[str] = Field(None, max_length=255, description="Client name")
    company_id: Optional[str] = Field(
        None, max_length=50, description="Company identifier"
    )


class PortfolioCandidate(BaseModel):
    """
    Candidate model for 组合计划 (Portfolio Plan) reference table.

    Derived from processed annuity performance fact data to create
    missing reference entries before fact loading.
    """

    组合代码: str = Field(
        ..., min_length=1, max_length=255, description="Portfolio code identifier"
    )
    年金计划号: str = Field(
        ..., min_length=1, max_length=255, description="Plan code (FK)"
    )
    组合名称: Optional[str] = Field(None, max_length=255, description="Portfolio name")
    组合类型: Optional[str] = Field(None, max_length=255, description="Portfolio type")
    运作开始日: Optional[date] = Field(None, description="Operation start date")
