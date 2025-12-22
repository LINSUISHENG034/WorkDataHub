#!/usr/bin/env python
"""
迁移年金账户名映射数据到 enrichment_index 表

将 legacy business 数据库中的规模明细表的年金账户名映射
迁移到 enterprise.enrichment_index 作为 account_name 类型的映射。

数据来源：business.规模明细 表
映射关系：年金账户名 -> company_id

Usage:
    # Dry run
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/migrate_account_name_mapping.py --dry-run

    # 实际迁移
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/migrate_account_name_mapping.py

    # 验证迁移结果
    PYTHONPATH=src uv run python scripts/migrations/enrichment_index/migrate_account_name_mapping.py --verify
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


def fetch_account_name_mapping_from_legacy(
    connection: Connection,
    batch_size: int = 1000,
) -> Generator[Dict, None, None]:
    """
    从 Legacy MySQL business 数据库获取年金账户名映射数据

    Returns:
        Generator of dictionaries with account_name and company_id
    """
    query = text("""
        SELECT DISTINCT
            "年金账户名" as account_name,
            "company_id" as company_id
        FROM business."规模明细"
        WHERE "年金账户名" IS NOT NULL
            AND "年金账户名" != ''
            AND "company_id" IS NOT NULL
            AND "company_id" != ''
        ORDER BY "年金账户名"
    """)

    result = connection.execute(query)
    for row in result:
        yield {
            "account_name": row[0].strip(),
            "company_id": row[1].strip(),
        }


def migrate_account_name_mapping(
    pg_connection: Connection,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    迁移年金账户名映射到 enrichment_index 表

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
        "migration.account_name.starting",
        batch_size=batch_size,
        dry_run=dry_run,
    )

    # 连接到Legacy PostgreSQL数据库（business schema）
    try:
        import os
        import re

        # Prefer explicit legacy DB URI; fall back to best-effort rewrite.
        legacy_db_url = os.environ.get("LEGACY_DATABASE__URI")
        if not legacy_db_url:
            database_url = os.environ.get("WDH_DATABASE__URI") or os.environ.get(
                "DATABASE_URL"
            )
            if not database_url:
                raise ValueError(
                    "LEGACY_DATABASE__URI (preferred) or WDH_DATABASE__URI/DATABASE_URL is required"
                )
            legacy_db_url = re.sub(r"/([^/]+)$", "/legacy", database_url)

        if legacy_db_url.startswith("postgres://"):
            legacy_db_url = legacy_db_url.replace("postgres://", "postgresql://", 1)

        from sqlalchemy import create_engine

        legacy_engine = create_engine(legacy_db_url)

        with legacy_engine.connect() as legacy_conn:
            repo = CompanyMappingRepository(pg_connection)
            records: List[EnrichmentIndexRecord] = []
            seen_records = set()  # 用于去重

            for row in fetch_account_name_mapping_from_legacy(legacy_conn, batch_size):
                stats["total_read"] += 1

                # 创建唯一标识符用于去重
                record_key = (row["account_name"], "account_name")

                # 跳过重复记录
                if record_key in seen_records:
                    stats["skipped"] += 1
                    continue

                seen_records.add(record_key)

                # 创建 enrichment_index 记录
                record = EnrichmentIndexRecord(
                    lookup_key=row["account_name"],
                    lookup_type=LookupType.ACCOUNT_NAME,
                    company_id=row["company_id"],
                    confidence=1.00,  # 所有映射都是高置信度
                    source=SourceType.LEGACY_MIGRATION,
                    source_table="legacy.business.规模明细",
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
                    if (stats["total_read"] + stats["skipped"]) % 5000 == 0:
                        logger.info(
                            "migration.account_name.progress",
                            processed=stats["total_read"] + stats["skipped"],
                            inserted=stats["inserted"],
                            skipped=stats["skipped"],
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
            "migration.account_name.error",
            error=str(e),
        )
        raise

    logger.info(
        "migration.account_name.completed",
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
        "account_name_total": """
            SELECT COUNT(*)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_name'
            AND source = 'legacy_migration'
        """,
        "account_name_unique": """
            SELECT COUNT(DISTINCT lookup_key)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_name'
            AND source = 'legacy_migration'
        """,
        "account_name_null_company_id": """
            SELECT COUNT(*)
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_name'
            AND source = 'legacy_migration'
            AND company_id IS NULL
        """,
        "sample_records": """
            SELECT lookup_key, company_id, confidence, hit_count
            FROM enterprise.enrichment_index
            WHERE lookup_type = 'account_name'
            AND source = 'legacy_migration'
            LIMIT 10
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
                    "hit_count": row[3],
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

✅ New Pipeline 已正确配置：
- src/work_data_hub/domain/annuity_performance/pipeline_builder.py
  - 使用 account_name_column="年金账户名"
  - 年金账户名在处理前被复制（客户名称 -> 年金账户名）

✅ enrichment_index 表已正确存储数据：
- lookup_type = 'account_name'

## 2. Legacy 代码清理建议

如果需要完全移除 Legacy 依赖，可以：

### 删除或更新以下文件：
- legacy/annuity_hub/data_handler/mappings.py 中的 get_company_id5_mapping 函数
- 所有使用 COMPANY_ID5_MAPPING 的 Legacy 清理器代码

## 3. 测试验证

- 测试包含 年金账户名 的数据能否正确解析
- 确认 account_name 映射在 enrichment_index 中的优先级正确

## 4. 迁移状态

- COMPANY_ID1_MAPPING → plan_code ✅ 已迁移 (1,125 条)
- COMPANY_ID2_MAPPING → account_number ✅ 已迁移 (10,286 条)
- COMPANY_ID3_MAPPING → 特殊处理 (默认值 '600866980')
- COMPANY_ID4_MAPPING → customer_name ✅ 已迁移 (19,840 条)
- COMPANY_ID5_MAPPING → account_name ✅ 已迁移 (待统计)

## 5. 优先级说明

在 New Pipeline 中的查找优先级：
1. YAML 配置（最高优先级）
2. enrichment_index 数据库缓存：
   - P1: plan_code
   - P2: account_name (年金账户名)
   - P3: account_number (集团企业客户号)
   - P4: customer_name (客户名称)
   - P5: plan_customer (组合)
3. EQC API 查询
4. 临时ID生成
"""

    print(cleanup_instructions)


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="迁移年金账户名映射数据到 enrichment_index",
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
            print(f"年金账户名映射总数: {results['account_name_total']:,}")
            print(f"唯一年金账户名数: {results['account_name_unique']:,}")
            print(f"空company_id记录数: {results['account_name_null_company_id']:,}")

            if results["sample_records"]:
                print("\n样本记录:")
                for i, rec in enumerate(results["sample_records"], 1):
                    print(
                        f"  {i}. {rec['lookup_key']} -> {rec['company_id']} "
                        f"(置信度: {rec['confidence']}, 命中次数: {rec['hit_count']})"
                    )

            # 检查数据完整性
            if results["account_name_total"] == results["account_name_unique"]:
                print("\n✅ 没有重复的年金账户名")
            else:
                print("\n❌ 存在重复的年金账户名")

            if results["account_name_null_company_id"] == 0:
                print("✅ 所有记录都有company_id")
            else:
                print(
                    f"❌ 有 {results['account_name_null_company_id']} 条记录缺少company_id"
                )

            return 0

        # 迁移模式
        start_time = time.perf_counter()
        stats = migrate_account_name_mapping(
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
