"""
Generate annuity_income seed data from Legacy MySQL for New Pipeline.

================================================================================
BACKGROUND & PURPOSE
================================================================================

This script generates seed data for the annuity_income domain by:
1. Exporting raw data from Legacy MySQL (business.收入明细)
2. Cleaning the data to prepare for New Pipeline processing

The goal is to build seed data that goes through the SAME New Pipeline processing
as any new data, ensuring consistent data processing standards (口径) across
all data, whether legacy or new.

================================================================================
WHY CLEAN DATA BEFORE NEW PIPELINE?
================================================================================

The New Pipeline has upgraded data processing modules (e.g., customer_name_normalize)
that provide better data quality than Legacy processing. To ensure seed data
matches the same standards as new data, we need to:

1. Remove Legacy-processed fields (company_id, 产品线代码)
2. Revert to original raw data (年金账户名 vs 客户名称)
3. Reset default values (G00) to let New Pipeline re-determine

This ensures seed data and future data are processed with IDENTICAL logic,
eliminating discrepancies due to different processing standards.

================================================================================
DATA FLOW
================================================================================

Legacy MySQL (business.收入明细)
    ↓ [Step 1: Export]
Raw CSV - preserves all original Legacy data
    ↓ [Step 2: Clean]
Cleaned CSV - Bronze layer input for New Pipeline
    ↓ [Step 3: New Pipeline ETL]
Standardized Silver/Gold data - seed data ready for use

================================================================================
TRANSFORMATION STEPS (Step 2: Clean)
================================================================================

Step 1: Handle Missing 年金账户名
---------------------------------
Problem: Some records have missing/empty 年金账户名 due to data quality issues.
Solution: Fill missing 年金账户名 with 客户名称 as fallback.
Rationale:
- 客户名称 contains the same customer information but may have been cleaned
- This ensures we don't lose customer name data
- New Pipeline will re-normalize anyway, so we just need the raw value

Step 2: Replace 客户名称 with 年金账户名
-----------------------------------------
Problem: 客户名称 in Legacy was already processed by Legacy cleaning logic.
Solution: Replace 客户名称 with 年金账户名 (most original data).
Rationale:
- 年金账户名 contains the most original, unprocessed customer name
- New Pipeline's customer_name_normalize module will re-clean this data
- This ensures seed data uses the same cleaning standards as new data

Step 3: Remove 年金账户名 Column
----------------------------------
After Step 2, we have:
- 客户名称: now contains the original 年金账户名 data
- 年金账户名: duplicate, can be removed

Step 4: Remove company_id and 产品线代码
-----------------------------------------
Problem: These fields were determined by Legacy logic.
Solution: Delete these columns entirely.
Rationale:
- New Pipeline will re-determine company_id via 5-step resolution strategy
- New Pipeline will re-map 产品线代码 from 业务类型
- Removing them ensures New Pipeline doesn't use Legacy values

Step 5: Reset G00 Institution Codes
------------------------------------
Problem: Legacy system defaults empty 机构代码 to "G00" (headquarters).
Solution: Change "G00" values to NULL.
Rationale:
- "G00" is a default, not necessarily accurate
- New Pipeline can re-determine the correct institution code
- NULL allows New Pipeline to apply its own logic

================================================================================
USAGE
================================================================================

Full Pipeline (Export + Clean):
    PYTHONPATH=src uv run python scripts/seed_data/generate_annuity_income_original_data.py

Export Only:
    PYTHONPATH=src uv run python scripts/seed_data/generate_annuity_income_original_data.py --export-only

Clean Only:
    PYTHONPATH=src uv run python scripts/seed_data/generate_annuity_income_original_data.py --clean-only --input data/seed_data/annuity_income_raw.csv

With Limit (for testing):
    PYTHONPATH=src uv run python scripts/seed_data/generate_annuity_income_original_data.py --limit 10000

Custom Output Path:
    PYTHONPATH=src uv run python scripts/seed_data/generate_annuity_income_original_data.py -o data/my_output.csv
    # Creates: data/my_output.csv (cleaned) and data/my_output_raw.csv (raw)

Author: Seed Data Generator
Date: 2026-01-08
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# ========================================================================
# Configuration
# ========================================================================

DEFAULT_OUTPUT_DIR = Path("data/seed_data")
DEFAULT_BATCH_SIZE = 50000
LEGACY_TABLE = 'business."收入明细"'


# ========================================================================
# Database Connection
# ========================================================================


def load_env_file(env_path: Path) -> dict[str, str]:
    """Load environment variables from a file."""
    env_vars = {}
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()
    return env_vars


def get_legacy_connection_string() -> str:
    """Get Legacy database connection string from environment or .wdh_env file."""
    # Priority 1: Environment variable
    db_url = os.getenv("LEGACY_DATABASE__URI") or os.getenv("LEGACY_MYSQL_URL")

    # Priority 2: Load from .wdh_env file
    if not db_url:
        project_root = Path(__file__).parent.parent.parent
        env_file = project_root / ".wdh_env"
        env_vars = load_env_file(env_file)
        db_url = env_vars.get("LEGACY_DATABASE__URI")

    # Priority 3: Try settings module
    if not db_url:
        try:
            from work_data_hub.config.settings import get_settings

            settings = get_settings()
            db_url = getattr(settings, "legacy_database_url", None)
        except ImportError:
            pass

    if not db_url:
        raise ValueError(
            "Legacy database connection string not found. "
            "Please set LEGACY_DATABASE__URI in .wdh_env or environment."
        )

    # SQLAlchemy requires 'postgresql://' not 'postgres://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    return db_url


# ========================================================================
# Step 1: Export Data from Legacy MySQL
# ========================================================================


def export_data(
    output_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    limit: int | None = None,
) -> Path:
    """
    Export annuity_income data from Legacy MySQL to CSV.

    Args:
        output_path: Path to output CSV file
        batch_size: Number of rows to fetch per batch
        limit: Maximum number of rows to export (None for all)

    Returns:
        Path to the exported file
    """
    print(f"\n{'=' * 70}")
    print("STEP 1: EXPORT DATA FROM LEGACY MYSQL")
    print(f"{'=' * 70}")
    print("🚀 Starting export from Legacy MySQL...")
    print(f"📁 Output file: {output_path}")

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create database connection
    db_url = get_legacy_connection_string()
    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            # Get total row count
            count_query = text(f"SELECT COUNT(*) as total FROM {LEGACY_TABLE}")
            total_rows = conn.execute(count_query).scalar()
            print(f"📊 Total rows in {LEGACY_TABLE}: {total_rows:,}")

            if limit:
                total_rows = min(total_rows, limit)
                print(f"⚠️ Export limited to: {total_rows:,} rows")

            print(f"📥 Exporting data in batches of {batch_size:,}...")

            # Export in batches to manage memory
            chunks = []
            for offset in range(0, total_rows, batch_size):
                remaining = min(batch_size, total_rows - offset)
                batch_query = (
                    f"SELECT * FROM {LEGACY_TABLE} ORDER BY id LIMIT {remaining} OFFSET {offset}"
                )
                batch_df = pd.read_sql(text(batch_query), conn)

                chunks.append(batch_df)
                exported = min(offset + batch_size, total_rows)
                print(
                    f"   ✓ Exported: {exported:,}/{total_rows:,} rows "
                    f"({exported / total_rows * 100:.1f}%)"
                )

            # Concatenate all batches
            print(f"🔄 Merging {len(chunks)} batches...")
            df = pd.concat(chunks, ignore_index=True)

            # Sort by id to ensure consistent ordering
            df = df.sort_values("id").reset_index(drop=True)

            # Export to CSV
            print(f"💾 Writing to CSV: {output_path}")
            df.to_csv(output_path, index=False, encoding="utf-8-sig")

            # Export metadata
            metadata_path = output_path.parent / f"{output_path.stem}_metadata.txt"
            with open(metadata_path, "w", encoding="utf-8") as f:
                f.write("# Annuity Income Export Metadata\n")
                f.write(f"# Export Date: {datetime.now().isoformat()}\n")
                f.write(f"# Source: Legacy MySQL - {LEGACY_TABLE}\n")
                f.write(f"# Total Rows: {len(df):,}\n")
                f.write(f"# Columns: {len(df.columns)}\n")
                f.write(f"# Column Names: {', '.join(df.columns.tolist())}\n")

            print("\n✅ Export completed successfully!")
            print(f"   📄 Output file: {output_path}")
            print(f"   📊 Total rows: {len(df):,}")
            print(f"   📋 Total columns: {len(df.columns)}")
            print(f"   📄 Metadata: {metadata_path}")

            return output_path

    except Exception as e:
        print(f"❌ Export failed: {e}")
        raise
    finally:
        engine.dispose()


# ========================================================================
# Step 2: Clean Data for New Pipeline
# ========================================================================


def clean_data(
    input_path: Path,
    output_path: Path,
) -> Path:
    """
    Clean exported annuity_income data for New Pipeline processing.

    Args:
        input_path: Path to input CSV file (exported from Legacy)
        output_path: Path to output CSV file (cleaned for New Pipeline)

    Returns:
        Path to the cleaned file
    """
    print(f"\n{'=' * 70}")
    print("STEP 2: CLEAN DATA FOR NEW PIPELINE")
    print(f"{'=' * 70}")
    print("🔧 Cleaning data for New Pipeline...")
    print(f"📄 Input: {input_path}")
    print(f"📄 Output: {output_path}")

    # Load data
    print(f"\n📥 Loading data from {input_path}...")
    df = pd.read_csv(input_path)
    print(f"   ✓ Loaded: {len(df):,} rows, {len(df.columns)} columns")

    # ========================================================================
    # Step 2.1: Handle Missing 年金账户名
    # ========================================================================
    print("\n🔄 Step 2.1: Handling missing 年金账户名...")

    if "年金账户名" in df.columns:
        # Count empty 年金账户名 before filling
        empty_before = (
            df["年金账户名"].isna()
            | (df["年金账户名"] == "")
            | (df["年金账户名"] == "null")
        ).sum()
        print(
            f"   📊 Empty 年金账户名 before filling: {empty_before:,} ({empty_before / len(df) * 100:.2f}%)"
        )

        # Fill missing 年金账户名 with 客户名称
        if "客户名称" in df.columns:
            mask = (
                df["年金账户名"].isna()
                | (df["年金账户名"] == "")
                | (df["年金账户名"] == "null")
            )
            df.loc[mask, "年金账户名"] = df.loc[mask, "客户名称"]

            filled_count = (
                (df["年金账户名"].notna())
                & (df["年金账户名"] != "")
                & (df["年金账户名"] != "null")
            ).sum()

            print("   ✓ Filled missing 年金账户名 with 客户名称")
            print(
                f"   📊 Non-empty 年金账户名 after filling: {filled_count:,} ({filled_count / len(df) * 100:.2f}%)"
            )
        else:
            print(
                "   ⚠️ Warning: '客户名称' column not found, cannot fill missing 年金账户名"
            )
    else:
        print("   ⚠️ Warning: '年金账户名' column not found")

    # ========================================================================
    # Step 2.2: Replace 客户名称 with 年金账户名
    # ========================================================================
    print("\n🔄 Step 2.2: Replacing 客户名称 with 年金账户名 (most original data)...")

    if "年金账户名" in df.columns:
        # Replace 客户名称 with 年金账户名
        df["客户名称"] = df["年金账户名"]

        # Remove 年金账户名 column
        df = df.drop(columns=["年金账户名"])

        print("   ✓ Replaced 客户名称 with 年金账户名")
        print("   ✓ Removed 年金账户名 column (now duplicate)")
    else:
        print("   ⚠️ Warning: '年金账户名' column not found, skipping")

    # ========================================================================
    # Step 2.3: Remove company_id and 产品线代码
    # ========================================================================
    print("\n🗑️  Step 2.3: Removing fields determined by Legacy...")

    for field in ["company_id", "产品线代码"]:
        if field in df.columns:
            df = df.drop(columns=[field])
            print(f"   ✓ Removed: {field} (will be re-determined by New Pipeline)")

    # ========================================================================
    # Step 2.4: Reset G00 Institution Codes to NULL
    # ========================================================================
    print("\n🔄 Step 2.4: Resetting 'G00' institution codes to NULL...")

    if "机构代码" in df.columns:
        g00_count = (df["机构代码"] == "G00").sum()
        df.loc[df["机构代码"] == "G00", "机构代码"] = None

        non_null_after = df["机构代码"].notna().sum()
        print(f"   ✓ Reset: {g00_count:,} rows from 'G00' to NULL")
        print(
            f"   📊 Non-null 机构代码: {non_null_after:,} ({non_null_after / len(df) * 100:.1f}%)"
        )
    else:
        print("   ⚠️ Warning: '机构代码' column not found")

    # ========================================================================
    # Final: Sort and Export
    # ========================================================================
    print("\n💾 Final: Sorting and exporting cleaned data...")

    if "id" in df.columns:
        df = df.sort_values("id").reset_index(drop=True)
        print("   ✓ Sorted by 'id' for consistent ordering")

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"   ✓ Exported to: {output_path}")

    # ========================================================================
    # Summary
    # ========================================================================
    print(f"\n{'=' * 70}")
    print("📊 CLEANING SUMMARY")
    print(f"{'=' * 70}")
    print(f"📄 Output: {output_path}")
    print(f"📊 Rows: {len(df):,}")
    print(f"📋 Columns: {len(df.columns)}")
    print("\n✅ Cleaning completed!")
    print(f"{'=' * 70}")

    return output_path


# ========================================================================
# Main Pipeline
# ========================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate annuity_income seed data from Legacy MySQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (export + clean)
  %(prog)s

  # Export only
  %(prog)s --export-only

  # Clean only
  %(prog)s --clean-only --input data/seed_data/raw.csv

  # With limit for testing
  %(prog)s --limit 10000

  # Custom output path (raw file auto-generated with _raw suffix)
  %(prog)s -o data/my_output.csv
        """,
    )

    # Execution mode
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--export-only",
        action="store_true",
        help="Only export data from Legacy MySQL, skip cleaning",
    )
    mode_group.add_argument(
        "--clean-only",
        action="store_true",
        help="Only clean existing exported data, skip export",
    )

    # Input/Output
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default=None,
        help="Input CSV file (required for --clean-only mode)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output path for cleaned CSV (raw file auto-generated with _raw suffix)",
    )

    # Export options
    parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of rows to fetch per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=None,
        help="Maximum number of rows to export (default: all rows)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.clean_only and not args.input:
        parser.error("--input is required when using --clean-only")

    # Generate output paths
    # User specifies cleaned output path, raw path is auto-generated
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f"annuity_income_{timestamp}.csv"

    if args.output:
        output_path = Path(args.output)

        # Handle directory path: if path is a directory or ends with separator, use default filename
        if output_path.is_dir() or str(args.output).endswith(("/", "\\")):
            output_path.mkdir(parents=True, exist_ok=True)
            cleaned_output = output_path / default_filename
        else:
            # Ensure .csv extension
            if output_path.suffix.lower() != ".csv":
                output_path = output_path.with_suffix(".csv")
            cleaned_output = output_path

        # Generate raw path: add _raw suffix before extension
        raw_output = (
            cleaned_output.parent / f"{cleaned_output.stem}_raw{cleaned_output.suffix}"
        )
    else:
        cleaned_output = DEFAULT_OUTPUT_DIR / f"annuity_income_{timestamp}.csv"
        raw_output = DEFAULT_OUTPUT_DIR / f"annuity_income_{timestamp}_raw.csv"

    # ========================================================================
    # Execute Pipeline
    # ========================================================================

    print(f"\n{'=' * 70}")
    print("ANNUITY INCOME SEED DATA GENERATION")
    print(f"{'=' * 70}")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Clean only mode
    if args.clean_only:
        clean_data(Path(args.input), cleaned_output)

    # Export only mode
    elif args.export_only:
        export_data(raw_output, batch_size=args.batch_size, limit=args.limit)

    # Full pipeline mode (default)
    else:
        # Step 1: Export
        export_data(raw_output, batch_size=args.batch_size, limit=args.limit)

        # Step 2: Clean
        clean_data(raw_output, cleaned_output)

        # Final summary
        print(f"\n{'=' * 70}")
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY")
        print(f"{'=' * 70}")
        print(f"📄 Raw data: {raw_output}")
        print(f"📄 Cleaned data: {cleaned_output}")
        print("\n📝 Next Steps:")
        print("   1. Move cleaned CSV to Bronze input directory")
        print("   2. Run New Pipeline ETL to generate Silver/Gold seed data")
        print("   3. Validate seed data quality")
        print(f"{'=' * 70}")

    print(f"\nEnd Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    main()
