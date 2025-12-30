"""Dagster jobs wiring I/O services into domain pipelines (Story 1.6).

Jobs compose the Story 1.5 pipeline steps plus I/O adapters via dependency
injection so that `work_data_hub.domain` never imports orchestration code.
This module also exposes a CLI for executing the orchestrated graph while
respecting the Clean Architecture flow: domain ← io ← orchestration.
"""

import argparse
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml
from dagster import Config, DagsterInstance, OpExecutionContext, job, op

from work_data_hub.config.settings import get_settings
from work_data_hub.domain.annuity_performance.service import (
    process_annuity_performance,
)
from work_data_hub.domain.pipelines.types import DomainPipelineResult
from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourcesValidationError,
    get_domain_config_v2,
)
from work_data_hub.io.connectors.file_connector import FileDiscoveryService
from work_data_hub.io.loader.warehouse_loader import WarehouseLoader

from .ops import (
    discover_files_op,
    gate_after_backfill,
    generic_backfill_refs_op,  # Epic 6.2 - configuration-driven backfill
    load_op,
    load_to_db_op,
    process_annuity_income_op,
    process_annuity_performance_op,
    process_company_lookup_queue_op,
    process_sandbox_trustee_performance_op,
    read_and_process_sandbox_trustee_files_op,
    read_csv_op,
    read_excel_op,
    validate_op,
)
from .reference_sync_jobs import reference_sync_job

# ============================================================================
# Story 7.4-1: Job Registry Pattern
# ============================================================================


@dataclass(frozen=True)
class JobEntry:
    """Registry entry for a domain's Dagster job(s).

    Attributes:
        job: The primary Dagster JobDefinition (required, must not be None)
        multi_file_job: Optional job for max_files > 1 scenarios
        supports_backfill: Whether domain has FK backfill configured in foreign_keys.yml
    """

    job: Any  # Dagster JobDefinition - MUST be a valid job, never None
    multi_file_job: Optional[Any] = None  # For max_files > 1 scenarios
    supports_backfill: bool = False  # Whether domain has FK backfill configured


@job
def sandbox_trustee_performance_job() -> Any:
    """
    End-to-end trustee performance processing job with optional reference backfill.

    This job orchestrates the complete ETL pipeline:
    1. Discover files matching domain patterns
    2. Read Excel data from discovered files
    3. Process data through domain service validation
    4. Derive reference candidates from processed data
    5. Backfill missing references to database (if enabled)
    6. Load data to database or generate execution plan
    """
    # Wire ops together - Dagster handles dependency graph
    discovered_paths = discover_files_op()

    # Note: For MVP, we'll modify the ops to handle the first file selection
    # The read_excel_op will internally select the first file from the list
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_sandbox_trustee_performance_op(
        excel_rows, discovered_paths
    )

    # Epic 6.2: Generic reference backfill using configuration-driven approach
    # Handles FK references via data_sources.yml config
    backfill_result = generic_backfill_refs_op(processed_data)

    # Gate before loading facts (FK-safe ordering)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)


@job
def sandbox_trustee_performance_multi_file_job() -> Any:
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
    processed_data = read_and_process_sandbox_trustee_files_op(discovered_paths)
    load_op(processed_data)  # No return needed


@job
def annuity_performance_job() -> Any:
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

    # Epic 6.2: Generic reference backfill using configuration-driven approach
    # Replaces legacy derive_plan_refs_op + derive_portfolio_refs_op + backfill_refs_op
    # Now handles all 5 FKs via config/foreign_keys.yml
    backfill_result = generic_backfill_refs_op(processed_data)

    # Gate before loading facts (FK-safe ordering)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)


@job
def annuity_income_job() -> Any:
    """
    End-to-end annuity income processing job with optional reference backfill.

    Story 7.3-7: Added reference backfill support (parity with annuity_performance).

    This job orchestrates the complete ETL pipeline for Chinese "收入明细" data:
    1. Discover files matching domain patterns
    2. Read Excel data from discovered files (sheet="收入明细")
    3. Process data through annuity income domain service
    4. Backfill missing references to mapping tables (if enabled)
    5. Load fact data to database or generate execution plan
    """
    # Wire ops together - Dagster handles dependency graph
    discovered_paths = discover_files_op()

    # Read Excel data and process through annuity income service
    excel_rows = read_excel_op(discovered_paths)
    processed_data = process_annuity_income_op(excel_rows, discovered_paths)

    # Story 7.3-7: Generic reference backfill (parity with annuity_performance)
    backfill_result = generic_backfill_refs_op(processed_data)

    # Gate before loading facts (FK-safe ordering)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)


class AnnuityPipelineConfig(Config):
    """Config schema for the Story 4.5 consolidated pipeline job."""

    month: str
    sync_lookup_budget: int = 0
    export_unknown_names: bool = True
    use_pipeline: Optional[bool] = None


@op
def run_annuity_pipeline_op(
    context: OpExecutionContext,
    config: AnnuityPipelineConfig,
) -> Dict[str, Any]:
    """
    Execute process_annuity_performance end-to-end for specified month.

    This op wires FileDiscoveryService and WarehouseLoader into the domain
    service, logs metrics, and returns the serialized PipelineResult.
    """

    file_discovery = FileDiscoveryService()
    loader: Optional[WarehouseLoader] = None
    try:
        loader = WarehouseLoader()
        result = process_annuity_performance(
            config.month,
            file_discovery=file_discovery,
            warehouse_loader=loader,
            sync_lookup_budget=config.sync_lookup_budget,
            export_unknown_names=config.export_unknown_names,
        )
    finally:
        if loader is not None:
            loader.close()

    _log_pipeline_metrics(context.log, result)
    return result.as_dict()


@job
def annuity_performance_story45_job() -> Any:
    """
    Story 4.5 Dagster job that executes the full annuity pipeline via one op.
    """

    run_annuity_pipeline_op()


@job
def process_company_lookup_queue_job() -> Any:
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


# ============================================================================
# Sample Pipeline Job (Story 1.9 Demonstration)
# ============================================================================


@job
def sample_pipeline_job() -> Any:
    """
    Sample end-to-end pipeline demonstrating Dagster orchestration (Story 1.9).

    This job demonstrates the integration of:
    - Story 1.5: Pipeline framework for data transformation
    - Story 1.8: WarehouseLoader for transactional database loading
    - Story 1.9: Dagster orchestration with thin op wrappers

    Pipeline Flow:
    1. read_csv_op: Read sample CSV data from tests/fixtures/sample_data.csv
    2. validate_op: Validate data using Pipeline framework
    3. load_to_db_op: Load to PostgreSQL using WarehouseLoader

    This is a reference implementation showing Clean Architecture:
    - Ops stay thin (5-10 lines)
    - Business logic delegated to domain services
    - I/O operations delegated to io/ layer
    """
    # Wire ops together - Dagster handles dependency graph
    raw_data = read_csv_op()
    validated = validate_op(raw_data)
    load_to_db_op(validated)


# JOB_REGISTRY: Single source of truth for domain → job mapping
# Story 7.4-1: Replaces if/elif dispatch chain with dictionary lookup
# NOTE: Must be defined AFTER all job functions to avoid NameError
JOB_REGISTRY: Dict[str, JobEntry] = {
    "annuity_performance": JobEntry(
        job=annuity_performance_job,
        supports_backfill=True,
    ),
    "annuity_income": JobEntry(
        job=annuity_income_job,
        supports_backfill=True,  # Story 7.3-7 added backfill support
    ),
    "sandbox_trustee_performance": JobEntry(
        job=sandbox_trustee_performance_job,
        multi_file_job=sandbox_trustee_performance_multi_file_job,
        supports_backfill=True,
    ),
}


def _log_pipeline_metrics(logger: Any, result: DomainPipelineResult) -> None:
    """Log concise telemetry for DomainPipelineResult."""
    logger.info(
        "annuity_pipeline.completed",
        extra={
            "rows_loaded": result.rows_loaded,
            "rows_failed": result.rows_failed,
            "duration_ms": result.duration_ms,
            "file_path": str(result.file_path),
            "version": result.version,
        },
    )


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

    data_sources: Dict[str, Any] = {}
    try:
        with open(settings.data_sources_config, "r", encoding="utf-8") as f:
            data_sources = yaml.safe_load(f) or {}
        if not isinstance(data_sources, dict):
            data_sources = {}

        domain_config = (data_sources.get("domains") or {}).get(args.domain, {}) or {}
        if not isinstance(domain_config, dict):
            domain_config = {}

        # Epic 3 schema prefers output.table + output.schema_name
        output_cfg = (
            domain_config.get("output") if isinstance(domain_config, dict) else None
        )
        if isinstance(output_cfg, dict) and output_cfg.get("table"):
            table_name = str(output_cfg["table"])
            schema_name = output_cfg.get("schema_name")
            if schema_name:
                table = f"{schema_name}.{table_name}"
            else:
                table = table_name
        else:
            table = domain_config.get("table", args.domain)  # Legacy fallback

        pk = domain_config.get("pk", [])  # Empty list if not defined

        # Runtime override via --pk (only affects delete_insert mode)
        pk_override = _parse_pk_override(getattr(args, "pk", None))
        if pk_override:
            pk = pk_override

    except Exception as e:
        print(f"Warning: Could not load data sources config: {e}")
        table = args.domain
        pk = []

    # Build discover_files_op config with optional period
    discover_config = {"domain": args.domain}
    if hasattr(args, "period") and args.period:
        discover_config["period"] = args.period

    run_config = {
        "ops": {
            "discover_files_op": {"config": discover_config},
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

    # Determine sheet configuration.
    # If --sheet not provided, try to get sheet_name from data_sources.yml.
    sheet_value = getattr(args, "sheet", None)
    if sheet_value is None:
        # Check if domain is Epic 3 schema and has sheet_name configured
        domain_config = (data_sources.get("domains") or {}).get(args.domain, {}) or {}
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
        # Use existing separate ops for single-file processing (backward compatibility)
        # Coerce sheet: if it's a digit-like string, pass as int; else pass as name
        sheet_cfg: Any
        try:
            sheet_cfg = int(sheet_value)
        except Exception:
            sheet_cfg = sheet_value
        run_config["ops"]["read_excel_op"] = {"config": {"sheet": sheet_cfg}}
        # process_trustee_performance_op has no config

    # Epic 6.2: Generic backfill configuration (configuration-driven approach)
    # Replaces legacy backfill_refs_op with generic_backfill_refs_op
    # Story 7.4-2: Check requires_backfill from domain config
    try:
        domain_cfg = get_domain_config_v2(
            args.domain, config_path=str(settings.data_sources_config)
        )
        requires_backfill = getattr(domain_cfg, "requires_backfill", False)
    except (DataSourcesValidationError, Exception):
        # Fallback to false if config loading fails (safe default)
        requires_backfill = False

    if requires_backfill:
        run_config["ops"]["generic_backfill_refs_op"] = {
            "config": {
                "domain": args.domain,
                "plan_only": effective_plan_only,
                "add_tracking_fields": False,  # mapping tables lack these
            }
        }

    # Add enrichment configuration for annuity_performance domain
    if args.domain == "annuity_performance":
        from work_data_hub.infrastructure.enrichment import EqcLookupConfig

        # Story 6.2-P17: EqcLookupConfig from CLI args (SSOT).
        eqc_config = EqcLookupConfig.from_cli_args(args)
        run_config["ops"]["process_annuity_performance_op"] = {
            "config": {
                # Legacy fields kept for backward compatibility / logging
                "enrichment_enabled": eqc_config.enabled,
                "enrichment_sync_budget": eqc_config.sync_budget,
                "export_unknown_names": eqc_config.export_unknown_names,
                # Story 6.2-P17: Preferred config payload
                "eqc_lookup_config": eqc_config.to_dict(),
                "plan_only": effective_plan_only,  # Use effective flag
                "use_pipeline": getattr(
                    args, "use_pipeline", None
                ),  # CLI override for pipeline framework
            }
        }

    return run_config


def _execute_queue_processing_job(args: argparse.Namespace) -> int:
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
        return 0

    except KeyboardInterrupt:
        print("⚠️ Queue processing interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ Unexpected queue processing failure: {e}")
        if args.raise_on_error:
            raise
        return 1


def _execute_reference_sync_job(args: argparse.Namespace) -> int:
    """
    Execute reference sync job for pre-loading authoritative data.

    Story 6.2.4: Syncs reference data from Legacy MySQL and config files
    to reference tables before fact processing.
    """
    effective_plan_only = not args.execute if hasattr(args, "execute") else True

    print("🚀 Starting reference data sync...")
    print(f"   Execute: {getattr(args, 'execute', False)}")
    print(f"   Plan-only: {effective_plan_only}")
    print("=" * 50)

    try:
        # Build run configuration for reference sync
        run_config = {
            "ops": {
                "reference_sync_op": {
                    "config": {
                        "plan_only": effective_plan_only,
                    }
                }
            }
        }

        # Execute reference sync job
        instance = DagsterInstance.ephemeral() if args.debug else None

        result = reference_sync_job.execute_in_process(
            run_config=run_config, instance=instance, raise_on_error=args.raise_on_error
        )

        # Report results
        print(f"✅ Reference sync completed: {result.success}")

        if result.success:
            # Extract sync results
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


# Story 6.2-P6: main() function removed per AC7 requirement.
# CLI functionality has been migrated to work_data_hub.cli.etl module.
# Use: python -m work_data_hub.cli etl --domains <domain> [options]
