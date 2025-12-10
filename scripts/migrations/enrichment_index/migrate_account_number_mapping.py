#!/usr/bin/env python
"""
迁移年金账户号映射数据到 enrichment_index 表

将 legacy.enterprise.annuity_account_mapping 表中的年金账户号映射
迁移到 enterprise.enrichment_index 作为 account_number 类型的映射。

注意：
1. 只迁移不以 'GM' 开头的年金账户号（符合 Legacy 逻辑）
2. 这些年金账户号在业务上称为"集团企业客户号"
3. 在 New Pipeline 中会被去除 'C' 前缀后使用

Usage:
    # Dry run
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/migrate_account_number_mapping.py --dry-run

    # 实际迁移
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/migrate_account_number_mapping.py

    # 验证迁移结果
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/migrate_account_number_mapping.py --verify
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Generator, List, Optional

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
    """Create SQLAlchemy engine from environment variable."""
    import os
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable is required. "
            "Example: postgresql://user:pass@localhost:5432/dbname"
        )
    return create_engine(database_url)


def fetch_account_number_mapping_from_legacy(
    connection: Connection,
    batch_size: int = 1000,
) -> Generator[Dict, None, None]:
    """
    从 Legacy PostgreSQL 数据库获取年金账户号映射数据

    注意：
    1. 只获取不以 'GM' 开头的年金账户号（符合 Legacy 逻辑）
    2. 过滤掉空的年金账户号和 company_id
    3. 这些数据对应于 Legacy 中的 COMPANY_ID2_MAPPING

    Returns:
        Generator of dictionaries with account_number and company_id
    """
    query = text("""
        SELECT
            "年金账户号" as account_number,
            "company_id" as company_id
        FROM enterprise.annuity_account_mapping
        WHERE "年金账户号" IS NOT NULL
            AND "年金账户号" != ''
            AND "company_id" IS NOT NULL
            AND "company_id" != ''
            AND "年金账户号" NOT LIKE 'GM%'
        ORDER BY "年金账户号"
    """)

    result = connection.execute(query)
    for row in result:
        yield {
            "account_number": row[0].strip(),
            "company_id": row[1].strip(),
        }


def migrate_account_number_mapping(
    pg_connection: Connection,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    迁移年金账户号映射到 enrichment_index 表

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
        "migration.account_number.starting",
        batch_size=batch_size,
        dry_run=dry_run,
    )

    # 连接到Legacy PostgreSQL数据库
    try:
        import os
        import re
        # 从DATABASE_URL构建legacy数据库连接
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")

        # 使用正则表达式替换数据库名为 legacy
        legacy_db_url = re.sub(r'/([^/]+)$', '/legacy', database_url)

        from sqlalchemy import create_engine
        legacy_engine = create_engine(legacy_db_url)

        with legacy_engine.connect() as legacy_conn:
            repo = CompanyMappingRepository(pg_connection)
            records: List[EnrichmentIndexRecord] = []

            for row in fetch_account_number_mapping_from_legacy(legacy_conn, batch_size):
                stats["total_read"] += 1

                # 创建 enrichment_index 记录
                record = EnrichmentIndexRecord(
                    lookup_key=row["account_number"],
                    lookup_type=LookupType.ACCOUNT_NUMBER,
                    company_id=row["company_id"],
                    confidence=1.00,  # 所有映射都是高置信度
                    source=SourceType.LEGACY_MIGRATION,
                    source_table="enterprise.annuity_account_mapping",
                )
                records.append(record)

                # 批量插入
                if len(records) >= batch_size:
                    if not dry_run:
                        result = repo.insert_enrichment_index_batch(records)
                        stats["inserted"] += result.inserted_count
                        # Note: InsertBatchResult doesn't have updated_count field
                        # The ON CONFLICT DO UPDATE logic handles updates internally
                    else:
                        stats["inserted"] += len(records)
                    records = []

                    # 进度日志
                    if stats["total_read"] % 5000 == 0:
                        logger.info(
                            "migration.account_number.progress",
                            processed=stats["total_read"],
                            inserted=stats["inserted"],
                        )

            # 处理最后一批
            if records:
                if not dry_run:
                    result = repo.insert_enrichment_index_batch(records)
                    stats["inserted"] += result.inserted_count
                    # Note: InsertBatchResult doesn't have updated_count field
                    # The ON CONFLICT DO UPDATE logic handles updates internally
                else:
                    stats["inserted"] += len(records)

            if not dry_run:
                pg_connection.commit()

    except Exception as e:
        stats["errors"] += 1
        logger.error(
            "migration.account_number.error",
            error=str(e),
        )
        raise

    logger.info(
        "migration.account_number.completed",
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
        "account_number_total": """
            SELECT COUNT(*)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_number'
            AND source = 'legacy_migration'
        """,
        "account_number_unique": """
            SELECT COUNT(DISTINCT lookup_key)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_number'
            AND source = 'legacy_migration'
        """,
        "account_number_null_company_id": """
            SELECT COUNT(*)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_number'
            AND source = 'legacy_migration'
            AND company_id IS NULL
        """,
        "sample_records": """
            SELECT lookup_key, company_id, confidence, hit_count
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_number'
            AND source = 'legacy_migration'
            LIMIT 10
        """,
        "gm_prefix_excluded": """
            SELECT COUNT(*)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_number'
            AND source = 'legacy_migration'
            AND lookup_key LIKE 'GM%'
        """,
    }

    results = {}
    for name, query in queries.items():
        if name == "sample_records":
            rows = pg_connection.execute(text(query)).fetchall()
            results[name] = [
                {
                    "lookup_key": row[0],
                    "company_id": row[1],
                    "confidence": float(row[2]),
                    "hit_count": row[3]
                }
                for row in rows
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

## 1. 已完成的修改

✅ New Pipeline 已正确配置使用 集团企业客户号 字段：
- src/work_data_hub/domain/annuity_performance/pipeline_builder.py
  - 添加了 account_number_column="集团企业客户号"
  - 保留清洗步骤：df["集团企业客户号"].str.lstrip("C")

✅ enrichment_index 表已正确存储数据：
- lookup_type = 'account_number' (不是 'group_customer')
- 包含 10,286 条映射记录

## 2. Legacy 代码清理建议

如果需要完全移除 Legacy 依赖，可以：

### 删除或更新以下文件：
- legacy/annuity_hub/data_handler/mappings.py 中的 get_company_id2_mapping 函数
- 所有使用 COMPANY_ID2_MAPPING 的 Legacy 清理器代码

## 3. 测试验证

- 测试包含 集团企业客户号 的数据能否正确解析
- 验证去除 'C' 前缀的逻辑正常工作
- 确认 account_number 映射在 enrichment_index 中的优先级正确

## 4. 迁移状态

- COMPANY_ID1_MAPPING → plan_code ✅ 已迁移 (1,125 条)
- COMPANY_ID2_MAPPING → account_number ✅ 已迁移 (10,286 条)
- COMPANY_ID3_MAPPING → 特殊处理 (默认值 '600866980')
- COMPANY_ID4_MAPPING → customer_name ⏳ 待迁移
- COMPANY_ID5_MAPPING → account_name ⏳ 待迁移
"""

    print(cleanup_instructions)


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="迁移年金账户号映射数据到 enrichment_index",
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
            print(f"年金账户号映射总数: {results['account_number_total']:,}")
            print(f"唯一年金账户号数: {results['account_number_unique']:,}")
            print(f"空company_id记录数: {results['account_number_null_company_id']:,}")
            print(f"GM前缀记录数（应为0）: {results['gm_prefix_excluded']:,}")

            if results['sample_records']:
                print("\n样本记录:")
                for i, rec in enumerate(results['sample_records'], 1):
                    print(f"  {i}. {rec['lookup_key']} -> {rec['company_id']} "
                          f"(置信度: {rec['confidence']}, 命中次数: {rec['hit_count']})")

            # 检查数据完整性
            if results['account_number_total'] == results['account_number_unique']:
                print("\n✅ 没有重复的年金账户号")
            else:
                print("\n❌ 存在重复的年金账户号")

            if results['account_number_null_company_id'] == 0:
                print("✅ 所有记录都有company_id")
            else:
                print(f"❌ 有 {results['account_number_null_company_id']} 条记录缺少company_id")

            if results['gm_prefix_excluded'] == 0:
                print("✅ 正确排除了GM前缀的记录")
            else:
                print(f"❌ 有 {results['gm_prefix_excluded']} 条GM前缀记录被错误包含")

            return 0

        # 迁移模式
        start_time = time.perf_counter()
        stats = migrate_account_number_mapping(
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

        if stats['errors'] > 0:
            return 1

        if not args.dry_run:
            print("\n建议运行以下命令验证迁移结果:")
            print(f"  {sys.argv[0]} --verify")

    return 0


if __name__ == "__main__":
    sys.exit(main())