"""
Diagnostic script for I006: ETL Backfill error diagnosis.
This script isolates the backfill operation to capture the full error stack.
"""
import logging
import sys

# Enable verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

import traceback
import psycopg2
import pandas as pd
from sqlalchemy import create_engine, text

# Import project components
from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill.generic_service import (
    GenericBackfillService,
    _qualified_table_name,
)
from work_data_hub.domain.reference_backfill.models import ForeignKeyConfig, BackfillColumnMapping


def diagnose_backfill():
    """Run a minimal backfill test to capture the exact error."""
    
    print("=" * 60)
    print("I006 Backfill Diagnosis Script")
    print("=" * 60)
    
    # Create a simple test FK config for 年金计划
    config = ForeignKeyConfig(
        name="annuity_plan",
        source_column="年金计划号",
        target_schema="mapping",
        target_table="年金计划",
        target_key="年金计划号",
        backfill_columns=[
            BackfillColumnMapping(source="计划名称", target="计划全称", optional=True)
        ],
        mode="insert_missing",
        depends_on=[]
    )
    
    # Create test data with a unique test value (columns as they would appear after derive_candidates)
    test_df = pd.DataFrame({
        "年金计划号": ["TEST_DIAG_001"],
        "计划全称": ["Test Diagnosis Plan"]
    })
    
    print(f"\n1. Test Configuration:")
    print(f"   - Target table: {config.target_schema}.{config.target_table}")
    print(f"   - Target key: {config.target_key}")
    print(f"   - Qualified table: {_qualified_table_name(config)}")
    
    print(f"\n2. Test Data:")
    print(test_df.to_string())
    
    # Get database connection
    print(f"\n3. Loading settings and connecting to database...")
    settings = get_settings()
    dsn = settings.database.get_connection_string()
    print(f"   DSN: {dsn[:50]}...")
    
    engine = create_engine(dsn, module=psycopg2)
    
    with engine.connect() as conn:
        # First verify the table exists and has the expected columns
        print(f"\n4. Checking table structure...")
        try:
            check_query = text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'mapping' 
                AND table_name = '年金计划'
                ORDER BY ordinal_position
            """)
            columns = conn.execute(check_query).fetchall()
            print(f"   Columns in mapping.年金计划:")
            for col_name, col_type in columns:
                print(f"      - {col_name}: {col_type}")
        except Exception as e:
            print(f"   ERROR checking table structure: {e}")
            traceback.print_exc()
            return
        
        # Initialize backfill service
        print(f"\n5. Running backfill (add_tracking_fields=False)...")
        service = GenericBackfillService(domain="diagnosis_test")
        
        try:
            # Run with add_tracking_fields=False since mapping tables don't have them
            inserted = service.backfill_table(
                candidates_df=test_df,
                config=config,
                conn=conn,
                add_tracking_fields=False
            )
            print(f"   SUCCESS! Inserted {inserted} records")
            
            # Rollback test data
            conn.rollback()
            print(f"   Rolled back test data")
            
        except Exception as e:
            print(f"\n   BACKFILL ERROR!")
            print(f"   Exception Type: {type(e).__name__}")
            print(f"   Exception Message: {e}")
            print(f"\n   Full stack trace:")
            traceback.print_exc()
            
            # Try to rollback
            try:
                conn.rollback()
            except:
                pass
    
    print("\n" + "=" * 60)
    print("Diagnosis complete")
    print("=" * 60)


if __name__ == "__main__":
    diagnose_backfill()
