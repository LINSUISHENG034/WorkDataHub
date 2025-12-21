#!/usr/bin/env python
"""
Cleanup script for enrichment_index data.

Applies the following cleanup rules:
1. Remove records with company_id = 'N' or company_id LIKE 'IN%' (invalid)
2. Remove records where lookup_key = company_id
3. Remove customer_name records when account_name exists for same lookup_key
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def create_engine_from_env():
    load_dotenv('.wdh_env')
    database_url = os.environ.get("WDH_DATABASE__URI")
    if not database_url:
        raise ValueError("WDH_DATABASE__URI is required")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return create_engine(database_url)


def analyze(conn):
    """Show what will be cleaned up."""
    print("=== Current Status ===")
    total = conn.execute(text("SELECT COUNT(*) FROM enterprise.enrichment_index")).scalar()
    print(f"Total rows: {total:,}")
    
    print("\n=== Records matching cleanup rules ===")
    
    # Rule 1
    r1 = conn.execute(text("""
        SELECT COUNT(*) FROM enterprise.enrichment_index 
        WHERE company_id = 'N' OR company_id LIKE 'IN%'
    """)).scalar()
    print(f"Rule 1 (company_id='N' or LIKE 'IN%'): {r1:,}")
    
    # Rule 2
    r2 = conn.execute(text("""
        SELECT COUNT(*) FROM enterprise.enrichment_index 
        WHERE lookup_key = company_id
    """)).scalar()
    print(f"Rule 2 (lookup_key = company_id): {r2:,}")
    
    # Rule 3
    r3 = conn.execute(text("""
        SELECT COUNT(*) FROM enterprise.enrichment_index ei
        WHERE lookup_type = 'customer_name'
        AND EXISTS (
            SELECT 1 FROM enterprise.enrichment_index ei2
            WHERE ei2.lookup_key = ei.lookup_key
            AND ei2.lookup_type = 'account_name'
        )
    """)).scalar()
    print(f"Rule 3 (customer_name duplicates of account_name): {r3:,}")
    
    return {"total": total, "r1": r1, "r2": r2, "r3": r3}


def cleanup(conn, dry_run=False):
    """Execute cleanup."""
    stats = analyze(conn)
    
    if dry_run:
        print("\n[DRY RUN] No changes made.")
        return stats
    
    print("\n=== Executing Cleanup ===")
    
    # Rule 1: Remove invalid company_id
    result = conn.execute(text("""
        DELETE FROM enterprise.enrichment_index 
        WHERE company_id = 'N' OR company_id LIKE 'IN%'
    """))
    print(f"Rule 1: Deleted {result.rowcount:,} rows")
    
    # Rule 2: Remove lookup_key = company_id
    result = conn.execute(text("""
        DELETE FROM enterprise.enrichment_index 
        WHERE lookup_key = company_id
    """))
    print(f"Rule 2: Deleted {result.rowcount:,} rows")
    
    # Rule 3: Remove customer_name when account_name exists for same lookup_key
    result = conn.execute(text("""
        DELETE FROM enterprise.enrichment_index ei
        WHERE lookup_type = 'customer_name'
        AND EXISTS (
            SELECT 1 FROM enterprise.enrichment_index ei2
            WHERE ei2.lookup_key = ei.lookup_key
            AND ei2.lookup_type = 'account_name'
        )
    """))
    print(f"Rule 3: Deleted {result.rowcount:,} rows")
    
    conn.commit()
    
    # Final count
    final = conn.execute(text("SELECT COUNT(*) FROM enterprise.enrichment_index")).scalar()
    print(f"\nFinal row count: {final:,} (removed {stats['total'] - final:,})")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Cleanup enrichment_index data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without making changes")
    parser.add_argument("--analyze", action="store_true", help="Only analyze, don't delete")
    args = parser.parse_args()
    
    engine = create_engine_from_env()
    
    with engine.connect() as conn:
        if args.analyze:
            analyze(conn)
        else:
            cleanup(conn, dry_run=args.dry_run)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
