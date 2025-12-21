"""
ETL CLI for WorkDataHub.

Story 6.2-P6: CLI Architecture Unification & Multi-Domain Batch Processing
Task 1.2: Extract jobs.py main() to cli/etl.py with single & multi-domain support

Story 6.2-P11: Token auto-refresh on CLI startup (T3.1-T3.3)

This module provides the CLI interface for running ETL jobs, supporting:
- Single domain processing (backward compatible)
- Multi-domain batch processing (new in Story 6.2-P6)
- Token validation and auto-refresh at startup (new in Story 6.2-P11)
- All existing CLI options from jobs.py

Usage:
    # Single domain
    python -m work_data_hub.cli etl --domains annuity_performance --period 202411 --execute

    # Multi-domain (Phase 2)
    python -m work_data_hub.cli etl --domains annuity_performance,annuity_income --period 202411 --execute

    # All domains (Phase 2)
    python -m work_data_hub.cli etl --all-domains --period 202411 --execute
    
    # Disable auto-refresh token (if you want to skip token check)
    python -m work_data_hub.cli etl --domains annuity_performance --no-auto-refresh-token --execute
"""

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional

import yaml

from work_data_hub.config.settings import get_settings


def _validate_and_refresh_token(auto_refresh: bool = True) -> bool:
    """
    Validate EQC token at CLI startup and auto-refresh if invalid.
    
    Story 6.2-P11 T3.1-T3.2: Pre-check Token validity before ETL execution.
    If token is invalid and auto_refresh is True, triggers auto-QR login flow.
    
    Args:
        auto_refresh: If True, auto-refresh token when validation fails.
        
    Returns:
        True if token is valid (or was successfully refreshed), False otherwise.
    """
    from work_data_hub.infrastructure.enrichment.eqc_provider import validate_eqc_token
    
    try:
        settings = get_settings()
        token = settings.eqc_token
        base_url = settings.eqc_base_url
        
        if not token:
            print("⚠️  No EQC token configured (WDH_EQC_TOKEN not set)")
            if not auto_refresh:
                print("   Continuing without token (EQC lookup will be disabled)")
                return True
            print("   Attempting to refresh token via QR login...")
            return _trigger_token_refresh()
        
        # Validate existing token
        print("🔐 Validating EQC token...", end=" ", flush=True)
        if validate_eqc_token(token, base_url):
            print("✅ Token valid")
            return True
        
        # Token is invalid
        print("❌ Token invalid/expired")
        
        if not auto_refresh:
            print("⚠️  Auto-refresh disabled (--no-auto-refresh-token)")
            print("   Run: python -m work_data_hub.cli auth refresh")
            return True  # Continue without valid token
            
        print("   Attempting to refresh token via QR login...")
        return _trigger_token_refresh()
        
    except Exception as e:
        print(f"⚠️  Token validation error: {e}")
        return True  # Continue anyway to avoid blocking pipeline


def _trigger_token_refresh() -> bool:
    """Trigger automatic token refresh via QR login."""
    try:
        from work_data_hub.io.auth.auto_eqc_auth import run_get_token_auto_qr

        token = run_get_token_auto_qr(save_to_env=True, timeout_seconds=180)
        if token:
            print("✅ Token refreshed successfully")
            # Make the refreshed token effective in the current process as well.
            # Settings are cached (lru_cache), so we must clear it to re-read `.wdh_env`.
            os.environ["WDH_EQC_TOKEN"] = token
            try:
                from work_data_hub.config.settings import get_settings

                get_settings.cache_clear()
            except Exception:
                # Best-effort; even if cache clear fails, the token is persisted to `.wdh_env`.
                pass
            return True
        else:
            print("❌ Token refresh failed")
            print("   Please run manually: python -m work_data_hub.cli auth refresh")
            return False
    except Exception as e:
        print(f"❌ Token refresh error: {e}")
        return False


def _check_database_connection() -> int:
    """
    Test database connection and display diagnostic info.

    Story 6.2-P16 AC-2: Database connection diagnostics.
    Validates settings and attempts connection without running ETL.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("🔍 Database Connection Diagnostics")
    print("=" * 50)

    try:
        settings = get_settings()

        from pathlib import Path

        # Display DSN components (never show password)
        print(f"   Host: {settings.database_host}")
        print(f"   Port: {settings.database_port}")
        print(f"   Database: {settings.database_db}")
        print(f"   User: {settings.database_user}")
        print(f"   Password: {'***' if settings.database_password else '(not set)'}")
        env_file = Path(".wdh_env")
        print(
            f"   .wdh_env: {env_file.resolve()} "
            f"({('found' if env_file.exists() else 'missing')})"
        )

        # Validate required settings
        missing = []
        if not settings.database_host:
            missing.append("WDH_DATABASE__HOST")
        if not settings.database_port:
            missing.append("WDH_DATABASE__PORT")
        if not settings.database_db:
            missing.append("WDH_DATABASE__DB")
        if not settings.database_user:
            missing.append("WDH_DATABASE__USER")
        if not settings.database_password:
            missing.append("WDH_DATABASE__PASSWORD")

        if missing:
            print(f"\n❌ Missing required settings: {', '.join(missing)}")
            print("   Add these to your .wdh_env file")
            return 1

        # Attempt connection
        print("\n🔌 Attempting connection...", end=" ", flush=True)

        import psycopg2

        dsn = settings.get_database_connection_string()
        conn = None
        try:
            conn = psycopg2.connect(dsn)
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
        finally:
            if conn is not None:
                conn.close()

        print("✅ Connected!")
        print(f"\n📋 PostgreSQL: {version.split(',')[0] if ',' in version else version}")
        print("=" * 50)
        print("✅ Database connection successful")
        return 0

    except Exception as e:
        print(f"❌ Failed")
        print(f"\n❌ Connection error: {e}")
        print("\n💡 Troubleshooting hints:")
        print("   - Verify WDH_DATABASE__* settings in .wdh_env")
        print("   - Check if PostgreSQL server is running")
        print("   - Verify network connectivity to database host")
        print("   - Confirm database user has login permissions")
        return 1


def _parse_pk_override(pk_arg: Any) -> List[str]:
    """
    Parse CLI --pk override into a clean list of column names.

    Accepts comma/semicolon separated string or list-like; ignores empty items.

    Args:
        pk_arg: Primary key override argument (string or list)

    Returns:
        List of column names
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


def build_run_config(args: argparse.Namespace, domain: str) -> Dict[str, Any]:
    """
    Build Dagster run_config from CLI arguments for a specific domain.

    Args:
        args: Parsed command line arguments
        domain: Domain name to process

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
    from work_data_hub.config.settings import get_settings

    settings = get_settings()

    data_sources: Dict[str, Any] = {}
    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f) or {}
        if not isinstance(data_sources, dict):
            data_sources = {}

        domain_config = (data_sources.get("domains") or {}).get(domain, {}) or {}
        if not isinstance(domain_config, dict):
            domain_config = {}

        # Epic 3 schema prefers output.table + output.schema_name
        output_cfg = domain_config.get("output") if isinstance(domain_config, dict) else None
        if isinstance(output_cfg, dict) and output_cfg.get("table"):
            table_name = str(output_cfg["table"])
            schema_name = output_cfg.get("schema_name")
            if schema_name:
                table = f"{schema_name}.{table_name}"
            else:
                table = table_name
        else:
            table = domain_config.get("table", domain)  # Legacy fallback

        pk = domain_config.get("pk", [])  # Legacy fallback
        # Epic 3 schema: pk in output section takes precedence
        if isinstance(output_cfg, dict) and "pk" in output_cfg:
            pk = output_cfg["pk"]

        # Runtime override via --pk (only affects delete_insert mode)
        pk_override = _parse_pk_override(getattr(args, "pk", None))
        if pk_override:
            pk = pk_override

    except Exception as e:
        print(f"Warning: Could not load data sources config: {e}")
        table = domain
        pk = []

    # Build discover_files_op config with optional period and selection strategy
    discover_config = {"domain": domain}
    if hasattr(args, "period") and args.period:
        discover_config["period"] = args.period
    # Story 6.2-P16: Pass file selection strategy from CLI to op
    if hasattr(args, "file_selection") and args.file_selection:
        discover_config["selection_strategy"] = args.file_selection

    run_config = {
        "ops": {
            "discover_files_op": {"config": discover_config},
            "load_op": {
                "config": {
                    "table": table,
                    "mode": args.mode,
                    "pk": pk,
                    "plan_only": effective_plan_only,
                    "skip": getattr(args, "skip_facts", False),
                }
            },
        }
    }

    # Add max_files parameter and conditionally configure ops
    max_files = getattr(args, "max_files", 1)

    # Determine sheet configuration
    sheet_value = getattr(args, "sheet", None)
    if sheet_value is None:
        # Check if domain is Epic 3 schema and has sheet_name configured
        domain_config = (data_sources.get("domains") or {}).get(domain, {}) or {}
        if isinstance(domain_config, dict) and "sheet_name" in domain_config:
            sheet_value = domain_config["sheet_name"]
        else:
            # Fallback to 0 for legacy domains
            sheet_value = "0"

    if max_files > 1:
        # Use new combined op for multi-file processing
        run_config["ops"]["read_and_process_sandbox_trustee_files_op"] = {
            "config": {"sheet": sheet_value, "max_files": max_files}
        }
    else:
        # Use existing separate ops for single-file processing
        sheet_cfg: Any
        try:
            sheet_cfg = int(sheet_value)
        except Exception:
            sheet_cfg = sheet_value
        run_config["ops"]["read_excel_op"] = {"config": {"sheet": sheet_cfg}}

    # Epic 6.2: Generic backfill configuration
    if domain in ["annuity_performance", "sandbox_trustee_performance"]:
        run_config["ops"]["generic_backfill_refs_op"] = {
            "config": {
                "domain": domain,
                "plan_only": effective_plan_only,
                "add_tracking_fields": False,  # mapping schema tables don't have tracking fields
            }
        }

    # Add enrichment configuration for annuity_performance domain
    if domain == "annuity_performance":
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig

        # Story 6.2-P17: Build EqcLookupConfig from CLI args (SSOT, semantic enforcement).
        eqc_config = EqcLookupConfig.from_cli_args(args)
        run_config["ops"]["process_annuity_performance_op"] = {
            "config": {
                # Legacy fields kept for backward compatibility / logging
                "enrichment_enabled": eqc_config.enabled,
                "enrichment_sync_budget": eqc_config.sync_budget,
                "export_unknown_names": eqc_config.export_unknown_names,
                # Story 6.2-P17: Preferred config payload
                "eqc_lookup_config": eqc_config.to_dict(),
                "plan_only": effective_plan_only,
                "use_pipeline": getattr(args, "use_pipeline", None),
            }
        }


    return run_config


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
        from dagster import DagsterInstance

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


def _load_configured_domains() -> List[str]:
    """
    Load list of configured data domains from data_sources.yml.

    Returns:
        List of domain names from config/data_sources.yml
    """
    from work_data_hub.config.settings import get_settings

    settings = get_settings()
    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f) or {}
        domains_config = data_sources.get("domains", {})
        if isinstance(domains_config, dict):
            return list(domains_config.keys())
        return []
    except Exception as e:
        print(f"Warning: Could not load data sources config: {e}")
        return []


def _validate_domains(domains: List[str], allow_special: bool = False) -> tuple[List[str], List[str]]:
    """
    Validate domain names against configured domains and special orchestration domains.

    Args:
        domains: List of domain names to validate
        allow_special: If True, allow special orchestration domains for single-domain runs

    Returns:
        Tuple of (valid_domains, invalid_domains)
    """
    # Special orchestration domains (not in data_sources.yml)
    SPECIAL_DOMAINS = {"company_mapping", "company_lookup_queue", "reference_sync"}

    # Load configured data domains
    configured_domains = set(_load_configured_domains())

    valid = []
    invalid = []

    for domain in domains:
        if domain in configured_domains:
            valid.append(domain)
        elif allow_special and domain in SPECIAL_DOMAINS:
            valid.append(domain)
        else:
            invalid.append(domain)

    return valid, invalid


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point for ETL operations.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Run WorkDataHub ETL job",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Core arguments
    parser.add_argument(
        "--domains",
        help="Domain(s) to process (single domain or comma-separated list)",
    )
    parser.add_argument(
        "--all-domains",
        action="store_true",
        help="Process all configured data domains from config/data_sources.yml",
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
        default=False,
        help="Generate execution plan without database connection (default unless --execute)",
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

    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Excel sheet to process (index like '0' or name like '规模明细'). If not provided, uses sheet_name from data_sources.yml for Epic 3 domains.",
    )

    # Period parameter for Epic 3 schema domains
    parser.add_argument(
        "--period",
        type=str,
        help="Period in YYYYMM format for Epic 3 domains (e.g., '202510')",
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

    # Story 6.2-P16 AC-1: File selection strategy for ambiguous matches
    parser.add_argument(
        "--file-selection",
        choices=["error", "newest", "oldest", "first"],
        default="error",
        help=(
            "Strategy when multiple files match patterns. "
            "'error' (default) raises an error, 'newest' selects most recently modified, "
            "'oldest' selects oldest, 'first' selects alphabetically first."
        ),
    )

    # Runtime override for composite key
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
    # Default behavior: enabled (so EQC sync lookups can run) unless explicitly disabled.
    parser.add_argument(
        "--enrichment",
        dest="enrichment_enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable company enrichment/EQC lookups (default: enabled)",
    )
    # Backward-compatible alias (kept for existing scripts/docs)
    parser.add_argument(
        "--enrichment-enabled",
        dest="enrichment_enabled",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--enrichment-sync-budget",
        type=int,
        default=500,
        help=(
            "Budget for synchronous EQC lookups per processing session "
            "(default: 500; set 0 to disable)"
        ),
    )
    parser.add_argument(
        "--export-unknown-names",
        action=argparse.BooleanOptionalAction,
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
    
    # Story 6.2-P11 T3.3: Token auto-refresh control
    parser.add_argument(
        "--no-auto-refresh-token",
        action="store_true",
        default=False,
        help="Disable automatic EQC token refresh at startup",
    )

    # Story 6.2-P16 AC-2: Database connection diagnostics
    parser.add_argument(
        "--check-db",
        action="store_true",
        default=False,
        help="Test database connection and exit (diagnostic mode)",
    )

    args = parser.parse_args(argv)

    # Story 6.2-P16 AC-2: --check-db diagnostic mode
    if getattr(args, "check_db", False):
        return _check_database_connection()

    # Validate domain arguments
    if not args.domains and not args.all_domains:
        parser.error("Either --domains or --all-domains must be specified")

    if args.domains and args.all_domains:
        parser.error("Cannot specify both --domains and --all-domains")

    # Story 6.2-P11 T3.1-T3.2: Token validation at CLI startup
    # Only validate for domains that may use EQC enrichment (annuity_performance).
    # `--no-auto-refresh-token` disables auto-refresh, but still performs a pre-check so
    # users can see token status and intentionally proceed without EQC lookups.
    auto_refresh_enabled = not getattr(args, "no_auto_refresh_token", False)
    enrichment_enabled = bool(getattr(args, "enrichment_enabled", False))

    domains_for_check: List[str] = []
    if args.domains:
        domains_for_check = [d.strip() for d in args.domains.split(",")]
    elif args.all_domains:
        domains_for_check = _load_configured_domains()

    enrichment_domains = {"annuity_performance"}
    if enrichment_enabled and any(d in enrichment_domains for d in domains_for_check):
        _validate_and_refresh_token(auto_refresh=auto_refresh_enabled)

    # Determine domains to process
    domains_to_process: List[str] = []

    if args.all_domains:
        # Task 2.3: Process all configured data domains
        configured_domains = _load_configured_domains()
        if not configured_domains:
            print("❌ No configured domains found in config/data_sources.yml")
            return 1

        # Exclude special orchestration domains from --all-domains
        SPECIAL_DOMAINS = {"company_mapping", "company_lookup_queue", "reference_sync"}
        domains_to_process = [d for d in configured_domains if d not in SPECIAL_DOMAINS]

        print(f"📋 Processing all configured domains: {', '.join(domains_to_process)}")
        print(f"   Total: {len(domains_to_process)} domains")
        print("=" * 50)

    elif args.domains:
        # Parse comma-separated domain list
        domains_to_process = [d.strip() for d in args.domains.split(",") if d.strip()]

        if not domains_to_process:
            parser.error("No valid domains specified")

        # Task 2.1: Validate domains based on count
        if len(domains_to_process) > 1:
            # Multi-domain: Only allow configured data domains
            valid, invalid = _validate_domains(domains_to_process, allow_special=False)

            if invalid:
                print(f"❌ Invalid domains for multi-domain processing: {', '.join(invalid)}")
                print(f"   Multi-domain runs only support configured data domains from config/data_sources.yml")
                print(f"   Special orchestration domains (company_mapping, company_lookup_queue, reference_sync)")
                print(f"   can only be used in single-domain runs")
                return 1

            domains_to_process = valid
            print(f"📋 Multi-domain batch processing: {', '.join(domains_to_process)}")
            print(f"   Total: {len(domains_to_process)} domains")
            print("=" * 50)

        else:
            # Single domain: Allow both configured and special domains
            valid, invalid = _validate_domains(domains_to_process, allow_special=True)

            if invalid:
                print(f"❌ Unknown domain: {invalid[0]}")
                configured = _load_configured_domains()
                print(f"   Available configured domains: {', '.join(configured)}")
                print(f"   Special orchestration domains: company_mapping, company_lookup_queue, reference_sync")
                return 1

            domains_to_process = valid

    # Task 2.2: Execute domains sequentially
    if len(domains_to_process) == 1:
        # Single domain execution
        return _execute_single_domain(args, domains_to_process[0])

    else:
        # Multi-domain batch execution
        print(f"🚀 Starting multi-domain batch processing...")
        print(f"   Execution mode: Sequential")
        print(f"   Continue on failure: Yes")
        print("=" * 50)

        results = {}
        failed_domains = []

        for i, domain in enumerate(domains_to_process, 1):
            print(f"\n{'=' * 50}")
            print(f"Processing domain {i}/{len(domains_to_process)}: {domain}")
            print(f"{'=' * 50}")

            try:
                exit_code = _execute_single_domain(args, domain)
                results[domain] = "SUCCESS" if exit_code == 0 else "FAILED"

                if exit_code != 0:
                    failed_domains.append(domain)
                    print(f"⚠️  Domain {domain} failed with exit code {exit_code}")
                else:
                    print(f"✅ Domain {domain} completed successfully")

            except KeyboardInterrupt:
                print(f"\n⚠️  Multi-domain processing interrupted by user at domain {domain}")
                results[domain] = "INTERRUPTED"
                return 130

            except Exception as e:
                print(f"❌ Unexpected error processing domain {domain}: {e}")
                results[domain] = "ERROR"
                failed_domains.append(domain)

                if args.raise_on_error:
                    raise

        # Print summary
        print(f"\n{'=' * 50}")
        print("📊 MULTI-DOMAIN BATCH PROCESSING SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total domains: {len(domains_to_process)}")
        print(f"Successful: {sum(1 for r in results.values() if r == 'SUCCESS')}")
        print(f"Failed: {len(failed_domains)}")
        print()

        print("Per-domain results:")
        for domain, status in results.items():
            status_icon = "✅" if status == "SUCCESS" else "❌"
            print(f"  {status_icon} {domain}: {status}")

        print(f"{'=' * 50}")

        # Return exit code 1 if any domain failed
        if failed_domains:
            print(f"❌ Multi-domain processing completed with {len(failed_domains)} failure(s)")
            return 1
        else:
            print("🎉 Multi-domain processing completed successfully")
            return 0


if __name__ == "__main__":
    sys.exit(main())
