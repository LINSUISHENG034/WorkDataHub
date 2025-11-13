"""Dagster jobs wiring I/O services into domain pipelines (Story 1.6).

Jobs compose the Story 1.5 pipeline steps plus I/O adapters via dependency
injection so that `work_data_hub.domain` never imports orchestration code.
This module also exposes a CLI for executing the orchestrated graph while
respecting the Clean Architecture flow: domain ← io ← orchestration.
"""

import argparse
import re
import sys
from typing import Any, Dict, List

import yaml
from dagster import DagsterInstance, job

from src.work_data_hub.config.settings import get_settings
from src.work_data_hub.io.loader.company_mapping_loader import (
    extract_legacy_mappings,
    generate_load_plan,
    load_company_mappings,
)

from .ops import (
    backfill_refs_op,
    derive_plan_refs_op,
    derive_portfolio_refs_op,
    discover_files_op,
    gate_after_backfill,
    load_op,
    process_annuity_performance_op,
    process_company_lookup_queue_op,
    process_sample_trustee_performance_op,
    read_and_process_sample_trustee_files_op,
    read_excel_op,
)


@job
def sample_trustee_performance_job():
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
    processed_data = process_sample_trustee_performance_op(excel_rows, discovered_paths)
    load_op(processed_data)  # No return needed


@job
def sample_trustee_performance_multi_file_job():
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
    processed_data = read_and_process_sample_trustee_files_op(discovered_paths)
    load_op(processed_data)  # No return needed


# Backward compatibility aliases for legacy tests/integrations
trustee_performance_job = sample_trustee_performance_job
trustee_performance_multi_file_job = sample_trustee_performance_multi_file_job


@job
def annuity_performance_job():
    """
    End-to-end annuity performance processing job with optional reference backfill.

    This job orchestrates the complete ETL pipeline for Chinese "规模明细" data:
    1. Discover files matching domain patterns
    2. Read Excel data from discovered files (sheet="规模明细")
    3. Process data through annuity performance domain service with column projection
    4. Derive reference candidates (plans and portfolios) from processed data
    5. Backfill missing references to database (if enabled)
    6. Load fact data to database or generate execution plan
    """
    # Wire ops together - Dagster handles dependency graph
    discovered_paths = discover_files_op()

    # Read Excel data and process through annuity performance service
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_annuity_performance_op(excel_rows, discovered_paths)

    # Derive reference candidates from processed data
    plan_candidates = derive_plan_refs_op(processed_data)
    portfolio_candidates = derive_portfolio_refs_op(processed_data)

    # Backfill references and gate before loading facts (FK‑safe ordering)
    backfill_result = backfill_refs_op(plan_candidates, portfolio_candidates)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)


@job
def import_company_mappings_job():
    """
    Company ID mapping migration job.

    This job handles the migration of legacy 5-layer COMPANY_ID mapping
    structure to the unified PostgreSQL enterprise.company_mapping table.
    Supports both plan-only (preview) and execute modes.

    Operations:
    1. Extract mappings from all 5 legacy sources (MySQL + hardcoded)
    2. Validate mapping consistency and detect conflicts
    3. Load to PostgreSQL with delete_insert (upsert) mode
    4. Generate execution statistics and validation reports

    This is a database-only job - no file discovery or Excel processing.
    """
    # This job is handled directly in main() since it doesn't use the standard
    # discover -> read -> process -> load pattern. It goes directly from
    # legacy extraction to database loading.
    pass


@job
def process_company_lookup_queue_job():
    """
    Company lookup queue processing job.

    This job processes pending company lookup requests from the queue using EQC API.
    Designed for scheduled/async execution to handle company name resolution
    that was queued during enrichment operations.

    Operations:
    1. Dequeue pending lookup requests in configurable batches
    2. Perform EQC lookups for each company name
    3. Cache successful results for future use
    4. Update request status (done/failed) appropriately
    5. Generate processing statistics and queue status reports

    This is a database-only job with no file discovery or Excel processing.
    """
    # Single op job - process the lookup queue
    process_company_lookup_queue_op()


def _parse_pk_override(pk_arg: Any) -> List[str]:
    """Parse CLI --pk override into a clean list of column names.

    Accepts comma/semicolon separated string or list-like; ignores empty items.
    """
    if pk_arg is None:
        return []
    # If already a list, normalize and return
    if isinstance(pk_arg, list):
        return [str(x).strip() for x in pk_arg if str(x).strip()]
    # Otherwise split by comma/semicolon
    text = str(pk_arg)
    parts = re.split(r"[,;]", text)
    return [p.strip() for p in parts if p.strip()]


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
        not args.execute
        if hasattr(args, "execute")
        else getattr(args, "plan_only", True)
    )

    # Load table/pk from data_sources.yml if needed
    settings = get_settings()

    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f)

        domain_config = data_sources.get("domains", {}).get(args.domain, {})
        table = domain_config.get("table", args.domain)  # Fallback to domain name
        pk = domain_config.get("pk", [])  # Empty list if not defined

        # Runtime override via --pk (only affects delete_insert mode)
        pk_override = _parse_pk_override(getattr(args, "pk", None))
        if pk_override:
            pk = pk_override

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
                    "skip": getattr(args, "skip_facts", False),  # NEW: skip flag
                }
            },
        }
    }

    # Add max_files parameter and conditionally configure ops
    max_files = getattr(args, "max_files", 1)

    if max_files > 1:
        # Use new combined op for multi-file processing
        run_config["ops"]["read_and_process_sample_trustee_files_op"] = {
            "config": {"sheet": args.sheet, "max_files": max_files}
        }
    else:
        # Use existing separate ops for single-file processing (backward compatibility)
        # Coerce sheet: if it's a digit-like string, pass as int; else pass as name
        sheet_cfg: Any
        try:
            sheet_cfg = int(args.sheet)
        except Exception:
            sheet_cfg = args.sheet
        run_config["ops"]["read_excel_op"] = {"config": {"sheet": sheet_cfg}}
        # process_trustee_performance_op has no config

    # Add backfill configuration (always include, but empty targets when disabled)
    backfill_refs = getattr(args, "backfill_refs", None)
    backfill_mode = getattr(args, "backfill_mode", "insert_missing")

    if backfill_refs:
        targets = [backfill_refs] if backfill_refs != "all" else ["all"]
    else:
        targets = []  # Empty targets = no backfill

    run_config["ops"]["backfill_refs_op"] = {
        "config": {
            "targets": targets,
            "mode": backfill_mode,
            "plan_only": effective_plan_only,
            "chunk_size": 1000,
        }
    }

    # Add enrichment configuration for annuity_performance domain
    if args.domain == "annuity_performance":
        run_config["ops"]["process_annuity_performance_op"] = {
            "config": {
                "enrichment_enabled": getattr(args, "enrichment_enabled", False),
                "enrichment_sync_budget": getattr(args, "enrichment_sync_budget", 0),
                "export_unknown_names": getattr(args, "export_unknown_names", True),
                "plan_only": effective_plan_only,  # Use effective flag
                "use_pipeline": getattr(
                    args, "use_pipeline", None
                ),  # CLI override for pipeline framework
            }
        }

    return run_config


def _execute_company_mapping_job(args: argparse.Namespace):
    """
    Execute company mapping migration job with direct database operations.

    This function handles the company mapping migration outside of the standard
    Dagster job framework since it doesn't follow the discover->read->process->load
    pattern. Instead it goes directly from legacy extraction to database loading.
    """
    import psycopg2

    from src.work_data_hub.domain.company_enrichment.service import (
        validate_mapping_consistency,
    )
    from src.work_data_hub.io.loader.company_mapping_loader import (
        CompanyMappingLoaderError,
    )

    effective_plan_only = not args.execute if hasattr(args, "execute") else True

    print("🚀 Starting company mapping migration...")
    print(f"   Domain: {args.domain}")
    print(f"   Mode: {args.mode}")
    print(f"   Execute: {args.execute}")
    print(f"   Plan-only: {effective_plan_only}")
    print("=" * 50)

    try:
        # Step 1: Extract legacy mappings
        print("📥 Extracting legacy mappings from 5 sources...")
        try:
            mappings = extract_legacy_mappings()
        except CompanyMappingLoaderError as e:
            print(f"❌ Legacy mapping extraction failed: {e}")
            return

        if not mappings:
            print("⚠️ No mappings extracted - migration aborted")
            return

        print(f"✅ Successfully extracted {len(mappings)} total mappings")

        # Step 2: Validate mapping consistency
        print("🔍 Validating mapping consistency...")
        warnings = validate_mapping_consistency(mappings)

        if warnings:
            print(f"⚠️ Found {len(warnings)} validation warnings:")
            for i, warning in enumerate(warnings[:5], 1):  # Show first 5
                print(f"   {i}. {warning}")
            if len(warnings) > 5:
                print(f"   ... and {len(warnings) - 5} more warnings")

        # Step 3: Generate execution plan
        print("📋 Generating execution plan...")
        plan = generate_load_plan(mappings, "enterprise", "company_mapping")

        print("MIGRATION PLAN:")
        print(f"  Target: {plan['table']}")
        print(f"  Total mappings: {plan['total_mappings']:,}")
        print("  Breakdown by type:")

        for match_type, count in plan["mapping_breakdown"].items():
            priority = {
                "plan": 1,
                "account": 2,
                "hardcode": 3,
                "name": 4,
                "account_name": 5,
            }.get(match_type, "?")
            print(f"    {match_type} (priority {priority}): {count:,} mappings")

        if effective_plan_only:
            print("\n" + "=" * 50)
            print("✅ Plan generation complete - no database changes made")
            return

        # Step 4: Execute migration
        print("💾 Executing database migration...")

        settings = get_settings()
        conn_string = settings.get_database_connection_string()

        try:
            with psycopg2.connect(conn_string) as conn:
                print(
                    "🔌 Connected to PostgreSQL: "
                    f"{settings.database_host}:{settings.database_port}/"
                    f"{settings.database_db}"
                )

                # Verify target table exists
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = %s
                    );
                """,
                    ("enterprise", "company_mapping"),
                )

                table_exists = cursor.fetchone()[0]
                cursor.close()

                if not table_exists:
                    print("❌ Target table enterprise.company_mapping does not exist")
                    print(
                        "Please run the DDL script first: "
                        "scripts/create_table/ddl/company_mapping.sql"
                    )
                    return

                # Execute the load
                stats = load_company_mappings(
                    mappings=mappings,
                    conn=conn,
                    schema="enterprise",
                    table="company_mapping",
                    mode="delete_insert",
                    chunk_size=1000,
                )

                print("✅ MIGRATION COMPLETED SUCCESSFULLY:")
                print(f"   Deleted: {stats['deleted']} existing records")
                print(f"   Inserted: {stats['inserted']} new records")
                print(f"   Batches processed: {stats['batches']}")

        except psycopg2.Error as e:
            print(f"❌ PostgreSQL connection/operation failed: {e}")
            return

        print("=" * 50)
        print("🎉 MIGRATION SUCCESS - All legacy mappings migrated")
        print("=" * 50)

    except KeyboardInterrupt:
        print("⚠️ Migration interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected migration failure: {e}")
        if args.raise_on_error:
            raise


def _execute_queue_processing_job(args: argparse.Namespace):
    """
    Execute company lookup queue processing job with direct queue operations.

    This function handles queue processing outside of the standard
    Dagster job framework, executing the process_company_lookup_queue_job
    with appropriate configuration and error handling.
    """
    effective_plan_only = not args.execute if hasattr(args, "execute") else True
    batch_size = getattr(args, "batch_size", 50)

    print("🚀 Starting company lookup queue processing...")
    print(f"   Batch size: {batch_size}")
    print(f"   Execute: {args.execute}")
    print(f"   Plan-only: {effective_plan_only}")
    print("=" * 50)

    try:
        # Build run configuration for queue processing
        run_config = {
            "ops": {
                "process_company_lookup_queue_op": {
                    "config": {
                        "batch_size": batch_size,
                        "plan_only": effective_plan_only,
                    }
                }
            }
        }

        # Execute queue processing job
        instance = DagsterInstance.ephemeral() if args.debug else None

        result = process_company_lookup_queue_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        print(f"✅ Queue processing completed successfully: {result.success}")

        if result.success:
            # Extract queue processing results
            output_data = result.output_for_node("process_company_lookup_queue_op")

            if output_data:
                processed_count = output_data.get("processed_count", 0)
                queue_status = output_data.get("queue_status", {})

                print("QUEUE PROCESSING RESULTS:")
                print(f"  Processed requests: {processed_count}")
                print(f"  Remaining pending: {queue_status.get('pending', 0)}")
                print(f"  Failed requests: {queue_status.get('failed', 0)}")
                print(f"  Completed requests: {queue_status.get('done', 0)}")

        print("=" * 50)
        if effective_plan_only:
            print("✅ Queue processing plan complete - no database changes made")
        else:
            print("🎉 QUEUE PROCESSING SUCCESS - Pending requests processed")
        print("=" * 50)

    except KeyboardInterrupt:
        print("⚠️ Queue processing interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected queue processing failure: {e}")
        if args.raise_on_error:
            raise


def main():
    """
    CLI entry point for local execution.

    Provides comprehensive argument parsing and execution with structured output,
    error handling, and support for both testing and production modes.
    """
    parser = argparse.ArgumentParser(
        description="Run WorkDataHub ETL job",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Core arguments
    parser.add_argument(
        "--domain", default="sample_trustee_performance", help="Domain to process"
    )
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

    # Pipeline framework toggle
    parser.add_argument(
        "--use-pipeline",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Use shared pipeline framework for annuity performance processing "
            "(overrides WDH_ANNUITY_PIPELINE_ENABLED setting)"
        ),
    )
    # Sheet can be an index or a name (string)
    parser.add_argument(
        "--sheet",
        type=str,
        default="0",
        help="Excel sheet to process (index like '0' or name like '规模明细')",
    )

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

    # Runtime override for composite key used by delete_insert mode
    parser.add_argument(
        "--pk",
        type=str,
        help=(
            "Override composite key for delete_insert mode. Comma or semicolon "
            "separated (e.g., '月度,计划代码,company_id')."
        ),
    )

    # Reference backfill arguments
    parser.add_argument(
        "--backfill-refs",
        choices=["plans", "portfolios", "all"],
        help="Enable reference backfill for missing plan/portfolio references",
    )
    parser.add_argument(
        "--backfill-mode",
        choices=["insert_missing", "fill_null_only"],
        default="insert_missing",
        help="Backfill mode: insert_missing (default) or fill_null_only",
    )
    parser.add_argument(
        "--skip-facts",
        action="store_true",
        default=False,
        help="Skip fact loading, run backfill only",
    )

    # Queue processing arguments
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for queue processing operations (default: 50)",
    )

    # Enrichment arguments
    parser.add_argument(
        "--enrichment-enabled",
        action="store_true",
        default=False,
        help="Enable company enrichment during processing",
    )
    parser.add_argument(
        "--enrichment-sync-budget",
        type=int,
        default=0,
        help="Budget for synchronous EQC lookups per processing session (default: 0)",
    )
    parser.add_argument(
        "--export-unknown-names",
        action="store_true",
        default=True,
        help="Export unknown company names to CSV for manual review",
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
        not args.execute
        if hasattr(args, "execute")
        else getattr(args, "plan_only", True)
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
    print(
        f"   Skip facts: {getattr(args, 'skip_facts', False)}"
    )  # NEW: skip facts status
    if hasattr(args, "backfill_refs") and args.backfill_refs:
        print(f"   Backfill refs: {args.backfill_refs}")
        print(f"   Backfill mode: {args.backfill_mode}")
    print("=" * 50)

    # Select appropriate job based on domain and max_files parameter
    max_files = getattr(args, "max_files", 1)

    domain_key = args.domain
    if domain_key == "trustee_performance":
        domain_key = "sample_trustee_performance"

    if domain_key == "annuity_performance":
        # Currently only single file supported for annuity performance
        selected_job = annuity_performance_job
        if max_files > 1:
            print(
                f"Warning: max_files > 1 not yet supported for {args.domain}, using 1"
            )
    elif domain_key == "sample_trustee_performance":
        selected_job = (
            sample_trustee_performance_multi_file_job
            if max_files > 1
            else sample_trustee_performance_job
        )
    elif domain_key == "company_mapping":
        # Special handling for company mapping migration
        return _execute_company_mapping_job(args)
    elif domain_key == "company_lookup_queue":
        # Special handling for company lookup queue processing
        return _execute_queue_processing_job(args)
    else:
        raise ValueError(
            f"Unsupported domain: {args.domain}. "
            f"Supported: sample_trustee_performance, annuity_performance, "
            f"company_mapping, company_lookup_queue"
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
            # Backfill summary (if configured)
            try:
                backfill_result = result.output_for_node("backfill_refs_op")
            except Exception:
                backfill_result = None

            # Load summary
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

            # Display backfill execution statistics (if available)
            if backfill_result:
                print("\n📥 Reference Backfill Summary:")
                print(f"   Plan-only: {backfill_result.get('plan_only', False)}")
                ops = backfill_result.get("operations", []) or []
                if not ops:
                    print("   Operations: 0 (skipped or no candidates)")
                for op in ops:
                    table = op.get("table")
                    inserted = op.get("inserted")
                    updated = op.get("updated")
                    if inserted is not None:
                        print(f"   {table}: inserted={inserted}")
                    if updated is not None:
                        print(f"   {table}: updated={updated}")

            # Display execution statistics for facts
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
                        print(
                            f"   Error in {event.node_name}: "
                            f"{event.event_specific_data}"
                        )

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
