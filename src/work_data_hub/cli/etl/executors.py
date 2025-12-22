"""
Job executors for ETL CLI.

Story 7.4: CLI Layer Modularization - Domain and job execution utilities.
"""

import argparse

from work_data_hub.config.settings import get_settings

from .config import build_run_config


def _execute_company_mapping_job(args: argparse.Namespace) -> int:
    """
    Execute company mapping migration job with direct database operations.

    This function handles the company mapping migration outside of the standard
    Dagster job framework since it doesn't follow the discover->read->process->load
    pattern. Instead it goes directly from legacy extraction to database loading.
    """
    import psycopg2

    from work_data_hub.domain.company_enrichment.service import (
        validate_mapping_consistency,
    )
    from work_data_hub.io.loader.company_mapping_loader import (
        CompanyMappingLoaderError,
        extract_legacy_mappings,
        generate_load_plan,
        load_company_mappings,
    )

    effective_plan_only = not args.execute if hasattr(args, "execute") else True

    print("🚀 Starting company mapping migration...")
    print(f"   Domain: {args.domains}")
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
            return 1

        if not mappings:
            print("⚠️ No mappings extracted - migration aborted")
            return 1

        print(f"✅ Successfully extracted {len(mappings)} total mappings")

        # Step 2: Validate mapping consistency
        print("🔍 Validating mapping consistency...")
        warnings = validate_mapping_consistency(mappings)

        if warnings:
            print(f"⚠️ Found {len(warnings)} validation warnings:")
            for i, warning in enumerate(warnings[:5], 1):
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
            return 0

        # Step 4: Execute migration
        print("💾 Executing database migration...")

        settings = get_settings()
        conn_string = settings.get_database_connection_string()

        try:
            with psycopg2.connect(conn_string) as conn:
                print(
                    f"🔌 Connected to PostgreSQL: "
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

                if not table_exists:
                    print("❌ Target table enterprise.company_mapping does not exist")
                    print("   Run database migrations first")
                    return 1

                # Execute load
                result = load_company_mappings(
                    conn, mappings, "enterprise", "company_mapping"
                )

                print("\n📊 Migration Results:")
                print(f"   Rows inserted: {result['inserted']:,}")
                print(f"   Rows updated: {result.get('updated', 0):,}")
                print(f"   Total processed: {result['total']:,}")

                conn.commit()
                print("\n" + "=" * 50)
                print("🎉 MIGRATION SUCCESS")
                print("=" * 50)
                return 0

        except psycopg2.Error as e:
            print(f"❌ Database error: {e}")
            return 1

    except KeyboardInterrupt:
        print("⚠️ Migration interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Unexpected migration failure: {e}")
        if args.raise_on_error:
            raise
        return 1


def _execute_queue_processing_job(args: argparse.Namespace) -> int:
    """Execute company lookup queue processing job."""
    from dagster import DagsterInstance

    from work_data_hub.orchestration.jobs import process_company_lookup_queue_job

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


def _execute_reference_sync_job(args: argparse.Namespace) -> int:
    """Execute reference sync job from authoritative sources."""
    from dagster import DagsterInstance

    from work_data_hub.orchestration.reference_sync_jobs import reference_sync_job
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


def _execute_single_domain(args: argparse.Namespace, domain: str) -> int:
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

    if domain_key == "annuity_performance":
        from work_data_hub.orchestration.jobs import annuity_performance_job

        selected_job = annuity_performance_job
        if max_files > 1:
            print(f"Warning: max_files > 1 not yet supported for {domain}, using 1")
    elif domain_key == "annuity_income":
        from work_data_hub.orchestration.jobs import annuity_income_job

        selected_job = annuity_income_job
        if max_files > 1:
            print(f"Warning: max_files > 1 not yet supported for {domain}, using 1")
    elif domain_key == "sandbox_trustee_performance":
        from work_data_hub.orchestration.jobs import (
            sandbox_trustee_performance_job,
            sandbox_trustee_performance_multi_file_job,
        )

        selected_job = (
            sandbox_trustee_performance_multi_file_job
            if max_files > 1
            else sandbox_trustee_performance_job
        )
    elif domain_key == "company_mapping":
        return _execute_company_mapping_job(args)
    elif domain_key == "company_lookup_queue":
        return _execute_queue_processing_job(args)
    elif domain_key == "reference_sync":
        return _execute_reference_sync_job(args)
    else:
        raise ValueError(
            f"Unsupported domain: {domain}. "
            f"Supported: sandbox_trustee_performance, annuity_performance, annuity_income, "
            f"company_mapping, company_lookup_queue, reference_sync"
        )

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
                        print(f"   Error in {event.node_name}: {event.event_specific_data}")

        return 0 if result.success else 1

    except Exception as e:
        print(f"💥 Job execution failed: {e}")
        if args.debug:
            import traceback

            print("\n🐛 Full traceback:")
            traceback.print_exc()
        return 1
