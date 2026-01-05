"""
Enrichment Index Seed Data Generator

This script generates enrichment_index seed data from multiple sources:
1. legacy.business."规模明细" - 年金账户名 and 客户名称 → customer_name
2. postgres.enterprise.base_info - company_full_name, company_former_name → customer_name, former_name
3. config/seeds/enrichment_index.csv - plan_code records (preserved)

Usage:
    uv run python scripts/migrations/seed/generate_enrichment_seed.py
"""

import csv
from datetime import datetime
from pathlib import Path

import psycopg2

from work_data_hub.infrastructure.cleansing.normalizers import normalize_customer_name

# Database connections
LEGACY_DB_URL = "postgresql://postgres:Post.169828@localhost:5432/legacy"
ENTERPRISE_DB_URL = "postgresql://postgres:Post.169828@localhost:5432/postgres"

# Output paths
SEED_OUTPUT_PATH = Path("config/seeds/enrichment_index_new.csv")
BACKUP_PATH = Path("config/seeds/enrichment_index_backup_20260105.csv")


def analyze_source_data():
    """Analyze source data distribution from all sources."""
    print("\n=== Source Data Analysis ===")

    # 1. Legacy database
    conn = psycopg2.connect(LEGACY_DB_URL)
    cur = conn.cursor()

    cur.execute('SELECT COUNT(*) FROM business."规模明细"')
    total = cur.fetchone()[0]
    print(f"\n[legacy.business.规模明细]")
    print(f"  Total records: {total}")

    cur.execute("""
        SELECT COUNT(*) 
        FROM business."规模明细" 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
    """)
    valid_company_id = cur.fetchone()[0]
    print(f"  Valid company_id (non-temp): {valid_company_id}")

    cur.execute("""
        SELECT COUNT(*) 
        FROM business."规模明细" 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
          AND "年金账户名" IS NOT NULL 
          AND trim("年金账户名") <> ''
    """)
    has_account_name = cur.fetchone()[0]
    print(f"  With 年金账户名: {has_account_name}")

    cur.execute("""
        SELECT COUNT(*) 
        FROM business."规模明细" 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
          AND ("年金账户名" IS NULL OR trim("年金账户名") = '')
          AND "客户名称" IS NOT NULL 
          AND trim("客户名称") <> ''
    """)
    only_customer_name = cur.fetchone()[0]
    print(f"  Only 客户名称 (no 年金账户名): {only_customer_name}")
    conn.close()

    # 2. Enterprise database
    conn = psycopg2.connect(ENTERPRISE_DB_URL)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM enterprise.base_info")
    base_info_total = cur.fetchone()[0]
    print(f"\n[postgres.enterprise.base_info]")
    print(f"  Total records: {base_info_total}")

    cur.execute("""
        SELECT COUNT(*) FROM enterprise.base_info 
        WHERE company_full_name IS NOT NULL 
          AND trim(company_full_name) <> ''
    """)
    has_full_name = cur.fetchone()[0]
    print(f"  With company_full_name: {has_full_name}")

    cur.execute("""
        SELECT COUNT(*) FROM enterprise.base_info 
        WHERE company_former_name IS NOT NULL 
          AND trim(company_former_name) <> ''
    """)
    has_former_name = cur.fetchone()[0]
    print(f"  With company_former_name: {has_former_name}")

    cur.execute("""
        SELECT COUNT(*) FROM enterprise.base_info 
        WHERE search_key_word IS NOT NULL 
          AND trim(search_key_word) <> ''
    """)
    has_search_keyword = cur.fetchone()[0]
    print(f"  With search_key_word: {has_search_keyword}")
    conn.close()

    return {
        "legacy": {
            "total": total,
            "valid_company_id": valid_company_id,
            "has_account_name": has_account_name,
            "only_customer_name": only_customer_name,
        },
        "base_info": {
            "total": base_info_total,
            "has_full_name": has_full_name,
            "has_former_name": has_former_name,
            "has_search_keyword": has_search_keyword,
        },
    }


def verify_normalization_consistency():
    """Verify that normalize_customer_name works correctly for our use case."""
    print("\n=== Verification: Normalization Consistency ===")

    # Updated for UPPERCASE output (2026-01-05 refactor)
    test_cases = [
        ("中国平安", "中国平安"),
        ("中国平安 ", "中国平安"),  # trailing space
        ("中国平安-已转出", "中国平安"),  # status marker
        ("中国平安（集团）", "中国平安（集团）"),  # parentheses preserved
        ("CHINA LIFE", "CHINALIFE"),  # UPPERCASE, no space
        ("  ABC  公司  ", "ABC公司"),  # multi-space, UPPERCASE
        ("中国平安（企业年金计划）", "中国平安"),  # status marker in brackets
    ]

    all_passed = True
    for input_str, expected in test_cases:
        result = normalize_customer_name(input_str)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} '{input_str}' -> '{result}' (expected: '{expected}')")

    return all_passed


def backup_existing_seed():
    """Backup existing seed data."""
    src = Path("config/seeds/enrichment_index.csv")
    if src.exists():
        import shutil

        shutil.copy(src, BACKUP_PATH)
        print(f"\nBacked up existing seed to: {BACKUP_PATH}")


def generate_seed_data():
    """Generate new enrichment_index seed data from all sources."""
    print("\n=== Generating Seed Data ===")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S+08")
    customer_name_records = []
    former_name_records = []
    seen_customer_keys = set()
    seen_former_keys = set()

    # =========================================================================
    # Source 1: legacy.business.规模明细
    # =========================================================================
    print("\n[1] Processing legacy.business.规模明细...")
    conn = psycopg2.connect(LEGACY_DB_URL)
    cur = conn.cursor()

    # 1a. From 年金账户名 (priority)
    cur.execute("""
        SELECT DISTINCT "年金账户名", company_id
        FROM business."规模明细" 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
          AND "年金账户名" IS NOT NULL 
          AND trim("年金账户名") <> ''
    """)

    account_name_count = 0
    for row in cur.fetchall():
        account_name, company_id = row
        lookup_key = normalize_customer_name(account_name)

        if not lookup_key or not company_id:
            continue

        if lookup_key in seen_customer_keys:
            continue

        seen_customer_keys.add(lookup_key)
        customer_name_records.append({
            "lookup_key": lookup_key,
            "lookup_type": "customer_name",
            "company_id": company_id.strip(),
            "confidence": "1.00",
            "source": "legacy_migration",
            "source_domain": "",
            "source_table": "business.规模明细",
            "hit_count": "0",
            "last_hit_at": "",
            "created_at": now,
            "updated_at": now,
        })
        account_name_count += 1

    print(f"    From 年金账户名: {account_name_count} records")

    # 1b. From 客户名称 only (when 年金账户名 is null)
    cur.execute("""
        SELECT DISTINCT "客户名称", company_id
        FROM business."规模明细" 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
          AND ("年金账户名" IS NULL OR trim("年金账户名") = '')
          AND "客户名称" IS NOT NULL 
          AND trim("客户名称") <> ''
    """)

    customer_name_only_count = 0
    for row in cur.fetchall():
        customer_name, company_id = row
        lookup_key = normalize_customer_name(customer_name)

        if not lookup_key or not company_id:
            continue

        if lookup_key in seen_customer_keys:
            continue

        seen_customer_keys.add(lookup_key)
        customer_name_records.append({
            "lookup_key": lookup_key,
            "lookup_type": "customer_name",
            "company_id": company_id.strip(),
            "confidence": "1.00",
            "source": "legacy_migration",
            "source_domain": "",
            "source_table": "business.规模明细",
            "hit_count": "0",
            "last_hit_at": "",
            "created_at": now,
            "updated_at": now,
        })
        customer_name_only_count += 1

    print(f"    From 客户名称 only: {customer_name_only_count} records")
    conn.close()

    # =========================================================================
    # Source 2: postgres.enterprise.base_info
    # =========================================================================
    print("\n[2] Processing postgres.enterprise.base_info...")
    conn = psycopg2.connect(ENTERPRISE_DB_URL)
    cur = conn.cursor()

    # 2a. From company_full_name → customer_name
    cur.execute("""
        SELECT company_id, company_full_name
        FROM enterprise.base_info 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
          AND company_full_name IS NOT NULL 
          AND trim(company_full_name) <> ''
    """)

    full_name_count = 0
    for row in cur.fetchall():
        company_id, full_name = row
        lookup_key = normalize_customer_name(full_name)

        if not lookup_key or not company_id:
            continue

        if lookup_key in seen_customer_keys:
            continue

        seen_customer_keys.add(lookup_key)
        customer_name_records.append({
            "lookup_key": lookup_key,
            "lookup_type": "customer_name",
            "company_id": company_id.strip(),
            "confidence": "1.00",
            "source": "eqc_api",
            "source_domain": "",
            "source_table": "enterprise.base_info",
            "hit_count": "0",
            "last_hit_at": "",
            "created_at": now,
            "updated_at": now,
        })
        full_name_count += 1

    print(f"    From company_full_name: {full_name_count} records")

    # 2b. From search_key_word → customer_name (补充)
    cur.execute("""
        SELECT company_id, search_key_word
        FROM enterprise.base_info 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
          AND search_key_word IS NOT NULL 
          AND trim(search_key_word) <> ''
    """)

    search_keyword_count = 0
    for row in cur.fetchall():
        company_id, search_keyword = row
        lookup_key = normalize_customer_name(search_keyword)

        if not lookup_key or not company_id:
            continue

        if lookup_key in seen_customer_keys:
            continue

        seen_customer_keys.add(lookup_key)
        customer_name_records.append({
            "lookup_key": lookup_key,
            "lookup_type": "customer_name",
            "company_id": company_id.strip(),
            "confidence": "0.95",  # Slightly lower confidence for search keyword
            "source": "eqc_api",
            "source_domain": "",
            "source_table": "enterprise.base_info",
            "hit_count": "0",
            "last_hit_at": "",
            "created_at": now,
            "updated_at": now,
        })
        search_keyword_count += 1

    print(f"    From search_key_word: {search_keyword_count} records")

    # 2c. From company_former_name → former_name
    cur.execute("""
        SELECT company_id, company_former_name
        FROM enterprise.base_info 
        WHERE company_id IS NOT NULL 
          AND company_id !~ '^IN'
          AND company_former_name IS NOT NULL 
          AND trim(company_former_name) <> ''
    """)

    former_name_count = 0
    for row in cur.fetchall():
        company_id, former_name = row
        # Former name may contain multiple names separated by comma
        names = [n.strip() for n in former_name.split(",") if n.strip()]

        for name in names:
            lookup_key = normalize_customer_name(name)

            if not lookup_key or not company_id:
                continue

            if lookup_key in seen_former_keys:
                continue

            # Also skip if already in customer_name (avoid duplicates)
            if lookup_key in seen_customer_keys:
                continue

            seen_former_keys.add(lookup_key)
            former_name_records.append({
                "lookup_key": lookup_key,
                "lookup_type": "former_name",
                "company_id": company_id.strip(),
                "confidence": "0.90",
                "source": "eqc_api",
                "source_domain": "",
                "source_table": "enterprise.base_info",
                "hit_count": "0",
                "last_hit_at": "",
                "created_at": now,
                "updated_at": now,
            })
            former_name_count += 1

    print(f"    From company_former_name: {former_name_count} records")
    conn.close()

    # =========================================================================
    # Source 3: Existing plan_code records
    # =========================================================================
    print("\n[3] Loading existing plan_code records...")
    existing_seed = Path("config/seeds/enrichment_index.csv")
    plan_code_records = []
    if existing_seed.exists():
        with open(existing_seed, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["lookup_type"] == "plan_code":
                    plan_code_records.append(row)

    print(f"    Existing plan_code records: {len(plan_code_records)}")

    # =========================================================================
    # Write output
    # =========================================================================
    print("\n=== Writing Output ===")
    SEED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "lookup_key",
        "lookup_type",
        "company_id",
        "confidence",
        "source",
        "source_domain",
        "source_table",
        "hit_count",
        "last_hit_at",
        "created_at",
        "updated_at",
    ]

    with open(SEED_OUTPUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        current_id = 1

        # Write plan_code records first (keep original IDs if possible)
        for row in plan_code_records:
            if "id" in row and row["id"]:
                row_id = int(row["id"])
                current_id = max(current_id, row_id + 1)
            writer.writerow(row)

        # Write customer_name records
        for record in customer_name_records:
            record["id"] = str(current_id)
            writer.writerow(record)
            current_id += 1

        # Write former_name records
        for record in former_name_records:
            record["id"] = str(current_id)
            writer.writerow(record)
            current_id += 1

    total_records = (
        len(plan_code_records) + len(customer_name_records) + len(former_name_records)
    )
    print(f"  Written to: {SEED_OUTPUT_PATH}")
    print(f"  Total records: {total_records}")

    return {
        "plan_code": len(plan_code_records),
        "customer_name": len(customer_name_records),
        "former_name": len(former_name_records),
        "total": total_records,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Enrichment Index Seed Data Generator")
    print("=" * 60)

    # Step 1: Analyze source data
    stats = analyze_source_data()

    # Step 2: Verify normalization
    if not verify_normalization_consistency():
        print("\nWARNING: Some normalization tests failed!")

    # Step 3: Backup existing seed
    backup_existing_seed()

    # Step 4: Generate new seed data
    result = generate_seed_data()

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  plan_code records: {result['plan_code']}")
    print(f"  customer_name records: {result['customer_name']}")
    print(f"  former_name records: {result['former_name']}")
    print(f"  Total: {result['total']}")
    print("=" * 60)
