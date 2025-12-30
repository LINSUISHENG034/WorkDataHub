"""
Job executors for ETL CLI.

Story 7.4: CLI Layer Modularization - Domain and job execution utilities.
"""

import argparse

from .config import build_run_config


def _execute_queue_processing_job(args: argparse.Namespace) -> int:
    """Execute company lookup queue processing job."""
    from dagster import DagsterInstance

    from work_data_hub.orchestration.jobs import (  # noqa: TID251 - CLI is outermost layer
        process_company_lookup_queue_job,
    )

    effective_plan_only = not args.execute if hasattr(args, "execute") else True

    print("🚀 Starting company lookup queue processing...")
    print(f"   Domain: {args.domains}")
    print(f"   Batch size: {args.batch_size}")
    print(f"   Execute: {args.execute}")
    print(f"   Plan-only: {effective_plan_only}")
    print("=" * 50)

    try:
        # Build run config for queue processing
        run_config = {
            "ops": {
                "process_company_lookup_queue_op": {
                    "config": {
                        "batch_size": args.batch_size,
                        "plan_only": effective_plan_only,
                    }
                }
            }
        }

        # Execute job
        instance = DagsterInstance.ephemeral() if args.debug else None
        result = process_company_lookup_queue_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        print(f"✅ Job completed successfully: {result.success}")

        if result.success:
            queue_result = result.output_for_node("process_company_lookup_queue_op")

            print("\n📊 Queue Processing Summary:")
            print(f"   Processed: {queue_result.get('processed', 0)} requests")
            print(f"   Successful: {queue_result.get('successful', 0)}")
            print(f"   Failed: {queue_result.get('failed', 0)}")
            print(f"   Remaining: {queue_result.get('remaining', 0)}")

        else:
            print("❌ Job completed with failures")

        return 0 if result.success else 1

    except KeyboardInterrupt:
        print("⚠️ Queue processing interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Unexpected queue processing failure: {e}")
        if args.raise_on_error:
            raise
        return 1


def _execute_reference_sync_job(args: argparse.Namespace) -> int:  # noqa: PLR0915 - CLI job executor
    """Execute reference sync job from authoritative sources."""
    from dagster import DagsterInstance

    from work_data_hub.orchestration.reference_sync_jobs import (  # noqa: TID251 - CLI is outermost layer
        reference_sync_job,
    )
    from work_data_hub.orchestration.reference_sync_ops import ReferenceSyncOpConfig

    effective_plan_only = not args.execute if hasattr(args, "execute") else True

    print("🚀 Starting reference sync from authoritative sources...")
    print(f"   Domain: {args.domains}")
    print(f"   Execute: {args.execute}")
    print(f"   Plan-only: {effective_plan_only}")
    print("=" * 50)

    try:
        # Build run config for reference sync
        run_config = {
            "ops": {
                "reference_sync_op": {
                    "config": ReferenceSyncOpConfig(
                        plan_only=effective_plan_only,
                    ).model_dump()
                }
            }
        }

        # Execute job
        instance = DagsterInstance.ephemeral() if args.debug else None
        result = reference_sync_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        print(f"✅ Job completed successfully: {result.success}")

        if result.success:
            output_data = result.output_for_node("reference_sync_op")
            if output_data:
                status = output_data.get("status", "unknown")
                total_synced = output_data.get("total_synced", 0)
                total_deleted = output_data.get("total_deleted", 0)
                failed_count = output_data.get("failed_count", 0)
                table_count = output_data.get("table_count", 0)

                print("\nREFERENCE SYNC RESULTS:")
                print(f"  Status: {status}")
                print(f"  Tables processed: {table_count}")
                print(f"  Rows synced: {total_synced}")
                print(f"  Rows deleted: {total_deleted}")
                print(f"  Failed tables: {failed_count}")

                # Show per-table results if available
                results_list = output_data.get("results", [])
                if results_list:
                    print("\n  Per-table breakdown:")
                    for r in results_list:
                        table = r.get("table", "unknown")
                        synced = r.get("rows_synced", 0)
                        deleted = r.get("rows_deleted", 0)
                        error = r.get("error")
                        if error:
                            print(f"    ❌ {table}: ERROR - {error}")
                        else:
                            print(f"    ✓ {table}: {synced} synced, {deleted} deleted")

        print("=" * 50)
        if effective_plan_only:
            print("✅ Reference sync plan complete - no database changes made")
        else:
            print("🎉 REFERENCE SYNC SUCCESS - Authoritative data loaded")
        print("=" * 50)
        return 0

    except KeyboardInterrupt:
        print("⚠️ Reference sync interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Unexpected reference sync failure: {e}")
        if args.raise_on_error:
            raise
        return 1


def _execute_single_domain(args: argparse.Namespace, domain: str) -> int:  # noqa: PLR0912, PLR0915 - CLI domain dispatcher
    """
    Execute ETL job for a single domain.

    Args:
        args: Parsed command line arguments
        domain: Domain name to process

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Calculate effective execution mode
    effective_plan_only = (
        not args.execute
        if hasattr(args, "execute")
        else getattr(args, "plan_only", True)
    )

    # Build run configuration
    run_config = build_run_config(args, domain)

    print(f"🚀 Starting {domain} job...")
    print(f"   Domain: {domain}")
    print(f"   Mode: {args.mode}")
    print(f"   Execute: {args.execute}")
    print(f"   Plan-only: {effective_plan_only}")
    print(f"   Sheet: {args.sheet}")
    print(f"   Max files: {args.max_files}")
    print(f"   Skip facts: {getattr(args, 'skip_facts', False)}")
    if hasattr(args, "backfill_refs") and args.backfill_refs:
        print(f"   Backfill refs: {args.backfill_refs}")
        print(f"   Backfill mode: {args.backfill_mode}")
    print("=" * 50)

    # Select appropriate job based on domain and max_files parameter
    max_files = getattr(args, "max_files", 1)

    domain_key = domain

    # Story 7.4-1: Use JOB_REGISTRY instead of if/elif chain
    # Handle special non-standard domains first
    if domain_key in ("company_lookup_queue", "reference_sync"):
        if domain_key == "company_lookup_queue":
            return _execute_queue_processing_job(args)
        else:  # reference_sync
            return _execute_reference_sync_job(args)

    # Lookup job in registry
    from work_data_hub.orchestration.jobs import JOB_REGISTRY

    job_entry = JOB_REGISTRY.get(domain_key)
    if not job_entry:
        supported = ", ".join(sorted(JOB_REGISTRY.keys()))
        raise ValueError(f"Unsupported domain: {domain}. Supported: {supported}")

    # Select job based on max_files parameter
    selected_job = job_entry.job
    if max_files > 1:
        if job_entry.multi_file_job:
            selected_job = job_entry.multi_file_job
        else:
            print(f"Warning: max_files > 1 not yet supported for {domain}, using 1")

    # Execute job with appropriate settings
    try:
        from dagster import DagsterInstance

        instance = DagsterInstance.ephemeral() if args.debug else None

        result = selected_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        print(f"✅ Job completed successfully: {result.success}")

        if result.success:
            # Extract and display execution summary
            try:
                backfill_result = result.output_for_node("generic_backfill_refs_op")
            except Exception:
                backfill_result = None

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

            # Display backfill execution statistics
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
                for event in result.all_node_events:
                    if event.is_failure:
                        print(
                            f"   Error in {event.node_name}: "
                            f"{event.event_specific_data}"
                        )

        return 0 if result.success else 1

    except Exception as e:
        print(f"💥 Job execution failed: {e}")
        if args.debug:
            import traceback

            print("\n🐛 Full traceback:")
            traceback.print_exc()
        return 1
