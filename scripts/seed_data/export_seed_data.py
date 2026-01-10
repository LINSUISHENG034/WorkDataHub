"""Export seed data from PostgreSQL to CSV files for version 002."""

import csv
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "Post.169828",
    "database": "postgres",
}

# Output directory
OUTPUT_DIR = Path("config/seeds/002")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def export_table_to_csv(query: str, output_file: Path) -> int:
    """Export query results to CSV file.

    Args:
        query: SQL query to execute
        output_file: Path to output CSV file

    Returns:
        Number of rows exported
    """
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        if not rows:
            print(f"Warning: No data returned for {output_file.name}")
            return 0

        # Write to CSV with BOM for Excel compatibility (like existing files)
        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print(f"Exported {len(rows)} rows to {output_file}")
        return len(rows)

    finally:
        conn.close()


def main():
    """Export seed data for version 002."""
    print("Exporting seed data from PostgreSQL...")

    # Export enrichment_index
    enrichment_query = """
        SELECT id, lookup_key, lookup_type, company_id, confidence, source,
               source_domain, source_table, hit_count, last_hit_at,
               created_at, updated_at
        FROM enterprise.enrichment_index
        ORDER BY id
    """
    enrichment_file = OUTPUT_DIR / "enrichment_index.csv"
    enrichment_count = export_table_to_csv(enrichment_query, enrichment_file)

    # Export base_info as 年金客户.csv (matching existing v001 naming)
    base_info_query = """
        SELECT id, company_id, search_key_word, name, name_display, symbol,
               rank_score, country, company_en_name, smdb_code, is_hk,
               coname, is_list, company_nature, _score, type, organization_code,
               le_rep, reg_cap, is_pa_relatedparty, province, est_date,
               company_short_name, is_debt, unite_code, registered_status,
               cocode, default_score, company_former_name, is_rank_list,
               trade_register_code, is_normal, company_full_name, data_source,
               raw_data, raw_business_info, raw_biz_label, api_fetched_at,
               updated_at
        FROM enterprise.base_info
        ORDER BY id
    """
    base_info_file = OUTPUT_DIR / "年金客户.csv"
    base_info_count = export_table_to_csv(base_info_query, base_info_file)

    print("\nExport summary:")
    print(f"  enrichment_index.csv: {enrichment_count:,} rows")
    print(f"  年金客户.csv: {base_info_count:,} rows")
    print(f"\nFiles saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
