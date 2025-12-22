#!/usr/bin/env python
"""
迁移年金计划映射数据到 enrichment_index 表

将 mapping.年金计划 表中的单一计划记录迁移到 enterprise.enrichment_index
作为 plan_code 类型的映射（DB-P1），解除对 Legacy 数据库的依赖。

Usage:
    # Dry run
    PYTHONPATH=src uv run python scripts/migrations/migrate_plan_mapping_to_enrichment_index.py --dry-run

    # 实际迁移
    PYTHONPATH=src uv run python scripts/migrations/migrate_plan_mapping_to_enrichment_index.py

    # 验证迁移结果
    PYTHONPATH=src uv run python scripts/migrations/migrate_plan_mapping_to_enrichment_index.py --verify
"""

import argparse
import sys
import time
from typing import Dict, Generator, List

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from work_data_hub.infrastructure.enrichment.mapping_repository import (
    CompanyMappingRepository,
)
from work_data_hub.infrastructure.enrichment.types import (
    EnrichmentIndexRecord,
    LookupType,
    SourceType,
)

logger = structlog.get_logger(__name__)


def create_engine_from_env():
    """Create SQLAlchemy engine from environment variables.

    Canonical env var is `WDH_DATABASE__URI` (from `.wdh_env`). Fallback to the
    common `DATABASE_URL` for compatibility.
    """
    import os

    database_url = os.environ.get("WDH_DATABASE__URI") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "WDH_DATABASE__URI (preferred) or DATABASE_URL is required. "
            "Example: postgresql://user:pass@localhost:5432/postgres"
        )

    # Fix for SQLAlchemy compatibility (postgres:// is deprecated)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    return create_engine(database_url)


def fetch_plan_mapping_from_legacy(
    connection: Connection,
    batch_size: int = 1000,
) -> Generator[Dict, None, None]:
    """
    从 Legacy PostgreSQL 数据库获取年金计划映射数据

    Returns:
        Generator of dictionaries with plan_code and company_id
    """
    query = text("""
        SELECT "年金计划号", "company_id"
        FROM legacy.mapping."年金计划"
        WHERE "计划类型" = '单一计划'
            AND "年金计划号" IS NOT NULL
            AND "年金计划号" != ''
            AND "年金计划号" != 'AN002'
            AND "company_id" IS NOT NULL
            AND "company_id" != ''
        ORDER BY "年金计划号"
    """)

    result = connection.execute(query)
    for row in result:
        yield {
            "plan_code": row[0].strip(),
            "company_id": row[1].strip(),
        }


def migrate_plan_mapping(
    pg_connection: Connection,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    迁移年金计划映射到 enrichment_index 表

    Args:
        pg_connection: PostgreSQL连接
        batch_size: 批处理大小
        dry_run: 是否只试运行

    Returns:
        迁移统计信息
    """
    stats = {
        "total_read": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    logger.info(
        "migration.plan_mapping.starting",
        batch_size=batch_size,
        dry_run=dry_run,
    )

    # 连接到Legacy PostgreSQL数据库
    try:
        import os

        # Prefer explicit legacy DB URI; fall back to target DB (single-DB mode).
        legacy_db_url = (
            os.environ.get("LEGACY_DATABASE__URI")
            or os.environ.get("WDH_DATABASE__URI")
            or os.environ.get("DATABASE_URL")
        )
        if not legacy_db_url:
            raise ValueError(
                "LEGACY_DATABASE__URI (preferred) or WDH_DATABASE__URI/DATABASE_URL is required"
            )

        if legacy_db_url.startswith("postgres://"):
            legacy_db_url = legacy_db_url.replace("postgres://", "postgresql://", 1)

        from sqlalchemy import create_engine

        legacy_engine = create_engine(legacy_db_url)

        with legacy_engine.connect() as legacy_conn:
            repo = CompanyMappingRepository(pg_connection)
            records: List[EnrichmentIndexRecord] = []

            for row in fetch_plan_mapping_from_legacy(legacy_conn, batch_size):
                stats["total_read"] += 1

                # 创建enrichment_index记录
                record = EnrichmentIndexRecord(
                    lookup_key=row["plan_code"],
                    lookup_type=LookupType.PLAN_CODE,
                    company_id=row["company_id"],
                    confidence=1.00,  # 所有计划代码都是高置信度
                    source=SourceType.LEGACY_MIGRATION,
                    source_table="mapping.年金计划",
                )
                records.append(record)

                # 批量插入
                if len(records) >= batch_size:
                    if not dry_run:
                        result = repo.insert_enrichment_index_batch(records)
                        stats["inserted"] += result.inserted_count
                    else:
                        stats["inserted"] += len(records)
                    records = []

                    # 进度日志
                    if stats["total_read"] % 5000 == 0:
                        logger.info(
                            "migration.plan_mapping.progress",
                            processed=stats["total_read"],
                            inserted=stats["inserted"],
                        )

            # 处理最后一批
            if records:
                if not dry_run:
                    result = repo.insert_enrichment_index_batch(records)
                    stats["inserted"] += result.inserted_count
                else:
                    stats["inserted"] += len(records)

            if not dry_run:
                pg_connection.commit()

    except Exception as e:
        stats["errors"] += 1
        logger.error(
            "migration.plan_mapping.error",
            error=str(e),
        )
        raise

    logger.info(
        "migration.plan_mapping.completed",
        **stats,
    )

    return stats


def verify_migration(pg_connection: Connection) -> Dict[str, int]:
    """
    验证迁移结果

    Args:
        pg_connection: PostgreSQL连接

    Returns:
        验证统计信息
    """
    queries = {
        "plan_code_total": """
            SELECT COUNT(*)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'plan_code'
            AND source = 'legacy_migration'
        """,
        "plan_code_unique": """
            SELECT COUNT(DISTINCT lookup_key)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'plan_code'
            AND source = 'legacy_migration'
        """,
        "plan_code_null_company_id": """
            SELECT COUNT(*)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'plan_code'
            AND source = 'legacy_migration'
            AND company_id IS NULL
        """,
        "sample_records": """
            SELECT lookup_key, company_id, confidence, hit_count
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'plan_code'
            AND source = 'legacy_migration'
            LIMIT 10
        """,
    }

    results = {}
    for name, query in queries.items():
        if name == "sample_records":
            results[name] = [
                dict(row._mapping)
                for row in pg_connection.execute(text(query)).fetchall()
            ]
        else:
            results[name] = pg_connection.execute(text(query)).scalar() or 0

    return results


def cleanup_legacy_dependency():
    """
    清理Legacy依赖的代码建议

    这个函数输出需要修改或删除的代码位置
    """
    cleanup_instructions = """
# 清理Legacy依赖的建议修改：

## 1. 删除或重构 src/work_data_hub/io/loader/company_mapping_loader.py

删除以下函数：
- _extract_company_id1_mapping() (第255-269行)
- extract_legacy_mappings() 中的COMPANY_ID1_MAPPING相关部分 (第75-95行)

## 2. 更新 src/work_data_hub/config/load_company_id_overrides.py

移除从Legacy数据库加载COMPANY_ID1_MAPPING的代码，只保留YAML加载。

## 3. 测试验证

运行以下测试确保没有破坏现有功能：
- 测试计划代码的company_id解析
- 验证所有测试用例通过

## 4. 文档更新

更新 domain-migration 文档，说明年金计划映射已完全迁移到 enrichment_index。
"""

    print(cleanup_instructions)


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="迁移年金计划映射数据到 enrichment_index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只试运行，不实际插入数据",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="批处理大小 (默认: 1000)",
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help="验证迁移结果",
    )

    parser.add_argument(
        "--cleanup-hints",
        action="store_true",
        help="显示清理Legacy依赖的建议",
    )

    args = parser.parse_args()

    if args.cleanup_hints:
        cleanup_legacy_dependency()
        return 0

    # 配置日志
    import logging

    log_level = logging.INFO
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    # 连接PostgreSQL
    pg_engine = create_engine_from_env()

    with pg_engine.connect() as pg_conn:
        if args.verify:
            # 验证模式
            results = verify_migration(pg_conn)

            print("\n=== 迁移验证结果 ===")
            print(f"计划代码映射总数: {results['plan_code_total']:,}")
            print(f"唯一计划代码数: {results['plan_code_unique']:,}")
            print(f"空company_id记录数: {results['plan_code_null_company_id']:,}")

            if results["sample_records"]:
                print("\n样本记录:")
                for i, rec in enumerate(results["sample_records"], 1):
                    print(
                        f"  {i}. {rec['lookup_key']} -> {rec['company_id']} "
                        f"(置信度: {rec['confidence']}, 命中次数: {rec['hit_count']})"
                    )

            # 检查数据完整性
            if results["plan_code_total"] == results["plan_code_unique"]:
                print("\n✅ 没有重复的计划代码")
            else:
                print("\n❌ 存在重复的计划代码")

            if results["plan_code_null_company_id"] == 0:
                print("✅ 所有记录都有company_id")
            else:
                print(
                    f"❌ 有 {results['plan_code_null_company_id']} 条记录缺少company_id"
                )

            return 0

        # 迁移模式
        start_time = time.perf_counter()
        stats = migrate_plan_mapping(
            pg_conn,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )

        duration = time.perf_counter() - start_time

        print("\n=== 迁移完成 ===")
        print(f"模式: {'试运行' if args.dry_run else '实际迁移'}")
        print(f"读取记录数: {stats['total_read']:,}")
        print(f"插入记录数: {stats['inserted']:,}")
        print(f"更新记录数: {stats['updated']:,}")
        print(f"跳过记录数: {stats['skipped']:,}")
        print(f"错误数: {stats['errors']:,}")
        print(f"耗时: {duration:.2f}秒")

        if stats["errors"] > 0:
            return 1

        if not args.dry_run:
            print("\n建议运行以下命令验证迁移结果:")
            print(f"  {sys.argv[0]} --verify")

    return 0


if __name__ == "__main__":
    sys.exit(main())
