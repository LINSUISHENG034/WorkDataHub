"""
EQC Confidence Backfill Script (Story 7.1-8, AC-7).

This script updates confidence scores in enrichment_index based on EQC match type
stored in base_info.raw_data.

Usage:
    # Dry-run mode (preview changes without executing)
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/enrichment/backfill_eqc_confidence.py --dry-run

    # Execute backfill
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/enrichment/backfill_eqc_confidence.py --execute

    # Custom config file
    PYTHONPATH=src uv run --env-file .wdh_env python scripts/enrichment/backfill_eqc_confidence.py \
        --config config/eqc_confidence.yml --execute
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from work_data_hub.config.settings import get_settings
from work_data_hub.utils.logging import get_logger

logger = get_logger(__name__)


def load_confidence_config(config_path: Optional[str] = None) -> Dict[str, float]:
    """
    Load EQC confidence mapping from YAML config.

    Args:
        config_path: Path to eqc_confidence.yml. If None, uses default path.

    Returns:
        Dictionary mapping match type to confidence score.
    """
    if config_path is None:
        config_path = "config/eqc_confidence.yml"

    config_file = Path(config_path)

    if not config_file.exists():
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return {
            "全称精确匹配": 1.00,
            "模糊匹配": 0.80,
            "拼音": 0.60,
            "default": 0.70,
        }

    with open(config_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("eqc_match_confidence", {})


def get_match_type_from_raw_data(raw_data: Dict) -> str:
    """
    Extract EQC match type from raw_data JSON.

    Args:
        raw_data: Raw API response from EQC search endpoint.

    Returns:
        Match type string (全称精确匹配, 模糊匹配, 拼音) or "default".
    """
    if not raw_data or not isinstance(raw_data, dict):
        return "default"

    results = raw_data.get("list", [])
    if not results or not isinstance(results, list):
        return "default"

    first_result = results[0]
    if not isinstance(first_result, dict):
        return "default"

    return first_result.get("type", "default")


def analyze_records(
    cursor,
    confidence_mapping: Dict[str, float],
) -> List[Dict]:
    """
    Analyze base_info records and determine confidence updates.

    Args:
        cursor: Database cursor.
        confidence_mapping: Match type to confidence mapping.

    Returns:
        List of records requiring updates, with current and new confidence.
    """
    query = """
        SELECT
            bi.company_id,
            bi.search_key_word,
            bi.raw_data,
            ei.confidence as current_confidence,
            ei.id as enrichment_index_id
        FROM enterprise.base_info bi
        LEFT JOIN enterprise.enrichment_index ei
            ON ei.company_id = bi.company_id
            AND ei.source = 'eqc_sync_lookup'
        WHERE bi.raw_data IS NOT NULL
          AND jsonb_array_length(bi.raw_data->'list') > 0
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    updates = []

    for row in rows:
        company_id = row[0]
        search_key_word = row[1]
        raw_data = row[2]
        current_confidence = row[3]
        enrichment_index_id = row[4]

        # Extract match type from raw_data
        match_type = get_match_type_from_raw_data(raw_data)

        # Get new confidence from mapping
        new_confidence = confidence_mapping.get(
            match_type, confidence_mapping.get("default", 0.70)
        )

        # Determine if update is needed
        needs_update = True
        if (
            current_confidence is not None
            and abs(float(current_confidence) - new_confidence) < 0.01
        ):
            needs_update = False

        updates.append(
            {
                "company_id": company_id,
                "search_key_word": search_key_word,
                "match_type": match_type,
                "current_confidence": current_confidence,
                "new_confidence": new_confidence,
                "enrichment_index_id": enrichment_index_id,
                "needs_update": needs_update,
            }
        )

    return updates


def execute_updates(cursor, updates: List[Dict]) -> int:
    """
    Execute confidence updates on enrichment_index.

    Args:
        cursor: Database cursor.
        updates: List of update records from analyze_records().

    Returns:
        Number of records updated.
    """
    updated_count = 0

    for record in updates:
        if not record["needs_update"]:
            continue

        if record["enrichment_index_id"] is None:
            # No enrichment_index record exists, skip
            logger.debug(
                "backfill.no_enrichment_record",
                company_id=record["company_id"],
                msg="No enrichment_index record found, skipping",
            )
            continue

        update_query = """
            UPDATE enterprise.enrichment_index
            SET confidence = %s,
                updated_at = NOW()
            WHERE id = %s
        """

        cursor.execute(
            update_query,
            (record["new_confidence"], record["enrichment_index_id"]),
        )

        updated_count += 1
        logger.info(
            "backfill.updated",
            enrichment_index_id=record["enrichment_index_id"],
            company_id=record["company_id"],
            old_confidence=record["current_confidence"],
            new_confidence=record["new_confidence"],
            match_type=record["match_type"],
        )

    return updated_count


def print_summary(updates: List[Dict]) -> None:
    """Print analysis summary."""
    total = len(updates)
    needs_update = sum(1 for u in updates if u["needs_update"])
    no_record = sum(1 for u in updates if u["enrichment_index_id"] is None)

    # Count by match type
    match_type_counts: Dict[str, int] = {}
    for u in updates:
        mt = u["match_type"]
        match_type_counts[mt] = match_type_counts.get(mt, 0) + 1

    print("\n" + "=" * 60)
    print("EQC Confidence Backfill Summary")
    print("=" * 60)
    print(f"Total records analyzed: {total}")
    print(f"Records requiring update: {needs_update}")
    print(f"No enrichment_index record: {no_record}")
    print("\nMatch Type Distribution:")
    for mt, count in sorted(match_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {mt}: {count}")

    if needs_update > 0:
        print("\nRecords to Update:")
        for u in updates:
            if u["needs_update"]:
                print(
                    f"  - {u['company_id']} ({u['search_key_word']}): "
                    f"{u['current_confidence']} → {u['new_confidence']} "
                    f"[{u['match_type']}]"
                )

    print("=" * 60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill EQC confidence scores based on match type"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing updates",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the backfill updates",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to eqc_confidence.yml (default: config/eqc_confidence.yml)",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Error: Must specify --dry-run or --execute")
        parser.print_help()
        sys.exit(1)

    logger.info(
        "backfill.started",
        dry_run=args.dry_run,
        config_path=args.config,
    )

    # Load confidence mapping
    confidence_mapping = load_confidence_config(args.config)
    logger.info(
        "backfill.config_loaded",
        mapping=confidence_mapping,
    )

    # Connect to database
    settings = get_settings()
    import psycopg2

    dsn = settings.get_database_connection_string()
    conn = psycopg2.connect(dsn)
    cursor = conn.cursor()

    try:
        # Analyze records
        updates = analyze_records(cursor, confidence_mapping)

        # Print summary
        print_summary(updates)

        # Execute updates if not dry-run
        if args.execute:
            updated_count = execute_updates(cursor, updates)

            conn.commit()

            logger.info(
                "backfill.completed",
                updated_count=updated_count,
                total_analyzed=len(updates),
            )

            print(f"\n✅ Backfill completed: {updated_count} records updated")
        else:
            print("\n⏭️  Dry-run mode - no changes made")

    except Exception as e:
        conn.rollback()
        logger.error(
            "backfill.error",
            error=str(e),
            exc_info=True,
        )
        print(f"\n❌ Error: {e}")
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
