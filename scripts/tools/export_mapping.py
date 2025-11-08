#!/usr/bin/env python3
"""
Legacy Mapping Extraction Utility

Extracts and formalizes all mapping dictionaries from the legacy AnnuityPerformanceCleaner
into version-controlled JSON fixtures for the new pipeline.

This utility:
- Connects to migrated PostgreSQL database using existing connection patterns
- Extracts 10 mapping dictionaries from various tables with proper SQL queries
- Generates standardized JSON files with metadata and UTF-8 encoding
- Documents missing entries and validation gaps for manual backfill
- Follows existing codebase patterns for database operations and JSON export
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from work_data_hub.config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TableNotFoundError(Exception):
    """Raised when a required table is not found in the database."""
    pass


class MappingMetadata(BaseModel):
    """Metadata for mapping exports."""
    description: str
    source: str  # table name or "hardcoded_dictionary"
    export_timestamp: datetime
    extractor_version: str = "1.0"
    row_count: Optional[int] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MappingExport(BaseModel):
    """Complete mapping export with metadata and data."""
    metadata: MappingMetadata
    data: Dict[str, str]  # key -> value mappings

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ExtractionPlan(BaseModel):
    """Configuration for extracting a specific mapping."""
    mapping_name: str
    source_type: str  # "database" or "hardcoded"
    description: str
    table_name: Optional[str] = None
    sql_query: Optional[str] = None
    hardcoded_data: Optional[Dict[str, str]] = None
    output_file: str


class MappingExtractor:
    """Main class for extracting legacy mappings."""

    def __init__(self):
        """Initialize the extractor with database connection."""
        self.settings = get_settings()
        self.dsn = self.settings.get_database_connection_string()
        self.missing_entries: List[str] = []

        # Define extraction plans for all 10 mappings
        self.extraction_plans = self._get_extraction_plans()

        logger.info("MappingExtractor initialized")

    def _get_extraction_plans(self) -> Dict[str, ExtractionPlan]:
        """Define extraction plans for all 10 legacy mappings."""

        # Hardcoded mappings from legacy code
        company_id3_mapping = {
            'FP0001': '614810477',
            'FP0002': '614810477',
            'FP0003': '610081428',
            'P0809': '608349737',
            'SC002': '604809109',
            'SC007': '602790403',
            'XNP466': '603968573',
            'XNP467': '603968573',
            'XNP596': '601038164',
        }

        default_portfolio_code_mapping = {
            '集合计划': 'QTAN001',
            '单一计划': 'QTAN002',
            '职业年金': 'QTAN003'
        }

        return {
            'company_id1_mapping': ExtractionPlan(
                mapping_name='company_id1_mapping',
                source_type='database',
                description='Plan codes (priority=1) from 年金计划 table',
                table_name='年金计划',
                sql_query="""
                    SELECT jsonb_object_agg(年金计划号, company_id)
                    FROM 年金计划
                    WHERE 计划类型 = '单一计划' AND 年金计划号 != 'AN002'
                """,
                output_file='tests/fixtures/mappings/company_id1_mapping.json'
            ),

            'company_id2_mapping': ExtractionPlan(
                mapping_name='company_id2_mapping',
                source_type='database',
                description='Account numbers (priority=2) from annuity_account_mapping table',
                table_name='annuity_account_mapping',
                sql_query="""
                    SELECT jsonb_object_agg(年金账户号, company_id)
                    FROM annuity_account_mapping
                    WHERE 年金账户号 NOT LIKE 'GM%'
                """,
                output_file='tests/fixtures/mappings/company_id2_mapping.json'
            ),

            'company_id3_mapping': ExtractionPlan(
                mapping_name='company_id3_mapping',
                source_type='hardcoded',
                description='Hardcoded mappings (priority=3) from mappings.py',
                hardcoded_data=company_id3_mapping,
                output_file='tests/fixtures/mappings/company_id3_mapping.json'
            ),

            'company_id4_mapping': ExtractionPlan(
                mapping_name='company_id4_mapping',
                source_type='database',
                description='Customer names (priority=4) from company_id_mapping table',
                table_name='company_id_mapping',
                sql_query="""
                    SELECT jsonb_object_agg(company_name, company_id)
                    FROM company_id_mapping
                """,
                output_file='tests/fixtures/mappings/company_id4_mapping.json'
            ),

            'company_id5_mapping': ExtractionPlan(
                mapping_name='company_id5_mapping',
                source_type='database',
                description='Account names (priority=5) from 规模明细 table',
                table_name='规模明细',
                sql_query="""
                    SELECT jsonb_object_agg(年金账户名, company_id)
                    FROM 规模明细
                    WHERE company_id IS NOT NULL
                """,
                output_file='tests/fixtures/mappings/company_id5_mapping.json'
            ),

            'company_branch_mapping': ExtractionPlan(
                mapping_name='company_branch_mapping',
                source_type='database',
                description='Institution -> code mapping from 组织架构 table',
                table_name='组织架构',
                sql_query="""
                    SELECT jsonb_object_agg(机构, 机构代码)
                    FROM 组织架构
                """,
                output_file='tests/fixtures/mappings/company_branch_mapping.json'
            ),

            'business_type_code_mapping': ExtractionPlan(
                mapping_name='business_type_code_mapping',
                source_type='database',
                description='Business type -> code mappings from 产品线 table',
                table_name='产品线',
                sql_query="""
                    SELECT jsonb_object_agg(产品线, 产品线代码)
                    FROM 产品线
                """,
                output_file='tests/fixtures/mappings/business_type_code_mapping.json'
            ),

            'default_portfolio_code_mapping': ExtractionPlan(
                mapping_name='default_portfolio_code_mapping',
                source_type='hardcoded',
                description='Default portfolio codes used when source is blank',
                hardcoded_data=default_portfolio_code_mapping,
                output_file='tests/fixtures/mappings/default_portfolio_code_mapping.json'
            ),

            'product_id_mapping': ExtractionPlan(
                mapping_name='product_id_mapping',
                source_type='database',
                description='Product -> ID mappings from 产品明细 table',
                table_name='产品明细',
                sql_query="""
                    SELECT jsonb_object_agg(产品明细, 产品ID)
                    FROM 产品明细
                """,
                output_file='tests/fixtures/mappings/product_id_mapping.json'
            ),

            'profit_metrics_mapping': ExtractionPlan(
                mapping_name='profit_metrics_mapping',
                source_type='database',
                description='Metrics -> code mappings from 利润指标 table',
                table_name='利润指标',
                sql_query="""
                    SELECT jsonb_object_agg(指标名称, 指标编码)
                    FROM 利润指标
                """,
                output_file='tests/fixtures/mappings/profit_metrics_mapping.json'
            ),
        }

    def check_table_exists(self, cursor, table_name: str) -> bool:
        """Check if a table exists in the database."""
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = %s
            );
        """, (table_name,))
        return cursor.fetchone()[0]

    def extract_mapping_from_database(self, plan: ExtractionPlan) -> MappingExport:
        """Extract a mapping from the database using the provided plan."""
        if not plan.table_name:
            raise ValueError(f"Table name required for database extraction of {plan.mapping_name}")
        if not plan.sql_query:
            raise ValueError(f"SQL query required for database extraction of {plan.mapping_name}")

        logger.info(f"Extracting {plan.mapping_name} from database table {plan.table_name}")

        with psycopg2.connect(self.dsn) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Check table existence first
                if not self.check_table_exists(cursor, plan.table_name):
                    error_msg = f"Table {plan.table_name} not found for {plan.mapping_name}"
                    logger.error(error_msg)
                    self.missing_entries.append(error_msg)
                    raise TableNotFoundError(error_msg)

                # Execute the mapping query
                try:
                    cursor.execute(plan.sql_query)
                    row = cursor.fetchone()
                    result = row[0] if row else {}

                    if not result:
                        warning_msg = f"No data found in {plan.table_name} for {plan.mapping_name}"
                        logger.warning(warning_msg)
                        self.missing_entries.append(warning_msg)

                    # Create metadata
                    metadata = MappingMetadata(
                        description=plan.description,
                        source=plan.table_name,
                        export_timestamp=datetime.now(),
                        row_count=len(result)
                    )

                    logger.info(
                        f"Successfully extracted {len(result)} mappings from {plan.table_name}"
                    )
                    return MappingExport(metadata=metadata, data=result)

                except Exception as e:
                    error_msg = f"Failed to query {plan.table_name} for {plan.mapping_name}: {e}"
                    logger.error(error_msg)
                    self.missing_entries.append(error_msg)
                    raise

    def extract_mapping_from_hardcoded(self, plan: ExtractionPlan) -> MappingExport:
        """Extract a mapping from hardcoded data."""
        logger.info(f"Extracting {plan.mapping_name} from hardcoded data")

        data = plan.hardcoded_data or {}

        # Create metadata
        metadata = MappingMetadata(
            description=plan.description,
            source="hardcoded_dictionary",
            export_timestamp=datetime.now(),
            row_count=len(data)
        )

        logger.info(f"Successfully extracted {len(data)} hardcoded mappings")
        return MappingExport(metadata=metadata, data=data)

    def save_mapping_to_json(self, mapping: MappingExport, output_path: str):
        """Save mapping to JSON file with UTF-8 encoding."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary for JSON serialization
        mapping_dict = mapping.model_dump()

        # Save with UTF-8 encoding and ensure_ascii=False for Chinese characters
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                mapping_dict,
                f,
                indent=2,
                ensure_ascii=False,  # Preserves Chinese characters
                sort_keys=True,      # Stable diffs
                default=str          # Handle datetime serialization
            )

        logger.info(f"Saved mapping to {output_path}")

    def extract_single_mapping(self, mapping_name: str) -> bool:
        """Extract a single mapping by name."""
        if mapping_name not in self.extraction_plans:
            logger.error(f"Unknown mapping: {mapping_name}")
            return False

        plan = self.extraction_plans[mapping_name]

        try:
            if plan.source_type == 'database':
                mapping_export = self.extract_mapping_from_database(plan)
            else:
                mapping_export = self.extract_mapping_from_hardcoded(plan)

            self.save_mapping_to_json(mapping_export, plan.output_file)
            return True

        except Exception as e:
            logger.error(f"Failed to extract {mapping_name}: {e}")
            return False

    def extract_all_mappings(self) -> bool:
        """Extract all mappings."""
        logger.info("Starting extraction of all mappings")

        success_count = 0
        total_count = len(self.extraction_plans)

        for mapping_name in self.extraction_plans:
            if self.extract_single_mapping(mapping_name):
                success_count += 1

        logger.info(f"Extraction completed: {success_count}/{total_count} successful")

        # Generate missing entries report
        self.generate_missing_entries_report()

        return success_count == total_count

    def generate_missing_entries_report(self):
        """Generate a report of missing entries and issues."""
        report_path = Path("tests/fixtures/mappings/_missing_entries.md")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Missing Entries Report\n\n")
            f.write(f"Generated on: {datetime.now().isoformat()}\n\n")

            if not self.missing_entries:
                f.write("✅ No missing entries or issues detected.\n")
            else:
                f.write("## Issues Found\n\n")
                for i, entry in enumerate(self.missing_entries, 1):
                    f.write(f"{i}. {entry}\n")

                f.write("\n## Recommendations\n\n")
                f.write("- Verify that all referenced tables have been migrated to PostgreSQL\n")
                f.write(
                    "- Check table and column names match between MySQL legacy and PostgreSQL\n"
                )
                f.write("- Consider manual backfill for missing mapping data\n")

        logger.info(f"Missing entries report saved to {report_path}")

    def list_available_mappings(self):
        """List all available mappings."""
        print("Available mappings:")
        for i, (name, plan) in enumerate(self.extraction_plans.items(), 1):
            print(f"  {i:2d}. {name:<30} ({plan.source_type:<10}) -> {plan.output_file}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract legacy mapping dictionaries to JSON fixtures"
    )
    parser.add_argument('--mapping', '-m', help='Extract specific mapping by name')
    parser.add_argument('--all', '-a', action='store_true', help='Extract all mappings')
    parser.add_argument('--list', '-l', action='store_true', help='List available mappings')
    parser.add_argument('--output', '-o', help='Custom output file (only with --mapping)')

    args = parser.parse_args()

    if args.list:
        extractor = MappingExtractor()
        extractor.list_available_mappings()
        return

    if not args.mapping and not args.all:
        parser.print_help()
        return

    try:
        extractor = MappingExtractor()

        if args.all:
            success = extractor.extract_all_mappings()
            if success:
                print("✅ All mappings extracted successfully")
            else:
                print("❌ Some mappings failed to extract - check logs")

        elif args.mapping:
            # Custom output path if specified
            if args.output:
                if args.mapping in extractor.extraction_plans:
                    extractor.extraction_plans[args.mapping].output_file = args.output

            success = extractor.extract_single_mapping(args.mapping)
            if success:
                print(f"✅ {args.mapping} extracted successfully")
            else:
                print(f"❌ Failed to extract {args.mapping}")

    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"❌ Script failed: {e}")


if __name__ == '__main__':
    main()
