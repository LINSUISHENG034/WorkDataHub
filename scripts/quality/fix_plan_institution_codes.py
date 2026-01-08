#!/usr/bin/env python
"""
Fix institution codes and names in business."规模明细" for single plans.

This script:
1. Loads the default_plan_institution_code.yml configuration
2. Updates records where 机构代码 = 'G00' for 单一计划 (single plans)
3. Only fixes data from 2024 and earlier
4. Updates both 机构代码 (institution_code) and 机构名称 (institution_name)

Database: postgres://postgres:Post.169828@localhost:5432/postgres
"""
import sys
from pathlib import Path

import yaml
from sqlalchemy import create_engine, text
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Database connection
DB_URL = "postgresql://postgres:Post.169828@localhost:5432/postgres"


def load_config():
    """Load the plan-institution mapping configuration."""
    config_path = (
        Path(__file__).parent.parent / "config" / "mappings" / "default_plan_institution_code.yml"
    )
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config.get("default_plan_institution_mapping", {})


def get_institution_name_mapping(engine):
    """Get institution code to name mapping from existing data."""
    query = """
    SELECT DISTINCT
        机构代码 AS institution_code,
        机构名称 AS institution_name
    FROM business."规模明细"
    WHERE 机构代码 IS NOT NULL
      AND 机构名称 IS NOT NULL
      AND 机构代码 != 'G00'
    """

    with engine.connect() as conn:
        result = conn.execute(text(query))
        return {row.institution_code: row.institution_name for row in result}


def get_records_to_fix(engine, plan_mapping):
    """Get records that need to be fixed."""
    query = """
    SELECT
        id,
        计划代码 AS plan_code,
        机构代码 AS current_institution_code,
        机构名称 AS current_institution_name
    FROM business."规模明细"
    WHERE 计划类型 = '单一计划'
      AND 机构代码 = 'G00'
      AND EXTRACT(YEAR FROM 月度) <= 2024
      AND 计划代码 = ANY(:plan_codes)
    ORDER BY 月度 DESC, 计划代码
    """

    plan_codes = list(plan_mapping.keys())

    with engine.connect() as conn:
        result = conn.execute(text(query), {"plan_codes": plan_codes})
        return list(result)


def fix_institution_data(engine, plan_mapping, institution_name_mapping, dry_run=True):
    """
    Fix institution codes and names in business."规模明细".

    Args:
        engine: Database engine
        plan_mapping: Dict mapping plan codes to institution codes
        institution_name_mapping: Dict mapping institution codes to names
        dry_run: If True, only show what would be changed without making changes

    Returns:
        Dict with statistics
    """
    # Get records to fix
    records = get_records_to_fix(engine, plan_mapping)

    if not records:
        return {"total_records": 0, "updated": 0, "skipped": 0}

    stats = {"total_records": len(records), "updated": 0, "skipped": 0, "errors": []}

    print(f"\nFound {len(records)} records to fix")
    print(f"Mode: {'DRY RUN - no changes will be made' if dry_run else 'LIVE - will make changes'}")
    print()

    # Group by plan code for batch processing
    from collections import defaultdict

    records_by_plan = defaultdict(list)
    for record in records:
        records_by_plan[record.plan_code].append(record)

    # Process each plan
    with engine.begin() as conn:
        for plan_code, plan_records in tqdm(
            records_by_plan.items(), desc="Processing plans", unit="plan"
        ):
            if plan_code not in plan_mapping:
                stats["skipped"] += len(plan_records)
                continue

            new_institution_code = plan_mapping[plan_code]
            new_institution_name = institution_name_mapping.get(new_institution_code)

            if not new_institution_name:
                stats["errors"].append(
                    f"No institution name found for code {new_institution_code} (plan {plan_code})"
                )
                stats["skipped"] += len(plan_records)
                continue

            # Prepare update query
            update_query = """
            UPDATE business."规模明细"
            SET 机构代码 = :new_institution_code,
                机构名称 = :new_institution_name,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :record_id
            """

            # Update each record
            for record in plan_records:
                if dry_run:
                    # Just print what would be changed
                    print(
                        f"Would update record {record.id}: "
                        f"{record.current_institution_code} -> {new_institution_code}, "
                        f"{record.current_institution_name} -> {new_institution_name}"
                    )
                else:
                    # Execute the update
                    conn.execute(
                        text(update_query),
                        {
                            "new_institution_code": new_institution_code,
                            "new_institution_name": new_institution_name,
                            "record_id": record.id,
                        },
                    )
                stats["updated"] += 1

    return stats


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix institution codes and names in business.规模明细"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the fix (default is dry-run mode)",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("修复 business.\"规模明细\" 机构代码和机构名称")
    print("=" * 80)
    print()

    # Load configuration
    print("📖 加载配置文件...")
    plan_mapping = load_config()
    print(f"   配置文件中有 {len(plan_mapping)} 条映射")
    print()

    # Connect to database
    print("🔗 连接数据库...")
    engine = create_engine(DB_URL)
    print()

    # Get institution name mapping
    print("📋 获取机构名称映射...")
    institution_name_mapping = get_institution_name_mapping(engine)
    print(f"   找到 {len(institution_name_mapping)} 个机构代码-名称映射")
    print()

    # Show sample of institution name mapping
    print("   机构代码-名称映射示例:")
    for code, name in list(institution_name_mapping.items())[:5]:
        print(f"     {code}: {name}")
    print("   ...")
    print()

    # Run the fix
    print("🔧 开始修复数据...")
    stats = fix_institution_data(
        engine, plan_mapping, institution_name_mapping, dry_run=not args.execute
    )
    print()

    # Print statistics
    print("=" * 80)
    print("📊 修复统计:")
    print(f"   总记录数: {stats['total_records']}")
    print(f"   已更新: {stats['updated']}")
    print(f"   已跳过: {stats['skipped']}")
    if stats["errors"]:
        print(f"   错误: {len(stats['errors'])}")
        for error in stats["errors"][:5]:
            print(f"     - {error}")
        if len(stats["errors"]) > 5:
            print(f"     ... 还有 {len(stats['errors']) - 5} 个错误")
    print()

    if not args.execute:
        print("⚠️  这是试运行模式,没有实际修改数据")
        print("💡 使用 --execute 参数来执行实际修复")
        print()
    else:
        print("✅ 数据修复完成!")
        print()

    print("=" * 80)
    return 0 if not stats["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
