"""
Column name normalization utility (Story 3.4).

Normalization steps (applied in order):
1) Convert non-string types to string (None -> "")
2) Strip leading/trailing whitespace
3) Replace full-width spaces (U+3000) with half-width
4) Replace newlines/tabs with a single space
5) Remove ALL whitespace characters
6) Generate Unnamed_N placeholders for empty names
7) Append _N suffixes for duplicates
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True
_custom_mappings: Dict[str, str] = {}


def normalize_column_names(columns: List[Any]) -> List[str]:
    """
    Normalize column names handling whitespace, encoding, empty names, and duplicates.

    Args:
        columns: List of column names (any type accepted)

    Returns:
        List of normalized column names (strings)
    """
    normalized: List[str] = []
    seen: Dict[str, int] = {}
    unnamed_counter = 1
    empty_placeholders = 0
    duplicates_resolved = 0

    for idx, col in enumerate(columns):
        original_value = col
        name = "" if col is None else str(col)

        # 1) Strip leading/trailing whitespace
        name = name.strip()

        # 2) Replace full-width spaces with half-width
        name = name.replace("\u3000", " ")

        # 3) Replace newlines/tabs with single space
        name = name.replace("\n", " ").replace("\t", " ")

        # 4) Remove ALL whitespace characters
        name = re.sub(r"\s+", "", name)

        # Apply custom overrides after whitespace normalization
        if name in _custom_mappings:
            name = _custom_mappings[name]

        # 5) Handle empty names
        if not name:
            name = f"Unnamed_{unnamed_counter}"
            unnamed_counter += 1
            empty_placeholders += 1
            logger.warning(
                "column_normalizer.empty_name_placeholder_generated column_index=%s "
                "original_value=%s placeholder=%s",
                idx,
                repr(original_value),
                name,
            )
            logging.getLogger().warning(
                "column_normalizer.empty_name_placeholder_generated column_index=%s "
                "original_value=%s placeholder=%s",
                idx,
                repr(original_value),
                name,
            )

        base_name = name

        # 6) Handle duplicates with suffixes
        if base_name in seen:
            seen[base_name] += 1
            name = f"{base_name}_{seen[base_name]}"
            duplicates_resolved += 1
            logger.warning(
                "column_normalizer.duplicate_name_resolved original_name=%s "
                "suffixed_name=%s occurrence_count=%s",
                base_name,
                name,
                seen[base_name] + 1,
            )
            logging.getLogger().warning(
                "column_normalizer.duplicate_name_resolved original_name=%s "
                "suffixed_name=%s occurrence_count=%s",
                base_name,
                name,
                seen[base_name] + 1,
            )
        else:
            seen[base_name] = 0

        normalized.append(name)

    logger.info(
        "column_normalizer.summary columns_normalized=%s "
        "empty_placeholders_generated=%s duplicates_resolved=%s",
        len(columns),
        empty_placeholders,
        duplicates_resolved,
    )
    logging.getLogger().info(
        "column_normalizer.summary columns_normalized=%s "
        "empty_placeholders_generated=%s duplicates_resolved=%s",
        len(columns),
        empty_placeholders,
        duplicates_resolved,
    )

    return normalized


def normalize_column_name(column_name: Any) -> str:
    """Normalize a single column name while keeping compatibility with existing
    callers."""
    return normalize_column_names([column_name])[0]


def normalize_columns(columns: List[Any]) -> Dict[str, str]:
    """
    Backward-compatible helper returning a mapping from original -> normalized.
    """
    normalized_list = normalize_column_names(columns)
    return dict(zip(columns, normalized_list))


def apply_column_normalization(
    data_rows: List[Dict[str, Any]], column_mapping: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """Apply normalization to a list of row dictionaries using provided or derived
    mapping."""
    if not data_rows:
        return data_rows

    if column_mapping is None:
        column_mapping = normalize_columns(list(data_rows[0].keys()))

    normalized_rows = []
    for row in data_rows:
        normalized_row = {}
        for original_col, value in row.items():
            normalized_col = column_mapping.get(original_col, original_col)
            normalized_row[normalized_col] = value
        normalized_rows.append(normalized_row)

    changed_mappings = {k: v for k, v in column_mapping.items() if k != v}
    if changed_mappings:
        logger.info(
            "column_normalizer.applied",
            extra={
                "columns_changed": len(changed_mappings),
                "mapping": changed_mappings,
            },
        )

    return normalized_rows


def add_domain_mapping(original: str, normalized: str) -> None:
    """
    Add a custom mapping override for specific column names.
    """
    _custom_mappings[original] = normalized
    logger.debug(
        "column_normalizer.add_domain_mapping",
        extra={"original": original, "normalized": normalized},
    )
