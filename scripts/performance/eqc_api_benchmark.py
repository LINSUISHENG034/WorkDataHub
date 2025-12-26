"""
EQC API Performance Benchmark Script

Measures baseline performance metrics for EQC API calls including:
- API latency per call (network + processing)
- Cache hit rate from enrichment_index
- Network vs processing time breakdown

Usage:
    PYTHONPATH=src uv run --env-file .wdh_env scripts/performance/eqc_api_benchmark.py

Story: 7.1-14 - EQC API Performance Optimization
Acceptance Criteria: AC-1 - Performance Baseline Established
"""

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

import pandas as pd
import psycopg2

from work_data_hub.config import settings
from work_data_hub.io.connectors.eqc import EQCClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@contextmanager
def get_postgres_connection():
    """
    Context manager for PostgreSQL connection.

    Yields:
        psycopg2 connection object
    """
    db_settings = settings.database
    conn = psycopg2.connect(
        host=db_settings.host,
        port=db_settings.port,
        user=db_settings.user,
        password=db_settings.password,
        database=db_settings.db,
        connect_timeout=30,
    )
    try:
        yield conn
    finally:
        conn.close()


class PerformanceMetrics(NamedTuple):
    """Container for benchmark metrics."""

    total_companies: int
    unique_companies: int
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    total_time_seconds: float
    avg_time_per_company: float
    api_call_count: int
    avg_api_latency: float


def get_test_company_names() -> list[str]:
    """
    Get 1000 unique company names from annuity_performance domain.

    Returns:
        List of unique company names (max 1000)
    """
    logger.info("Loading test data from annuity_performance domain...")

    query = """
        SELECT DISTINCT 客户名称
        FROM business.规模明细
        WHERE 客户名称 IS NOT NULL
        LIMIT 1000
    """

    with get_postgres_connection() as conn:
        df = pd.read_sql_query(query, conn)

    company_names = df["客户名称"].dropna().unique().tolist()
    logger.info(f"Loaded {len(company_names)} unique company names")

    return company_names


def measure_cache_performance(
    company_names: list[str],
) -> dict[str, any]:
    """
    Measure current cache hit rate from enrichment_index.

    Args:
        company_names: List of company names to lookup

    Returns:
        Dictionary with cache metrics
    """
    logger.info("Measuring cache performance...")

    # Batch query enrichment_index (table is in enterprise schema)
    query = """
        SELECT
            lookup_key,
            COUNT(*) as hit_count
        FROM enterprise.enrichment_index
        WHERE lookup_type = 'customer_name'
          AND lookup_key = ANY(%(company_names)s)
        GROUP BY lookup_key
    """

    with get_postgres_connection() as conn:
        df = pd.read_sql_query(query, conn, params={"company_names": company_names})
    cached_keys = set(df["lookup_key"].tolist())

    cache_hits = len(cached_keys)
    cache_misses = len(company_names) - cache_hits
    cache_hit_rate = cache_hits / len(company_names) if company_names else 0

    logger.info(
        f"Cache Performance: "
        f"{cache_hits} hits, {cache_misses} misses, "
        f"{cache_hit_rate:.1%} hit rate"
    )

    return {
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": cache_hit_rate,
        "cached_keys": cached_keys,
    }


def measure_api_latency(
    company_names: list[str],
    sample_size: int = 10,
) -> dict[str, any]:
    """
    Measure EQC API latency for a sample of cache misses.

    Args:
        company_names: List of company names to test (should be cache misses)
        sample_size: Number of companies to test (default: 10)

    Returns:
        Dictionary with API latency metrics
    """
    logger.info(f"Measuring API latency for {sample_size} sample companies...")

    # Limit sample size to avoid excessive API calls
    sample_names = company_names[:sample_size]

    eqc_client = EQCClient()

    latencies = []
    api_call_counts = []

    for name in sample_names:
        start = time.time()

        try:
            # Make actual EQC API call (3 sequential calls internally)
            result = eqc_client.get_business_info(name)
            call_count = 3 if result else 0

            elapsed = time.time() - start
            latencies.append(elapsed)
            api_call_counts.append(call_count)

            logger.info(f"  {name}: {elapsed:.2f}s ({call_count} API calls)")

        except Exception as e:
            logger.warning(f"  {name}: Failed - {e}")
            latencies.append(0)
            api_call_counts.append(0)

    # Filter out failed calls
    valid_latencies = [t for t in latencies if t > 0]
    avg_latency = sum(valid_latencies) / len(valid_latencies) if valid_latencies else 0
    total_api_calls = sum(api_call_counts)

    logger.info(
        f"API Latency: {avg_latency:.2f}s average ({len(valid_latencies)}/{sample_size} successful)"
    )

    return {
        "avg_latency": avg_latency,
        "total_api_calls": total_api_calls,
        "successful_calls": len(valid_latencies),
        "latencies": latencies,
    }


def run_benchmark() -> PerformanceMetrics:
    """
    Run complete performance benchmark.

    Returns:
        PerformanceMetrics with all measurements
    """
    logger.info("=" * 60)
    logger.info("EQC API Performance Benchmark")
    logger.info("=" * 60)

    # Step 1: Load test data
    company_names = get_test_company_names()
    unique_count = len(company_names)

    if unique_count == 0:
        logger.error("No company names found in test data")
        raise ValueError("Cannot run benchmark without test data")

    # Step 2: Measure cache performance
    cache_metrics = measure_cache_performance(company_names)

    # Step 3: Measure API latency (sample only)
    # Use cache misses for API latency measurement
    cache_misses = [
        name for name in company_names if name not in cache_metrics["cached_keys"]
    ]

    api_metrics = {}
    if cache_misses:
        api_metrics = measure_api_latency(cache_misses, sample_size=10)
    else:
        logger.warning("All companies cached - cannot measure API latency")
        api_metrics = {"avg_latency": 0, "total_api_calls": 0}

    # Calculate estimated total time for full dataset
    cache_time = cache_metrics["cache_hits"] * 0.01  # ~10ms per cache lookup
    api_time = cache_metrics["cache_misses"] * api_metrics["avg_latency"]
    estimated_total = cache_time + api_time

    # Compile metrics
    metrics = PerformanceMetrics(
        total_companies=unique_count,
        unique_companies=unique_count,
        cache_hits=cache_metrics["cache_hits"],
        cache_misses=cache_metrics["cache_misses"],
        cache_hit_rate=cache_metrics["cache_hit_rate"],
        total_time_seconds=estimated_total,
        avg_time_per_company=estimated_total / unique_count if unique_count else 0,
        api_call_count=api_metrics["total_api_calls"],
        avg_api_latency=api_metrics["avg_latency"],
    )

    # Print summary
    logger.info("=" * 60)
    logger.info("BENCHMARK SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Test Dataset Size: {metrics.unique_companies} unique companies")
    logger.info(f"Cache Hit Rate: {metrics.cache_hit_rate:.1%}")
    logger.info(f"  - Cache Hits: {metrics.cache_hits}")
    logger.info(f"  - Cache Misses: {metrics.cache_misses}")
    logger.info(f"Average API Latency: {metrics.avg_api_latency:.2f}s per company")
    logger.info(f"Estimated Total Time: {metrics.total_time_seconds:.2f}s")
    logger.info(f"Average Time per Company: {metrics.avg_time_per_company:.2f}s")
    logger.info("=" * 60)

    return metrics


def main():
    """Main entry point."""
    try:
        metrics = run_benchmark()

        # Save results to file for documentation
        output_path = Path("scripts/performance/eqc_api_baseline.txt")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write("EQC API Performance Baseline\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Test Dataset: {metrics.unique_companies} unique companies\n\n")
            f.write("Cache Performance:\n")
            f.write(f"  - Hit Rate: {metrics.cache_hit_rate:.1%}\n")
            f.write(f"  - Hits: {metrics.cache_hits}\n")
            f.write(f"  - Misses: {metrics.cache_misses}\n\n")
            f.write("API Latency:\n")
            f.write(f"  - Average: {metrics.avg_api_latency:.2f}s per company\n")
            f.write(f"  - API Calls: {metrics.api_call_count}\n\n")
            f.write("Estimated Processing Time:\n")
            f.write(f"  - Total: {metrics.total_time_seconds:.2f}s\n")
            f.write(f"  - Per Company: {metrics.avg_time_per_company:.2f}s\n")

        logger.info(f"\nBaseline saved to: {output_path}")
        logger.info("\n✅ Benchmark completed successfully")

    except Exception as e:
        logger.error(f"❌ Benchmark failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
