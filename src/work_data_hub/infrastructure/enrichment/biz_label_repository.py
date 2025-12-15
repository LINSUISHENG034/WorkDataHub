"""
BizLabel Repository for batch operations on enterprise.biz_label.

Story 6.2-P9: Raw Data Cleansing & Transformation
Task 3.2: Implement BizLabelRepository
"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy import text
from sqlalchemy.engine import Connection

from work_data_hub.domain.company_enrichment.models import BizLabelRecord

logger = logging.getLogger(__name__)


class BizLabelRepository:
    """
    Repository for batch operations on enterprise.biz_label table.

    Uses DELETE + INSERT pattern for replacing all labels for a company.
    """

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def upsert_batch(self, company_id: str, labels: List[BizLabelRecord]) -> int:
        """
        Replace all labels for a company with new batch.

        Uses DELETE existing + INSERT new pattern.

        Args:
            company_id: Company ID to update labels for
            labels: List of BizLabelRecord to persist

        Returns:
            Number of labels inserted
        """
        # Delete existing labels for this company
        delete_sql = text("""
            DELETE FROM enterprise.biz_label
            WHERE company_id = :company_id
        """)

        try:
            self.connection.execute(delete_sql, {"company_id": company_id})
        except Exception as e:
            logger.error(
                "biz_label_repository.delete_failed",
                company_id=company_id,
                error=str(e),
            )
            raise

        if not labels:
            return 0

        # Batch insert using VALUES clause for better performance
        # Build parameterized query for all labels at once
        value_placeholders = []
        params: dict = {}

        for i, label in enumerate(labels):
            value_placeholders.append(
                f"(:company_id_{i}, :type_{i}, :lv1_name_{i}, :lv2_name_{i}, "
                f":lv3_name_{i}, :lv4_name_{i}, NOW(), NOW())"
            )
            params[f"company_id_{i}"] = label.company_id
            params[f"type_{i}"] = label.type
            params[f"lv1_name_{i}"] = label.lv1_name
            params[f"lv2_name_{i}"] = label.lv2_name
            params[f"lv3_name_{i}"] = label.lv3_name
            params[f"lv4_name_{i}"] = label.lv4_name

        insert_sql = text(f"""
            INSERT INTO enterprise.biz_label (
                company_id,
                type,
                lv1_name,
                lv2_name,
                lv3_name,
                lv4_name,
                created_at,
                updated_at
            ) VALUES {', '.join(value_placeholders)}
        """)

        try:
            self.connection.execute(insert_sql, params)
            inserted = len(labels)
        except Exception as e:
            logger.error(
                "biz_label_repository.batch_insert_failed",
                company_id=company_id,
                label_count=len(labels),
                error=str(e),
            )
            raise

        logger.debug(
            "biz_label_repository.batch_complete",
            company_id=company_id,
            inserted=inserted,
            total=len(labels),
        )

        return inserted
