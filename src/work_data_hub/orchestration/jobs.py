"""Dagster jobs for domain ETL pipelines.

Phase 4 Refactor: Uses generic_domain_job with DomainServiceProtocol.
"""

import argparse
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml
from dagster import job

from work_data_hub.config.settings import get_settings
from work_data_hub.infrastructure.settings.data_source_schema import (
    DataSourcesValidationError,
    get_domain_config_v2,
)

from .ops import (
    discover_files_op,
    gate_after_backfill,
    generic_backfill_refs_op,
    load_op,
    process_company_lookup_queue_op,
    read_and_process_sandbox_trustee_files_op,
    read_data_op,
)
from .ops.generic_ops import process_domain_op_v2


@dataclass(frozen=True)
class JobEntry:
    """Registry entry for a domain's Dagster job(s)."""

    job: Any
    multi_file_job: Optional[Any] = None
    supports_backfill: bool = False


@job
def generic_domain_job() -> Any:
    """
    Generic domain processing job using DomainServiceProtocol.

    Phase 4 Refactor: Replaces all per-domain jobs with a single generic job
    that uses the Protocol registry to dispatch to the correct domain service.

    Phase 0 Enhancement: Uses read_data_op for multi-source support.

    Pipeline Flow:
    1. Discover files matching domain patterns
    2. Read data via unified read_data_op (supports single_file and multi_table)
    3. Process data through generic domain op (uses Protocol registry)
    4. Backfill missing references (if domain requires it)
    5. Load data to database or generate execution plan
    """
    discovered_paths = discover_files_op()
    rows = read_data_op(discovered_paths)
    processed_data = process_domain_op_v2(rows, discovered_paths)

    # Generic backfill (configured per-domain in data_sources.yml)
    backfill_result = generic_backfill_refs_op(processed_data)
    gated_rows = gate_after_backfill(processed_data, backfill_result)
    load_op(gated_rows)


@job
def generic_domain_multi_file_job() -> Any:
    """
    Generic domain job for multi-file scenarios.

    Uses combined read+process op for handling multiple files.
    """
    discovered_paths = discover_files_op()
    processed_data = read_and_process_sandbox_trustee_files_op(discovered_paths)
    load_op(processed_data)


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


# JOB_REGISTRY: Single source of truth for domain → job mapping
# Story 7.4-1: Replaces if/elif dispatch chain with dictionary lookup
# NOTE: Must be defined AFTER all job functions to avoid NameError
# Phase 4: All domains now use generic_domain_job via Protocol registry
JOB_REGISTRY: Dict[str, JobEntry] = {
    "annuity_performance": JobEntry(
        job=generic_domain_job,
        supports_backfill=True,
    ),
    "annuity_income": JobEntry(
        job=generic_domain_job,
        supports_backfill=True,
    ),
    "annual_award": JobEntry(
        job=generic_domain_job,
        supports_backfill=False,
    ),
    "annual_loss": JobEntry(
        job=generic_domain_job,
        supports_backfill=False,
    ),
    "sandbox_trustee_performance": JobEntry(
        job=generic_domain_job,
        multi_file_job=generic_domain_multi_file_job,
        supports_backfill=True,
    ),
}

# Backward-compatible aliases for legacy imports
# These jobs are now accessed via JOB_REGISTRY but some modules still import directly
sandbox_trustee_performance_multi_file_job = generic_domain_multi_file_job
sandbox_trustee_performance_job = generic_domain_job
annuity_performance_job = generic_domain_job
annuity_performance_story45_job = generic_domain_job
annuity_income_job = generic_domain_job
sample_pipeline_job = generic_domain_job


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
    # Also check for sheet_names (multi-sheet) configuration.
    sheet_value = getattr(args, "sheet", None)
    sheet_names_list = None

    domain_config = (data_sources.get("domains") or {}).get(args.domain, {}) or {}

    if sheet_value is None:
        # Check if domain has sheet_names (multi-sheet) configured
        if isinstance(domain_config, dict) and "sheet_names" in domain_config:
            sheet_names_list = domain_config["sheet_names"]
        # Otherwise try sheet_name
        elif isinstance(domain_config, dict) and "sheet_name" in domain_config:
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
            sheet_cfg = int(sheet_value) if sheet_value else 0
        except Exception:
            sheet_cfg = sheet_value

        # Build read_data_op config (Phase 0: unified data loading)
        read_data_config: Dict[str, Any] = {
            "domain": args.domain,
            "sheet": sheet_cfg,
        }

        # Add sheet_names if configured (multi-sheet support)
        if sheet_names_list:
            read_data_config["sheet_names"] = sheet_names_list

        run_config["ops"]["read_data_op"] = {"config": read_data_config}

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

    # Phase 4: Generic domain op configuration (replaces per-domain op configs)
    run_config["ops"]["process_domain_op_v2"] = {
        "config": {
            "domain": args.domain,
            "plan_only": effective_plan_only,
        }
    }

    return run_config


# Story 6.2-P6: main() function removed per AC7 requirement.
# CLI functionality has been migrated to work_data_hub.cli.etl module.
# Use: python -m work_data_hub.cli etl --domains <domain> [options]
