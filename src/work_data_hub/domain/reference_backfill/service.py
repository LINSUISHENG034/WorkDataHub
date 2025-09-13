"""
Service functions for deriving reference candidates from processed fact data.

This module provides pure functions for extracting unique reference table
candidates from processed annuity performance fact data. The functions
handle deduplication, field mapping, and data validation.
"""

import logging
from typing import Any, Dict, List

from .models import AnnuityPlanCandidate, PortfolioCandidate

logger = logging.getLogger(__name__)


def derive_plan_candidates(processed_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Derive unique annuity plan candidates from processed fact data.

    Extracts unique plan references by 计划代码 and merges additional
    fields from multiple rows, with later non-null values taking precedence.

    Args:
        processed_rows: List of processed annuity performance fact dictionaries

    Returns:
        List of dictionaries ready for insertion into 年金计划 table

    Raises:
        ValueError: If input data is invalid
    """
    if not processed_rows:
        logger.info("No processed rows provided for plan candidate derivation")
        return []

    if not isinstance(processed_rows, list):
        raise ValueError("Processed rows must be a list")

    plan_map = {}  # Key: 年金计划号, Value: candidate dict

    for row_index, row in enumerate(processed_rows):
        try:
            # Extract plan code (required field)
            plan_code = row.get("计划代码")
            if not plan_code:
                logger.debug(f"Row {row_index}: skipping due to missing 计划代码")
                continue

            # Normalize plan code (same as output model validation)
            plan_code = str(plan_code).strip()
            if not plan_code:
                logger.debug(f"Row {row_index}: skipping due to empty 计划代码 after normalization")
                continue

            # Build or merge candidate
            if plan_code not in plan_map:
                plan_map[plan_code] = {
                    "年金计划号": plan_code,
                    "计划全称": row.get("计划名称"),
                    "计划类型": row.get("计划类型"),
                    "客户名称": row.get("客户名称"),
                    "company_id": row.get("company_id"),
                }
            else:
                # Merge additional fields (last non-null wins)
                existing = plan_map[plan_code]
                merge_fields = ["计划全称", "计划类型", "客户名称", "company_id"]
                for field in merge_fields:
                    if row.get(field) and not existing.get(field):
                        existing[field] = row[field]

        except Exception as e:
            logger.warning(f"Error processing row {row_index} for plan candidates: {e}")
            continue

    candidates = list(plan_map.values())
    logger.info(
        f"Derived {len(candidates)} unique plan candidates "
        f"from {len(processed_rows)} processed rows"
    )

    return candidates


def derive_portfolio_candidates(processed_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Derive unique portfolio candidates from processed fact data.

    Extracts unique portfolio references by 组合代码 and 年金计划号 combination.
    Each portfolio must be associated with a plan.

    Args:
        processed_rows: List of processed annuity performance fact dictionaries

    Returns:
        List of dictionaries ready for insertion into 组合计划 table

    Raises:
        ValueError: If input data is invalid
    """
    if not processed_rows:
        logger.info("No processed rows provided for portfolio candidate derivation")
        return []

    if not isinstance(processed_rows, list):
        raise ValueError("Processed rows must be a list")

    portfolio_map = {}  # Key: 组合代码, Value: candidate dict

    for row_index, row in enumerate(processed_rows):
        try:
            # Extract required fields
            portfolio_code = row.get("组合代码")
            plan_code = row.get("计划代码")

            if not portfolio_code or not plan_code:
                logger.debug(
                    f"Row {row_index}: skipping due to missing 组合代码 or 计划代码"
                )
                continue

            # Normalize codes
            portfolio_code = str(portfolio_code).strip()
            plan_code = str(plan_code).strip()

            if not portfolio_code or not plan_code:
                logger.debug(
                    f"Row {row_index}: skipping due to empty codes after normalization"
                )
                continue

            # Build candidate (portfolio code should be unique per plan)
            if portfolio_code not in portfolio_map:
                portfolio_map[portfolio_code] = {
                    "组合代码": portfolio_code,
                    "年金计划号": plan_code,
                    "组合名称": row.get("组合名称"),
                    "组合类型": row.get("组合类型"),
                    "运作开始日": None,  # Not available in fact data, keep NULL
                }
            else:
                # If portfolio code already exists, verify plan consistency
                existing = portfolio_map[portfolio_code]
                if existing["年金计划号"] != plan_code:
                    logger.warning(
                        f"Row {row_index}: Portfolio {portfolio_code} mapped to different plans: "
                        f"{existing['年金计划号']} vs {plan_code}. Keeping first."
                    )
                else:
                    # Same plan, merge additional fields (last non-null wins)
                    merge_fields = ["组合名称", "组合类型"]
                    for field in merge_fields:
                        if row.get(field) and not existing.get(field):
                            existing[field] = row[field]

        except Exception as e:
            logger.warning(f"Error processing row {row_index} for portfolio candidates: {e}")
            continue

    candidates = list(portfolio_map.values())
    logger.info(
        f"Derived {len(candidates)} unique portfolio candidates "
        f"from {len(processed_rows)} processed rows"
    )

    return candidates


def validate_plan_candidates(candidates: List[Dict[str, Any]]) -> List[AnnuityPlanCandidate]:
    """
    Validate plan candidates using Pydantic models.

    Args:
        candidates: List of plan candidate dictionaries

    Returns:
        List of validated AnnuityPlanCandidate models

    Raises:
        ValidationError: If validation fails for any candidate
    """
    validated = []
    for i, candidate in enumerate(candidates):
        try:
            validated.append(AnnuityPlanCandidate(**candidate))
        except Exception as e:
            logger.error(f"Plan candidate {i} validation failed: {e}")
            raise

    return validated


def validate_portfolio_candidates(candidates: List[Dict[str, Any]]) -> List[PortfolioCandidate]:
    """
    Validate portfolio candidates using Pydantic models.

    Args:
        candidates: List of portfolio candidate dictionaries

    Returns:
        List of validated PortfolioCandidate models

    Raises:
        ValidationError: If validation fails for any candidate
    """
    validated = []
    for i, candidate in enumerate(candidates):
        try:
            validated.append(PortfolioCandidate(**candidate))
        except Exception as e:
            logger.error(f"Portfolio candidate {i} validation failed: {e}")
            raise

    return validated
