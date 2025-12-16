"""Query table structure from database"""
import os
from sqlalchemy import create_engine, text

uri = os.getenv('WDH_DATABASE__URI')
# Fix postgres -> postgresql if needed
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)

engine = create_engine(uri)

with engine.connect() as conn:
    # Get columns from mapping.年金计划
    result = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema='mapping' AND table_name='年金计划' 
        ORDER BY ordinal_position
    """))
    print("Columns in mapping.年金计划:")
    cols = list(result)
    if not cols:
        print("  (No columns found - table may not exist or have different name)")
    else:
        for row in cols:
            print(f"  - {row[0]}: {row[1]}")
