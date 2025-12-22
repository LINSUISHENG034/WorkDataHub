"""
Generic Backfill Framework - Integrated Verification Script (Enhanced)

验证目标：
1. 配置Schema兼容性 - Pydantic模型解析
2. 真正的拓扑排序 - 基于depends_on的DAG排序
3. 循环依赖检测 - 检测并报错
4. 全部4个FK覆盖 - 年金计划、组合计划、产品线、组织架构
5. 数据来源追踪字段 - _source, _needs_review, _derived_from_domain, _derived_at
6. 大数据集性能基准 - 10000行测试

Created: 2025-12-12
Enhanced: 2025-12-12 (PM Review)
"""

import logging
import time
from datetime import datetime
from graphlib import CycleError, TopologicalSorter
from typing import List, Literal

import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import Boolean, Column, DateTime, MetaData, String, Table, create_engine

# 设置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [BackfillVerify] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ==========================================
# PART 1: 配置模型 (Pydantic)
# ==========================================


class BackfillColumnMapping(BaseModel):
    source: str = Field(..., description="Fact data column")
    target: str = Field(..., description="Reference table column")
    optional: bool = Field(default=False)


class ForeignKeyConfig(BaseModel):
    name: str
    source_column: str
    target_table: str
    target_key: str
    backfill_columns: List[BackfillColumnMapping]
    mode: Literal["insert_missing", "fill_null_only"] = "insert_missing"
    priority: int = 1  # Deprecated: use depends_on for ordering
    depends_on: List[str] = Field(default_factory=list)


class DomainForeignKeysConfig(BaseModel):
    foreign_keys: List[ForeignKeyConfig] = Field(default_factory=list)


# ==========================================
# PART 2: 通用回填服务原型 (Enhanced)
# ==========================================


class GenericBackfillServicePrototype:
    def __init__(self, engine, domain: str = "unknown"):
        self.engine = engine
        self.domain = domain

    def _topological_sort(
        self, configs: List[ForeignKeyConfig]
    ) -> List[ForeignKeyConfig]:
        """
        真正的拓扑排序 - 基于 depends_on 字段
        使用 Python 3.9+ graphlib.TopologicalSorter
        """
        name_map = {c.name: c for c in configs}

        # 构建依赖图
        graph = {}
        for c in configs:
            graph[c.name] = set(c.depends_on)

        # 验证依赖存在性
        for name, deps in graph.items():
            for dep in deps:
                if dep not in name_map:
                    raise ValueError(
                        f"Foreign key '{name}' depends on unknown key '{dep}'"
                    )

        # 拓扑排序 (会自动检测循环依赖)
        sorter = TopologicalSorter(graph)
        try:
            sorted_names = list(sorter.static_order())
        except CycleError as e:
            raise ValueError(f"Circular dependency detected: {e}")

        return [name_map[name] for name in sorted_names]

    def derive_candidates(
        self, df: pd.DataFrame, config: ForeignKeyConfig
    ) -> pd.DataFrame:
        """从事实表中提取候选数据"""
        mapping = {m.source: m.target for m in config.backfill_columns}
        available_sources = [s for s in mapping.keys() if s in df.columns]

        if config.source_column not in df.columns:
            logger.warning(
                f"  [Skip] FK column '{config.source_column}' not found in data"
            )
            return pd.DataFrame()

        # 提取并去重
        candidates = (
            df[available_sources]
            .drop_duplicates()
            .dropna(subset=[config.source_column])
        )
        candidates = candidates.rename(columns=mapping)

        return candidates

    def backfill_table(
        self,
        candidates: pd.DataFrame,
        config: ForeignKeyConfig,
        conn,
        add_tracking_fields: bool = True,
    ) -> int:
        """
        执行回填操作 (带数据来源追踪)
        Returns: 插入的记录数
        """
        if candidates.empty:
            return 0

        table_name = config.target_table
        key_col = config.target_key

        # 1. 查出现有 Key
        existing = pd.read_sql(f'SELECT "{key_col}" FROM "{table_name}"', conn)
        existing_keys = set(existing[key_col])

        # 2. 过滤出新 Key
        to_insert = candidates[~candidates[key_col].isin(existing_keys)].copy()

        if to_insert.empty:
            logger.info(f"  [No-Op] All keys for {table_name} already exist")
            return 0

        # 3. 添加数据来源追踪字段
        if add_tracking_fields:
            to_insert["_source"] = "auto_derived"
            to_insert["_needs_review"] = True
            to_insert["_derived_from_domain"] = self.domain
            to_insert["_derived_at"] = datetime.now()

        # 4. 插入
        logger.info(
            f"  [Insert] Inserting {len(to_insert)} new records into {table_name}"
        )
        to_insert.to_sql(table_name, conn, if_exists="append", index=False)

        return len(to_insert)

    def run(
        self,
        df: pd.DataFrame,
        configs: List[ForeignKeyConfig],
        conn,
        add_tracking_fields: bool = True,
    ) -> dict:
        """
        执行完整的回填流程
        Returns: 统计信息
        """
        sorted_configs = self._topological_sort(configs)

        stats = {
            "total_inserted": 0,
            "tables_processed": [],
            "processing_order": [c.name for c in sorted_configs],
        }

        for config in sorted_configs:
            logger.info(f"Processing FK config: {config.name} -> {config.target_table}")
            candidates = self.derive_candidates(df, config)
            inserted = self.backfill_table(
                candidates, config, conn, add_tracking_fields
            )
            stats["total_inserted"] += inserted
            stats["tables_processed"].append(
                {"table": config.target_table, "inserted": inserted}
            )

        return stats


# ==========================================
# PART 3: 测试用例
# ==========================================


class VerificationResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.details = {}

    def __str__(self):
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        return f"{status} - {self.name}: {self.message}"


def test_config_schema_validation() -> VerificationResult:
    """测试1: 配置Schema兼容性"""
    result = VerificationResult("Configuration Schema Validation")

    # 完整的4个FK配置
    full_fk_config = [
        {
            "name": "fk_plan",
            "source_column": "计划代码",
            "target_table": "年金计划",
            "target_key": "年金计划号",
            "backfill_columns": [
                {"source": "计划代码", "target": "年金计划号"},
                {"source": "计划名称", "target": "计划名称", "optional": True},
            ],
            "priority": 1,
        },
        {
            "name": "fk_portfolio",
            "source_column": "组合代码",
            "target_table": "组合计划",
            "target_key": "组合代码",
            "backfill_columns": [
                {"source": "组合代码", "target": "组合代码"},
                {"source": "计划代码", "target": "年金计划号"},
            ],
            "priority": 2,
            "depends_on": ["fk_plan"],
        },
        {
            "name": "fk_product_line",
            "source_column": "产品线代码",
            "target_table": "产品线",
            "target_key": "产品线代码",
            "backfill_columns": [
                {"source": "产品线代码", "target": "产品线代码"},
                {"source": "产品线名称", "target": "产品线名称", "optional": True},
            ],
            "priority": 1,
        },
        {
            "name": "fk_organization",
            "source_column": "组织代码",
            "target_table": "组织架构",
            "target_key": "组织代码",
            "backfill_columns": [
                {"source": "组织代码", "target": "组织代码"},
                {"source": "组织名称", "target": "组织名称", "optional": True},
            ],
            "priority": 1,
        },
    ]

    try:
        validated = [ForeignKeyConfig(**cfg) for cfg in full_fk_config]
        result.passed = True
        result.message = f"All {len(validated)} FK configs parsed successfully"
        result.details = {"config_count": len(validated)}
    except ValidationError as e:
        result.message = f"Validation failed: {e}"

    return result


def test_topological_sort() -> VerificationResult:
    """测试2: 真正的拓扑排序"""
    result = VerificationResult("Topological Sort (depends_on)")

    # 创建有依赖关系的配置
    configs = [
        ForeignKeyConfig(
            name="fk_child",
            source_column="child_id",
            target_table="child",
            target_key="id",
            backfill_columns=[BackfillColumnMapping(source="child_id", target="id")],
            depends_on=["fk_parent"],
        ),
        ForeignKeyConfig(
            name="fk_parent",
            source_column="parent_id",
            target_table="parent",
            target_key="id",
            backfill_columns=[BackfillColumnMapping(source="parent_id", target="id")],
            depends_on=["fk_grandparent"],
        ),
        ForeignKeyConfig(
            name="fk_grandparent",
            source_column="gp_id",
            target_table="grandparent",
            target_key="id",
            backfill_columns=[BackfillColumnMapping(source="gp_id", target="id")],
        ),
    ]

    engine = create_engine("sqlite:///:memory:")
    service = GenericBackfillServicePrototype(engine)

    try:
        sorted_configs = service._topological_sort(configs)
        sorted_names = [c.name for c in sorted_configs]

        # 验证顺序: grandparent -> parent -> child
        expected_order = ["fk_grandparent", "fk_parent", "fk_child"]

        if sorted_names == expected_order:
            result.passed = True
            result.message = f"Correct order: {' -> '.join(sorted_names)}"
        else:
            result.message = f"Wrong order: {sorted_names}, expected: {expected_order}"

        result.details = {"sorted_order": sorted_names}
    except Exception as e:
        result.message = f"Sort failed: {e}"

    return result


def test_circular_dependency_detection() -> VerificationResult:
    """测试3: 循环依赖检测"""
    result = VerificationResult("Circular Dependency Detection")

    # 创建循环依赖配置
    configs = [
        ForeignKeyConfig(
            name="fk_a",
            source_column="a_id",
            target_table="table_a",
            target_key="id",
            backfill_columns=[BackfillColumnMapping(source="a_id", target="id")],
            depends_on=["fk_b"],
        ),
        ForeignKeyConfig(
            name="fk_b",
            source_column="b_id",
            target_table="table_b",
            target_key="id",
            backfill_columns=[BackfillColumnMapping(source="b_id", target="id")],
            depends_on=["fk_a"],  # 循环!
        ),
    ]

    engine = create_engine("sqlite:///:memory:")
    service = GenericBackfillServicePrototype(engine)

    try:
        service._topological_sort(configs)
        result.message = "Failed to detect circular dependency!"
    except ValueError as e:
        if "Circular dependency" in str(e) or "cycle" in str(e).lower():
            result.passed = True
            result.message = "Correctly detected and raised error"
            result.details = {"error": str(e)}
        else:
            result.message = f"Wrong error type: {e}"
    except Exception as e:
        result.message = f"Unexpected error: {e}"

    return result


def test_all_four_fks() -> VerificationResult:
    """测试4: 全部4个FK覆盖"""
    result = VerificationResult("All 4 FK Coverage")

    # 创建内存数据库
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()

    # 创建4个引用表 (带追踪字段)
    for table_name, key_col in [
        ("年金计划", "年金计划号"),
        ("组合计划", "组合代码"),
        ("产品线", "产品线代码"),
        ("组织架构", "组织代码"),
    ]:
        Table(
            table_name,
            metadata,
            Column(key_col, String, primary_key=True),
            Column("名称", String),
            Column("_source", String),
            Column("_needs_review", Boolean),
            Column("_derived_from_domain", String),
            Column("_derived_at", DateTime),
        )

    metadata.create_all(engine)

    # 4个FK配置
    configs = [
        ForeignKeyConfig(
            name="fk_plan",
            source_column="计划代码",
            target_table="年金计划",
            target_key="年金计划号",
            backfill_columns=[
                BackfillColumnMapping(source="计划代码", target="年金计划号"),
                BackfillColumnMapping(source="计划名称", target="名称", optional=True),
            ],
        ),
        ForeignKeyConfig(
            name="fk_portfolio",
            source_column="组合代码",
            target_table="组合计划",
            target_key="组合代码",
            backfill_columns=[
                BackfillColumnMapping(source="组合代码", target="组合代码"),
                BackfillColumnMapping(source="组合名称", target="名称", optional=True),
            ],
            depends_on=["fk_plan"],
        ),
        ForeignKeyConfig(
            name="fk_product_line",
            source_column="产品线代码",
            target_table="产品线",
            target_key="产品线代码",
            backfill_columns=[
                BackfillColumnMapping(source="产品线代码", target="产品线代码"),
                BackfillColumnMapping(
                    source="产品线名称", target="名称", optional=True
                ),
            ],
        ),
        ForeignKeyConfig(
            name="fk_organization",
            source_column="组织代码",
            target_table="组织架构",
            target_key="组织代码",
            backfill_columns=[
                BackfillColumnMapping(source="组织代码", target="组织代码"),
                BackfillColumnMapping(source="组织名称", target="名称", optional=True),
            ],
        ),
    ]

    # 测试数据 (包含所有4个FK的值，模拟真实事实表)
    fact_data = pd.DataFrame(
        {
            "计划代码": ["PLAN_001", "PLAN_002", "PLAN_001"],
            "计划名称": ["Plan A", "Plan B", "Plan A"],
            "组合代码": ["PORT_001", "PORT_002", "PORT_001"],
            "组合名称": ["Portfolio A", "Portfolio B", "Portfolio A"],
            "产品线代码": ["PL_001", "PL_001", "PL_002"],
            "产品线名称": ["Product Line A", "Product Line A", "Product Line B"],
            "组织代码": ["ORG_001", "ORG_002", "ORG_003"],
            "组织名称": ["Org A", "Org B", "Org C"],
        }
    )

    service = GenericBackfillServicePrototype(engine, domain="annuity_performance")

    with engine.connect() as conn:
        try:
            stats = service.run(fact_data, configs, conn)

            # 验证每个表都有数据
            tables_with_data = 0
            for table_name in ["年金计划", "组合计划", "产品线", "组织架构"]:
                count = pd.read_sql(
                    f'SELECT COUNT(*) as cnt FROM "{table_name}"', conn
                ).iloc[0]["cnt"]
                if count > 0:
                    tables_with_data += 1

            if tables_with_data == 4:
                result.passed = True
                result.message = (
                    f"All 4 tables populated, {stats['total_inserted']} total records"
                )
                result.details = stats
            else:
                result.message = f"Only {tables_with_data}/4 tables have data"

        except Exception as e:
            result.message = f"Execution failed: {e}"
            import traceback

            traceback.print_exc()

    return result


def test_tracking_fields() -> VerificationResult:
    """测试5: 数据来源追踪字段"""
    result = VerificationResult("Data Source Tracking Fields")

    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()

    Table(
        "test_table",
        metadata,
        Column("id", String, primary_key=True),
        Column("_source", String),
        Column("_needs_review", Boolean),
        Column("_derived_from_domain", String),
        Column("_derived_at", DateTime),
    )
    metadata.create_all(engine)

    config = ForeignKeyConfig(
        name="fk_test",
        source_column="test_id",
        target_table="test_table",
        target_key="id",
        backfill_columns=[BackfillColumnMapping(source="test_id", target="id")],
    )

    fact_data = pd.DataFrame({"test_id": ["TEST_001", "TEST_002"]})

    service = GenericBackfillServicePrototype(engine, domain="test_domain")

    with engine.connect() as conn:
        try:
            service.run(fact_data, [config], conn, add_tracking_fields=True)

            # 验证追踪字段
            records = pd.read_sql('SELECT * FROM "test_table"', conn)

            checks = {
                "_source": all(records["_source"] == "auto_derived"),
                "_needs_review": all(records["_needs_review"] == True),
                "_derived_from_domain": all(
                    records["_derived_from_domain"] == "test_domain"
                ),
                "_derived_at": all(records["_derived_at"].notna()),
            }

            if all(checks.values()):
                result.passed = True
                result.message = "All tracking fields correctly populated"
                result.details = {"record_count": len(records), "checks": checks}
            else:
                failed = [k for k, v in checks.items() if not v]
                result.message = f"Failed checks: {failed}"
                result.details = {"checks": checks}

        except Exception as e:
            result.message = f"Execution failed: {e}"
            import traceback

            traceback.print_exc()

    return result


def test_large_dataset_performance() -> VerificationResult:
    """测试6: 大数据集性能基准"""
    result = VerificationResult("Large Dataset Performance (10K rows)")

    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()

    Table(
        "perf_table",
        metadata,
        Column("id", String, primary_key=True),
        Column("_source", String),
        Column("_needs_review", Boolean),
        Column("_derived_from_domain", String),
        Column("_derived_at", DateTime),
    )
    metadata.create_all(engine)

    config = ForeignKeyConfig(
        name="fk_perf",
        source_column="perf_id",
        target_table="perf_table",
        target_key="id",
        backfill_columns=[BackfillColumnMapping(source="perf_id", target="id")],
    )

    # 生成10000行测试数据
    row_count = 10000
    fact_data = pd.DataFrame({"perf_id": [f"PERF_{i:06d}" for i in range(row_count)]})

    service = GenericBackfillServicePrototype(engine, domain="perf_test")

    with engine.connect() as conn:
        try:
            start_time = time.time()
            stats = service.run(fact_data, [config], conn, add_tracking_fields=True)
            elapsed = time.time() - start_time

            # 性能基准: 10000行应在5秒内完成
            threshold_seconds = 5.0

            if elapsed < threshold_seconds and stats["total_inserted"] == row_count:
                result.passed = True
                result.message = f"{row_count} rows in {elapsed:.2f}s ({row_count / elapsed:.0f} rows/sec)"
            else:
                result.message = (
                    f"Too slow: {elapsed:.2f}s (threshold: {threshold_seconds}s)"
                )

            result.details = {
                "row_count": row_count,
                "elapsed_seconds": round(elapsed, 3),
                "rows_per_second": round(row_count / elapsed, 1),
                "inserted": stats["total_inserted"],
            }

        except Exception as e:
            result.message = f"Execution failed: {e}"
            import traceback

            traceback.print_exc()

    return result


# ==========================================
# PART 4: 主验证流程
# ==========================================


def verify_integration():
    logger.info("=" * 60)
    logger.info("Generic Backfill Framework - Enhanced Verification")
    logger.info("=" * 60)

    # 运行所有测试
    tests = [
        test_config_schema_validation,
        test_topological_sort,
        test_circular_dependency_detection,
        test_all_four_fks,
        test_tracking_fields,
        test_large_dataset_performance,
    ]

    results = []
    for test_func in tests:
        logger.info(f"\n>>> Running: {test_func.__doc__.strip()}")
        result = test_func()
        results.append(result)
        logger.info(str(result))
        if result.details:
            logger.info(f"    Details: {result.details}")

    # 汇总
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for r in results:
        status = "✅" if r.passed else "❌"
        logger.info(f"  {status} {r.name}")

    logger.info("-" * 60)
    logger.info(f"  Total: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 ALL VERIFICATIONS PASSED - Technical feasibility confirmed!")
        return True
    else:
        logger.info(f"\n⚠️  {total - passed} test(s) failed - Review required")
        return False


if __name__ == "__main__":
    success = verify_integration()
    exit(0 if success else 1)
