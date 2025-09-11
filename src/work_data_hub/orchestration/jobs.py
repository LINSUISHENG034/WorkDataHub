"""
Dagster jobs and CLI interface for WorkDataHub ETL orchestration.

This module provides the main trustee_performance_job that composes the four ops
into an end-to-end workflow, plus a CLI interface for local execution with
comprehensive argument support and structured output.
"""

import argparse
import sys
from typing import Any, Dict

import yaml
from dagster import DagsterInstance, job

from ..config.settings import get_settings
from .ops import (
    discover_files_op,
    load_op,
    process_annuity_performance_op,
    process_trustee_performance_op,
    read_and_process_trustee_files_op,
    read_excel_op,
)


@job
def trustee_performance_job():
    """
    End-to-end trustee performance processing job.

    This job orchestrates the complete ETL pipeline:
    1. Discover files matching domain patterns
    2. Read Excel data from discovered files
    3. Process data through domain service validation
    4. Load data to database or generate execution plan
    """
    # Wire ops together - Dagster handles dependency graph
    discovered_paths = discover_files_op()

    # Note: For MVP, we'll modify the ops to handle the first file selection
    # The read_excel_op will internally select the first file from the list
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_trustee_performance_op(excel_rows, discovered_paths)
    load_op(processed_data)  # No return needed


@job
def trustee_performance_multi_file_job():
    """
    End-to-end trustee performance processing job for multi-file scenarios.

    This job orchestrates the complete ETL pipeline for multiple files:
    1. Discover files matching domain patterns
    2. Read and process multiple Excel files in combined operation
    3. Load accumulated data to database or generate execution plan
    """
    # Wire ops together - Dagster handles dependency graph
    discovered_paths = discover_files_op()

    # Use combined op for multi-file processing
    processed_data = read_and_process_trustee_files_op(discovered_paths)
    load_op(processed_data)  # No return needed


@job
def annuity_performance_job():
    """
    End-to-end annuity performance processing job.

    This job orchestrates the complete ETL pipeline for Chinese "规模明细" data:
    1. Discover files matching domain patterns
    2. Read Excel data from discovered files (sheet="规模明细")
    3. Process data through annuity performance domain service with column projection
    4. Load data to database or generate execution plan
    """
    # Wire ops together - Dagster handles dependency graph
    discovered_paths = discover_files_op()

    # Read Excel data and process through annuity performance service
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_annuity_performance_op(excel_rows, discovered_paths)
    load_op(processed_data)  # No return needed


def build_run_config(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Build Dagster run_config from CLI arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        Dictionary with nested configuration for all ops
    """
    # Single source of truth calculation - execute takes precedence over plan-only
    effective_plan_only = (
        not args.execute if hasattr(args, "execute") else getattr(args, "plan_only", True)
    )

    # Load table/pk from data_sources.yml if needed
    settings = get_settings()

    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f)

        domain_config = data_sources.get("domains", {}).get(args.domain, {})
        table = domain_config.get("table", args.domain)  # Fallback to domain name
        pk = domain_config.get("pk", [])  # Empty list if not defined

    except Exception as e:
        print(f"Warning: Could not load data sources config: {e}")
        table = args.domain
        pk = []

    run_config = {
        "ops": {
            "discover_files_op": {"config": {"domain": args.domain}},
            "load_op": {
                "config": {
                    "table": table,
                    "mode": args.mode,
                    "pk": pk,
                    "plan_only": effective_plan_only,  # Use effective flag
                }
            },
        }
    }

    # Add max_files parameter and conditionally configure ops
    max_files = getattr(args, "max_files", 1)

    if max_files > 1:
        # Use new combined op for multi-file processing
        run_config["ops"]["read_and_process_trustee_files_op"] = {
            "config": {"sheet": args.sheet, "max_files": max_files}
        }
    else:
        # Use existing separate ops for single-file processing (backward compatibility)
        run_config["ops"]["read_excel_op"] = {"config": {"sheet": args.sheet}}
        # process_trustee_performance_op has no config

    return run_config


def main():
    """
    CLI entry point for local execution.

    Provides comprehensive argument parsing and execution with structured output,
    error handling, and support for both testing and production modes.
    """
    parser = argparse.ArgumentParser(
        description="Run WorkDataHub trustee performance job",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Core arguments
    parser.add_argument("--domain", default="trustee_performance", help="Domain to process")
    parser.add_argument(
        "--mode",
        choices=["delete_insert", "append"],
        default="delete_insert",
        help="Load mode for database operations",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        default=True,
        help="Generate execution plan without database connection",
    )
    parser.add_argument("--sheet", type=int, default=0, help="Excel sheet index to process")

    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute against database (default: plan-only mode for safety)",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=1,
        help="Maximum number of discovered files to process (default: 1)",
    )

    # Advanced options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging and persist run in Dagster UI",
    )
    parser.add_argument(
        "--raise-on-error",
        action="store_true",
        help="Raise exceptions immediately (useful for testing)",
    )

    args = parser.parse_args()

    # Calculate effective execution mode for consistent display and logic
    effective_plan_only = (
        not args.execute if hasattr(args, "execute") else getattr(args, "plan_only", True)
    )

    # Build run configuration from CLI arguments
    run_config = build_run_config(args)

    print(f"🚀 Starting {args.domain} job...")
    print(f"   Domain: {args.domain}")
    print(f"   Mode: {args.mode}")
    print(f"   Execute: {args.execute}")
    print(f"   Plan-only: {effective_plan_only}")
    print(f"   Sheet: {args.sheet}")
    print(f"   Max files: {args.max_files}")
    print("=" * 50)

    # Select appropriate job based on domain and max_files parameter
    max_files = getattr(args, "max_files", 1)

    if args.domain == "annuity_performance":
        # Currently only single file supported for annuity performance
        selected_job = annuity_performance_job
        if max_files > 1:
            print(f"Warning: max_files > 1 not yet supported for {args.domain}, using 1")
    elif args.domain == "trustee_performance":
        selected_job = (
            trustee_performance_multi_file_job if max_files > 1 else trustee_performance_job
        )
    else:
        raise ValueError(
            f"Unsupported domain: {args.domain}. "
            f"Supported: trustee_performance, annuity_performance"
        )

    # Execute job with appropriate settings
    try:
        # Use ephemeral instance for debug mode to avoid DAGSTER_HOME requirement
        instance = DagsterInstance.ephemeral() if args.debug else None

        result = selected_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        print(f"✅ Job completed successfully: {result.success}")

        if result.success:
            # Extract and display execution summary
            load_result = result.output_for_node("load_op")

            if effective_plan_only and "sql_plans" in load_result:
                print("\n📋 SQL Execution Plan:")
                print("-" * 30)
                for i, (op_type, sql, params) in enumerate(load_result["sql_plans"], 1):
                    print(f"{i}. {op_type}:")
                    print(f"   {sql}")
                    if params:
                        print(f"   Parameters: {len(params)} values")
                    print()

            # Display execution statistics
            print("\n📊 Execution Summary:")
            print(f"   Table: {load_result.get('table', 'N/A')}")
            print(f"   Mode: {load_result.get('mode', 'N/A')}")
            print(f"   Deleted: {load_result.get('deleted', 0)} rows")
            print(f"   Inserted: {load_result.get('inserted', 0)} rows")
            print(f"   Batches: {load_result.get('batches', 0)}")

        else:
            print("❌ Job completed with failures")
            if not args.raise_on_error:
                # Print error details when not raising
                for event in result.all_node_events:
                    if event.is_failure:
                        print(f"   Error in {event.node_name}: {event.event_specific_data}")

    except Exception as e:
        print(f"💥 Job execution failed: {e}")
        if args.debug:
            import traceback

            print("\n🐛 Full traceback:")
            traceback.print_exc()
        return 1  # Exit code for failure

    return 0  # Exit code for success


if __name__ == "__main__":
    sys.exit(main())
