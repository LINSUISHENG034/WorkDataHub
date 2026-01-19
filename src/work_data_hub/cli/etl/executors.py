"""
Job executors for ETL CLI.

Story 7.4: CLI Layer Modularization - Domain and job execution utilities.
Story 7.5-4: Rich Terminal UX Enhancement - Console abstraction integration.
"""

import argparse

from .config import build_run_config
from .console import get_console
from .dagster_logging import merge_logger_config


def _get_console_from_args(args: argparse.Namespace):
    """Get console instance from CLI arguments.

    Story 7.5-4: Factory function for console selection based on --no-rich flag.

    Args:
        args: Parsed CLI arguments

    Returns:
        BaseConsole instance (RichConsole or PlainConsole)
    """
    no_rich = getattr(args, "no_rich", False)
    return get_console(no_rich=no_rich)


def _execute_queue_processing_job(args: argparse.Namespace) -> int:
    """Execute company lookup queue processing job."""
    from dagster import DagsterInstance

    from work_data_hub.orchestration.jobs import (  # noqa: TID251 - CLI is outermost layer
        process_company_lookup_queue_job,
    )

    console = _get_console_from_args(args)
    effective_plan_only = not args.execute if hasattr(args, "execute") else True

    console.print("🚀 Starting company lookup queue processing...")
    console.print(f"   Domain: {args.domains}")
    console.print(f"   Batch size: {args.batch_size}")
    console.print(f"   Execute: {args.execute}")
    console.print(f"   Plan-only: {effective_plan_only}")
    console.print("=" * 50)

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

        # Story 7.5-6: Apply Dagster logger configuration
        debug_mode = getattr(args, "debug", False)
        verbose_mode = getattr(args, "verbose", False)
        quiet_mode = getattr(args, "quiet", False)
        run_config = merge_logger_config(
            run_config, debug=debug_mode, verbose=verbose_mode, quiet=quiet_mode
        )

        # Execute job
        instance = DagsterInstance.ephemeral() if debug_mode else None
        result = process_company_lookup_queue_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        console.print(f"✅ Job completed successfully: {result.success}")

        if result.success:
            queue_result = result.output_for_node("process_company_lookup_queue_op")

            console.print("\n📊 Queue Processing Summary:")
            console.print(f"   Processed: {queue_result.get('processed', 0)} requests")
            console.print(f"   Successful: {queue_result.get('successful', 0)}")
            console.print(f"   Failed: {queue_result.get('failed', 0)}")
            console.print(f"   Remaining: {queue_result.get('remaining', 0)}")

        else:
            console.print("❌ Job completed with failures")

        return 0 if result.success else 1

    except KeyboardInterrupt:
        console.print("⚠️ Queue processing interrupted by user")
        return 130
    except Exception as e:
        console.print(f"❌ Unexpected queue processing failure: {e}")
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

    console = _get_console_from_args(args)
    effective_plan_only = not args.execute if hasattr(args, "execute") else True

    console.print("🚀 Starting reference sync from authoritative sources...")
    console.print(f"   Domain: {args.domains}")
    console.print(f"   Execute: {args.execute}")
    console.print(f"   Plan-only: {effective_plan_only}")
    console.print("=" * 50)

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

        # Story 7.5-6: Apply Dagster logger configuration
        debug_mode = getattr(args, "debug", False)
        verbose_mode = getattr(args, "verbose", False)
        quiet_mode = getattr(args, "quiet", False)
        run_config = merge_logger_config(
            run_config, debug=debug_mode, verbose=verbose_mode, quiet=quiet_mode
        )

        # Execute job
        instance = DagsterInstance.ephemeral() if debug_mode else None
        result = reference_sync_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        console.print(f"✅ Job completed successfully: {result.success}")

        if result.success:
            output_data = result.output_for_node("reference_sync_op")
            if output_data:
                status = output_data.get("status", "unknown")
                total_synced = output_data.get("total_synced", 0)
                total_deleted = output_data.get("total_deleted", 0)
                failed_count = output_data.get("failed_count", 0)
                table_count = output_data.get("table_count", 0)

                console.print("\nREFERENCE SYNC RESULTS:")
                console.print(f"  Status: {status}")
                console.print(f"  Tables processed: {table_count}")
                console.print(f"  Rows synced: {total_synced}")
                console.print(f"  Rows deleted: {total_deleted}")
                console.print(f"  Failed tables: {failed_count}")

                # Show per-table results if available
                results_list = output_data.get("results", [])
                if results_list:
                    console.print("\n  Per-table breakdown:")
                    for r in results_list:
                        table = r.get("table", "unknown")
                        synced = r.get("rows_synced", 0)
                        deleted = r.get("rows_deleted", 0)
                        error = r.get("error")
                        if error:
                            console.print(f"    ❌ {table}: ERROR - {error}")
                        else:
                            console.print(
                                f"    ✓ {table}: {synced} synced, {deleted} deleted"
                            )

        console.print("=" * 50)
        if effective_plan_only:
            console.print("✅ Reference sync plan complete - no database changes made")
        else:
            console.print("🎉 REFERENCE SYNC SUCCESS - Authoritative data loaded")
        console.print("=" * 50)
        return 0

    except KeyboardInterrupt:
        console.print("⚠️ Reference sync interrupted by user")
        return 130
    except Exception as e:
        console.print(f"❌ Unexpected reference sync failure: {e}")
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
    console = _get_console_from_args(args)

    # Calculate effective execution mode
    effective_plan_only = (
        not args.execute
        if hasattr(args, "execute")
        else getattr(args, "plan_only", True)
    )

    # Build run configuration
    run_config = build_run_config(args, domain)

    console.print(f"🚀 Starting {domain} job...")
    console.print(f"   Domain: {domain}")
    console.print(f"   Mode: {args.mode}")
    console.print(f"   Execute: {args.execute}")
    console.print(f"   Plan-only: {effective_plan_only}")
    console.print(f"   Sheet: {args.sheet}")
    console.print(f"   Max files: {args.max_files}")
    console.print(f"   Skip facts: {getattr(args, 'skip_facts', False)}")
    if hasattr(args, "backfill_refs") and args.backfill_refs:
        console.print(f"   Backfill refs: {args.backfill_refs}")
        console.print(f"   Backfill mode: {args.backfill_mode}")
    console.print("=" * 50)

    # Story 7.5-4 AC-2: Display file discovery tree (if files are in run_config)
    files_list = (
        run_config.get("ops", {})
        .get("discover_files_op", {})
        .get("config", {})
        .get("files_list", [])
    )
    if files_list and console.is_rich_enabled():
        from pathlib import Path

        tree = console.tree(f"📂 {domain}")
        for file_path in files_list:
            # Story 7.5-4 AC-3: Add clickable hyperlink for file paths
            file_link = console.hyperlink(file_path, Path(file_path).name)
            tree.add(f"📄 {file_link}")
        console.print(tree)
        console.print("")

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
            console.print(
                f"Warning: max_files > 1 not yet supported for {domain}, using 1"
            )

    # Execute job with appropriate settings
    try:
        from dagster import DagsterInstance

        # Story 7.5-6: Apply Dagster logger configuration based on CLI flags
        debug_mode = getattr(args, "debug", False)
        verbose_mode = getattr(args, "verbose", False)
        quiet_mode = getattr(args, "quiet", False)
        run_config = merge_logger_config(
            run_config, debug=debug_mode, verbose=verbose_mode, quiet=quiet_mode
        )

        instance = DagsterInstance.ephemeral() if debug_mode else None

        # Story 7.5-4 AC-2: Live status display during job execution
        with console.status(f"[bold green]Processing {domain}..."):
            result = selected_job.execute_in_process(
                run_config=run_config,
                instance=instance,
                raise_on_error=args.raise_on_error,
            )

        # Report results
        console.print(f"✅ Job completed successfully: {result.success}")

        # Story 7.5-5: Display hyperlink to failure log if failures occurred
        if result.success:
            # Check if failure CSV was generated
            from pathlib import Path

            session_id = getattr(args, "session_id", None)
            if session_id:
                failure_log_path = Path("logs") / f"wdh_etl_failures_{session_id}.csv"
                if failure_log_path.exists():
                    link_text = console.hyperlink(
                        f"Saved failure log to {failure_log_path.name}",
                        failure_log_path,
                    )
                    console.print(f"📄 {link_text}")

        if result.success:
            # Extract and display execution summary
            try:
                backfill_result = result.output_for_node("generic_backfill_refs_op")
            except Exception:
                backfill_result = None

            load_result = result.output_for_node("load_op")

            if effective_plan_only and "sql_plans" in load_result:
                console.print("\n📋 SQL Execution Plan:")
                console.print("-" * 30)
                for i, (op_type, sql, params) in enumerate(load_result["sql_plans"], 1):
                    console.print(f"{i}. {op_type}:")
                    console.print(f"   {sql}")
                    if params:
                        console.print(f"   Parameters: {len(params)} values")
                    console.print("")

            # Display backfill execution statistics
            if backfill_result:
                console.print("\n📥 Reference Backfill Summary:")
                console.print(
                    f"   Plan-only: {backfill_result.get('plan_only', False)}"
                )
                ops = backfill_result.get("operations", []) or []
                if not ops:
                    console.print("   Operations: 0 (skipped or no candidates)")
                for op in ops:
                    table = op.get("table")
                    inserted = op.get("inserted")
                    updated = op.get("updated")
                    if inserted is not None:
                        console.print(f"   {table}: inserted={inserted}")
                    if updated is not None:
                        console.print(f"   {table}: updated={updated}")

            # Display execution statistics for facts
            console.print("\n📊 Execution Summary:")
            console.print(f"   Table: {load_result.get('table', 'N/A')}")
            console.print(f"   Mode: {load_result.get('mode', 'N/A')}")
            console.print(f"   Deleted: {load_result.get('deleted', 0)} rows")
            console.print(f"   Inserted: {load_result.get('inserted', 0)} rows")
            console.print(f"   Batches: {load_result.get('batches', 0)}")

        else:
            console.print("❌ Job completed with failures")
            if not args.raise_on_error:
                from .error_formatter import format_step_failure

                for event in result.all_node_events:
                    if event.is_failure:
                        clean_message = format_step_failure(
                            event.node_name, event.event_specific_data
                        )
                        console.print(f"   {clean_message}")

        # Story 7.6-6: Execute Post-ETL hooks on success
        # Design Decision: Hook failures are logged as warnings but do NOT fail the
        # ETL job. This ensures data loading completes even if downstream sync fails.
        # Users can manually re-run via `customer-mdm sync` command.
        if result.success and not getattr(args, "no_post_hooks", False):
            from .hooks import run_post_etl_hooks

            period = getattr(args, "period", None)
            console.print("\n🪝 Running Post-ETL hooks...")
            try:
                run_post_etl_hooks(domain=domain, period=period)
                console.print("✓ Post-ETL hooks completed")
            except Exception as e:
                console.print(f"⚠ Post-ETL hooks failed: {e}")  # Warning only
                if args.debug:
                    import traceback

                    console.print("\n🐛 Hook traceback:")
                    traceback.print_exc()

        return 0 if result.success else 1

    except Exception as e:
        console.print(f"💥 Job execution failed: {e}")
        if args.debug:
            import traceback

            console.print("\n🐛 Full traceback:")
            traceback.print_exc()
        return 1
