"""
Comprehensive ETL Backfill diagnosis script.
Runs the full backfill flow with real data to capture exact error.
"""
import logging
import sys
import traceback

# Enable verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

import psycopg2
import pandas as pd
import yaml
from pathlib import Path
from sqlalchemy import create_engine, text

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.reference_backfill.generic_service import GenericBackfillService
from work_data_hub.domain.reference_backfill.models import ForeignKeyConfig, BackfillColumnMapping


def load_fk_configs(domain_config: dict) -> list[ForeignKeyConfig]:
    """Load FK configs from domain configuration."""
    fk_configs = []
    foreign_keys = domain_config.get('foreign_keys', [])
    
    for fk_def in foreign_keys:
        backfill_cols = []
        for col in fk_def.get('backfill_columns', []):
            backfill_cols.append(BackfillColumnMapping(
                source=col['source'],
                target=col['target'],
                optional=col.get('optional', False)
            ))
        
        config = ForeignKeyConfig(
            name=fk_def['name'],
            source_column=fk_def['source_column'],
            target_schema=fk_def.get('target_schema', 'public'),
            target_table=fk_def['target_table'],
            target_key=fk_def['target_key'],
            mode=fk_def.get('mode', 'insert_missing'),
            depends_on=fk_def.get('depends_on', []),
            backfill_columns=backfill_cols,
        )
        fk_configs.append(config)
    
    return fk_configs


def main():
    print("=" * 80)
    print("COMPREHENSIVE ETL BACKFILL DIAGNOSIS")
    print("=" * 80)
    
    # Load data sources config
    config_path = Path("config/data_sources.yml")
    with open(config_path) as f:
        data_sources = yaml.safe_load(f)
    
    domain_config = data_sources['domains']['annuity_performance']
    print(f"\n1. Domain Config: annuity_performance")
    print(f"   - Output table: {domain_config['output']['table']}")
    
    # Get FK configs
    fk_configs = load_fk_configs(domain_config)
    print(f"\n2. FK Configs loaded: {len(fk_configs)}")
    for cfg in fk_configs:
        print(f"   - {cfg.name}: {cfg.source_column} -> {cfg.target_schema}.{cfg.target_table}")
    
    # Create a sample DataFrame simulating transformation output
    # Include columns that would exist after pipeline transformation
    print("\n3. Creating sample transformed data...")
    sample_data = pd.DataFrame({
        "计划代码": ["TEST_PLAN_001", "TEST_PLAN_002"],
        "计划名称": ["Test Plan 1", "Test Plan 2"],
        "计划类型": ["DB", "DC"],
        "客户名称": ["Test Client 1", "Test Client 2"],
        "主拓代码": ["001", "002"],
        "主拓机构": ["北京分公司", "上海分公司"],
        "资格": ["全托", "投管"],
        "组合代码": ["TEST_PORT_001", "TEST_PORT_002"],
        "组合名称": ["Portfolio 1", "Portfolio 2"],
        "组合类型": ["普通", "专户"],
        "产品线代码": ["A01", "A02"],
        "业务类型": ["年金A类", "年金B类"],
        "机构代码": ["ORG001", "ORG002"],
        "机构": ["机构1", "机构2"],
    })
    print(sample_data.to_string())
    
    # Get database connection
    print("\n4. Connecting to database...")
    settings = get_settings()
    dsn = settings.database.get_connection_string()
    engine = create_engine(dsn, module=psycopg2)
    
    with engine.connect() as conn:
        # Initialize service
        service = GenericBackfillService(domain="diagnosis_full")
        
        # Run with plan_only=False but in a try block
        print("\n5. Running backfill with add_tracking_fields=False...")
        try:
            result = service.run(
                df=sample_data,
                configs=fk_configs,
                conn=conn,
                add_tracking_fields=False,  # mapping tables don't have tracking fields
                plan_only=False
            )
            print(f"   SUCCESS!")
            print(f"   - Processing order: {result.processing_order}")
            print(f"   - Total inserted: {result.total_inserted}")
            print(f"   - Total skipped: {result.total_skipped}")
            
            # Rollback test data
            conn.rollback()
            print("   Rolled back test data")
            
        except Exception as e:
            print(f"\n   BACKFILL ERROR!")
            print(f"   Exception Type: {type(e).__name__}")
            print(f"   Exception Message: {e}")
            print(f"\n   Full stack trace:")
            traceback.print_exc()
            
            try:
                conn.rollback()
            except:
                pass
    
    print("\n" + "=" * 80)
    print("Diagnosis complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
