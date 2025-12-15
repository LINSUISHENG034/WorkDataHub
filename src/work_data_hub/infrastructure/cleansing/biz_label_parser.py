"""
BizLabel Parser Service for transforming raw JSONB labels to normalized records.

Story 6.2-P9: Raw Data Cleansing & Transformation
Task 2.2: Implement BizLabelParser service
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from work_data_hub.domain.company_enrichment.models import BizLabelRecord

logger = logging.getLogger(__name__)


class BizLabelParser:
    """
    Parse raw_biz_label JSONB and flatten to BizLabelRecord records.

    Handles the nested labels[].labels[] structure from EQC findLabels API
    and applies null companyId fallback logic per Legacy crawler pattern.
    """

    def parse(
        self, raw_biz_label: Optional[Dict[str, Any]], fallback_company_id: str
    ) -> List[BizLabelRecord]:
        """
        Parse raw_biz_label JSONB and flatten to individual BizLabelRecord records.

        Handles null companyId with sibling fallback per Legacy pattern.

        Args:
            raw_biz_label: Raw JSONB from base_info.raw_biz_label
            fallback_company_id: Company ID from base_info.company_id (final fallback)

        Returns:
            List of BizLabelRecord, one per label entry

        Note:
            The raw_biz_label structure from EQC findLabels API:
            {
                "labels": [
                    {
                        "type": "行业分类",
                        "labels": [
                            {"companyId": "123", "lv1Name": "...", "lv2Name": "...", ...},
                            {"companyId": None, "lv1Name": "...", "lv2Name": "...", ...},
                        ]
                    },
                    ...
                ]
            }
        """
        if raw_biz_label is None:
            return []

        results: List[BizLabelRecord] = []
        categories = raw_biz_label.get("labels", [])

        if not isinstance(categories, list):
            logger.warning(
                "biz_label_parser.invalid_labels_structure: expected list, got %s",
                type(categories).__name__,
            )
            return []

        for category in categories:
            if not isinstance(category, dict):
                continue

            label_type = category.get("type", "")
            labels_list = category.get("labels", [])

            if not isinstance(labels_list, list):
                continue

            # Collect company_ids from siblings for fallback
            sibling_company_id: Optional[str] = None
            for lab in labels_list:
                if isinstance(lab, dict) and lab.get("companyId"):
                    sibling_company_id = str(lab["companyId"])
                    break

            for lab in labels_list:
                if not isinstance(lab, dict):
                    continue

                company_id = lab.get("companyId")

                # Fallback logic: if companyId is None, try sibling value
                if company_id is None:
                    company_id = sibling_company_id

                # Final fallback: use the fallback_company_id from base_info
                if company_id is None:
                    company_id = fallback_company_id

                # Ensure company_id is a string
                company_id = str(company_id) if company_id else fallback_company_id

                try:
                    record = BizLabelRecord(
                        company_id=company_id,
                        type=self._clean_string(label_type),
                        lv1_name=self._clean_string(lab.get("lv1Name")),
                        lv2_name=self._clean_string(lab.get("lv2Name")),
                        lv3_name=self._clean_string(lab.get("lv3Name")),
                        lv4_name=self._clean_string(lab.get("lv4Name")),
                    )
                    results.append(record)
                except Exception as e:
                    logger.warning(
                        "biz_label_parser.record_creation_failed",
                        company_id=company_id,
                        label_type=label_type,
                        error=str(e),
                    )
                    continue

        return results

    def _clean_string(self, value: Any) -> Optional[str]:
        """Clean and strip string value."""
        if value is None:
            return None
        result = str(value).strip()
        return result if result else None
